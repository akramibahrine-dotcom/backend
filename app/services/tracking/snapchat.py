from __future__ import annotations

import time

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import hash_phone_snapchat
from app.schemas.tracking import CAPIOrderPayload

logger = get_logger(__name__)

SNAP_CAPI_URL = "https://tr.snapchat.com/v2/conversion"


async def send_purchase_event(payload: CAPIOrderPayload) -> dict:
    """Send PURCHASE event to Snapchat Conversions API."""
    settings = get_settings()

    if not settings.snap_pixel_id or not settings.snap_access_token:
        logger.warning("snap_capi_not_configured")
        return {"status": "skipped", "reason": "not_configured"}

    if payload.is_test and not settings.send_test_events:
        logger.info("snap_capi_skipped_test_order")
        return {"status": "skipped", "reason": "test_order"}

    hashed_phone = hash_phone_snapchat(payload.phone_e164)

    user_data: dict = {
        "ph": [hashed_phone],
        "client_ip_address": payload.ip_address or "",
        "client_user_agent": payload.user_agent or "",
    }
    if payload.sc_click_id:
        user_data["sc_click_id"] = payload.sc_click_id
    if payload.sc_cookie1:
        user_data["sc_cookie1"] = payload.sc_cookie1

    event_payload = {
        "pixel_id": settings.snap_pixel_id,
        "test_event_code": settings.snap_test_event_code if settings.snap_test_event_code else None,
        "data": [
            {
                "event_name": "PURCHASE",
                "event_time": int(time.time()),
                "event_source_url": payload.event_source_url or "",
                "action_source": "WEB",
                "event_id": payload.event_id,
                "user_data": user_data,
                "custom_data": {
                    "currency": "SAR",
                    "price": str(payload.total_sar),
                    "number_items": sum(c.quantity for c in payload.contents),
                    "content_ids": [c.id for c in payload.contents],
                    "order_id": payload.order_id,
                    "transaction_id": payload.event_id,
                },
            }
        ],
    }

    if not event_payload.get("test_event_code"):
        del event_payload["test_event_code"]

    try:
        result = await _post_to_snap(
            access_token=settings.snap_access_token,
            payload=event_payload,
        )
        logger.info("snap_capi_sent", event_id=payload.event_id, order_id=payload.order_id)
        return {"status": "sent", "response": result}
    except Exception as exc:
        logger.error("snap_capi_failed", error=str(exc), order_id=payload.order_id)
        return {"status": "failed", "error": str(exc)}


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=4), reraise=True)
async def _post_to_snap(access_token: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            SNAP_CAPI_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        return response.json()
