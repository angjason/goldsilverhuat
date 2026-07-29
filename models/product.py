from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Promotion:
    """A dealer promotion/offer on a product."""

    regular_price: Decimal
    offer_price: Decimal
    label: str = "Limited Time Offer"

    @property
    def discount_pct(self) -> float:
        return float((self.regular_price - self.offer_price) / self.regular_price * 100)


@dataclass
class ScrapedProduct:
    """Raw product data as extracted from a dealer's website."""

    dealer: str
    name: str
    price: Decimal
    currency: str = "SGD"
    url: str = ""
    in_stock: bool = True
    promotion: Promotion | None = None


@dataclass
class NormalizedPrice:
    """A scraped product matched to a canonical product name."""

    canonical_name: str
    dealer: str
    price: Decimal
    currency: str
    url: str
    in_stock: bool
    promotion: Promotion | None = None


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
