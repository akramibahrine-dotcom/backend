from __future__ import annotations

from dataclasses import dataclass

BUNDLE_PRICES: dict[int, int] = {
    1: 199,
    2: 279,
    3: 349,
}

PRODUCT_BUNDLE_PRICES: dict[str, dict[int, int]] = {
    "fertility-tea": {1: 299, 2: 549, 3: 699},
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
    "fertility-tea": "axis-y-serum",
    "axis-y-serum": "weight-support-tea",
}


@dataclass
class ProductInfo:
    product_id: str
    name_ar: str
    sku: str
    slug: str
    concern_ar: str
    upsell_product_id: str
    cross_sell_product_ids: tuple[str, ...]


PRODUCTS: dict[str, ProductInfo] = {
    "weight-support-tea": ProductInfo(
        product_id="weight-support-tea",
        name_ar="شاي عشبي لدعم إدارة الوزن",
        sku="BAYT-WST-001",
        slug="weight-support-tea",
        concern_ar="مرافقة إدارة الوزن",
        upsell_product_id="colon-comfort-tea",
        cross_sell_product_ids=("colon-comfort-tea", "liver-wellness-tea"),
    ),
    "colon-comfort-tea": ProductInfo(
        product_id="colon-comfort-tea",
        name_ar="شاي عشبي لراحة القولون والغازات",
        sku="BAYT-CCT-002",
        slug="colon-comfort-tea",
        concern_ar="راحة القولون والغازات",
        upsell_product_id="liver-wellness-tea",
        cross_sell_product_ids=("weight-support-tea", "hemorrhoid-comfort-tea"),
    ),
    "hemorrhoid-comfort-tea": ProductInfo(
        product_id="hemorrhoid-comfort-tea",
        name_ar="شاي عشبي لدعم الراحة مع البواسير",
        sku="BAYT-HCT-003",
        slug="hemorrhoid-comfort-tea",
        concern_ar="راحة يومية مع البواسير",
        upsell_product_id="colon-comfort-tea",
        cross_sell_product_ids=("colon-comfort-tea", "liver-wellness-tea"),
    ),
    "liver-wellness-tea": ProductInfo(
        product_id="liver-wellness-tea",
        name_ar="شاي عشبي لدعم صحة الكبد",
        sku="BAYT-LWT-004",
        slug="liver-wellness-tea",
        concern_ar="مرافقة عافية الكبد",
        upsell_product_id="weight-support-tea",
        cross_sell_product_ids=("weight-support-tea", "colon-comfort-tea"),
    ),
    "lung-smoking-support-tea": ProductInfo(
        product_id="lung-smoking-support-tea",
        name_ar="شاي عشبي لدعم الرئة وتقليل آثار التدخين",
        sku="BAYT-LST-005",
        slug="lung-smoking-support-tea",
        concern_ar="مرافقة الصدر وآثار التدخين",
        upsell_product_id="liver-wellness-tea",
        cross_sell_product_ids=("liver-wellness-tea", "colon-comfort-tea"),
    ),
    "prostate-wellness-tea": ProductInfo(
        product_id="prostate-wellness-tea",
        name_ar="شاي عشبي لدعم صحة البروستات",
        sku="BAYT-PWT-006",
        slug="prostate-wellness-tea",
        concern_ar="مرافقة عافية البروستات",
        upsell_product_id="liver-wellness-tea",
        cross_sell_product_ids=("liver-wellness-tea", "lung-smoking-support-tea"),
    ),
    "fertility-tea": ProductInfo(
        product_id="fertility-tea",
        name_ar="شاي Fertility لمرافقة صحة الأنثى",
        sku="BAYT-FTT-007",
        slug="fertility-tea",
        concern_ar="دعم صحة الأنثى والخصوبة",
        upsell_product_id="axis-y-serum",
        cross_sell_product_ids=("axis-y-serum", "weight-support-tea"),
    ),
    "axis-y-serum": ProductInfo(
        product_id="axis-y-serum",
        name_ar="سيروم اكسس واي لتصحيح البقع",
        sku="BAYT-SKN-001",
        slug="axis-y-serum",
        concern_ar="توحيد لون البشرة وتصحيح البقع",
        upsell_product_id="weight-support-tea",
        cross_sell_product_ids=("colon-comfort-tea",),
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
    """Validate server-authoritative catalog bundle price."""
    prices = PRODUCT_BUNDLE_PRICES.get(product_id, BUNDLE_PRICES)
    if quantity not in prices:
        return False
    expected = prices[quantity]
    return price_sar == expected


def validate_upsell(
    product_id: str,
    main_product_ids: list[str],
    price_sar: int,
    *,
    welcome_discount: bool = False,
) -> bool:
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
