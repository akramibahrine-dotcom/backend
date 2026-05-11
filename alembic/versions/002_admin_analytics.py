"""Admin analytics clicks

Revision ID: 002
Revises: 001
Create Date: 2026-05-11

"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_clicks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(100), nullable=True),
        sa.Column("event_name", sa.String(80), nullable=False),
        sa.Column("page_url", sa.Text, nullable=True),
        sa.Column("referrer", sa.Text, nullable=True),
        sa.Column("product_id", sa.String(100), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("device_type", sa.String(50), nullable=True),
        sa.Column("browser", sa.String(100), nullable=True),
        sa.Column("os", sa.String(100), nullable=True),
        sa.Column("utm_source", sa.String(200), nullable=True),
        sa.Column("utm_medium", sa.String(200), nullable=True),
        sa.Column("utm_campaign", sa.String(200), nullable=True),
        sa.Column("utm_content", sa.String(200), nullable=True),
        sa.Column("utm_term", sa.String(200), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("country_iso_code", sa.String(10), nullable=True),
        sa.Column("risk_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("ip_risk", sa.Numeric(6, 2), nullable=True),
        sa.Column("is_valid_ksa", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("invalid_reason", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_site_clicks_session_id", "site_clicks", ["session_id"])
    op.create_index("ix_site_clicks_event_name", "site_clicks", ["event_name"])
    op.create_index("ix_site_clicks_product_id", "site_clicks", ["product_id"])
    op.create_index("ix_site_clicks_device_type", "site_clicks", ["device_type"])
    op.create_index("ix_site_clicks_country_iso_code", "site_clicks", ["country_iso_code"])
    op.create_index("ix_site_clicks_is_valid_ksa", "site_clicks", ["is_valid_ksa"])
    op.create_index("ix_site_clicks_created_at", "site_clicks", ["created_at"])

    op.create_table(
        "admin_login_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("device_type", sa.String(50), nullable=True),
        sa.Column("browser", sa.String(100), nullable=True),
        sa.Column("os", sa.String(100), nullable=True),
        sa.Column("country_iso_code", sa.String(10), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_login_events_username", "admin_login_events", ["username"])
    op.create_index("ix_admin_login_events_ip_address", "admin_login_events", ["ip_address"])
    op.create_index("ix_admin_login_events_status", "admin_login_events", ["status"])
    op.create_index("ix_admin_login_events_created_at", "admin_login_events", ["created_at"])
    op.create_index("ix_admin_login_events_last_seen_at", "admin_login_events", ["last_seen_at"])

    op.create_table(
        "admin_access_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("rule_type", sa.String(50), nullable=False),
        sa.Column("value", sa.String(200), nullable=False),
        sa.Column("action", sa.String(50), nullable=False, server_default="allow"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_admin_access_rules_rule_type", "admin_access_rules", ["rule_type"])
    op.create_index("ix_admin_access_rules_enabled", "admin_access_rules", ["enabled"])

    op.create_table(
        "store_translation_overrides",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("locale", sa.String(20), nullable=False, server_default="ar"),
        sa.Column("translation_key", sa.String(300), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_store_translation_overrides_translation_key", "store_translation_overrides", ["translation_key"])
    op.create_index("ix_store_translation_overrides_enabled", "store_translation_overrides", ["enabled"])


def downgrade() -> None:
    op.drop_table("store_translation_overrides")
    op.drop_table("admin_access_rules")
    op.drop_table("admin_login_events")
    op.drop_table("site_clicks")
