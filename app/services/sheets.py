from __future__ import annotations

import random
import string
from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.order import Order, OrderItem
from app.schemas.order import CreateOrderRequest

logger = get_logger(__name__)


def build_order_payload(
    order: Order,
    items: list[OrderItem],
    fraud_decision: str,
    fraud_reason: str,
    country_iso: str | None,
    risk_score: float | None,
    ip_risk: float | None,
    is_vpn_proxy: str = "",
) -> dict:
    items_summary = "; ".join(
        f"{item.quantity}x {item.product_name_ar}" for item in items
    )
    item_count = sum(item.quantity for item in items)

    return {
        "public_order_number": order.public_order_number,
        "created_at": order.created_at.isoformat() if order.created_at else "",
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone_e164,
        "items_summary": items_summary,
        "item_count": item_count,
        "subtotal_sar": order.subtotal_sar,
        "shipping_sar": order.shipping_sar,
        "total_sar": order.total_sar,
        "display_currency": order.display_currency or "SAR",
        "display_total": float(order.display_total) if order.display_total else order.total_sar,
        "payment_method": "COD",
        "status": order.status,
        "confirmation_status": "pending",
        "is_test_order": order.is_test_order,
        "fraud_decision": fraud_decision,
        "fraud_reason": fraud_reason,
        "ip_country": country_iso or "",
        "risk_score": risk_score or "",
        "ip_risk": ip_risk or "",
        "utm_source": order.utm_source or "",
        "utm_medium": order.utm_medium or "",
        "utm_campaign": order.utm_campaign or "",
        "utm_content": order.utm_content or "",
        "utm_term": order.utm_term or "",
        "landing_page_url": order.landing_page_url or "",
        "page_url": order.page_url or "",
        "purchase_event_id": order.purchase_event_id or "",
        "vpn_proxy": is_vpn_proxy,
        "notes": "",
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
        "secret": settings.google_sheets_webhook_secret,
        "order": build_order_payload(
            order=order,
            items=items,
            fraud_decision=fraud_decision,
            fraud_reason=fraud_reason,
            country_iso=country_iso,
            risk_score=risk_score,
            ip_risk=ip_risk,
            is_vpn_proxy=is_vpn_proxy,
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
    Push a *rejected* (or fraud-flagged) order attempt to the Google Sheet so
    the operator can see every attempt — not only successful orders.
    Never raises.
    """
    settings = get_settings()

    if not settings.google_sheets_webhook_url:
        logger.warning("sheets_webhook_not_configured_rejected")
        return {"status": "skipped", "reason": "not_configured"}

    items_summary = "; ".join(
        f"{item.quantity}x {item.product_id}" for item in req.items
    )
    item_count = sum(item.quantity for item in req.items)

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = "".join(random.choices(string.digits, k=4))
    public_number = f"BSH-REJ-{today}-{suffix}"

    tracking = req.tracking
    utm = tracking.utm if tracking else None

    payload = {
        "secret": settings.google_sheets_webhook_secret,
        "order": {
            "public_order_number": public_number,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "customer_name": req.customer.name,
            "customer_phone": phone_e164 or req.customer.phone,
            "items_summary": items_summary,
            "item_count": item_count,
            "subtotal_sar": req.pricing.subtotal_sar,
            "shipping_sar": req.pricing.shipping_sar,
            "total_sar": req.pricing.total_sar,
            "display_currency": req.pricing.currency or "SAR",
            "display_total": req.pricing.total_sar,
            "payment_method": "COD",
            "status": "rejected",
            "confirmation_status": "rejected",
            "is_test_order": False,
            "fraud_decision": "rejected",
            "fraud_reason": fraud_reason,
            "ip_country": country_iso or "",
            "risk_score": risk_score if risk_score is not None else "",
            "ip_risk": ip_risk if ip_risk is not None else "",
            "utm_source": utm.source if utm else "",
            "utm_medium": utm.medium if utm else "",
            "utm_campaign": utm.campaign if utm else "",
            "utm_content": utm.content if utm else "",
            "utm_term": utm.term if utm else "",
            "landing_page_url": tracking.landing_page_url if tracking else "",
            "page_url": tracking.page_url if tracking else "",
            "purchase_event_id": tracking.purchase_event_id if tracking else "",
            "vpn_proxy": is_vpn_proxy,
            "notes": f"REJECTED ATTEMPT - IP: {client_ip}",
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
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()
