from __future__ import annotations

import pytest

from config.products import PRODUCTS, CanonicalProduct


def get_product(name: str) -> CanonicalProduct:
    for product in PRODUCTS:
        if product.name == name:
            return product
    raise AssertionError(f"no canonical product named {name!r} in PRODUCTS")


class TestBrandWeightOrdering:
    def test_brand_then_weight_matches(self):
        product = get_product("1oz PAMP Gold Bar")
        assert product.matches("PAMP Suisse 1oz Gold Bar")

    def test_weight_then_brand_matches(self):
        product = get_product("1oz PAMP Gold Bar")
        assert product.matches("1 oz Gold Bar - PAMP Suisse")

    def test_case_insensitive(self):
        product = get_product("1oz PAMP Gold Bar")
        assert product.matches("pamp 1OZ gold bar")

    def test_unrelated_brand_does_not_match(self):
        product = get_product("1oz PAMP Gold Bar")
        assert not product.matches("Valcambi 1oz Gold Bar")


class TestWeightBoundaries:
    """Weight regexes must not cross-match neighbouring weights that share digits
    (e.g. '1g' inside '10g', '5g' inside '50g'/'250g', '100g' inside '1000g')."""

    @pytest.mark.parametrize(
        "canonical_name,should_match,should_not_match",
        [
            ("1g PAMP Gold Bar", "PAMP 1g Gold Bar", ["PAMP 10g Gold Bar", "PAMP 100g Gold Bar"]),
            ("10g PAMP Gold Bar", "PAMP 10g Gold Bar", ["PAMP 1g Gold Bar", "PAMP 100g Gold Bar"]),
            ("100g PAMP Gold Bar", "PAMP 100g Gold Bar", ["PAMP 10g Gold Bar", "PAMP 1g Gold Bar"]),
            ("5g PAMP Gold Bar", "PAMP 5g Gold Bar", ["PAMP 50g Gold Bar"]),
            ("50g PAMP Gold Bar", "PAMP 50g Gold Bar", ["PAMP 5g Gold Bar"]),
            ("1oz PAMP Gold Bar", "PAMP 1oz Gold Bar", ["PAMP 10oz Gold Bar"]),
        ],
    )
    def test_weight_does_not_cross_match(self, canonical_name, should_match, should_not_match):
        product = get_product(canonical_name)
        assert product.matches(should_match)
        for text in should_not_match:
            assert not product.matches(text), f"{canonical_name!r} incorrectly matched {text!r}"

    def test_1kg_matches_1000_gram_alias(self):
        product = get_product("1kg Heraeus Silver Bar")
        assert product.matches("Heraeus 1000g Silver Bar")
        assert product.matches("Heraeus 1kg Silver Bar")


class TestMetalExclusion:
    def test_gold_canonical_excludes_silver_labeled_product(self):
        product = get_product("1oz PAMP Gold Bar")
        assert not product.matches("PAMP 1oz Silver Bar")

    def test_silver_canonical_excludes_gold_labeled_product(self):
        product = get_product("1oz PAMP Silver Bar")
        assert not product.matches("PAMP 1oz Gold Bar")


class TestMapleLeafCoin:
    def test_matches_brand_before_weight_order(self):
        product = get_product("1 oz Canadian Maple Leaf Gold Coin")
        assert product.matches("Canadian Maple Leaf Gold Coin 1oz")

    def test_matches_gold_first_order(self):
        product = get_product("1 oz Canadian Maple Leaf Gold Coin")
        assert product.matches("Gold Canadian Maple Leaf 1oz Coin")

    def test_does_not_match_generic_gold_bar(self):
        product = get_product("1 oz Canadian Maple Leaf Gold Coin")
        assert not product.matches("PAMP 1oz Gold Bar")

    def test_does_not_match_silver_maple_leaf(self):
        product = get_product("1 oz Canadian Maple Leaf Gold Coin")
        assert not product.matches("1oz Canadian Silver Maple Leaf Coin")

    @pytest.mark.xfail(
        reason=(
            "Known gap: all 7 hand-written Maple Leaf patterns require 'canadian'/'gold' "
            "to appear before the weight token. A weight-first listing, which is a common "
            "real-world dealer format, matches none of them. See config/products.py:127-142."
        ),
        strict=True,
    )
    def test_matches_weight_first_listing_name(self):
        product = get_product("1 oz Canadian Maple Leaf Gold Coin")
        assert product.matches("1oz Canadian Gold Maple Leaf Coin")
