from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["development", "production", "test"] = "production"
    api_base_url: str = "https://api.baytseha.shop"
    frontend_base_url: str = "https://baytseha.shop"
    cors_origins: str = "https://baytseha.shop,https://www.baytseha.shop"

    # Database
    database_url: str = "postgresql+asyncpg://baytseha:baytseha_dev@localhost:5432/baytseha"
    run_migrations_on_start: bool = True

    # Admin
    admin_username: str = ""
    admin_password: str = ""

    # Phone / Testing
    test_phone_whitelist: str = "0501234987"
    trust_proxy_headers: bool = True

    # MaxMind
    maxmind_account_id: str = ""
    maxmind_license_key: str = ""
    maxmind_minfraud_endpoint: str = "https://minfraud.maxmind.com/minfraud/v2.0/insights"
    maxmind_max_risk_score: float = 25.0
    maxmind_max_ip_risk: float = 10.0
    maxmind_allowed_countries: str = "SA,AE,KW,QA,BH,OM,LB,IQ,LY"
    analytics_allowed_countries: str = "SA,AE,KW,QA,BH,OM,LB,IQ,LY"
    maxmind_block_anonymous_ip: bool = True
    fraud_provider_failure_mode: Literal["reject", "allow"] = "reject"

    # Google Sheets
    google_sheets_webhook_url: str = ""

    # Meta CAPI
    meta_pixel_id: str = ""
    meta_capi_access_token: str = ""
    meta_test_event_code: str = ""
    meta_capi_version: str = "v19.0"

    # TikTok Events API
    tiktok_pixel_code: str = ""
    tiktok_access_token: str = ""
    tiktok_test_event_code: str = ""

    # Snapchat CAPI
    snap_pixel_id: str = ""
    snap_access_token: str = ""
    snap_test_event_code: str = ""

    # Controls whether to send Purchase events for test orders
    send_test_events: bool = False

    # Currency
    currency_api_url: str = ""
    currency_api_key: str = ""
    default_currency: str = "SAR"

    # Welcome promo (must match frontend `WELCOME_PROMO_CODE`)
    welcome_promo_codes: str = "عميل10,WELCOME10"

    # Logging
    log_level: str = "INFO"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str) -> str:
        return v

    def get_cors_origins_list(self) -> list[str]:
        return [o.strip().lower() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def maxmind_configured(self) -> bool:
        return bool(self.maxmind_account_id and self.maxmind_license_key)

    def get_allowed_countries(self) -> set[str]:
        return {c.strip().upper() for c in self.maxmind_allowed_countries.split(",") if c.strip()}

    def get_analytics_allowed_countries(self) -> set[str]:
        return {c.strip().upper() for c in self.analytics_allowed_countries.split(",") if c.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
