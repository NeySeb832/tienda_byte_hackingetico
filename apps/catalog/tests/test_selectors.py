"""Featured products shown on the home page."""

from decimal import Decimal

import pytest
from django.test import override_settings

from apps.catalog.selectors import CONDITIONS, featured_controllers, featured_products

ALL_PRODUCTS = [*featured_products(), *featured_controllers()]


@pytest.mark.parametrize("product", ALL_PRODUCTS, ids=lambda p: p.name)
def test_featured_products_are_consistent(product):
    assert isinstance(product.price, Decimal)
    assert product.price > 0
    assert product.condition in CONDITIONS
    assert product.condition_class == f"condition-{product.condition.lower()}"


@override_settings(BYTE_FREE_SHIPPING_FROM=300_000)
def test_free_shipping_threshold():
    by_name = {p.name: p for p in ALL_PRODUCTS}
    assert by_name["Nintendo Switch 2"].free_shipping is True
    assert by_name["Control DualSense blanco"].free_shipping is False


@override_settings(BYTE_FREE_SHIPPING_FROM=100_000)
def test_free_shipping_threshold_is_configurable():
    assert all(p.free_shipping for p in featured_controllers())
