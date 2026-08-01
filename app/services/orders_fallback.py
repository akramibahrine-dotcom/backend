"""
Fallback order creation when the database is unavailable.
Sends order data to Google Sheets and returns a synthetic response
so the customer still reaches the thank-you page.
"""
from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, Request

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import normalize_phone
from app.schemas.order import CreateOrderRequest, CreateOrderResponse
from app.services import geoip as geoip_svc
from app.services.products import get_product, validate_bundle_price, validate_upsell

logger = get_logger(__name__)


def _get_client_ip(request: Request) -> str:
    settings = get_settings()
    if settings.trust_proxy_headers:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "0.0.0.0"


async def create_order_fallback(req: CreateOrderRequest, request: Request) -> CreateOrderResponse:
    settings = get_settings()
    client_ip = _get_client_ip(request)

    # Basic phone validation
    cleaned = req.customer.phone.replace(" ", "").replace("-", "")
    wl_digits = settings.test_phone_whitelist.strip().lstrip("+").lstrip("0")
    cleaned_digits = cleaned.lstrip("+").lstrip("0")
    is_test = cleaned == settings.test_phone_whitelist.strip() or (
        wl_digits and (cleaned_digits.endswith(wl_digits) or wl_digits.endswith(cleaned_digits))
    )
    phone_result = normalize_phone(cleaned)
    if not phone_result and not is_test:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_phone", "message": "اكتبي رقم جوال صحيح لإكمال الطلب."},
        )

    # Country gate also enforced in the DB-fallback path.
    # If phone belongs to an allowed country, trust it (handles VPN users).
    if not is_test:
        from app.services import sheets as sheets_svc
        import asyncio as _asyncio
        allowed_countries = settings.get_allowed_countries()
        ip_iso = await geoip_svc.lookup_country(client_ip)
        phone_iso = phone_result[3] if phone_result else None
        phone_is_allowed = phone_iso and phone_iso in allowed_countries

        if allowed_countries and ip_iso and ip_iso not in allowed_countries:
            if phone_is_allowed:
                pass  # VPN user with valid GCC phone — allow
            else:
                _asyncio.create_task(sheets_svc.send_rejected_attempt_to_sheets(
                    req=req,
                    client_ip=client_ip,
                    phone_e164=phone_result[0] if phone_result else req.customer.phone,
                    fraud_reason=f"country_not_allowed_geoip:{ip_iso}",
                    country_iso=ip_iso,
                ))
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "order_rejected",
                        "message": "عذرًا، لا يمكن إتمام الطلب حاليًا. يرجى المحاولة لاحقًا أو التواصل معنا عبر واتساب.",
                    },
                )
        if ip_iso and phone_iso and ip_iso != phone_iso:
            if phone_is_allowed:
                pass  # VPN user with valid GCC phone — allow
            else:
                _asyncio.create_task(sheets_svc.send_rejected_attempt_to_sheets(
                    req=req,
                    client_ip=client_ip,
                    phone_e164=phone_result[0] if phone_result else req.customer.phone,
                    fraud_reason=f"phone_ip_country_mismatch:{phone_iso}_vs_{ip_iso}",
                    country_iso=ip_iso,
                ))
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "order_rejected",
                        "message": "عذرًا، لا يمكن إتمام الطلب حاليًا. يرجى المحاولة لاحقًا أو التواصل معنا عبر واتساب.",
                    },
                )

    # Basic price validation
    welcome_codes = {c.strip() for c in settings.welcome_promo_codes.split(",") if c.strip()}
    welcome_active = bool(req.promo_code and req.promo_code.strip() in welcome_codes)

    items_total = 0
    items_summary_parts = []
    for item in req.items:
        product = get_product(item.product_id)
        if not product:
            raise HTTPException(
                status_code=422,
                detail={"error": "invalid_product", "message": "منتج غير موجود في الكتالوج."},
            )
        if not validate_bundle_price(item.product_id, item.quantity, item.bundle_price_sar, welcome_discount=welcome_active):
            raise HTTPException(
                status_code=422,
                detail={"error": "invalid_price", "message": "سعر الباقة غير صحيح."},
            )
        items_total += item.bundle_price_sar
        items_summary_parts.append(f"{item.quantity}x {product.name_ar}")

    upsell_total = 0
    if req.upsell and req.upsell.accepted and req.upsell.product_id:
        main_ids = [item.product_id for item in req.items]
        upsell_price = req.upsell.price_sar or 0
        if not validate_upsell(req.upsell.product_id, main_ids, upsell_price, welcome_discount=welcome_active):
            raise HTTPException(
                status_code=422,
                detail={"error": "invalid_upsell", "message": "عرض الإضافة غير صحيح."},
            )
        upsell_total = upsell_price
        upsell_product = get_product(req.upsell.product_id)
        if upsell_product:
            items_summary_parts.append(f"1x {upsell_product.name_ar} (upsell)")

    total_sar = items_total + upsell_total + req.pricing.shipping_sar

    if req.pricing.total_sar != total_sar:
        raise HTTPException(
            status_code=422,
            detail={"error": "total_mismatch", "message": "إجمالي الطلب غير صحيح."},
        )

    # Generate synthetic order ID
    order_id = str(uuid.uuid4())
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = "".join(random.choices(string.digits, k=4))
    public_number = f"BAYT-{today}-{suffix}"

    # Send to Google Sheets as the primary record
    if settings.google_sheets_webhook_url:
        from app.services.sheets import (
            COUNTRY_NAMES,
            COUNTRY_CURRENCY,
            _country_from_phone,
            _format_date,
            _format_national_address,
        )
        from app.services.traffic_source import derive_traffic_platform, platform_to_utm_source

        tracking = req.tracking
        utm = tracking.utm if tracking else None
        today_str = _format_date(datetime.now(timezone.utc))
        phone_for_country = (phone_result[0] if phone_result else req.customer.phone)
        phone_iso = _country_from_phone(phone_for_country)
        country_name = COUNTRY_NAMES.get(phone_iso, phone_iso)
        currency = req.pricing.currency or COUNTRY_CURRENCY.get(phone_iso, "SAR")
        display_price = (
            float(req.pricing.display_total)
            if req.pricing.display_total is not None and currency != "SAR"
            else float(total_sar)
        )

        skus = []
        names = []
        qtys = []
        for item in req.items:
            p = get_product(item.product_id)
            skus.append(p.sku if p else item.product_id)
            names.append(p.name_ar if p else item.product_id)
            qtys.append(str(item.quantity))
        if req.upsell and req.upsell.accepted and req.upsell.product_id:
            up = get_product(req.upsell.product_id)
            if up:
                skus.append(up.sku)
                names.append(up.name_ar)
                qtys.append("1")

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
                "date":            today_str,
                "country":         country_name,
                "name":            req.customer.name,
                "phone":           phone_for_country,
                "address":         getattr(req.customer, "address", None) or "",
                "url":             (tracking.landing_page_url or tracking.page_url or "") if tracking else "",
                "sku":             "/".join(skus),
                "product":         "/".join(names),
                "quantity":        "/".join(qtys),
                "price":           display_price,
                "currency":        currency,
                "notes":           f"FALLBACK - DB unavailable. IP: {client_ip}",
                "traffic_platform": traffic_platform,
                "utm_source":      utm_source,
                "utm_medium":      utm.medium if utm else "",
                "utm_campaign":    utm.campaign if utm else "",
                "utm_term":        utm.term if utm else "",
                "utm_content":     utm.content if utm else "",
                "national_address": _format_national_address(getattr(req.customer, "address", None) or ""),
                "spend":           "",
                "orders":          "",
                "cpl":             "",
                "status":          "pending_confirmation",
            },
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    settings.google_sheets_webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
            logger.info("fallback_order_sent_to_sheets", order_id=order_id, public_number=public_number)
        except Exception as sheets_exc:
            logger.error("fallback_sheets_also_failed", error=str(sheets_exc))
    else:
        logger.warning("fallback_no_sheets_configured", order_id=order_id)

    logger.info(
        "fallback_order_created",
        order_id=order_id,
        public_number=public_number,
        total=total_sar,
        is_test=is_test,
    )

    return CreateOrderResponse(
        order_id=order_id,
        public_order_number=public_number,
        status="pending_confirmation",
        total_sar=total_sar,
        is_test_order=is_test,
        thank_you_url=f"{settings.frontend_base_url}/thank-you/{order_id}",
        purchase_event_id=req.tracking.purchase_event_id,
    )
