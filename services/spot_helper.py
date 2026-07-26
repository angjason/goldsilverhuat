"""Spot price calculation for arbitrary weights."""

from __future__ import annotations

import re
from decimal import Decimal

from services.spot_price import SpotPrices

TROY_OZ_IN_GRAMS = Decimal("31.1035")

WEIGHT_IN_GRAMS: dict[str, Decimal] = {
    "1g": Decimal("1"),
    "5g": Decimal("5"),
    "10g": Decimal("10"),
    "20g": Decimal("20"),
    "50g": Decimal("50"),
    "100g": Decimal("100"),
    "250g": Decimal("250"),
    "500g": Decimal("500"),
    "1oz": TROY_OZ_IN_GRAMS,
    "10oz": TROY_OZ_IN_GRAMS * 10,
    "1kg": Decimal("1000"),
}

_WEIGHT_PATTERNS: list[tuple[re.Pattern, Decimal]] = sorted(
    [(re.compile(rf"(?<!\d){re.escape(k)}\b", re.IGNORECASE), v)
     for k, v in WEIGHT_IN_GRAMS.items()],
    key=lambda x: -len(x[0].pattern),
)


def get_spot_for_product(canonical_name: str, spot: SpotPrices | None) -> Decimal | None:
    """Calculate the spot price for a product based on its metal and weight."""
    if not spot:
        return None

    name_lower = canonical_name.lower()

    if "gold" in name_lower:
        per_gram = spot.gold_oz / TROY_OZ_IN_GRAMS if spot.gold_oz else None
    elif "silver" in name_lower:
        per_gram = spot.silver_oz / TROY_OZ_IN_GRAMS if spot.silver_oz else None
    else:
        return None

    if per_gram is None:
        return None

    for pattern, grams in _WEIGHT_PATTERNS:
        if pattern.search(canonical_name):
            return per_gram * grams

    return None
