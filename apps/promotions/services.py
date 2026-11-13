"""Coupons: validation, discount calculation, approval (segregation of duties).

Customers always get the same generic message for any invalid code, so the endpoint
cannot be used to discover which codes exist (and it is rate limited in the view).
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import record_event
from apps.promotions.models import Coupon, CouponRedemption

INVALID = "El cupón no es válido o no aplica a esta compra."


@dataclass(frozen=True, slots=True)
class CouponResult:
    coupon: Coupon
    discount: Decimal
    free_shipping: bool


def normalize_code(code: str) -> str:
    return "".join(ch for ch in code.strip().upper() if ch.isalnum() or ch == "-")[:30]


def needs_approval(coupon: Coupon) -> bool:
    return coupon.kind == Coupon.Kind.PERCENT and coupon.value > Decimal(
        settings.BYTE_HIGH_DISCOUNT_APPROVAL_PCT
    )


@transaction.atomic
def approve_coupon(coupon: Coupon, *, approver: Any) -> Coupon:
    locked = Coupon.objects.select_for_update().get(pk=coupon.pk)
    if locked.created_by_id is not None and locked.created_by_id == getattr(approver, "pk", None):
        raise ValidationError("Quien crea un cupón no puede aprobarlo.")
    locked.approved_by = approver
    locked.approved_at = timezone.now()
    locked.save(update_fields=["approved_by", "approved_at", "updated_at"])
    record_event("promotions.coupon_approved", actor=approver, target=locked)
    return locked


def evaluate(code: str, *, user: Any, subtotal: Decimal, lock: bool = False) -> CouponResult:
    """Check a code for ``user`` and compute its discount over ``subtotal`` (VAT included)."""
    normalized = normalize_code(code)
    queryset = Coupon.objects.select_for_update() if lock else Coupon.objects
    coupon = queryset.filter(code=normalized, is_active=True).first()
    now = timezone.now()
    if (
        coupon is None
        or coupon.starts_at > now
        or (coupon.ends_at is not None and coupon.ends_at <= now)
        or subtotal < coupon.min_subtotal
        or (needs_approval(coupon) and coupon.approved_by_id is None)
    ):
        raise ValidationError(INVALID)
    used = CouponRedemption.objects.filter(coupon=coupon).exclude(
        order__status__in=("payment_failed", "expired", "cancelled")
    )
    if coupon.usage_limit is not None and used.count() >= coupon.usage_limit:
        raise ValidationError(INVALID)
    if user is not None and used.filter(user=user).count() >= coupon.per_user_limit:
        raise ValidationError(INVALID)
    if coupon.first_order_only and user is not None:
        from apps.orders.models import Order

        if Order.objects.filter(user=user).filter(~Q(paid_at=None)).exists():
            raise ValidationError(INVALID)
    if coupon.kind == Coupon.Kind.FREE_SHIPPING:
        return CouponResult(coupon=coupon, discount=Decimal("0"), free_shipping=True)
    if coupon.kind == Coupon.Kind.PERCENT:
        discount = (subtotal * coupon.value / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    else:
        discount = coupon.value
    if coupon.max_discount is not None:
        discount = min(discount, coupon.max_discount)
    return CouponResult(coupon=coupon, discount=min(discount, subtotal), free_shipping=False)
