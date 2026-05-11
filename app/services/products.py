from __future__ import annotations

from dataclasses import dataclass


BUNDLE_PRICES: dict[int, int] = {
    1: 199,
    2: 279,
    3: 349,
}

UPSELL_PRICE_SAR = 99

WELCOME_DISCOUNT_PERCENT = 10


def discounted_amount(amount: int) -> int:
    """Integer SAR after welcome discount (floor)."""
    return max(1, amount * (100 - WELCOME_DISCOUNT_PERCENT) // 100)


UPSELL_MAP: dict[str, str] = {
    "weight-support-tea": "colon-comfort-tea",
    "colon-comfort-tea": "liver-wellness-tea",
    "hemorrhoid-comfort-tea": "colon-comfort-tea",
    "liver-wellness-tea": "weight-support-tea",
    "lung-smoking-support-tea": "liver-wellness-tea",
    "prostate-wellness-tea": "liver-wellness-tea",
}


@dataclass
class ProductInfo:
    product_id: str
    name_ar: str
    sku: str


PRODUCTS: dict[str, ProductInfo] = {
    "weight-support-tea": ProductInfo(
        product_id="weight-support-tea",
        name_ar="شاي عشبي لدعم إدارة الوزن",
        sku="BAYT-WST-001",
    ),
    "colon-comfort-tea": ProductInfo(
        product_id="colon-comfort-tea",
        name_ar="شاي عشبي لراحة القولون والغازات",
        sku="BAYT-CCT-002",
    ),
    "hemorrhoid-comfort-tea": ProductInfo(
        product_id="hemorrhoid-comfort-tea",
        name_ar="شاي عشبي لدعم الراحة مع البواسير",
        sku="BAYT-HCT-003",
    ),
    "liver-wellness-tea": ProductInfo(
        product_id="liver-wellness-tea",
        name_ar="شاي عشبي لدعم صحة الكبد",
        sku="BAYT-LWT-004",
    ),
    "lung-smoking-support-tea": ProductInfo(
        product_id="lung-smoking-support-tea",
        name_ar="شاي عشبي لدعم الرئة وتقليل آثار التدخين",
        sku="BAYT-LST-005",
    ),
    "prostate-wellness-tea": ProductInfo(
        product_id="prostate-wellness-tea",
        name_ar="شاي عشبي لدعم صحة البروستات",
        sku="BAYT-PWT-006",
    ),
}


def get_product(product_id: str) -> ProductInfo | None:
    return PRODUCTS.get(product_id)


def validate_bundle_price(
    product_id: str,
    quantity: int,
    price_sar: int,
    *,
    welcome_discount: bool = False,
) -> bool:
    """Catalog bundle price, or discounted price when welcome promo is active."""
    if quantity not in BUNDLE_PRICES:
        return False
    expected = BUNDLE_PRICES[quantity]
    if price_sar == expected:
        return True
    if welcome_discount and price_sar == discounted_amount(expected):
        return True
    return False


def validate_upsell(
    product_id: str,
    main_product_ids: list[str],
    price_sar: int,
    *,
    welcome_discount: bool = False,
) -> bool:
    allowed = {UPSELL_PRICE_SAR}
    if welcome_discount:
        allowed.add(discounted_amount(UPSELL_PRICE_SAR))
    if price_sar not in allowed:
        return False
    if get_product(product_id) is None:
        return False
    for main_id in main_product_ids:
        if UPSELL_MAP.get(main_id) == product_id:
            return True
    return get_product(product_id) is not None


def calculate_expected_total(items_total: int, upsell_total: int, shipping: int) -> int:
    return items_total + upsell_total + shipping
