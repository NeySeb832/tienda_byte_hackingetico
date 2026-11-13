"""Write-side use cases for pricing: the price engine, manual and scheduled price changes.

Two pricing modes (``Product.PricingMode``):

* **fixed**: every variant has its own price (``price_override``).
* **modifiers**: price = product base price + the modifiers of the variant's option values,
  unless the variant has a fixed ``price_override``.

Every change of ``ProductVariant.price`` goes through ``_apply_price`` so it is written to the
append-only ``PriceHistory`` and to the audit log. Prices are COP with VAT included (ADR-0004).
"""

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.services import record_event
from apps.catalog.models import Product, ProductOptionValue, ProductVariant
from apps.core.money import MoneyInput, to_money
from apps.pricing.models import PriceHistory, ScheduledPriceChange

Reason = PriceHistory.Reason


def _positive(amount: MoneyInput) -> Decimal:
    value = to_money(amount)
    if value <= 0:
        raise ValidationError("El precio debe ser mayor que cero.")
    return value


def price_from_modifiers(product: Product, value_ids: Iterable[int]) -> Decimal:
    """Base price plus the modifiers of the given attribute values (modifiers mode)."""
    if product.base_price is None:
        raise ValidationError("El producto no tiene precio base.")
    total = ProductOptionValue.objects.filter(
        option__product=product, value_id__in=list(value_ids)
    ).aggregate(total=Sum("price_modifier"))["total"]
    return to_money(product.base_price + (total or Decimal("0")))


def compute_variant_price(variant: ProductVariant) -> Decimal:
    """The price the engine assigns to a variant (override first, then modifiers)."""
    if variant.price_override is not None:
        return to_money(variant.price_override)
    if variant.product.pricing_mode == Product.PricingMode.FIXED:
        raise ValidationError("En modo de precio fijo cada variante necesita su precio.")
    return _positive(
        price_from_modifiers(variant.product, variant.values.values_list("pk", flat=True))
    )


def record_initial_price(
    variant: ProductVariant, *, actor: Any = None, at: datetime | None = None
) -> PriceHistory:
    return PriceHistory.objects.create(
        variant=variant,
        price=variant.price,
        reason=Reason.INITIAL,
        changed_by=actor if getattr(actor, "pk", None) else None,
        changed_at=at or timezone.now(),
    )


def _apply_price(
    locked: ProductVariant,
    new_price: Decimal,
    *,
    actor: Any,
    reason: str,
    note: str = "",
    pin: bool,
) -> PriceHistory | None:
    """Set the price of a variant already locked with ``select_for_update``."""
    if locked.price == new_price and (not pin or locked.price_override == new_price):
        return None
    previous = locked.price
    locked.price = new_price
    if pin:
        locked.price_override = new_price
    locked.save(update_fields=["price", "price_override", "updated_at"])
    if previous == new_price:
        return None
    entry = PriceHistory.objects.create(
        variant=locked,
        price=new_price,
        previous_price=previous,
        reason=reason,
        note=note[:200],
        changed_by=actor if getattr(actor, "pk", None) else None,
    )
    record_event(
        "pricing.price_changed",
        actor=actor,
        target=locked,
        changes={"sku": locked.sku, "from": str(previous), "to": str(new_price), "reason": reason},
    )
    return entry


@transaction.atomic
def change_variant_price(
    variant: ProductVariant,
    new_price: MoneyInput,
    *,
    actor: Any = None,
    note: str = "",
    reason: str = Reason.MANUAL,
) -> PriceHistory | None:
    """Fix a new price for a variant. Returns the history row, or None if unchanged."""
    price = _positive(new_price)
    locked = ProductVariant.objects.select_for_update().get(pk=variant.pk)
    entry = _apply_price(locked, price, actor=actor, reason=reason, note=note, pin=True)
    variant.price, variant.price_override = locked.price, locked.price_override
    return entry


@transaction.atomic
def recalculate_product_prices(product: Product, *, actor: Any = None) -> int:
    """Re-apply the modifiers to every variant without a fixed price. Returns changes."""
    if product.pricing_mode != Product.PricingMode.MODIFIERS:
        return 0
    changed = 0
    for locked in product.variants.select_for_update().order_by("pk"):
        if locked.price_override is not None:
            continue
        new_price = compute_variant_price(locked)
        if _apply_price(locked, new_price, actor=actor, reason=Reason.RECALCULATED, pin=False):
            changed += 1
    return changed


def schedule_price_change(
    variant: ProductVariant,
    new_price: MoneyInput,
    starts_at: datetime,
    *,
    actor: Any = None,
    note: str = "",
) -> ScheduledPriceChange:
    price = _positive(new_price)
    if timezone.is_naive(starts_at):
        raise ValidationError("La fecha debe incluir zona horaria.")
    if starts_at <= timezone.now():
        raise ValidationError("La fecha de inicio debe ser futura.")
    change = ScheduledPriceChange.objects.create(
        variant=variant,
        new_price=price,
        starts_at=starts_at,
        note=note[:200],
        created_by=actor if getattr(actor, "pk", None) else None,
    )
    record_event(
        "pricing.price_scheduled",
        actor=actor,
        target=change,
        changes={"sku": variant.sku, "to": str(price), "starts_at": starts_at.isoformat()},
    )
    return change


@transaction.atomic
def cancel_scheduled_change(change: ScheduledPriceChange, *, actor: Any = None) -> None:
    locked = ScheduledPriceChange.objects.select_for_update().get(pk=change.pk)
    if locked.status != ScheduledPriceChange.Status.PENDING:
        raise ValidationError("Solo se pueden cancelar cambios pendientes.")
    locked.status = ScheduledPriceChange.Status.CANCELLED
    locked.save(update_fields=["status", "updated_at"])
    change.status = locked.status
    record_event("pricing.price_schedule_cancelled", actor=actor, target=locked)


def apply_due_price_changes(*, now: datetime | None = None) -> int:
    """Apply every pending change whose start date has passed (Celery Beat task).

    Rows are locked with ``SKIP LOCKED`` so two workers never apply the same change.
    """
    now = now or timezone.now()
    applied = 0
    with transaction.atomic():
        due = (
            ScheduledPriceChange.objects.select_for_update(skip_locked=True)
            .filter(status=ScheduledPriceChange.Status.PENDING, starts_at__lte=now)
            .order_by("starts_at", "pk")
        )
        for change in due:
            locked = ProductVariant.objects.select_for_update().get(pk=change.variant_id)
            _apply_price(
                locked,
                change.new_price,
                actor=change.created_by,
                reason=Reason.SCHEDULED,
                note=f"Cambio programado {change.public_id}",
                pin=True,
            )
            change.status = ScheduledPriceChange.Status.APPLIED
            change.applied_at = now
            change.save(update_fields=["status", "applied_at", "updated_at"])
            applied += 1
    return applied
