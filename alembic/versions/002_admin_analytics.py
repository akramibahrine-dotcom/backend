"""Admin analytics clicks

Revision ID: 002
Revises: 001
Create Date: 2026-05-11

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS site_clicks (
            id VARCHAR(36) PRIMARY KEY,
            session_id VARCHAR(100),
            event_name VARCHAR(80) NOT NULL,
            page_url TEXT,
            referrer TEXT,
            product_id VARCHAR(100),
            source VARCHAR(100),
            device_type VARCHAR(50),
            browser VARCHAR(100),
            os VARCHAR(100),
            utm_source VARCHAR(200),
            utm_medium VARCHAR(200),
            utm_campaign VARCHAR(200),
            utm_content VARCHAR(200),
            utm_term VARCHAR(200),
            ip_address VARCHAR(50),
            user_agent TEXT,
            country_iso_code VARCHAR(10),
            risk_score NUMERIC(6, 2),
            ip_risk NUMERIC(6, 2),
            is_valid_ksa BOOLEAN NOT NULL DEFAULT FALSE,
            invalid_reason VARCHAR(200),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_site_clicks_session_id ON site_clicks (session_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_site_clicks_event_name ON site_clicks (event_name)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_site_clicks_product_id ON site_clicks (product_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_site_clicks_device_type ON site_clicks (device_type)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_site_clicks_country_iso_code ON site_clicks (country_iso_code)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_site_clicks_is_valid_ksa ON site_clicks (is_valid_ksa)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_site_clicks_created_at ON site_clicks (created_at)"))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS admin_login_events (
            id VARCHAR(36) PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            ip_address VARCHAR(50),
            user_agent TEXT,
            device_type VARCHAR(50),
            browser VARCHAR(100),
            os VARCHAR(100),
            country_iso_code VARCHAR(10),
            status VARCHAR(50) NOT NULL DEFAULT 'success',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_admin_login_events_username ON admin_login_events (username)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_admin_login_events_ip_address ON admin_login_events (ip_address)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_admin_login_events_status ON admin_login_events (status)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_admin_login_events_created_at ON admin_login_events (created_at)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_admin_login_events_last_seen_at ON admin_login_events (last_seen_at)"))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS admin_access_rules (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            rule_type VARCHAR(50) NOT NULL,
            value VARCHAR(200) NOT NULL,
            action VARCHAR(50) NOT NULL DEFAULT 'allow',
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_admin_access_rules_rule_type ON admin_access_rules (rule_type)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_admin_access_rules_enabled ON admin_access_rules (enabled)"))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS store_translation_overrides (
            id VARCHAR(36) PRIMARY KEY,
            locale VARCHAR(20) NOT NULL DEFAULT 'ar',
            translation_key VARCHAR(300) NOT NULL,
            value TEXT NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_store_translation_overrides_translation_key ON store_translation_overrides (translation_key)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_store_translation_overrides_enabled ON store_translation_overrides (enabled)"))


def downgrade() -> None:
    op.drop_table("store_translation_overrides")
    op.drop_table("admin_access_rules")
    op.drop_table("admin_login_events")
    op.drop_table("site_clicks")
