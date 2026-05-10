from __future__ import annotations

import hashlib
import re


KSA_MOBILE_PATTERN = re.compile(
    r"^(?:\+966|00966|966|0)?5[0-9]{8}$"
)

COUNTRY_PHONE_PATTERNS: list[tuple[str, re.Pattern, str]] = [
    ("966", re.compile(r"^(?:\+966|00966|966|0)?5[0-9]{8}$"), "SA"),
    ("971", re.compile(r"^(?:\+971|00971|971|0)?5[0-9]{8}$"), "AE"),
    ("974", re.compile(r"^(?:\+974|00974|974)?[0-9]{8}$"), "QA"),
    ("973", re.compile(r"^(?:\+973|00973|973)?[0-9]{8}$"), "BH"),
    ("968", re.compile(r"^(?:\+968|00968|968)?[0-9]{8}$"), "OM"),
    ("965", re.compile(r"^(?:\+965|00965|965)?[0-9]{8}$"), "KW"),
    ("964", re.compile(r"^(?:\+964|00964|964|0)?7[0-9]{9}$"), "IQ"),
    ("961", re.compile(r"^(?:\+961|00961|961|0)?[0-9]{7,8}$"), "LB"),
    ("218", re.compile(r"^(?:\+218|00218|218|0)?9[0-9]{8}$"), "LY"),
]

PHONE_CC_TO_ISO = {cc: iso for cc, _, iso in COUNTRY_PHONE_PATTERNS}

_STRIP_PREFIXES = [
    ("+966", 4), ("00966", 5), ("966", 3),
    ("+971", 4), ("00971", 5), ("971", 3),
    ("+974", 4), ("00974", 5), ("974", 3),
    ("+973", 4), ("00973", 5), ("973", 3),
    ("+968", 4), ("00968", 5), ("968", 3),
    ("+965", 4), ("00965", 5), ("965", 3),
    ("+964", 4), ("00964", 5), ("964", 3),
    ("+961", 4), ("00961", 5), ("961", 3),
    ("+218", 4), ("00218", 5), ("218", 3),
]


def normalize_ksa_phone(raw: str) -> tuple[str, str, str] | None:
    """
    Normalize a KSA mobile number to three formats.

    Returns (e164, digits_no_plus, local) or None if invalid.
    e164:         +9665XXXXXXXX
    digits_no_plus: 9665XXXXXXXX
    local:        05XXXXXXXX
    """
    cleaned = re.sub(r"[\s\-\(\).]", "", raw)

    if not KSA_MOBILE_PATTERN.match(cleaned):
        return None

    if cleaned.startswith("+966"):
        local_digits = cleaned[4:]
    elif cleaned.startswith("00966"):
        local_digits = cleaned[5:]
    elif cleaned.startswith("966"):
        local_digits = cleaned[3:]
    elif cleaned.startswith("0"):
        local_digits = cleaned[1:]
    else:
        local_digits = cleaned

    if not re.match(r"^5[0-9]{8}$", local_digits):
        return None

    e164 = f"+966{local_digits}"
    digits_no_plus = f"966{local_digits}"
    local = f"0{local_digits}"

    return e164, digits_no_plus, local


def normalize_phone(raw: str) -> tuple[str, str, str, str] | None:
    """
    Validate and normalize a phone from any allowed Arab country.

    Returns (e164, digits_no_plus, display, iso_country_code) or None.
    Tries KSA first (most common), then other countries.
    """
    cleaned = re.sub(r"[\s\-\(\).]", "", raw)

    for country_code, pattern, iso in COUNTRY_PHONE_PATTERNS:
        if not pattern.match(cleaned):
            continue

        for prefix, length in _STRIP_PREFIXES:
            if cleaned.startswith(prefix) and prefix.lstrip("+0").startswith(country_code):
                local_digits = cleaned[length:]
                break
        else:
            local_digits = cleaned.lstrip("0")

        e164 = f"+{country_code}{local_digits}"
        digits_no_plus = f"{country_code}{local_digits}"
        display = f"0{local_digits}" if country_code == "966" else e164
        return e164, digits_no_plus, display, iso

    return None


def hash_sha256(value: str) -> str:
    """Return lowercase SHA-256 hex of a string."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_phone_meta(phone_e164: str) -> str:
    """
    Hash phone for Meta CAPI.
    Normalize: digits including country code, no symbols.
    Input: +9665XXXXXXXX -> 9665XXXXXXXX -> SHA-256
    """
    digits = re.sub(r"[^\d]", "", phone_e164)
    return hash_sha256(digits)


def hash_phone_tiktok(phone_e164: str) -> str:
    """
    Hash phone for TikTok Events API.
    Use E.164 with + prefix before SHA-256.
    Input: +9665XXXXXXXX -> SHA-256(+9665XXXXXXXX)
    """
    return hash_sha256(phone_e164)


def hash_phone_snapchat(phone_e164: str) -> str:
    """
    Hash phone for Snapchat CAPI.
    Normalize: include country code, remove leading double zero,
    remove leading national zero, remove non-numeric including +.
    Input: +9665XXXXXXXX -> 9665XXXXXXXX -> SHA-256
    """
    digits = re.sub(r"[^\d]", "", phone_e164)
    return hash_sha256(digits)
