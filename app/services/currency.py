from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_rates_cache: dict[str, Any] = {}
_cache_timestamp: float = 0
_CACHE_TTL = 6 * 3600  # 6 hours

FALLBACK_RATES: dict[str, float] = {
    "SAR": 1.0,
    "USD": 0.267,
    "EUR": 0.245,
    "GBP": 0.210,
    "AED": 0.980,
    "KWD": 0.082,
    "BHD": 0.100,
    "OMR": 0.103,
    "QAR": 0.972,
    "EGP": 13.1,
    "JOD": 0.189,
    "LBP": 4763.0,
    "MAD": 2.67,
    "TND": 0.830,
    "TRY": 8.70,
    "PKR": 74.5,
    "INR": 22.3,
    "CAD": 0.363,
    "AUD": 0.411,
    "JPY": 40.0,
    "CNY": 1.93,
    "IQD": 349.5,
    "SDG": 160.0,
    "LYD": 1.29,
    "YER": 66.7,
    "SYP": 3467.0,
    "DZD": 35.9,
    "MYR": 1.19,
    "IDR": 4200.0,
    "NGN": 413.0,
}


async def get_exchange_rates() -> dict[str, float]:
    """
    Returns SAR-based exchange rates dict.
    Cached for 6 hours. Falls back to static rates on failure.
    """
    global _rates_cache, _cache_timestamp

    now = time.time()
    if _rates_cache and (now - _cache_timestamp) < _CACHE_TTL:
        return _rates_cache

    settings = get_settings()

    if not settings.currency_api_url:
        return FALLBACK_RATES.copy()

    try:
        rates = await _fetch_rates(settings.currency_api_url, settings.currency_api_key)
        _rates_cache = rates
        _cache_timestamp = now
        return rates
    except Exception as exc:
        logger.warning("currency_fetch_failed", error=str(exc))
        return _rates_cache if _rates_cache else FALLBACK_RATES.copy()


async def _fetch_rates(api_url: str, api_key: str) -> dict[str, float]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        params: dict[str, str] = {"base": "SAR"}
        if api_key:
            params["apikey"] = api_key
        response = await client.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("rates", data)
