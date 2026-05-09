from __future__ import annotations

import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import hash_phone_meta
from app.schemas.tracking import CAPIOrderPayload

logger = get_logger(__name__)


async def send_purchase_event(payload: CAPIOrderPayload) -> dict:
    """
    Send Purchase server event to Meta Conversions API.
    Returns result dict with status. Never raises on failure.
    """
    settings = get_settings()

    if not settings.meta_pixel_id or not settings.meta_capi_access_token:
        logger.warning("meta_capi_not_configured")
        return {"status": "skipped", "reason": "not_configured"}

    if payload.is_test and not settings.send_test_events:
        logger.info("meta_capi_skipped_test_order")
        return {"status": "skipped", "reason": "test_order"}

    hashed_phone = hash_phone_meta(payload.phone_e164)

    user_data: dict = {
        "ph": [hashed_phone],
    }
    if payload.ip_address:
        user_data["client_ip_address"] = payload.ip_address
    if payload.user_agent:
        user_data["client_user_agent"] = payload.user_agent
    if payload.fbp:
        user_data["fbp"] = payload.fbp
    if payload.fbc:
        user_data["fbc"] = payload.fbc

    event_payload = {
        "data": [
            {
                "event_name": "Purchase",
                "event_time": int(time.time()),
                "event_id": payload.event_id,
                "action_source": "website",
                "event_source_url": payload.event_source_url or settings.frontend_base_url,
                "user_data": user_data,
                "custom_data": {
                    "currency": "SAR",
                    "value": payload.total_sar,
                    "contents": [
                        {"id": c.id, "quantity": c.quantity, "item_price": c.item_price}
                        for c in payload.contents
                    ],
                    "content_type": "product",
                    "order_id": payload.order_id,
                },
            }
        ]
    }

    if settings.meta_test_event_code:
        event_payload["test_event_code"] = settings.meta_test_event_code

    try:
        result = await _post_to_meta(
            pixel_id=settings.meta_pixel_id,
            access_token=settings.meta_capi_access_token,
            version=settings.meta_capi_version,
            payload=event_payload,
        )
        logger.info("meta_capi_sent", event_id=payload.event_id, order_id=payload.order_id)
        return {"status": "sent", "response": result}
    except Exception as exc:
        logger.error("meta_capi_failed", error=str(exc), order_id=payload.order_id)
        return {"status": "failed", "error": str(exc)}


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4), reraise=True)
async def _post_to_meta(pixel_id: str, access_token: str, version: str, payload: dict) -> dict:
    url = f"https://graph.facebook.com/{version}/{pixel_id}/events"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url,
            params={"access_token": access_token},
            json=payload,
        )
        response.raise_for_status()
        return response.json()
