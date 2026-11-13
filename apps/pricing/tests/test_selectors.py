"""Honest reference prices (Ley 1480), lowest price in 30 days and the price sparkline."""

from datetime import timedelta
from decimal import Decimal
from itertools import count

import pytest
from django.utils import timezone

from apps.catalog.models import Product, ProductVariant
from apps.pricing.models import PriceHistory
from apps.pricing.selectors import price_insight, price_sparkline
from tests.factories import category

pytestmark = pytest.mark.django_db

NOW = timezone.now()
_ids = count()


def variant_with_history(*changes: tuple[int, int]) -> ProductVariant:
    """``changes``: (days ago, price) in chronological order; the first is the initial price."""
    n = next(_ids)
    product = Product.objects.create(
        name=f"Consola {n}",
        slug=f"consola-{n}",
        product_type=Product.Type.CONSOLE,
        category=category(),
    )
    current = Decimal(changes[-1][1])
    variant = ProductVariant.objects.create(
        product=product,
        sku=f"CONSOLA-{n}",
        combination_key="default",
        price=current,
        price_override=current,
    )
    previous = None
    for days_ago, price in changes:
        PriceHistory.objects.create(
            variant=variant,
            price=Decimal(price),
            previous_price=previous,
            reason=PriceHistory.Reason.INITIAL if previous is None else PriceHistory.Reason.MANUAL,
            changed_at=NOW - timedelta(days=days_ago),
        )
        previous = Decimal(price)
    return variant


def insight(*changes):
    return price_insight(variant_with_history(*changes), now=NOW)


def test_no_reference_without_a_drop():
    result = insight((90, 1000000))
    assert result.reference is None
    assert result.lowest_30d == Decimal("1000000")
    assert result.saving == 0
    assert result.saving_pct == 0


def test_recent_drop_shows_the_lowest_price_of_the_previous_30_days():
    result = insight((90, 1000000), (20, 950000), (5, 800000))
    assert result.current == Decimal("800000")
    assert result.reference == Decimal("950000")
    assert result.saving == Decimal("150000")
    assert result.saving_pct == 16
    assert result.lowest_30d == Decimal("800000")


def test_price_increase_never_shows_a_reference():
    result = insight((90, 900000), (5, 1000000))
    assert result.reference is None
    assert result.lowest_30d == Decimal("900000")


def test_old_drop_no_longer_shows_a_reference():
    assert insight((120, 1000000), (40, 800000)).reference is None


def test_drop_after_a_brief_increase_uses_the_lowest_previous_price():
    # 900k for weeks, raised to 1M for 3 days, then "discounted" to 950k: no real discount.
    assert insight((60, 900000), (8, 1000000), (5, 950000)).reference is None


def test_flat_sparkline():
    line = price_sparkline(variant_with_history((120, 1000000)), now=NOW)
    assert line.is_flat
    assert line.low == line.high == Decimal("1000000")
    assert line.changes == 0


def test_sparkline_with_changes():
    variant = variant_with_history((120, 1000000), (60, 900000), (10, 950000))
    line = price_sparkline(variant, now=NOW, width=90, height=40)
    assert not line.is_flat
    assert (line.low, line.high) == (Decimal("900000"), Decimal("1000000"))
    assert line.changes == 2
    points = line.points.split()
    assert points[0].startswith("0.0,")
    assert points[-1].startswith("90.0,")


def test_sparkline_of_a_new_product_starts_at_its_first_price():
    line = price_sparkline(variant_with_history((3, 500000)), now=NOW)
    assert line.is_flat
    assert line.since > NOW - timedelta(days=4)
