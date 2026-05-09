from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.order import Order


class FraudCheck(Base):
    __tablename__ = "fraud_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    phone_e164_masked: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="maxmind")
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    country_iso_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    ip_risk: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    is_anonymous_proxy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_anonymous_vpn: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_hosting_provider: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_public_proxy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_residential_proxy: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_tor_exit_node: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    raw_response: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    order: Mapped["Order | None"] = relationship("Order", back_populates="fraud_checks")
