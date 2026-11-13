"""Coupons: validation, discount calculation, approval (segregation of duties).

Customers always get the same generic message for any invalid code, so the endpoint
cannot be used to discover which codes exist (and it is rate limited in the view).
"""

import zlib
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import record_event
from apps.promotions.models import Coupon, CouponRedemption, CreditEntry, LoyaltyEntry

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


# --- Loyalty points and store credit (append-only ledgers) ------------------------------------

POINTS_PER_PESOS = 1000  # 1 point for every $1.000 paid
REDEEM_BLOCK = 1000  # points per redemption block
CREDIT_PER_BLOCK = 10000  # $10.000 of store credit per 1.000 points


def _append(model: Any, user: Any, delta: int, reason: str, **fields: Any) -> Any:
    """Lock the user's ledger (advisory lock) and append an entry with the new balance."""
    with connection.cursor() as cursor:
        # Stable key per ledger table (zlib, not hash(): it changes between processes).
        key = zlib.crc32(model._meta.db_table.encode()) & 0x7FFFFFFF
        cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [key, user.pk % 2**31])
    last = model.objects.filter(user=user).order_by("-created_at", "-pk").first()
    balance = (last.balance if last else 0) + delta
    if balance < 0:
        raise ValidationError("Saldo insuficiente.")
    return model.objects.create(user=user, delta=delta, balance=balance, reason=reason, **fields)


def points_balance(user: Any) -> int:
    last = LoyaltyEntry.objects.filter(user=user).order_by("-created_at", "-pk").first()
    return last.balance if last else 0


def credit_balance(user: Any) -> int:
    last = CreditEntry.objects.filter(user=user).order_by("-created_at", "-pk").first()
    return last.balance if last else 0


@transaction.atomic
def award_points(order: Any) -> LoyaltyEntry | None:
    """Points for a paid order with a customer account (idempotent per order)."""
    if order.user_id is None or order.user.is_staff:
        return None
    points = int(order.total // POINTS_PER_PESOS)
    if (
        points <= 0
        or LoyaltyEntry.objects.filter(
            user=order.user, reason="earned", reference=order.number
        ).exists()
    ):
        return None
    return _append(
        LoyaltyEntry, order.user, points, LoyaltyEntry.Reason.EARNED, reference=order.number
    )


@transaction.atomic
def reverse_points(order: Any, *, fraction: Decimal = Decimal("1")) -> LoyaltyEntry | None:
    """A refund takes back the points earned with the refunded part (never below zero)."""
    earned = LoyaltyEntry.objects.filter(
        user=order.user, reason="earned", reference=order.number
    ).first()
    if earned is None:
        return None
    take = min(int(earned.delta * fraction), points_balance(order.user))
    if take <= 0:
        return None
    return _append(
        LoyaltyEntry, order.user, -take, LoyaltyEntry.Reason.REVERSED, reference=order.number
    )


@transaction.atomic
def redeem_points(user: Any, blocks: int) -> CreditEntry:
    if isinstance(blocks, bool) or not isinstance(blocks, int) or blocks < 1:
        raise ValidationError("Elige cuántos bloques de 1.000 puntos quieres canjear.")
    _append(
        LoyaltyEntry, user, -blocks * REDEEM_BLOCK, LoyaltyEntry.Reason.REDEEMED, created_by=user
    )
    entry = _append(
        CreditEntry, user, blocks * CREDIT_PER_BLOCK, CreditEntry.Reason.POINTS, created_by=user
    )
    record_event("loyalty.points_redeemed", actor=user, target=user, changes={"blocks": blocks})
    return entry


@transaction.atomic
def add_credit(
    user: Any, amount: int, reason: str, *, actor: Any = None, reference: str = ""
) -> CreditEntry:
    if amount <= 0:
        raise ValidationError("El valor debe ser positivo.")
    entry = _append(CreditEntry, user, amount, reason, created_by=actor, reference=reference[:64])
    record_event(
        "credit.added", actor=actor, target=user, changes={"amount": amount, "reason": reason}
    )
    return entry


@transaction.atomic
def spend_credit(user: Any, amount: int, *, actor: Any = None, reference: str = "") -> CreditEntry:
    entry = _append(
        CreditEntry,
        user,
        -amount,
        CreditEntry.Reason.SPENT,
        created_by=actor,
        reference=reference[:64],
    )
    record_event("credit.spent", actor=actor, target=user, changes={"amount": amount})
    return entry
