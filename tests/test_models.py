from __future__ import annotations

from decimal import Decimal, DivisionByZero

import pytest

from models.product import ComparisonResult, NormalizedPrice, Promotion


def make_price(dealer: str, price: str, in_stock: bool = True) -> NormalizedPrice:
    return NormalizedPrice(
        canonical_name="1oz Test Gold Bar",
        dealer=dealer,
        price=Decimal(price),
        currency="SGD",
        url="",
        in_stock=in_stock,
    )


class TestComparisonResultCheapest:
    def test_returns_cheapest_in_stock_price(self):
        result = ComparisonResult(
            canonical_name="1oz Test Gold Bar",
            prices=[make_price("A", "5000"), make_price("B", "4800"), make_price("C", "5200")],
        )
        assert result.cheapest.dealer == "B"

    def test_ignores_out_of_stock_prices(self):
        result = ComparisonResult(
            canonical_name="1oz Test Gold Bar",
            prices=[make_price("A", "4000", in_stock=False), make_price("B", "5000", in_stock=True)],
        )
        assert result.cheapest.dealer == "B"

    def test_returns_none_when_nothing_in_stock(self):
        result = ComparisonResult(
            canonical_name="1oz Test Gold Bar",
            prices=[make_price("A", "4000", in_stock=False)],
        )
        assert result.cheapest is None

    def test_returns_none_with_no_prices(self):
        result = ComparisonResult(canonical_name="1oz Test Gold Bar", prices=[])
        assert result.cheapest is None


class TestPromotionDiscountPct:
    def test_computes_percentage_off(self):
        promo = Promotion(regular_price=Decimal("100"), offer_price=Decimal("80"))
        assert promo.discount_pct == pytest.approx(20.0)

    @pytest.mark.xfail(
        raises=DivisionByZero,
        strict=True,
        reason=(
            "Known gap: discount_pct divides by regular_price with no zero-check "
            "(models/product.py:17). A scraper that produces regular_price=0 would "
            "crash report generation instead of degrading gracefully."
        ),
    )
    def test_zero_regular_price_does_not_crash(self):
        # a non-zero numerator divided by zero raises decimal.DivisionByZero
        # (dividing zero by zero would instead raise decimal.DivisionUndefined)
        promo = Promotion(regular_price=Decimal("0"), offer_price=Decimal("10"))
        promo.discount_pct
