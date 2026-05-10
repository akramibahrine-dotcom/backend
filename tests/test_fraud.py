"""Tests for MaxMind fraud decision logic."""
from __future__ import annotations

from app.services.maxmind import _evaluate_result

class MockSettings:
    maxmind_allowed_countries = "SA"
    maxmind_block_anonymous_ip = True
    maxmind_max_risk_score = 25.0
    maxmind_max_ip_risk = 10.0

    def get_allowed_countries(self) -> set[str]:
        return {"SA"}


SETTINGS = MockSettings()


def make_response(
    country_iso="SA",
    risk_score=5.0,
    ip_risk=2.0,
    is_anonymous=False,
    is_anonymous_proxy=False,
    is_anonymous_vpn=False,
    is_hosting_provider=False,
    is_public_proxy=False,
    is_residential_proxy=False,
    is_tor_exit_node=False,
):
    return {
        "risk_score": risk_score,
        "ip_address": {
            "risk": ip_risk,
            "country": {"iso_code": country_iso},
            "traits": {
                "is_anonymous": is_anonymous,
                "is_anonymous_proxy": is_anonymous_proxy,
                "is_anonymous_vpn": is_anonymous_vpn,
                "is_hosting_provider": is_hosting_provider,
                "is_public_proxy": is_public_proxy,
                "is_residential_proxy": is_residential_proxy,
                "is_tor_exit_node": is_tor_exit_node,
            },
        },
    }


class TestFraudDecisionLogic:
    def test_ksa_low_risk_allowed(self):
        result = _evaluate_result(make_response(country_iso="SA", risk_score=5), SETTINGS)
        assert result.allowed is True
        assert result.decision == "allowed"
        assert result.reason == "passed"

    def test_non_ksa_rejected(self):
        result = _evaluate_result(make_response(country_iso="US"), SETTINGS)
        assert result.allowed is False
        assert result.reason == "country_not_allowed"

    def test_high_risk_score_rejected(self):
        result = _evaluate_result(make_response(risk_score=30), SETTINGS)
        assert result.allowed is False
        assert result.reason == "high_risk_score"

    def test_high_ip_risk_rejected(self):
        result = _evaluate_result(make_response(ip_risk=15), SETTINGS)
        assert result.allowed is False
        assert result.reason == "high_ip_risk"

    def test_anonymous_ip_rejected(self):
        result = _evaluate_result(make_response(is_anonymous=True), SETTINGS)
        assert result.allowed is False
        assert result.reason == "anonymous_ip"

    def test_vpn_rejected(self):
        result = _evaluate_result(make_response(is_anonymous_vpn=True), SETTINGS)
        assert result.allowed is False
        assert result.reason == "anonymous_vpn"

    def test_proxy_rejected(self):
        result = _evaluate_result(make_response(is_anonymous_proxy=True), SETTINGS)
        assert result.allowed is False
        assert result.reason == "anonymous_proxy"

    def test_hosting_provider_rejected(self):
        result = _evaluate_result(make_response(is_hosting_provider=True), SETTINGS)
        assert result.allowed is False
        assert result.reason == "hosting_provider"

    def test_public_proxy_rejected(self):
        result = _evaluate_result(make_response(is_public_proxy=True), SETTINGS)
        assert result.allowed is False
        assert result.reason == "public_proxy"

    def test_residential_proxy_rejected(self):
        result = _evaluate_result(make_response(is_residential_proxy=True), SETTINGS)
        assert result.allowed is False
        assert result.reason == "residential_proxy"

    def test_tor_exit_node_rejected(self):
        result = _evaluate_result(make_response(is_tor_exit_node=True), SETTINGS)
        assert result.allowed is False
        assert result.reason == "tor_exit_node"

    def test_ksa_at_exact_threshold_allowed(self):
        result = _evaluate_result(make_response(risk_score=25.0, ip_risk=10.0), SETTINGS)
        assert result.allowed is True

    def test_empty_traits_handled(self):
        data = {
            "risk_score": 5,
            "ip_address": {
                "risk": 2,
                "country": {"iso_code": "SA"},
                "traits": {},
            },
        }
        result = _evaluate_result(data, SETTINGS)
        assert result.allowed is True

    def test_missing_ip_address_handled(self):
        data = {"risk_score": 5}
        result = _evaluate_result(data, SETTINGS)
        assert result.allowed is False
        assert result.reason == "country_not_allowed"
