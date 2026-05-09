"""Tests for KSA phone normalization and security utilities."""
from __future__ import annotations

import pytest

from app.core.security import (
    hash_phone_meta,
    hash_phone_snapchat,
    hash_phone_tiktok,
    normalize_ksa_phone,
)


class TestNormalizeKsaPhone:
    def test_local_format_05(self):
        result = normalize_ksa_phone("0501234567")
        assert result is not None
        e164, digits, local = result
        assert e164 == "+966501234567"
        assert digits == "966501234567"
        assert local == "0501234567"

    def test_format_5xx(self):
        result = normalize_ksa_phone("501234567")
        assert result is not None
        e164, digits, local = result
        assert e164 == "+966501234567"

    def test_format_966(self):
        result = normalize_ksa_phone("966501234567")
        assert result is not None
        e164, digits, local = result
        assert e164 == "+966501234567"

    def test_format_plus966(self):
        result = normalize_ksa_phone("+966501234567")
        assert result is not None
        e164, digits, local = result
        assert e164 == "+966501234567"

    def test_format_00966(self):
        result = normalize_ksa_phone("00966501234567")
        assert result is not None
        e164, _, _ = result
        assert e164 == "+966501234567"

    def test_invalid_non_ksa(self):
        assert normalize_ksa_phone("+12125551234") is None

    def test_invalid_short(self):
        assert normalize_ksa_phone("0501") is None

    def test_invalid_landline(self):
        assert normalize_ksa_phone("0112345678") is None

    def test_whitespace_stripped(self):
        result = normalize_ksa_phone("0501 234 567")
        assert result is not None
        e164, _, _ = result
        assert e164 == "+966501234567"

    def test_whitelist_phone_unchanged(self):
        # Whitelist phone bypasses normalization in the service layer
        result = normalize_ksa_phone("055000000")
        assert result is None  # Not a valid full KSA mobile - handled by whitelist logic


class TestPhoneHashing:
    def test_meta_hash_is_lowercase_hex(self):
        h = hash_phone_meta("+966501234567")
        assert h == h.lower()
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_meta_strips_plus(self):
        h1 = hash_phone_meta("+966501234567")
        # Meta hashes digits only: 966501234567
        import hashlib
        expected = hashlib.sha256("966501234567".encode()).hexdigest()
        assert h1 == expected

    def test_tiktok_includes_plus(self):
        h = hash_phone_tiktok("+966501234567")
        import hashlib
        expected = hashlib.sha256("+966501234567".encode()).hexdigest()
        assert h == expected

    def test_snapchat_strips_plus(self):
        h = hash_phone_snapchat("+966501234567")
        import hashlib
        expected = hashlib.sha256("966501234567".encode()).hexdigest()
        assert h == expected

    def test_no_raw_phone_in_hash(self):
        """Hash outputs should not contain the raw phone number."""
        phone = "+966501234567"
        for fn in [hash_phone_meta, hash_phone_tiktok, hash_phone_snapchat]:
            h = fn(phone)
            assert phone not in h
            assert "966501234567" not in h

    def test_meta_tiktok_snap_differ(self):
        """Platforms use different normalization, so hashes should differ."""
        phone = "+966501234567"
        h_meta = hash_phone_meta(phone)
        h_tiktok = hash_phone_tiktok(phone)
        assert h_meta != h_tiktok
