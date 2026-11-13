"""Coupons: discounts, limits, generic errors and segregation of duties."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.promotions import services
from apps.promotions.models import Coupon
from tests.factories import make_user

pytestmark = pytest.mark.django_db


def coupon(code="BYTE10", **fields):
    defaults = {"kind": Coupon.Kind.PERCENT, "value": Decimal("10")}
    return Coupon.objects.create(code=code, **{**defaults, **fields})


def test_percent_with_cap_and_fixed():
    coupon(max_discount=Decimal("50000"))
    result = services.evaluate(" byte10 ", user=None, subtotal=Decimal("1000000"))
    assert result.discount == Decimal("50000")
    coupon("MENOS20K", kind=Coupon.Kind.FIXED, value=Decimal("20000"))
    assert services.evaluate("MENOS20K", user=None, subtotal=Decimal("15000")).discount == Decimal(
        "15000"
    )
    coupon("ENVIOGRATIS", kind=Coupon.Kind.FREE_SHIPPING)
    assert services.evaluate("enviogratis", user=None, subtotal=Decimal("1")).free_shipping


@pytest.mark.parametrize(
    "fields",
    [
        {"is_active": False},
        {"starts_at": timezone.now() + timedelta(days=1)},
        {"ends_at": timezone.now() - timedelta(minutes=1)},
        {"min_subtotal": Decimal("500000")},
        {"value": Decimal("40")},  # needs approval
    ],
)
def test_invalid_coupons_share_one_generic_message(fields):
    coupon(**fields)
    with pytest.raises(ValidationError, match="no es válido") as exc:
        services.evaluate("BYTE10", user=None, subtotal=Decimal("100000"))
    with pytest.raises(ValidationError) as missing:
        services.evaluate("NOEXISTE", user=None, subtotal=Decimal("100000"))
    assert exc.value.messages == missing.value.messages


def test_high_discount_needs_another_person():
    creator, approver = make_user(), make_user()
    big = coupon(value=Decimal("40"), created_by=creator)
    with pytest.raises(ValidationError, match="no puede aprobarlo"):
        services.approve_coupon(big, approver=creator)
    with pytest.raises(IntegrityError), transaction.atomic():
        Coupon.objects.filter(pk=big.pk).update(approved_by=creator)
    services.approve_coupon(big, approver=approver)
    assert services.evaluate("BYTE10", user=None, subtotal=Decimal("100000")).discount == Decimal(
        "40000"
    )


def test_database_rejects_lowercase_codes_and_bad_percentages():
    with pytest.raises(IntegrityError), transaction.atomic():
        coupon("minusculas")
    with pytest.raises(IntegrityError), transaction.atomic():
        coupon("MAS100", value=Decimal("150"))
