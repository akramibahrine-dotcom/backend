from __future__ import annotations

import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import hash_phone_tiktok
from app.schemas.tracking import CAPIOrderPayload

logger = get_logger(__name__)

TIKTOK_EVENTS_API = "https://business-api.tiktok.com/open_api/v1.3/event/track/"


async def send_purchase_event(payload: CAPIOrderPayload) -> dict:
    """Send Purchase/CompletePayment to TikTok Events API."""
    settings = get_settings()

    if not settings.tiktok_pixel_code or not settings.tiktok_access_token:
        logger.warning("tiktok_capi_not_configured")
        return {"status": "skipped", "reason": "not_configured"}

    if payload.is_test and not settings.send_test_events:
        logger.info("tiktok_capi_skipped_test_order")
        return {"status": "skipped", "reason": "test_order"}

    hashed_phone = hash_phone_tiktok(payload.phone_e164)

    context: dict = {
        "ip": payload.ip_address or "",
        "user_agent": payload.user_agent or "",
        "user": {"phone_number": hashed_phone},
    }
    if payload.ttclid:
        context["ad"] = {"callback": payload.ttclid}
    if payload.ttp:
        context["user"]["ttp"] = payload.ttp

    event_payload = {
        "pixel_code": settings.tiktok_pixel_code,
        "event": "CompletePayment",
        "event_id": payload.event_id,
        "timestamp": str(int(time.time())),
        "context": context,
        "properties": {
            "currency": "SAR",
            "value": str(payload.total_sar),
            "contents": [
                {"content_id": c.id, "quantity": c.quantity, "price": str(c.item_price)}
                for c in payload.contents
            ],
            "order_id": payload.order_id,
        },
    }

    if settings.tiktok_test_event_code:
        event_payload["test_event_code"] = settings.tiktok_test_event_code

    try:
        result = await _post_to_tiktok(
            access_token=settings.tiktok_access_token,
            payload=event_payload,
        )
        logger.info("tiktok_capi_sent", event_id=payload.event_id, order_id=payload.order_id)
        return {"status": "sent", "response": result}
    except Exception as exc:
        logger.error("tiktok_capi_failed", error=str(exc), order_id=payload.order_id)
        return {"status": "failed", "error": str(exc)}


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4), reraise=True)
async def _post_to_tiktok(access_token: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            TIKTOK_EVENTS_API,
            headers={
                "Access-Token": access_token,
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        return response.json()
