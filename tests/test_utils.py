from __future__ import annotations

from decimal import Decimal

from scrapers.utils import parse_sgd_price, resolve_url


class TestParseSgdPrice:
    def test_dollar_sign_format(self):
        assert parse_sgd_price("S$5,530.21") == Decimal("5530.21")

    def test_sgd_prefix_format(self):
        assert parse_sgd_price("SGD 5,240.38") == Decimal("5240.38")

    def test_bare_number_format(self):
        assert parse_sgd_price("5,530.21") == Decimal("5530.21")

    def test_no_thousands_separator(self):
        assert parse_sgd_price("S$530.21") == Decimal("530.21")

    def test_price_embedded_in_surrounding_text(self):
        assert parse_sgd_price("Now only S$5,530.21 (was S$5,999.00)") == Decimal("5530.21")

    def test_below_min_value_returns_none(self):
        # default min_value is 10
        assert parse_sgd_price("S$5.00") is None

    def test_at_min_value_boundary_is_accepted(self):
        assert parse_sgd_price("S$10.00") == Decimal("10.00")

    def test_custom_min_value(self):
        assert parse_sgd_price("S$500.00", min_value=Decimal("1000")) is None
        assert parse_sgd_price("S$1500.00", min_value=Decimal("1000")) == Decimal("1500.00")

    def test_no_price_in_text_returns_none(self):
        assert parse_sgd_price("Out of stock") is None

    def test_integer_only_price_not_matched(self):
        # regex requires two decimal places; a bare integer like "5530" won't match
        assert parse_sgd_price("5530") is None


class TestResolveUrl:
    def test_absolute_url_returned_unchanged(self):
        assert resolve_url("https://example.com/product", "https://base.com") == "https://example.com/product"

    def test_relative_url_is_prefixed(self):
        assert resolve_url("/product/1", "https://base.com") == "https://base.com/product/1"

    def test_http_absolute_url_returned_unchanged(self):
        assert resolve_url("http://example.com/x", "https://base.com") == "http://example.com/x"
