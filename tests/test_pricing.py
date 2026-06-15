"""Tests for bundle pricing validation."""
from __future__ import annotations

from app.services.products import (
    BUNDLE_PRICES,
    UPSELL_PRICE_SAR,
    validate_bundle_price,
    validate_upsell,
    get_product,
    calculate_expected_total,
)


class TestBundlePrices:
    def test_one_piece_is_199(self):
        assert BUNDLE_PRICES[1] == 199

    def test_two_pieces_is_279(self):
        assert BUNDLE_PRICES[2] == 279

    def test_three_pieces_is_349(self):
        assert BUNDLE_PRICES[3] == 349

    def test_upsell_is_99(self):
        assert UPSELL_PRICE_SAR == 99


class TestValidateBundlePrice:
    def test_valid_1_piece(self):
        assert validate_bundle_price("weight-support-tea", 1, 199) is True

    def test_valid_2_pieces(self):
        assert validate_bundle_price("colon-comfort-tea", 2, 279) is True

    def test_valid_3_pieces(self):
        assert validate_bundle_price("liver-wellness-tea", 3, 349) is True

    def test_tampered_price_rejected(self):
        assert validate_bundle_price("weight-support-tea", 1, 1) is False
        assert validate_bundle_price("weight-support-tea", 2, 199) is False
        assert validate_bundle_price("weight-support-tea", 3, 279) is False

    def test_invalid_quantity_rejected(self):
        assert validate_bundle_price("weight-support-tea", 4, 349) is False
        assert validate_bundle_price("weight-support-tea", 0, 0) is False


class TestUpsellValidation:
    def test_valid_upsell_weight_to_colon(self):
        assert validate_upsell("colon-comfort-tea", ["weight-support-tea"], 99) is True

    def test_valid_upsell_colon_to_liver(self):
        assert validate_upsell("liver-wellness-tea", ["colon-comfort-tea"], 99) is True

    def test_wrong_price_rejected(self):
        assert validate_upsell("colon-comfort-tea", ["weight-support-tea"], 100) is False
        assert validate_upsell("colon-comfort-tea", ["weight-support-tea"], 199) is False

    def test_nonexistent_product_rejected(self):
        assert validate_upsell("fake-tea-xyz", ["weight-support-tea"], 99) is False

    def test_upsell_at_199_rejected(self):
        assert validate_upsell("colon-comfort-tea", ["weight-support-tea"], 199) is False


class TestProductCatalog:
    def test_all_six_products_exist(self):
        ids = [
            "weight-support-tea",
            "colon-comfort-tea",
            "hemorrhoid-comfort-tea",
            "liver-wellness-tea",
            "lung-smoking-support-tea",
            "prostate-wellness-tea",
        ]
        for pid in ids:
            product = get_product(pid)
            assert product is not None, f"Product {pid} not found"
            assert product.name_ar

    def test_product_names_in_arabic(self):
        for product in [
            get_product("weight-support-tea"),
            get_product("colon-comfort-tea"),
        ]:
            assert product is not None
            assert any(
                "\u0600" <= ch <= "\u06ff" for ch in product.name_ar
            ), "Product name should contain Arabic characters"

    def test_unknown_product_returns_none(self):
        assert get_product("fake-product") is None


class TestTotalCalculation:
    def test_single_item_no_upsell(self):
        assert calculate_expected_total(279, 0, 0) == 279

    def test_single_item_with_upsell(self):
        assert calculate_expected_total(279, 99, 0) == 378

    def test_multi_item_with_upsell_and_shipping(self):
        assert calculate_expected_total(279 + 199, 99, 25) == 602


class TestWelcomeFlagDoesNotChangeValidatedPrices:
    def test_old_welcome_discounted_bundle_rejected(self):
        assert validate_bundle_price("weight-support-tea", 1, 179, welcome_discount=True) is False

    def test_catalog_bundle_ok_with_welcome_flag(self):
        assert validate_bundle_price("weight-support-tea", 1, 199, welcome_discount=True) is True

    def test_old_welcome_discounted_upsell_rejected(self):
        assert validate_upsell("colon-comfort-tea", ["weight-support-tea"], 89, welcome_discount=True) is False

    def test_catalog_upsell_ok_with_welcome_flag(self):
        assert validate_upsell("colon-comfort-tea", ["weight-support-tea"], 99, welcome_discount=True) is True
