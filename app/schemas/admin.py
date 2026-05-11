from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UTMInput(BaseModel):
    source: str | None = None
    medium: str | None = None
    campaign: str | None = None
    content: str | None = None
    term: str | None = None


class TrackClickRequest(BaseModel):
    event_name: str = Field(..., min_length=1, max_length=80)
    session_id: str | None = Field(None, max_length=100)
    page_url: str | None = Field(None, max_length=2000)
    referrer: str | None = Field(None, max_length=2000)
    product_id: str | None = Field(None, max_length=100)
    source: str | None = Field(None, max_length=100)
    device_type: str | None = Field(None, max_length=50)
    browser: str | None = Field(None, max_length=100)
    os: str | None = Field(None, max_length=100)
    utm: UTMInput | None = None


class TrackClickResponse(BaseModel):
    accepted: bool
    reason: str | None = None


class AdminMetricsResponse(BaseModel):
    start_date: datetime
    end_date: datetime
    clicks: int
    unique_sessions: int
    orders: int
    revenue_sar: int
    average_order_value_sar: float
    conversion_rate: float
    rejected_attempts: int
    today: dict
    all_time: dict
    live_visitors: int
    new_customers: int
    cross_sell_rate: float
    upsell_rate: float
    top_products: list[dict]
    products: list[dict]
    daily: list[dict]
    campaign_breakdown: list[dict]
    traffic_sources: list[dict]
    device_breakdown: list[dict]
    country_breakdown: list[dict]


class AdminOrderItem(BaseModel):
    product_id: str
    product_name_ar: str
    quantity: int
    bundle_price_sar: int
    source: str


class AdminOrderListItem(BaseModel):
    id: str
    public_order_number: str
    status: str
    customer_name: str
    customer_phone_local: str
    total_sar: int
    is_test_order: bool
    created_at: datetime
    utm_source: str | None = None
    utm_campaign: str | None = None
    country_iso_code: str | None = None
    fraud_decision: str | None = None
    fraud_reason: str | None = None


class AdminOrdersResponse(BaseModel):
    orders: list[AdminOrderListItem]


class AdminOrderDetail(AdminOrderListItem):
    customer_phone_e164: str
    subtotal_sar: int
    shipping_sar: int
    display_currency: str | None = None
    display_total: float | None = None
    landing_page_url: str | None = None
    page_url: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    utm_medium: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    risk_score: float | None = None
    ip_risk: float | None = None
    items: list[AdminOrderItem]
    tracking_events: list[dict]
    webhook_deliveries: list[dict]


class AdminSessionResponse(BaseModel):
    ok: bool


class AdminAccessRuleInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    rule_type: str = Field(..., pattern="^(country|device|ip)$")
    value: str = Field(..., min_length=1, max_length=200)
    action: str = Field(..., pattern="^(allow|block)$")
    enabled: bool = True
    notes: str | None = None


class AdminAccessRuleResponse(AdminAccessRuleInput):
    id: str
    created_at: datetime
    updated_at: datetime


class AdminAccessRulesResponse(BaseModel):
    rules: list[AdminAccessRuleResponse]


class TranslationOverrideInput(BaseModel):
    locale: str = Field(default="ar", min_length=2, max_length=20)
    translation_key: str = Field(..., min_length=1, max_length=300)
    value: str = Field(..., min_length=1)
    enabled: bool = True


class TranslationOverrideResponse(TranslationOverrideInput):
    id: str
    created_at: datetime
    updated_at: datetime


class TranslationOverridesResponse(BaseModel):
    translations: list[TranslationOverrideResponse]


class AdminLoginEventsResponse(BaseModel):
    logins: list[dict]
    live: list[dict]
