"""Canonical product definitions — generated from brand × weight matrices."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class CanonicalProduct:
    """A product we want to compare across dealers."""

    name: str
    metal: str
    weight: str
    patterns: list[re.Pattern] = field(default_factory=list)
    exclude_patterns: list[re.Pattern] = field(default_factory=list)
    min_price: Decimal = Decimal("0")

    def matches(self, product_name: str) -> bool:
        if any(p.search(product_name) for p in self.exclude_patterns):
            return False
        return any(p.search(product_name) for p in self.patterns)


def _compile(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


# --- Brand aliases ---

GOLD_BRAND_ALIASES: dict[str, list[str]] = {
    "PAMP": ["pamp", "pamp suisse"],
    "Perth Mint": ["perth mint", "perth"],
    "Argor-Heraeus": [r"argor.heraeus", "argor heraeus"],
    "Valcambi": ["valcambi"],
}

SILVER_BRAND_ALIASES: dict[str, list[str]] = {
    "Heraeus": ["heraeus"],
    "Perth Mint": ["perth mint", "perth"],
    "Nadir": ["nadir"],
    "PAMP": ["pamp", "pamp suisse"],
}

# --- Weight aliases ---

WEIGHT_ALIASES: dict[str, list[str]] = {
    "1g": [r"(?<!\d)1\s*g(?:ram)?(?:\b|$)", r"(?<!\d)1\s*gm\b"],
    "5g": [r"(?<!\d)5\s*g(?:ram)?(?:\b|$)", r"(?<!\d)5\s*gm\b"],
    "10g": [r"(?<!\d)10\s*g(?:ram)?(?:\b|$)", r"(?<!\d)10\s*gm\b"],
    "20g": [r"(?<!\d)20\s*g(?:ram)?(?:\b|$)", r"(?<!\d)20\s*gm\b"],
    "50g": [r"(?<!\d)50\s*g(?:ram)?(?:\b|$)", r"(?<!\d)50\s*gm\b"],
    "100g": [r"(?<!\d)100\s*g(?:ram|m)?(?:\b|$)"],
    "250g": [r"(?<!\d)250\s*g(?:ram|m)?(?:\b|$)"],
    "500g": [r"(?<!\d)500\s*g(?:ram|m)?(?:\b|$)"],
    "1oz": [r"(?<!\d)1\s*(?:troy\s*)?oz(?!\s*\))", r"(?<!\d)1oz\b"],
    "10oz": [r"(?<!\d)10\s*(?:troy\s*)?oz", r"(?<!\d)10oz\b"],
    "1kg": [r"(?<!\d)1\s*kg\b", r"(?<!\d)1\s*kilo\b", r"(?<!\d)1000\s*g(?:ram)?"],
}

# --- Min prices (SGD) to filter false matches ---

GOLD_MIN_PRICES: dict[str, Decimal] = {
    "1g": Decimal("150"),
    "5g": Decimal("750"),
    "10g": Decimal("1500"),
    "20g": Decimal("3000"),
    "1oz": Decimal("4500"),
    "50g": Decimal("7500"),
    "100g": Decimal("15000"),
}

SILVER_MIN_PRICES: dict[str, Decimal] = {
    "1oz": Decimal("50"),
    "10oz": Decimal("500"),
    "100g": Decimal("150"),
    "250g": Decimal("400"),
    "500g": Decimal("800"),
    "1kg": Decimal("1500"),
}

# --- Exclude patterns ---

GOLD_EXCLUDES = _compile([r"\bsilver\b", r"\bplatinum\b", r"\bpalladium\b"])
SILVER_EXCLUDES = _compile([r"\bgold\b", r"\bplatinum\b", r"\bpalladium\b"])


# --- Product generation ---

def _build_brand_patterns(brand_aliases: list[str], weight_aliases: list[str]) -> list[str]:
    """Generate regex patterns for brand × weight in both orderings."""
    patterns = []
    for brand in brand_aliases:
        for weight in weight_aliases:
            patterns.append(f"{brand}.*{weight}")
            patterns.append(f"{weight}.*{brand}")
    return patterns


def _build_generic_patterns(metal: str, weight_aliases: list[str]) -> list[str]:
    """Generate regex patterns for any-brand metal bar of a given weight."""
    patterns = []
    for weight in weight_aliases:
        patterns.append(f"{metal}.*(?:bar|cast|minted).*{weight}")
        patterns.append(f"{weight}.*{metal}.*(?:bar|cast|minted)")
        patterns.append(f"{metal}.*{weight}")
        patterns.append(f"{weight}.*{metal}")
    return patterns


def _generate_products() -> list[CanonicalProduct]:
    products: list[CanonicalProduct] = []

    # --- Gold brand-specific ---
    gold_weights = ["1g", "5g", "10g", "20g", "1oz", "50g", "100g"]
    for brand, aliases in GOLD_BRAND_ALIASES.items():
        for weight in gold_weights:
            w_aliases = WEIGHT_ALIASES[weight]
            patterns = _build_brand_patterns(aliases, w_aliases)
            products.append(CanonicalProduct(
                name=f"{weight} {brand} Gold Bar",
                metal="gold",
                weight=weight,
                min_price=GOLD_MIN_PRICES[weight],
                exclude_patterns=GOLD_EXCLUDES,
                patterns=_compile(patterns),
            ))

    # --- Silver brand-specific ---
    silver_weights = ["1oz", "10oz", "100g", "250g", "500g", "1kg"]
    for brand, aliases in SILVER_BRAND_ALIASES.items():
        for weight in silver_weights:
            w_aliases = WEIGHT_ALIASES[weight]
            patterns = _build_brand_patterns(aliases, w_aliases)
            products.append(CanonicalProduct(
                name=f"{weight} {brand} Silver Bar",
                metal="silver",
                weight=weight,
                min_price=SILVER_MIN_PRICES[weight],
                exclude_patterns=SILVER_EXCLUDES,
                patterns=_compile(patterns),
            ))

    # --- Generic (cheapest any brand) ---
    for weight in gold_weights:
        w_aliases = WEIGHT_ALIASES[weight]
        patterns = _build_generic_patterns("gold", w_aliases)
        products.append(CanonicalProduct(
            name=f"{weight} Gold Bar (any brand)",
            metal="gold",
            weight=weight,
            min_price=GOLD_MIN_PRICES[weight],
            exclude_patterns=GOLD_EXCLUDES,
            patterns=_compile(patterns),
        ))

    for weight in silver_weights:
        w_aliases = WEIGHT_ALIASES[weight]
        patterns = _build_generic_patterns("silver", w_aliases)
        products.append(CanonicalProduct(
            name=f"{weight} Silver Bar (any brand)",
            metal="silver",
            weight=weight,
            min_price=SILVER_MIN_PRICES[weight],
            exclude_patterns=SILVER_EXCLUDES,
            patterns=_compile(patterns),
        ))

    # --- Gold coins (manual) ---
    products.append(CanonicalProduct(
        name="1 oz Canadian Maple Leaf Gold Coin",
        metal="gold",
        weight="1oz",
        min_price=Decimal("4500"),
        exclude_patterns=GOLD_EXCLUDES,
        patterns=_compile([
            r"(?:canadian|canada).*maple\s*leaf.*gold.*1\s*oz",
            r"1\s*oz.*(?:canadian|canada).*maple\s*leaf.*gold",
            r"gold.*(?:canadian|canada).*maple.*1\s*oz",
            r"maple\s*leaf.*1\s*oz.*gold",
            r"gold.*coin.*maple.*1\s*oz",
            r"gold\s*coin\s*canadian\s*maple.*1oz",
            r"gold\s*bullion\s*coins?\s*1\s*oz",
        ]),
    ))

    return products


PRODUCTS: list[CanonicalProduct] = _generate_products()
