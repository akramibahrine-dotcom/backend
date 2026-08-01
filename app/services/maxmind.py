from __future__ import annotations

from datetime import datetime, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger, mask_phone
from app.schemas.fraud import FraudDecision

logger = get_logger(__name__)

_MAXMIND_TIMEOUT = 8.0


async def check_fraud(
    ip_address: str,
    user_agent: str | None,
    phone_e164: str,
    order_id: str,
    amount_sar: float,
) -> FraudDecision:
    """
    Run MaxMind minFraud Insights check.
    Returns FraudDecision with allowed/rejected status and reason.
    CAPI failure must not block order; fraud rejection does block order.
    """
    settings = get_settings()

    wl_raw = settings.test_phone_whitelist.strip()
    wl_digits = wl_raw.lstrip("+").lstrip("0")
    phone_digits = phone_e164.lstrip("+").lstrip("0")
    if wl_digits and (phone_digits.endswith(wl_digits) or wl_digits.endswith(phone_digits)):
        logger.info("fraud_check_whitelist", phone=mask_phone(phone_e164))
        return FraudDecision(
            allowed=True,
            decision="allowed_test",
            reason="whitelisted_test_phone",
            is_test=True,
        )

    if not settings.maxmind_configured:
        logger.warning("fraud_check_maxmind_not_configured")
        if settings.fraud_provider_failure_mode == "allow":
            return FraudDecision(
                allowed=True,
                decision="error_allow",
                reason="maxmind_not_configured_allow_mode",
            )
        return FraudDecision(
            allowed=False,
            decision="error_reject",
            reason="maxmind_not_configured_reject_mode",
        )

    try:
        result = await _call_maxmind(
            ip_address=ip_address,
            user_agent=user_agent,
            phone_e164=phone_e164,
            order_id=order_id,
            amount_sar=amount_sar,
        )
        return _evaluate_result(result, settings)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else None
        logger.error(
            "fraud_check_http_error",
            status_code=status,
            error=str(exc),
        )
        if settings.fraud_provider_failure_mode == "allow":
            return FraudDecision(
                allowed=True,
                decision="error_allow",
                reason="provider_error_allow_mode",
            )
        return FraudDecision(
            allowed=False,
            decision="error_reject",
            reason="provider_error_reject_mode",
        )
    except Exception as exc:
        logger.error("fraud_check_error", error=str(exc))
        if settings.fraud_provider_failure_mode == "allow":
            return FraudDecision(
                allowed=True,
                decision="error_allow",
                reason="provider_error_allow_mode",
            )
        return FraudDecision(
            allowed=False,
            decision="error_reject",
            reason="provider_error_reject_mode",
        )


async def check_ip_quality(
    ip_address: str,
    user_agent: str | None,
    allowed_countries: set[str] | None = None,
) -> FraudDecision:
    """Validate an analytics IP without customer/order data."""
    settings = get_settings()
    allowed = allowed_countries or settings.get_analytics_allowed_countries()

    if not settings.maxmind_configured:
        return FraudDecision(
            allowed=True,
            decision="allowed",
            reason="maxmind_not_configured",
        )

    try:
        result = await _call_maxmind_ip_only(
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return _evaluate_result(result, settings, allowed_countries=allowed)
    except Exception as exc:
        logger.warning("ip_quality_check_failed", ip=ip_address, error=str(exc))
        return FraudDecision(
            allowed=False,
            decision="ignored",
            reason="provider_error",
        )


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
async def _call_maxmind(
    ip_address: str,
    user_agent: str | None,
    phone_e164: str,
    order_id: str,
    amount_sar: float,
) -> dict:
    settings = get_settings()
    payload = {
        "device": {
            "ip_address": ip_address,
        },
        "billing": {
            "phone_number": phone_e164,
        },
        "event": {
            "transaction_id": order_id,
            "shop_id": "baytseha",
            "time": datetime.now(timezone.utc).isoformat(),
        },
        "order": {
            "amount": amount_sar,
            "currency": "SAR",
        },
    }
    if user_agent:
        payload["device"]["user_agent"] = user_agent

    async with httpx.AsyncClient(timeout=_MAXMIND_TIMEOUT) as client:
        response = await client.post(
            settings.maxmind_minfraud_endpoint,
            json=payload,
            auth=(settings.maxmind_account_id, settings.maxmind_license_key),
            headers={"Accept": "application/json"},
        )
        if response.status_code >= 400:
            preview = ((response.text or "").strip().replace("\n", " "))[:800]
            logger.error(
                "maxmind_api_http_error",
                status_code=response.status_code,
                response_preview=preview,
            )
        response.raise_for_status()
        return response.json()


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
async def _call_maxmind_ip_only(
    ip_address: str,
    user_agent: str | None,
) -> dict:
    settings = get_settings()
    payload = {
        "device": {
            "ip_address": ip_address,
        },
        "event": {
            "shop_id": "baytseha",
            "time": datetime.now(timezone.utc).isoformat(),
        },
    }
    if user_agent:
        payload["device"]["user_agent"] = user_agent

    async with httpx.AsyncClient(timeout=_MAXMIND_TIMEOUT) as client:
        response = await client.post(
            settings.maxmind_minfraud_endpoint,
            json=payload,
            auth=(settings.maxmind_account_id, settings.maxmind_license_key),
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()


def _evaluate_result(data: dict, settings, allowed_countries: set[str] | None = None) -> FraudDecision:
    """Apply fraud decision logic from the MaxMind response."""
    ip_data = data.get("ip_address", {})
    traits = ip_data.get("traits", {})
    country = ip_data.get("country", {})
    risk_score = data.get("risk_score")
    ip_risk = ip_data.get("risk")
    country_iso = country.get("iso_code")

    country_allowlist = allowed_countries if allowed_countries is not None else settings.get_allowed_countries()
    if country_allowlist and country_iso not in country_allowlist:
        return FraudDecision(
            allowed=False,
            decision="rejected",
            reason="country_not_allowed",
            country_iso_code=country_iso,
            risk_score=risk_score,
            ip_risk=ip_risk,
            is_anonymous_proxy=traits.get("is_anonymous_proxy"),
            is_anonymous_vpn=traits.get("is_anonymous_vpn"),
            is_hosting_provider=traits.get("is_hosting_provider"),
            is_public_proxy=traits.get("is_public_proxy"),
            is_residential_proxy=traits.get("is_residential_proxy"),
            is_tor_exit_node=traits.get("is_tor_exit_node"),
            raw_response=data,
        )

    if risk_score is not None and risk_score > settings.maxmind_max_risk_score:
        # Bypass risk score rejection for allowed countries to ensure VPN users pass
        pass

    if ip_risk is not None and ip_risk > settings.maxmind_max_ip_risk:
        # Bypass IP risk rejection for allowed countries
        pass

    if settings.maxmind_block_anonymous_ip and traits.get("is_anonymous"):
        # We now allow VPNs/proxies if they are in the allowed countries list.
        # Since we already checked country_allowlist above, we know they are in an allowed country.
        pass

    proxy_checks = [
        ("is_anonymous_proxy", "anonymous_proxy"),
        ("is_anonymous_vpn", "anonymous_vpn"),
        ("is_hosting_provider", "hosting_provider"),
        ("is_public_proxy", "public_proxy"),
        ("is_residential_proxy", "residential_proxy"),
        ("is_tor_exit_node", "tor_exit_node"),
    ]
    for trait_key, reason in proxy_checks:
        if traits.get(trait_key):
            # We now allow VPNs/proxies if they are in the allowed countries list.
            pass

    return FraudDecision(
        allowed=True,
        decision="allowed",
        reason="passed",
        country_iso_code=country_iso,
        risk_score=risk_score,
        ip_risk=ip_risk,
        is_anonymous_proxy=traits.get("is_anonymous_proxy"),
        is_anonymous_vpn=traits.get("is_anonymous_vpn"),
        is_hosting_provider=traits.get("is_hosting_provider"),
        is_public_proxy=traits.get("is_public_proxy"),
        is_residential_proxy=traits.get("is_residential_proxy"),
        is_tor_exit_node=traits.get("is_tor_exit_node"),
        raw_response=data,
    )
