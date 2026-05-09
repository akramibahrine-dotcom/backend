"""Tests for CAPI payload builders and phone hashing."""
from __future__ import annotations

import pytest

from app.core.security import hash_phone_meta, hash_phone_tiktok, hash_phone_snapchat


class TestCAPIPhoneHashing:
    """Verify hashing rules per platform per docs/09-tracking-pixels-capi.md."""

    def test_meta_hash_excludes_plus(self):
        """Meta normalizes digits including country code, no symbols."""
        import hashlib
        phone = "+966501234567"
        expected = hashlib.sha256("966501234567".encode()).hexdigest()
        assert hash_phone_meta(phone) == expected

    def test_tiktok_hash_includes_plus(self):
        """TikTok hashes E.164 with + prefix."""
        import hashlib
        phone = "+966501234567"
        expected = hashlib.sha256("+966501234567".encode()).hexdigest()
        assert hash_phone_tiktok(phone) == expected

    def test_snapchat_hash_digits_only_with_country(self):
        """Snapchat: digits only with country code, no + symbol."""
        import hashlib
        phone = "+966501234567"
        expected = hashlib.sha256("966501234567".encode()).hexdigest()
        assert hash_phone_snapchat(phone) == expected

    def test_all_hashes_are_64_chars(self):
        phone = "+966501234567"
        for fn in [hash_phone_meta, hash_phone_tiktok, hash_phone_snapchat]:
            assert len(fn(phone)) == 64

    def test_all_hashes_are_lowercase_hex(self):
        phone = "+966501234567"
        for fn in [hash_phone_meta, hash_phone_tiktok, hash_phone_snapchat]:
            h = fn(phone)
            assert h == h.lower()
            assert all(c in "0123456789abcdef" for c in h)

    def test_raw_phone_not_in_hash(self):
        """Hashed output must never contain raw phone digits."""
        phone = "+966501234567"
        for fn in [hash_phone_meta, hash_phone_tiktok, hash_phone_snapchat]:
            h = fn(phone)
            assert "501234567" not in h
            assert "966501234567" not in h
