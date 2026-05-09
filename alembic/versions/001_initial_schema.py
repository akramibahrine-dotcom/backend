"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-08

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("public_order_number", sa.String(50), unique=True, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending_confirmation"),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("customer_phone_e164", sa.String(20), nullable=False),
        sa.Column("customer_phone_local", sa.String(20), nullable=False),
        sa.Column("is_test_order", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("subtotal_sar", sa.Integer, nullable=False),
        sa.Column("shipping_sar", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_sar", sa.Integer, nullable=False),
        sa.Column("display_currency", sa.String(10), nullable=True),
        sa.Column("display_total", sa.Numeric(12, 2), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("landing_page_url", sa.Text, nullable=True),
        sa.Column("page_url", sa.Text, nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("utm_source", sa.String(200), nullable=True),
        sa.Column("utm_medium", sa.String(200), nullable=True),
        sa.Column("utm_campaign", sa.String(200), nullable=True),
        sa.Column("utm_content", sa.String(200), nullable=True),
        sa.Column("utm_term", sa.String(200), nullable=True),
        sa.Column("purchase_event_id", sa.String(100), unique=True, nullable=True),
        sa.Column("idempotency_key", sa.String(100), unique=True, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_orders_public_order_number", "orders", ["public_order_number"])
    op.create_index("ix_orders_customer_phone_e164", "orders", ["customer_phone_e164"])
    op.create_index("ix_orders_created_at", "orders", ["created_at"])
    op.create_index("ix_orders_purchase_event_id", "orders", ["purchase_event_id"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.String(100), nullable=False),
        sa.Column("product_name_ar", sa.String(300), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("bundle_price_sar", sa.Integer, nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="product_page"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "fraud_checks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("phone_e164_masked", sa.String(30), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False, server_default="maxmind"),
        sa.Column("decision", sa.String(50), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False, server_default=""),
        sa.Column("country_iso_code", sa.String(10), nullable=True),
        sa.Column("risk_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("ip_risk", sa.Numeric(6, 2), nullable=True),
        sa.Column("is_anonymous_proxy", sa.Boolean, nullable=True),
        sa.Column("is_anonymous_vpn", sa.Boolean, nullable=True),
        sa.Column("is_hosting_provider", sa.Boolean, nullable=True),
        sa.Column("is_public_proxy", sa.Boolean, nullable=True),
        sa.Column("is_residential_proxy", sa.Boolean, nullable=True),
        sa.Column("is_tor_exit_node", sa.Boolean, nullable=True),
        sa.Column("raw_response", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_fraud_checks_ip_address", "fraud_checks", ["ip_address"])
    op.create_index("ix_fraud_checks_created_at", "fraud_checks", ["created_at"])

    op.create_table(
        "tracking_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("event_name", sa.String(100), nullable=False),
        sa.Column("event_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("request_payload", postgresql.JSONB, nullable=True),
        sa.Column("response_payload", postgresql.JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tracking_events_platform", "tracking_events", ["platform"])
    op.create_index("ix_tracking_events_event_id", "tracking_events", ["event_id"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("destination", sa.String(100), nullable=False, server_default="google_sheets"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("response_status", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("tracking_events")
    op.drop_table("fraud_checks")
    op.drop_table("order_items")
    op.drop_table("orders")
