from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.fraud import FraudCheck
    from app.models.event import TrackingEvent, WebhookDelivery


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    public_order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending_confirmation")

    customer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_phone_e164: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    customer_phone_local: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_test_order: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    subtotal_sar: Mapped[int] = mapped_column(Integer, nullable=False)
    shipping_sar: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_sar: Mapped[int] = mapped_column(Integer, nullable=False)
    display_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    display_total: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    landing_page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)

    utm_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String(200), nullable=True)

    purchase_event_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    items: Mapped[list["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    fraud_checks: Mapped[list["FraudCheck"]] = relationship("FraudCheck", back_populates="order")
    tracking_events: Mapped[list["TrackingEvent"]] = relationship("TrackingEvent", back_populates="order")
    webhook_deliveries: Mapped[list["WebhookDelivery"]] = relationship("WebhookDelivery", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name_ar: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    bundle_price_sar: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="product_page")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    order: Mapped["Order"] = relationship("Order", back_populates="items")
