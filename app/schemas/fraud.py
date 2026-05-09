from __future__ import annotations

from pydantic import BaseModel


class FraudDecision(BaseModel):
    allowed: bool
    decision: str
    reason: str
    country_iso_code: str | None = None
    risk_score: float | None = None
    ip_risk: float | None = None
    is_test: bool = False
    is_anonymous_proxy: bool | None = None
    is_anonymous_vpn: bool | None = None
    is_hosting_provider: bool | None = None
    is_public_proxy: bool | None = None
    is_residential_proxy: bool | None = None
    is_tor_exit_node: bool | None = None
    raw_response: dict | None = None
