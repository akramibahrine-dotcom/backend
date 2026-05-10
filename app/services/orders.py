from __future__ import annotations

import asyncio
import random
import re
import string
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger, mask_phone
from app.core.security import normalize_ksa_phone, normalize_phone
from app.models.event import TrackingEvent, WebhookDelivery
from app.models.fraud import FraudCheck
from app.models.order import Order, OrderItem
from app.schemas.fraud import FraudDecision
from app.schemas.order import CreateOrderRequest, CreateOrderResponse, ValidateOrderRequest, ValidateOrderResponse
from app.schemas.tracking import CAPIContent, CAPIOrderPayload
from app.services import geoip as geoip_svc
from app.services import maxmind as maxmind_svc
from app.services import sheets as sheets_svc
from app.services.products import (
    get_product,
    validate_bundle_price,
    validate_upsell,
)
from app.services.tracking import meta as meta_svc
from app.services.tracking import snapchat as snap_svc
from app.services.tracking import tiktok as tiktok_svc

logger = get_logger(__name__)

KSA_MOBILE_RE = re.compile(r"^(?:\+966|00966|966|0)?5[0-9]{8}$")


def get_client_ip(request: Request) -> str:
    settings = get_settings()
    if settings.trust_proxy_headers:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "0.0.0.0"


async def generate_public_order_number(db: AsyncSession) -> str:
    """Generate unique BSH-YYYYMMDD-XXXX order number."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    while True:
        suffix = "".join(random.choices(string.digits, k=4))
        number = f"BSH-{today}-{suffix}"
        existing = await db.execute(
            select(Order).where(Order.public_order_number == number)
        )
        if existing.scalar_one_or_none() is None:
            return number


def _validate_phone(raw_phone: str, test_whitelist: str) -> tuple[str, str, str, str | None] | None:
    """Returns (e164, digits_no_plus, display, iso_country) or None."""
    cleaned = re.sub(r"[\s\-\(\).]", "", raw_phone)
    if cleaned == test_whitelist:
        return cleaned, cleaned, cleaned, None
    return normalize_phone(cleaned)


async def validate_order(req: ValidateOrderRequest, request: Request) -> ValidateOrderResponse:
    settings = get_settings()
    phone_result = _validate_phone(req.customer.phone, settings.test_phone_whitelist)
    if not phone_result:
        return ValidateOrderResponse(
            valid=False,
            error="اكتبي رقم جوال صحيح",
            error_code="invalid_phone",
        )
    _, _, local, _ = phone_result
    return ValidateOrderResponse(valid=True, normalized_phone=local)


async def create_order(req: CreateOrderRequest, request: Request, db: AsyncSession) -> CreateOrderResponse:
    settings = get_settings()
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")

    # Phone validation
    phone_result = _validate_phone(req.customer.phone, settings.test_phone_whitelist)
    if not phone_result:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_phone",
                "message": "اكتبي رقم جوال صحيح لإكمال الطلب.",
            },
        )
    phone_e164, phone_digits, phone_local, phone_iso = phone_result
    wl_raw = settings.test_phone_whitelist.strip()
    wl_digits = wl_raw.lstrip("+").lstrip("0")
    phone_tail = phone_e164.lstrip("+").lstrip("0")
    is_test = phone_tail.endswith(wl_digits) or wl_digits.endswith(phone_tail)

    # Idempotency check
    if req.idempotency_key:
        existing = await db.execute(
            select(Order).where(Order.idempotency_key == req.idempotency_key)
        )
        existing_order = existing.scalar_one_or_none()
        if existing_order:
            logger.info("order_idempotent_reuse", order_id=existing_order.id)
            return CreateOrderResponse(
                order_id=existing_order.id,
                public_order_number=existing_order.public_order_number,
                status=existing_order.status,
                total_sar=existing_order.total_sar,
                is_test_order=existing_order.is_test_order,
                thank_you_url=f"{settings.frontend_base_url}/thank-you/{existing_order.id}",
            )

    welcome_codes = {c.strip() for c in settings.welcome_promo_codes.split(",") if c.strip()}
    welcome_active = bool(req.promo_code and req.promo_code.strip() in welcome_codes)

    # Server-side cart validation
    items_total = 0
    validated_items = []
    for item in req.items:
        product = get_product(item.product_id)
        if not product:
            raise HTTPException(
                status_code=422,
                detail={"error": "invalid_product", "message": "منتج غير موجود في الكتالوج."},
            )
        if not validate_bundle_price(
            item.product_id,
            item.quantity,
            item.bundle_price_sar,
            welcome_discount=welcome_active,
        ):
            raise HTTPException(
                status_code=422,
                detail={"error": "invalid_price", "message": "سعر الباقة غير صحيح."},
            )
        items_total += item.bundle_price_sar
        validated_items.append((item, product))

    upsell_total = 0
    if req.upsell and req.upsell.accepted and req.upsell.product_id:
        main_ids = [item.product_id for item in req.items]
        upsell_price = req.upsell.price_sar or 0
        if not validate_upsell(
            req.upsell.product_id,
            main_ids,
            upsell_price,
            welcome_discount=welcome_active,
        ):
            raise HTTPException(
                status_code=422,
                detail={"error": "invalid_upsell", "message": "عرض الإضافة غير صحيح."},
            )
        upsell_total = upsell_price
        upsell_product = get_product(req.upsell.product_id)
        if upsell_product:
            validated_items.append((
                type("UpsellItem", (), {
                    "product_id": req.upsell.product_id,
                    "quantity": 1,
                    "bundle_price_sar": upsell_price,
                    "source": "checkout_upsell",
                })(),
                upsell_product,
            ))

    shipping = req.pricing.shipping_sar
    expected_total = items_total + upsell_total + shipping

    if req.pricing.total_sar != expected_total:
        raise HTTPException(
            status_code=422,
            detail={"error": "total_mismatch", "message": "إجمالي الطلب غير صحيح."},
        )

    # Always-on country gate (works even if MaxMind is down/unconfigured).
    # Skipped only for the whitelisted test phone.
    allowed_countries = settings.get_allowed_countries()
    ip_iso_fallback = None if is_test else await geoip_svc.lookup_country(client_ip)

    if not is_test and allowed_countries:
        if ip_iso_fallback and ip_iso_fallback not in allowed_countries:
            logger.warning(
                "country_not_allowed_geoip",
                ip=client_ip,
                ip_iso=ip_iso_fallback,
            )
            fraud_check_record = FraudCheck(
                phone_e164_masked=mask_phone(phone_e164),
                ip_address=client_ip,
                decision="rejected",
                reason=f"country_not_allowed_geoip:{ip_iso_fallback}",
                country_iso_code=ip_iso_fallback,
            )
            db.add(fraud_check_record)
            await db.commit()
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "order_rejected",
                    "message": "عذرًا، الطلبات غير متاحة في بلدك حاليًا. تواصلي معنا إذا كان هذا خطأ.",
                },
            )

        if ip_iso_fallback and phone_iso and ip_iso_fallback != phone_iso:
            logger.warning(
                "phone_ip_country_mismatch_geoip",
                phone_iso=phone_iso,
                ip_iso=ip_iso_fallback,
                ip=client_ip,
            )
            fraud_check_record = FraudCheck(
                phone_e164_masked=mask_phone(phone_e164),
                ip_address=client_ip,
                decision="rejected",
                reason=f"phone_ip_country_mismatch:{phone_iso}_vs_{ip_iso_fallback}",
                country_iso_code=ip_iso_fallback,
            )
            db.add(fraud_check_record)
            await db.commit()
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "order_rejected",
                    "message": "رقم الجوال لا يتطابق مع بلد الاتصال. إذا كان هذا خطأ تواصلي معنا.",
                },
            )

    # MaxMind layer: VPN / proxy / Tor / risk score (independent of basic country gate)
    fraud_result = await maxmind_svc.check_fraud(
        ip_address=client_ip,
        user_agent=user_agent,
        phone_e164=phone_e164,
        order_id=f"pre-{req.idempotency_key or 'none'}",
        amount_sar=float(expected_total),
    )

    if not fraud_result.allowed:
        fraud_check_record = FraudCheck(
            phone_e164_masked=mask_phone(phone_e164),
            ip_address=client_ip,
            decision=fraud_result.decision,
            reason=fraud_result.reason,
            country_iso_code=fraud_result.country_iso_code or ip_iso_fallback,
            risk_score=fraud_result.risk_score,
            ip_risk=fraud_result.ip_risk,
            raw_response=fraud_result.raw_response,
        )
        db.add(fraud_check_record)
        await db.commit()
        raise HTTPException(
            status_code=403,
            detail={
                "error": "order_rejected",
                "message": "عذرًا، لا يمكن إتمام الطلب. إذا كنتِ تعتقدين أن هذا خطأ، تواصلي معنا.",
            },
        )

    # Re-check IP/phone match using whichever country signal we got (MaxMind preferred)
    effective_ip_iso = fraud_result.country_iso_code or ip_iso_fallback
    if (
        not is_test
        and phone_iso
        and effective_ip_iso
        and effective_ip_iso != phone_iso
    ):
        logger.warning(
            "phone_ip_country_mismatch",
            phone_iso=phone_iso,
            ip_iso=effective_ip_iso,
            ip=client_ip,
        )
        fraud_check_record = FraudCheck(
            phone_e164_masked=mask_phone(phone_e164),
            ip_address=client_ip,
            decision="rejected",
            reason=f"phone_ip_country_mismatch:{phone_iso}_vs_{effective_ip_iso}",
            country_iso_code=effective_ip_iso,
            risk_score=fraud_result.risk_score,
            ip_risk=fraud_result.ip_risk,
            raw_response=fraud_result.raw_response,
        )
        db.add(fraud_check_record)
        await db.commit()
        raise HTTPException(
            status_code=403,
            detail={
                "error": "order_rejected",
                "message": "رقم الجوال لا يتطابق مع بلد الاتصال. إذا كان هذا خطأ تواصلي معنا.",
            },
        )

    # Create order
    public_number = await generate_public_order_number(db)
    tracking = req.tracking or type("T", (), {
        "purchase_event_id": None, "fbp": None, "fbc": None,
        "ttp": None, "ttclid": None, "sc_click_id": None, "sc_cookie1": None,
        "landing_page_url": None, "page_url": None, "utm": None,
    })()

    utm = tracking.utm if hasattr(tracking, "utm") and tracking.utm else None

    order = Order(
        public_order_number=public_number,
        status="pending_confirmation",
        customer_name=req.customer.name,
        customer_phone_e164=phone_e164,
        customer_phone_local=phone_local,
        is_test_order=is_test or fraud_result.is_test,
        subtotal_sar=expected_total - shipping,
        shipping_sar=shipping,
        total_sar=expected_total,
        display_currency=req.pricing.currency if req.pricing.currency != "SAR" else None,
        ip_address=client_ip,
        user_agent=user_agent,
        purchase_event_id=tracking.purchase_event_id,
        idempotency_key=req.idempotency_key,
        landing_page_url=tracking.landing_page_url,
        page_url=tracking.page_url,
        utm_source=utm.source if utm else None,
        utm_medium=utm.medium if utm else None,
        utm_campaign=utm.campaign if utm else None,
        utm_content=utm.content if utm else None,
        utm_term=utm.term if utm else None,
    )
    db.add(order)
    await db.flush()

    order_items = []
    for item, product in validated_items:
        oi = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            product_name_ar=product.name_ar,
            quantity=item.quantity,
            bundle_price_sar=item.bundle_price_sar,
            source=item.source,
        )
        db.add(oi)
        order_items.append(oi)

    fraud_record = FraudCheck(
        order_id=order.id,
        phone_e164_masked=mask_phone(phone_e164),
        ip_address=client_ip,
        decision=fraud_result.decision,
        reason=fraud_result.reason,
        country_iso_code=fraud_result.country_iso_code,
        risk_score=fraud_result.risk_score,
        ip_risk=fraud_result.ip_risk,
        raw_response=fraud_result.raw_response,
    )
    db.add(fraud_record)
    await db.commit()

    logger.info(
        "order_created",
        order_id=order.id,
        public_number=public_number,
        is_test=order.is_test_order,
        total=expected_total,
    )

    # Fire CAPI and Sheets async (non-blocking for order response)
    capi_payload = CAPIOrderPayload(
        order_id=order.id,
        event_id=tracking.purchase_event_id or order.id,
        total_sar=float(expected_total),
        contents=[
            CAPIContent(id=oi.product_id, quantity=oi.quantity, item_price=oi.bundle_price_sar)
            for oi in order_items
        ],
        phone_e164=phone_e164,
        ip_address=client_ip,
        user_agent=user_agent,
        fbp=tracking.fbp if hasattr(tracking, "fbp") else None,
        fbc=tracking.fbc if hasattr(tracking, "fbc") else None,
        ttp=tracking.ttp if hasattr(tracking, "ttp") else None,
        ttclid=tracking.ttclid if hasattr(tracking, "ttclid") else None,
        sc_click_id=tracking.sc_click_id if hasattr(tracking, "sc_click_id") else None,
        sc_cookie1=tracking.sc_cookie1 if hasattr(tracking, "sc_cookie1") else None,
        event_source_url=tracking.page_url if hasattr(tracking, "page_url") else None,
        is_test=order.is_test_order,
    )

    asyncio.create_task(
        _fire_post_order_tasks(
            order=order,
            order_items=order_items,
            capi_payload=capi_payload,
            fraud_result=fraud_result,
            db_factory=db.get_bind(),
        )
    )

    return CreateOrderResponse(
        order_id=order.id,
        public_order_number=public_number,
        status=order.status,
        total_sar=expected_total,
        is_test_order=order.is_test_order,
        thank_you_url=f"{settings.frontend_base_url}/thank-you/{order.id}",
    )


def _detect_vpn_proxy_label(fraud: FraudDecision) -> str:
    """Build a human-readable label for VPN/proxy detection flags."""
    flags: list[str] = []
    if fraud.is_anonymous_vpn:
        flags.append("VPN")
    if fraud.is_anonymous_proxy:
        flags.append("Proxy")
    if fraud.is_public_proxy:
        flags.append("Public Proxy")
    if fraud.is_residential_proxy:
        flags.append("Residential Proxy")
    if fraud.is_hosting_provider:
        flags.append("Hosting/Datacenter")
    if fraud.is_tor_exit_node:
        flags.append("Tor")
    return ", ".join(flags) if flags else ""


async def _fire_post_order_tasks(
    order: Order,
    order_items: list[OrderItem],
    capi_payload: CAPIOrderPayload,
    fraud_result: FraudDecision,
    db_factory,
) -> None:
    """Run CAPI + Sheets tasks after order creation without blocking the response."""
    from app.db.session import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        meta_result, tiktok_result, snap_result = await asyncio.gather(
            meta_svc.send_purchase_event(capi_payload),
            tiktok_svc.send_purchase_event(capi_payload),
            snap_svc.send_purchase_event(capi_payload),
            return_exceptions=True,
        )

        for platform, result in [("meta", meta_result), ("tiktok", tiktok_result), ("snapchat", snap_result)]:
            if isinstance(result, Exception):
                status = "failed"
                error = str(result)
                response = None
            else:
                status = result.get("status", "failed")
                error = result.get("error")
                response = result.get("response")

            te = TrackingEvent(
                order_id=order.id,
                platform=platform,
                event_name="Purchase",
                event_id=capi_payload.event_id,
                status=status,
                response_payload=response,
                error=error,
            )
            session.add(te)

        sheets_result = await sheets_svc.send_to_sheets(
            order=order,
            items=order_items,
            fraud_decision=fraud_result.decision,
            fraud_reason=fraud_result.reason,
            country_iso=fraud_result.country_iso_code,
            risk_score=fraud_result.risk_score,
            ip_risk=fraud_result.ip_risk,
            is_vpn_proxy=_detect_vpn_proxy_label(fraud_result),
        )
        wd = WebhookDelivery(
            order_id=order.id,
            destination="google_sheets",
            status=sheets_result.get("status", "failed"),
            attempts=1,
            last_error=sheets_result.get("error"),
        )
        session.add(wd)
        await session.commit()
