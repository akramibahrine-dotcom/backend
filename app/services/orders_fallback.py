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
        cleaned_digits.endswith(wl_digits) or wl_digits.endswith(cleaned_digits)
    )
    phone_result = normalize_phone(cleaned)
    if not phone_result and not is_test:
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_phone", "message": "اكتبي رقم جوال صحيح لإكمال الطلب."},
        )

    # Country gate also enforced in the DB-fallback path
    if not is_test:
        allowed_countries = settings.get_allowed_countries()
        ip_iso = await geoip_svc.lookup_country(client_ip)
        phone_iso = phone_result[3] if phone_result else None
        if allowed_countries and ip_iso and ip_iso not in allowed_countries:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "order_rejected",
                    "message": "عذرًا، الطلبات غير متاحة في بلدك حاليًا.",
                },
            )
        if ip_iso and phone_iso and ip_iso != phone_iso:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "order_rejected",
                    "message": "رقم الجوال لا يتطابق مع بلد الاتصال.",
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

    # Generate synthetic order ID
    order_id = str(uuid.uuid4())
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = "".join(random.choices(string.digits, k=4))
    public_number = f"BSH-{today}-{suffix}"

    # Send to Google Sheets as the primary record
    if settings.google_sheets_webhook_url:
        tracking = req.tracking
        utm = tracking.utm if tracking else None
        payload = {
            "secret": settings.google_sheets_webhook_secret,
            "order": {
                "public_order_number": public_number,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "customer_name": req.customer.name,
                "customer_phone": req.customer.phone,
                "items_summary": "; ".join(items_summary_parts),
                "item_count": sum(item.quantity for item in req.items),
                "subtotal_sar": total_sar - req.pricing.shipping_sar,
                "shipping_sar": req.pricing.shipping_sar,
                "total_sar": total_sar,
                "display_currency": req.pricing.currency or "SAR",
                "display_total": total_sar,
                "payment_method": "COD",
                "status": "pending_confirmation",
                "confirmation_status": "pending",
                "is_test_order": is_test,
                "fraud_decision": "skipped_db_fallback",
                "fraud_reason": "database_unavailable",
                "ip_country": "",
                "risk_score": "",
                "ip_risk": "",
                "utm_source": utm.source if utm else "",
                "utm_medium": utm.medium if utm else "",
                "utm_campaign": utm.campaign if utm else "",
                "utm_content": utm.content if utm else "",
                "utm_term": utm.term if utm else "",
                "landing_page_url": tracking.landing_page_url if tracking else "",
                "page_url": tracking.page_url if tracking else "",
                "purchase_event_id": tracking.purchase_event_id if tracking else "",
                "vpn_proxy": "",
                "notes": f"FALLBACK ORDER - DB unavailable. IP: {client_ip}",
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
    )
