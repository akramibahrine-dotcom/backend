from __future__ import annotations

import random
import re
import string
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.order import Order, OrderItem
from app.schemas.order import CreateOrderRequest
from app.services.products import get_product
from app.services.traffic_source import derive_traffic_platform, platform_to_utm_source
from app.services.currency import FALLBACK_RATES, convert_sar_to

logger = get_logger(__name__)

try:
    KSA_TZ = ZoneInfo("Asia/Riyadh")
except Exception:
    KSA_TZ = timezone(timedelta(hours=3))
SHEETS_DATE_FORMAT = "%d/%m/%Y %H:%M:%S"

# ISO country code → Arabic country name
COUNTRY_NAMES: dict[str, str] = {
    "SA": "المملكة العربية السعودية",
    "AE": "الإمارات العربية المتحدة",
    "QA": "قطر",
    "BH": "البحرين",
    "OM": "عُمان",
    "KW": "الكويت",
    "IQ": "العراق",
    "LB": "لبنان",
    "LY": "ليبيا",
}

# ISO country code → default currency
COUNTRY_CURRENCY: dict[str, str] = {
    "SA": "SAR",
    "AE": "AED",
    "QA": "QAR",
    "BH": "BHD",
    "OM": "OMR",
    "KW": "KWD",
    "IQ": "IQD",
    "LB": "LBP",
    "LY": "LYD",
}


def _country_from_phone(phone_e164: str) -> str:
    """Derive ISO country code from E.164 phone number."""
    from app.core.security import COUNTRY_PHONE_PATTERNS
    for _cc, pattern, iso in COUNTRY_PHONE_PATTERNS:
        if pattern.match(phone_e164):
            return iso
    return ""


def _format_date(dt: datetime | None) -> str:
    """Format order timestamp for Google Sheets (Saudi local time with seconds)."""
    if not dt:
        dt = datetime.now(timezone.utc)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(KSA_TZ)
    return local.strftime(SHEETS_DATE_FORMAT)


def _format_national_address(address: str) -> str:
    if not address:
        return ""
    # Look for 4 letters followed by optional space/dash and 4 numbers
    match = re.search(r'([A-Za-z]{4})[\s\-]*(\d{4})', address)
    if match:
        return f"{match.group(1).upper()}{match.group(2)}"
    return ""


def build_sheets_row(
    order: Order,
    items: list[OrderItem],
    country_iso: str | None,
    customer_address: str = "",
    *,
    ttclid: str | None = None,
    fbc: str | None = None,
    sc_click_id: str | None = None,
) -> dict:
    """Build the flat dict that maps 1-to-1 to the Google Sheet columns."""
    # Derive country from phone first, fall back to IP-based ISO
    phone_iso = _country_from_phone(order.customer_phone_e164)
    effective_iso = phone_iso or country_iso or ""

    country_name = COUNTRY_NAMES.get(effective_iso, effective_iso)

    # Currency: use display_currency if set, else derive from country, else SAR
    currency = (
        order.display_currency
        or COUNTRY_CURRENCY.get(effective_iso, "SAR")
    )

    # Total price in display currency
    if order.display_total:
        price = float(order.display_total)
    elif currency != "SAR":
        price = convert_sar_to(float(order.total_sar), currency, FALLBACK_RATES)
    else:
        price = float(order.total_sar)

    # Products / SKUs / quantities as slash-joined strings
    skus: list[str] = []
    product_names: list[str] = []
    quantities: list[str] = []

    for item in items:
        product_info = get_product(item.product_id)
        skus.append(product_info.sku if product_info else item.product_id)
        product_names.append(
            product_info.name_ar if product_info else item.product_id
        )
        quantities.append(str(item.quantity))

    # URL: prefer landing page, fall back to page_url
    url = order.landing_page_url or order.page_url or ""

    traffic_platform = derive_traffic_platform(
        utm_source=order.utm_source,
        utm_medium=order.utm_medium,
        landing_page_url=order.landing_page_url,
        page_url=order.page_url,
        ttclid=ttclid,
        fbc=fbc,
        sc_click_id=sc_click_id,
    )
    utm_source = order.utm_source or platform_to_utm_source(traffic_platform)

    return {
        "order_id":        order.public_order_number,
        "date":            _format_date(order.created_at),
        "country":         country_name,
        "name":            order.customer_name,
        "phone":           order.customer_phone_e164,
        "address":         customer_address,
        "url":             url,
        "sku":             "/".join(skus),
        "product":         "/".join(product_names),
        "quantity":        "/".join(quantities),
        "price":           price,
        "currency":        currency,
        "notes":           "",
        "traffic_platform": traffic_platform,
        "utm_source":      utm_source,
        "utm_medium":      order.utm_medium or "",
        "utm_campaign":    order.utm_campaign or "",
        "utm_term":        order.utm_term or "",
        "utm_content":     order.utm_content or "",
        "national_address": _format_national_address(customer_address),
        "spend":           "",
        "orders":          "",
        "cpl":             "",
        "status":          "",
    }


async def send_to_sheets(
    order: Order,
    items: list[OrderItem],
    fraud_decision: str,
    fraud_reason: str,
    country_iso: str | None,
    risk_score: float | None,
    ip_risk: float | None,
    is_vpn_proxy: str = "",
    customer_address: str = "",
    ttclid: str | None = None,
    fbc: str | None = None,
    sc_click_id: str | None = None,
) -> dict:
    """
    Forward order to Google Sheets webhook.
    Returns status dict. Never raises.
    """
    settings = get_settings()

    if not settings.google_sheets_webhook_url:
        logger.warning("sheets_webhook_not_configured")
        return {"status": "skipped", "reason": "not_configured"}

    payload = {
        "order": build_sheets_row(
            order=order,
            items=items,
            country_iso=country_iso,
            customer_address=customer_address,
            ttclid=ttclid,
            fbc=fbc,
            sc_click_id=sc_click_id,
        ),
    }

    try:
        result = await _post_to_sheets(
            url=settings.google_sheets_webhook_url,
            payload=payload,
        )
        if not result.get("ok"):
            logger.warning("sheets_webhook_returned_not_ok", response=result, order_id=order.id)
            return {"status": "failed", "error": result.get("error", "ok=false")}
        logger.info("sheets_webhook_sent", order_id=order.id)
        return {"status": "sent", "response": result}
    except Exception as exc:
        logger.error("sheets_webhook_failed", error=str(exc), order_id=order.id)
        return {"status": "failed", "error": str(exc)}


async def send_rejected_attempt_to_sheets(
    req: CreateOrderRequest,
    client_ip: str,
    phone_e164: str,
    fraud_reason: str,
    country_iso: str | None,
    is_vpn_proxy: str = "",
    risk_score: float | None = None,
    ip_risk: float | None = None,
) -> dict:
    """
    Push a rejected order attempt to the Google Sheet.
    Never raises.
    """
    settings = get_settings()

    if not settings.google_sheets_webhook_url:
        logger.warning("sheets_webhook_not_configured_rejected")
        return {"status": "skipped", "reason": "not_configured"}

    # Derive country
    from app.core.security import COUNTRY_PHONE_PATTERNS
    phone_iso = ""
    for _cc, pattern, iso in COUNTRY_PHONE_PATTERNS:
        if pattern.match(phone_e164):
            phone_iso = iso
            break
    effective_iso = phone_iso or country_iso or ""
    country_name = COUNTRY_NAMES.get(effective_iso, effective_iso)
    currency = req.pricing.currency or COUNTRY_CURRENCY.get(effective_iso, "SAR")
    price = (
        float(req.pricing.display_total)
        if req.pricing.display_total is not None and currency != "SAR"
        else float(req.pricing.total_sar)
    )

    # Build product/sku/qty strings from request items
    skus: list[str] = []
    product_names: list[str] = []
    quantities: list[str] = []
    for item in req.items:
        product_info = get_product(item.product_id)
        skus.append(product_info.sku if product_info else item.product_id)
        product_names.append(product_info.name_ar if product_info else item.product_id)
        quantities.append(str(item.quantity))

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = "".join(random.choices(string.digits, k=4))
    public_number = f"BAYT-REJ-{today}-{suffix}"

    tracking = req.tracking
    utm = tracking.utm if tracking else None
    url = (tracking.landing_page_url or tracking.page_url or "") if tracking else ""
    traffic_platform = derive_traffic_platform(
        utm_source=utm.source if utm else None,
        utm_medium=utm.medium if utm else None,
        landing_page_url=tracking.landing_page_url if tracking else None,
        page_url=tracking.page_url if tracking else None,
        ttclid=tracking.ttclid if tracking else None,
        fbc=tracking.fbc if tracking else None,
        sc_click_id=tracking.sc_click_id if tracking else None,
    )
    utm_source = (utm.source if utm else None) or platform_to_utm_source(traffic_platform)

    payload = {
        "order": {
            "order_id":        public_number,
            "date":            _format_date(datetime.now(timezone.utc)),
            "country":         country_name,
            "name":            req.customer.name,
            "phone":           phone_e164 or req.customer.phone,
            "address":         req.customer.address or "",
            "url":             url,
            "sku":             "/".join(skus),
            "product":         "/".join(product_names),
            "quantity":        "/".join(quantities),
            "price":           price,
            "currency":        currency,
            "notes":           f"REJECTED - {fraud_reason} - IP: {client_ip}",
            "traffic_platform": traffic_platform,
            "utm_source":      utm_source,
            "utm_medium":      utm.medium if utm else "",
            "utm_campaign":    utm.campaign if utm else "",
            "utm_term":        utm.term if utm else "",
            "utm_content":     utm.content if utm else "",
            "national_address": _format_national_address(req.customer.address or ""),
            "spend":           "",
            "orders":          "",
            "cpl":             "",
            "status":          "rejected",
        },
    }

    try:
        result = await _post_to_sheets(
            url=settings.google_sheets_webhook_url,
            payload=payload,
        )
        logger.info(
            "sheets_rejected_attempt_sent",
            ref=public_number,
            reason=fraud_reason,
        )
        return {"status": "sent", "response": result}
    except Exception as exc:
        logger.error(
            "sheets_rejected_attempt_failed",
            error=str(exc),
            reason=fraud_reason,
        )
        return {"status": "failed", "error": str(exc)}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8), reraise=True)
async def _post_to_sheets(url: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        response = await client.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()
