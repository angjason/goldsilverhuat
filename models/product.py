from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ScrapedProduct:
    """Raw product data as extracted from a dealer's website."""

    dealer: str
    name: str
    price: Decimal
    currency: str = "SGD"
    url: str = ""
    in_stock: bool = True


@dataclass
class NormalizedPrice:
    """A scraped product matched to a canonical product name."""

    canonical_name: str
    dealer: str
    price: Decimal
    currency: str
    url: str
    in_stock: bool


@dataclass
class ComparisonResult:
    """Price comparison for a single canonical product across dealers."""

    canonical_name: str
    prices: list[NormalizedPrice]

    @property
    def cheapest(self) -> NormalizedPrice | None:
        in_stock = [p for p in self.prices if p.in_stock]
        if not in_stock:
            return None
        return min(in_stock, key=lambda p: p.price)
