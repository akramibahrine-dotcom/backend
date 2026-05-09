from __future__ import annotations

from pydantic import BaseModel


class CAPIContent(BaseModel):
    id: str
    quantity: int
    item_price: float


class CAPIOrderPayload(BaseModel):
    order_id: str
    event_id: str
    total_sar: float
    contents: list[CAPIContent]
    phone_e164: str
    ip_address: str | None
    user_agent: str | None
    fbp: str | None = None
    fbc: str | None = None
    ttp: str | None = None
    ttclid: str | None = None
    sc_click_id: str | None = None
    sc_cookie1: str | None = None
    event_source_url: str | None = None
    is_test: bool = False
