from __future__ import annotations

import re
from decimal import Decimal

from config.products import CanonicalProduct
from models.product import ScrapedProduct
from services.normalizer import normalize


def make_canonical(name: str = "1oz Test Gold Bar", min_price: Decimal = Decimal("0")) -> CanonicalProduct:
    return CanonicalProduct(
        name=name,
        metal="gold",
        weight="1oz",
        patterns=[re.compile(r"test", re.IGNORECASE)],
        exclude_patterns=[],
        min_price=min_price,
    )


def make_scraped(
    dealer: str,
    price: str,
    in_stock: bool = True,
    name: str = "Test Gold Bar 1oz",
) -> ScrapedProduct:
    return ScrapedProduct(dealer=dealer, name=name, price=Decimal(price), in_stock=in_stock)


class TestStockAndPricePrecedence:
    """A dealer can have multiple listings matching the same canonical product
    (e.g. paginated or duplicated listings). normalize() must keep the single
    best one per (canonical, dealer): in-stock beats out-of-stock, and among
    equal stock status, cheaper wins."""

    def test_in_stock_beats_cheaper_out_of_stock(self):
        canonical = make_canonical()
        scraped = [
            make_scraped("DealerA", "5000", in_stock=True),
            make_scraped("DealerA", "4000", in_stock=False),
        ]
        result = normalize(scraped, [canonical])
        assert len(result) == 1
        assert result[0].price == Decimal("5000")
        assert result[0].in_stock is True

    def test_in_stock_replaces_out_of_stock_regardless_of_price(self):
        canonical = make_canonical()
        scraped = [
            make_scraped("DealerA", "4000", in_stock=False),
            make_scraped("DealerA", "5000", in_stock=True),
        ]
        result = normalize(scraped, [canonical])
        assert len(result) == 1
        assert result[0].price == Decimal("5000")
        assert result[0].in_stock is True

    def test_cheaper_in_stock_replaces_pricier_in_stock(self):
        canonical = make_canonical()
        scraped = [
            make_scraped("DealerA", "5000", in_stock=True),
            make_scraped("DealerA", "4500", in_stock=True),
        ]
        result = normalize(scraped, [canonical])
        assert result[0].price == Decimal("4500")

    def test_pricier_in_stock_does_not_replace_cheaper_in_stock(self):
        canonical = make_canonical()
        scraped = [
            make_scraped("DealerA", "4500", in_stock=True),
            make_scraped("DealerA", "5000", in_stock=True),
        ]
        result = normalize(scraped, [canonical])
        assert result[0].price == Decimal("4500")

    def test_cheaper_out_of_stock_replaces_pricier_out_of_stock(self):
        canonical = make_canonical()
        scraped = [
            make_scraped("DealerA", "5000", in_stock=False),
            make_scraped("DealerA", "4500", in_stock=False),
        ]
        result = normalize(scraped, [canonical])
        assert len(result) == 1
        assert result[0].price == Decimal("4500")
        assert result[0].in_stock is False

    def test_pricier_out_of_stock_does_not_replace_cheaper_out_of_stock(self):
        canonical = make_canonical()
        scraped = [
            make_scraped("DealerA", "4500", in_stock=False),
            make_scraped("DealerA", "5000", in_stock=False),
        ]
        result = normalize(scraped, [canonical])
        assert result[0].price == Decimal("4500")


class TestGrouping:
    def test_keeps_one_result_per_dealer(self):
        canonical = make_canonical()
        scraped = [
            make_scraped("DealerA", "5000"),
            make_scraped("DealerB", "4800"),
        ]
        result = normalize(scraped, [canonical])
        dealers = {r.dealer for r in result}
        assert dealers == {"DealerA", "DealerB"}
        assert len(result) == 2

    def test_min_price_filters_out_false_positive_matches(self):
        canonical = make_canonical(min_price=Decimal("1000"))
        scraped = [make_scraped("DealerA", "5.00")]
        result = normalize(scraped, [canonical])
        assert result == []

    def test_item_matching_no_canonical_product_is_dropped(self):
        canonical = make_canonical()
        scraped = [make_scraped("DealerA", "5000", name="Completely Unrelated Item")]
        result = normalize(scraped, [canonical])
        assert result == []

    def test_empty_input_returns_empty_list(self):
        assert normalize([], [make_canonical()]) == []
