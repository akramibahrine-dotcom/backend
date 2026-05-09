from __future__ import annotations

from dataclasses import dataclass


BUNDLE_PRICES: dict[int, int] = {
    1: 199,
    2: 279,
    3: 349,
}

UPSELL_PRICE_SAR = 99

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


PRODUCTS: dict[str, ProductInfo] = {
    "weight-support-tea": ProductInfo(
        product_id="weight-support-tea",
        name_ar="شاي عشبي لدعم إدارة الوزن",
    ),
    "colon-comfort-tea": ProductInfo(
        product_id="colon-comfort-tea",
        name_ar="شاي عشبي لراحة القولون والغازات",
    ),
    "hemorrhoid-comfort-tea": ProductInfo(
        product_id="hemorrhoid-comfort-tea",
        name_ar="شاي عشبي لدعم الراحة مع البواسير",
    ),
    "liver-wellness-tea": ProductInfo(
        product_id="liver-wellness-tea",
        name_ar="شاي عشبي لدعم صحة الكبد",
    ),
    "lung-smoking-support-tea": ProductInfo(
        product_id="lung-smoking-support-tea",
        name_ar="شاي عشبي لدعم الرئة وتقليل آثار التدخين",
    ),
    "prostate-wellness-tea": ProductInfo(
        product_id="prostate-wellness-tea",
        name_ar="شاي عشبي لدعم صحة البروستات",
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
    """Validates catalog bundle SAR. welcome_discount is unused (API compat)."""
    _ = product_id
    _ = welcome_discount
    if quantity not in BUNDLE_PRICES:
        return False
    return price_sar == BUNDLE_PRICES[quantity]


def validate_upsell(
    product_id: str,
    main_product_ids: list[str],
    price_sar: int,
    *,
    welcome_discount: bool = False,
) -> bool:
    _ = welcome_discount
    if price_sar != UPSELL_PRICE_SAR:
        return False
    if get_product(product_id) is None:
        return False
    for main_id in main_product_ids:
        if UPSELL_MAP.get(main_id) == product_id:
            return True
    return False


def calculate_expected_total(items_total: int, upsell_total: int, shipping: int) -> int:
    return items_total + upsell_total + shipping
