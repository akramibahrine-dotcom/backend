from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CustomerInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    phone: str = Field(..., min_length=7, max_length=20)
    address: str | None = Field(None, max_length=500)


class OrderItemInput(BaseModel):
    product_id: str = Field(..., min_length=1, max_length=100)
    quantity: Literal[1, 2, 3]
    bundle_price_sar: int = Field(..., gt=0)
    source: Literal["product_page", "cart_cross_sell", "checkout_upsell"] = "product_page"


class UpsellInput(BaseModel):
    accepted: bool
    product_id: str | None = None
    price_sar: int | None = None


class PricingInput(BaseModel):
    subtotal_sar: int = Field(..., ge=0)
    shipping_sar: int = Field(default=0, ge=0)
    total_sar: int = Field(..., ge=0)
    currency: str = "SAR"
    display_total: float | None = None


class UTMData(BaseModel):
    source: str | None = None
    medium: str | None = None
    campaign: str | None = None
    content: str | None = None
    term: str | None = None


class TrackingInput(BaseModel):
    purchase_event_id: str = Field(..., min_length=8, max_length=100)
    initiate_checkout_event_id: str | None = None
    fbp: str | None = None
    fbc: str | None = None
    ttp: str | None = None
    ttclid: str | None = None
    sc_click_id: str | None = None
    sc_cookie1: str | None = None
    landing_page_url: str | None = None
    page_url: str | None = None
    utm: UTMData | None = None


class CreateOrderRequest(BaseModel):
    customer: CustomerInput
    promo_code: str | None = None
    items: list[OrderItemInput] = Field(..., min_length=1)
    upsell: UpsellInput | None = None
    pricing: PricingInput
    tracking: TrackingInput
    idempotency_key: str | None = None

    @field_validator("items")
    @classmethod
    def validate_items_not_empty(cls, v: list[OrderItemInput]) -> list[OrderItemInput]:
        if not v:
            raise ValueError("Order must have at least one item")
        return v


class ValidateOrderRequest(BaseModel):
    customer: CustomerInput
    items: list[OrderItemInput] = Field(..., min_length=1)
    pricing: PricingInput


class OrderItemResponse(BaseModel):
    id: str
    product_id: str
    product_name_ar: str
    quantity: int
    bundle_price_sar: int
    source: str


class CreateOrderResponse(BaseModel):
    order_id: str
    public_order_number: str
    status: str
    total_sar: int
    is_test_order: bool
    thank_you_url: str
    purchase_event_id: str


class ValidateOrderResponse(BaseModel):
    valid: bool
    normalized_phone: str | None = None
    error: str | None = None
    error_code: str | None = None
