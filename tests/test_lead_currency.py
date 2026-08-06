"""Sheet amounts must follow the lead's own country, never the storefront default."""
from __future__ import annotations

import pytest

from app.services.sheets import resolve_lead_currency


class TestResolveLeadCurrency:
    @pytest.mark.parametrize(
        "phone,expected",
        [
            ("+966501234567", "SAR"),
            ("+96891234567", "OMR"),
            ("+971501234567", "AED"),
            ("+97433123456", "QAR"),
            ("+97336123456", "BHD"),
            ("+96550123456", "KWD"),
            ("+9647701234567", "IQD"),
            ("+96170123456", "LBP"),
            ("+218911234567", "LYD"),
        ],
    )
    def test_phone_country_decides(self, phone: str, expected: str):
        # Storefront posts SAR for everyone; the lead's country must win.
        assert resolve_lead_currency(phone, "SAR") == expected

    def test_ip_country_used_when_phone_unrecognized(self):
        assert resolve_lead_currency("+33612345678", "SAR", "OM") == "OMR"

    def test_requested_currency_kept_for_unmapped_country(self):
        assert resolve_lead_currency("+33612345678", "EUR") == "EUR"

    def test_defaults_to_sar_without_any_signal(self):
        assert resolve_lead_currency("", None, None) == "SAR"
