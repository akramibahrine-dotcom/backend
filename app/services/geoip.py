"""
Free IP -> country lookup used as a fallback / always-on country gate.

We rely on this so that phone-country / IP-country enforcement works even
when MaxMind credentials are missing, expired, or rate-limited. MaxMind
remains the primary signal for VPN / proxy / Tor / risk score detection.

Provider: ipapi.co (free tier: 1k req/day, no key needed).
We cache results in-process for 6h to stay well under the free quota.
"""
from __future__ import annotations

import time
from typing import Final

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

_CACHE: dict[str, tuple[str | None, float]] = {}
_CACHE_TTL_S: Final = 6 * 60 * 60  # 6 hours
_TIMEOUT_S: Final = 4.0
_PRIVATE_PREFIXES: Final = (
    "10.", "127.", "169.254.", "192.168.",
    "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.",
    "172.24.", "172.25.", "172.26.", "172.27.",
    "172.28.", "172.29.", "172.30.", "172.31.",
    "0.0.0.0", "::1",
)


def _is_private(ip: str) -> bool:
    return any(ip.startswith(p) for p in _PRIVATE_PREFIXES)


async def lookup_country(ip: str) -> str | None:
    """Return ISO-2 country code for an IP, or None if it cannot be resolved."""
    if not ip or _is_private(ip):
        return None

    now = time.monotonic()
    cached = _CACHE.get(ip)
    if cached and (now - cached[1]) < _CACHE_TTL_S:
        return cached[0]

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.get(f"https://ipapi.co/{ip}/country/")
            if resp.status_code != 200:
                logger.warning(
                    "geoip_lookup_non_200",
                    ip=ip,
                    status=resp.status_code,
                )
                return None
            text = (resp.text or "").strip().upper()
            iso = text if len(text) == 2 and text.isalpha() else None
            _CACHE[ip] = (iso, now)
            return iso
    except Exception as exc:
        logger.warning("geoip_lookup_failed", ip=ip, error=str(exc))
        return None
