from __future__ import annotations

from dataclasses import dataclass

BUNDLE_PRICES: dict[int, int] = {
    1: 199,
    2: 279,
    3: 349,
}

PRODUCT_BUNDLE_PRICES: dict[str, dict[int, int]] = {
    "fertility-tea": {1: 229, 2: 349, 3: 449},
    "scar-gel": {1: 179, 3: 199, 5: 249},
    "eelhoe-fresh-breath": {1: 129, 2: 199, 3: 249},
    # BOGO totals: 1+1 free → 2 boxes, 2+2 → 4, 3+3 → 6
    "c60-fullerene-serum": {2: 199, 4: 279, 6: 349},
}

# Fixed display prices per currency (not FX conversion) — qty → currency → amount
PRODUCT_PRICE_OVERRIDES: dict[str, dict[int, dict[str, float]]] = {
    "c60-fullerene-serum": {
        2: {"OMR": 21},
        4: {"OMR": 29},
        6: {"OMR": 39},
    },
}

UPSELL_PRICE_SAR = 99

WELCOME_DISCOUNT_PERCENT = 10


def discounted_amount(amount: int) -> int:
    """Integer SAR after welcome discount (floor)."""
    return max(1, amount * (100 - WELCOME_DISCOUNT_PERCENT) // 100)


UPSELL_MAP: dict[str, str] = {
    "weight-support-tea": "colon-comfort-tea",
    "bloom-coffee": "weight-support-tea",
    "colon-comfort-tea": "liver-wellness-tea",
    "hemorrhoid-comfort-tea": "colon-comfort-tea",
    "liver-wellness-tea": "weight-support-tea",
    "lung-smoking-support-tea": "liver-wellness-tea",
    "prostate-wellness-tea": "liver-wellness-tea",
    "fertility-tea": "axis-y-serum",
    "axis-y-serum": "weight-support-tea",
    "scar-gel": "axis-y-serum",
    "eelhoe-fresh-breath": "axis-y-serum",
    "c60-fullerene-serum": "axis-y-serum",
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
    "bloom-coffee": ProductInfo(
        product_id="bloom-coffee",
        name_ar="قهوة بلوم لفقدان الوزن وصحة الجهاز الهضمي",
        sku="BAYT-BLM-001",
        slug="bloom-coffee",
        concern_ar="فقدان الوزن وصحة الجهاز الهضمي",
        upsell_product_id="weight-support-tea",
        cross_sell_product_ids=("weight-support-tea", "colon-comfort-tea"),
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
        name_ar="شاي الخصوبة الجنسية من بيت الصحه",
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
    "scar-gel": ProductInfo(
        product_id="scar-gel",
        name_ar="جل السيليكون الأمريكي لعلاج الندوب والحروق",
        sku="CopAkramGeL!",
        slug="scar-gel",
        concern_ar="علاج الندوب والحروق وآثار العمليات",
        upsell_product_id="axis-y-serum",
        cross_sell_product_ids=("axis-y-serum", "fertility-tea"),
    ),
    "eelhoe-fresh-breath": ProductInfo(
        product_id="eelhoe-fresh-breath",
        name_ar="إكسير EELHOE لعلاج رائحة الفم الكريهة",
        sku="BAYT-EEL-001",
        slug="eelhoe-fresh-breath",
        concern_ar="علاج رائحة الفم الكريهة",
        upsell_product_id="axis-y-serum",
        cross_sell_product_ids=("axis-y-serum", "scar-gel"),
    ),
    "c60-fullerene-serum": ProductInfo(
        product_id="c60-fullerene-serum",
        name_ar="كبسولات سيروم فوليرين C60 متعددة المفعول",
        sku="CopaffFullereneSerum",
        slug="c60-fullerene-serum",
        concern_ar="تجديد البشرة ومكافحة التجاعيد والبقع الداكنة",
        upsell_product_id="axis-y-serum",
        cross_sell_product_ids=("axis-y-serum", "scar-gel"),
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


def get_display_line_price(
    product_id: str,
    quantity: int,
    price_sar: int | float,
    currency: str,
    rates: dict[str, float],
) -> float:
    """Per-line price in customer currency (override first, else convert SAR)."""
    from app.services.currency import convert_sar_to

    override = PRODUCT_PRICE_OVERRIDES.get(product_id, {}).get(quantity, {}).get(currency)
    if override is not None:
        return float(override)
    return convert_sar_to(price_sar, currency, rates)


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
