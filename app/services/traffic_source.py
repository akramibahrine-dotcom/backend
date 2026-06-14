from __future__ import annotations

from urllib.parse import parse_qs, urlparse


def _parse_url_params(url: str | None) -> dict[str, str]:
    if not url:
        return {}
    try:
        qs = parse_qs(urlparse(url).query)
        return {k: (v[0] if v else "") for k, v in qs.items()}
    except Exception:
        return {}


def _match_source_token(source: str, medium: str) -> str | None:
    source = source.lower().strip()
    medium = medium.lower().strip()

    if any(token in source for token in ("tiktok", "tt_ads", "ttads")) or "tiktok" in medium:
        return "TikTok"
    if any(token in source for token in ("facebook", "fb", "instagram", "ig", "meta")):
        return "Meta"
    if any(token in source for token in ("snapchat", "snap")):
        return "Snapchat"
    if any(token in source for token in ("google", "gclid", "youtube")):
        return "Google"
    return None


def derive_traffic_platform(
    *,
    utm_source: str | None = None,
    utm_medium: str | None = None,
    landing_page_url: str | None = None,
    page_url: str | None = None,
    ttclid: str | None = None,
    fbc: str | None = None,
    sc_click_id: str | None = None,
) -> str:
    """Map UTMs / click IDs / landing URL to a readable ad platform label."""
    matched = _match_source_token(utm_source or "", utm_medium or "")
    if matched:
        return matched

    if ttclid:
        return "TikTok"
    if fbc:
        return "Meta"
    if sc_click_id:
        return "Snapchat"

    for url in (landing_page_url, page_url):
        params = _parse_url_params(url)
        if params.get("ttclid"):
            return "TikTok"
        if params.get("fbclid") or params.get("fbc"):
            return "Meta"
        if params.get("ScCid") or params.get("sc_cid") or params.get("sccid"):
            return "Snapchat"
        if params.get("gclid"):
            return "Google"

        url_match = _match_source_token(
            params.get("utm_source", ""),
            params.get("utm_medium", ""),
        )
        if url_match:
            return url_match

    if utm_source and utm_source.strip():
        return utm_source.strip().title()

    return "Direct"


def platform_to_utm_source(platform: str) -> str:
    """Normalize platform label for the utm_source sheet column."""
    mapping = {
        "TikTok": "tiktok",
        "Meta": "facebook",
        "Snapchat": "snapchat",
        "Google": "google",
        "Direct": "direct",
    }
    return mapping.get(platform, platform.lower())
