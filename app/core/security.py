from __future__ import annotations

import hashlib
import re


KSA_MOBILE_PATTERN = re.compile(
    r"^(?:\+966|00966|966|0)?5[0-9]{8}$"
)


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
