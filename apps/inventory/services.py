"""Business logic (write side) for the inventory app.

Services are the only place allowed to change domain state: they validate
business rules, run inside transactions and record audit events.

Stock rows are always locked with ``select_for_update()`` inside ``transaction.atomic()``,
in primary-key order, so concurrent checkouts never deadlock nor oversell. Every change of
physical units is written to the append-only kardex (``StockMovement``).
"""

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.audit.services import record_event
from apps.catalog.models import ProductVariant
from apps.inventory.models import (
    InventoryAdjustment,
    StockItem,
    StockMovement,
    StockReservation,
    StockTransfer,
    Store,
)
from apps.notifications import services as alerts


class OutOfStockError(ValidationError):
    """Not enough free units for a variant."""

    def __init__(self, variant: ProductVariant, available: int) -> None:
        self.variant = variant
        self.available = available
        super().__init__(
            f"Solo quedan {available} unidad(es) de «{variant.product.name}» ({variant.sku})."
        )


def _movement(
    item: StockItem,
    delta: int,
    reason: str,
    *,
    actor: Any = None,
    reference: str = "",
    note: str = "",
) -> StockMovement:
    return StockMovement.objects.create(
        variant_id=item.variant_id,
        store_id=item.store_id,
        delta=delta,
        balance=item.quantity,
        reason=reason,
        reference=reference[:64],
        note=note[:200],
        created_by=actor if getattr(actor, "pk", None) else None,
    )


@transaction.atomic
def set_stock(
    variant: ProductVariant,
    store: Store,
    quantity: int,
    *,
    actor: Any = None,
    note: str = "",
    reason: str = StockMovement.Reason.ADJUSTMENT,
) -> StockItem:
    """Set the physical units of a variant in a store (stock count)."""
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
        raise ValidationError("La cantidad debe ser un entero mayor o igual a cero.")
    StockItem.objects.get_or_create(variant=variant, store=store)
    item = StockItem.objects.select_for_update().get(variant=variant, store=store)
    if quantity < item.reserved:
        raise ValidationError("No se puede dejar menos unidades que las reservadas.")
    previous = item.quantity
    if previous == quantity:
        return item
    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    if quantity > previous:
        alerts.stock_became_available(variant.pk)
    _movement(item, quantity - previous, reason, actor=actor, note=note)
    record_event(
        "inventory.stock_set",
        actor=actor,
        target=item,
        changes={
            "sku": variant.sku,
            "store": store.code,
            "from": previous,
            "to": quantity,
            "note": note[:120],
        },
    )
    return item


def _locked_items(variant_ids: Iterable[int]) -> list[StockItem]:
    return list(
        StockItem.objects.select_for_update()
        .filter(variant_id__in=list(variant_ids), store__is_active=True)
        .select_related("store")
        .order_by("pk")
    )


@transaction.atomic
def reserve_for_order(
    order: Any,
    lines: Iterable[tuple[ProductVariant, int]],
    *,
    expires_at: datetime,
    preferred_store: Store | None = None,
) -> list[StockReservation]:
    """Hold units for every line or none (all-or-nothing). Raises ``OutOfStockError``.

    The preferred store (pickup) is used first, then stores with more free units.
    """
    wanted: dict[int, int] = defaultdict(int)
    variants: dict[int, ProductVariant] = {}
    for variant, quantity in lines:
        wanted[variant.pk] += quantity
        variants[variant.pk] = variant
    items = _locked_items(wanted)
    by_variant: dict[int, list[StockItem]] = defaultdict(list)
    for item in items:
        by_variant[item.variant_id].append(item)
    reservations = []
    for variant_id, quantity in wanted.items():
        candidates = by_variant.get(variant_id, [])
        if preferred_store is not None:
            candidates = [item for item in candidates if item.store_id == preferred_store.pk]
        free = sum(item.available for item in candidates)
        if free < quantity:
            raise OutOfStockError(variants[variant_id], max(free, 0))
        candidates.sort(key=lambda item: (-item.available, item.pk))
        pending = quantity
        for item in candidates:
            if pending == 0:
                break
            take = min(pending, item.available)
            if take <= 0:
                continue
            StockItem.objects.filter(pk=item.pk).update(reserved=F("reserved") + take)
            item.reserved += take
            reservations.append(
                StockReservation(
                    variant_id=variant_id,
                    store_id=item.store_id,
                    order=order,
                    quantity=take,
                    expires_at=expires_at,
                )
            )
            pending -= take
    return StockReservation.objects.bulk_create(reservations)


def _settle(order: Any, *, consume: bool, actor: Any = None) -> int:
    active = list(
        StockReservation.objects.select_for_update()
        .filter(order=order, status=StockReservation.Status.ACTIVE)
        .order_by("pk")
    )
    if not active:
        return 0
    items = {
        (item.variant_id, item.store_id): item
        for item in _locked_items({reservation.variant_id for reservation in active})
    }
    for reservation in active:
        item = items[(reservation.variant_id, reservation.store_id)]
        item.reserved -= reservation.quantity
        if consume:
            item.quantity -= reservation.quantity
        item.save(update_fields=["quantity", "reserved", "updated_at"])
        if consume:
            _movement(
                item,
                -reservation.quantity,
                StockMovement.Reason.SALE,
                actor=actor,
                reference=getattr(order, "number", ""),
            )
        reservation.status = (
            StockReservation.Status.CONSUMED if consume else StockReservation.Status.RELEASED
        )
        reservation.save(update_fields=["status", "updated_at"])
    return len(active)


@transaction.atomic
def consume_reservations(order: Any, *, actor: Any = None) -> int:
    """Payment approved: reserved units leave the store (kardex: sale)."""
    return _settle(order, consume=True, actor=actor)


@transaction.atomic
def release_reservations(order: Any) -> int:
    """Payment failed or expired: units become available again."""
    return _settle(order, consume=False)


# --- Back office: generic movements, adjustments (SoD) and transfers --------------------------


@transaction.atomic
def move_stock(
    variant: ProductVariant,
    store: Store,
    delta: int,
    reason: str,
    *,
    actor: Any = None,
    reference: str = "",
    note: str = "",
) -> StockItem:
    """Add (or remove) physical units, keeping ``quantity >= reserved`` and writing the kardex."""
    if delta == 0:
        raise ValidationError("La cantidad debe ser distinta de cero.")
    StockItem.objects.get_or_create(variant=variant, store=store)
    item = StockItem.objects.select_for_update().get(variant=variant, store=store)
    if item.quantity + delta < item.reserved:
        raise OutOfStockError(variant, max(item.available, 0))
    item.quantity += delta
    item.save(update_fields=["quantity", "updated_at"])
    if delta > 0:
        alerts.stock_became_available(variant.pk)
    _movement(item, delta, reason, actor=actor, reference=reference, note=note)
    return item


def request_adjustment(
    variant: ProductVariant, store: Store, counted: int, *, reason: str, actor: Any
) -> InventoryAdjustment:
    if isinstance(counted, bool) or not isinstance(counted, int) or counted < 0:
        raise ValidationError("La cantidad contada debe ser un entero mayor o igual a cero.")
    if not reason.strip():
        raise ValidationError("Indica el motivo del ajuste.")
    adjustment = InventoryAdjustment.objects.create(
        variant=variant,
        store=store,
        counted_quantity=counted,
        reason=reason.strip()[:200],
        requested_by=actor,
    )
    record_event(
        "inventory.adjustment_requested",
        actor=actor,
        target=adjustment,
        changes={"sku": variant.sku, "counted": counted},
    )
    return adjustment


@transaction.atomic
def decide_adjustment(
    adjustment: InventoryAdjustment, *, approver: Any, approve: bool
) -> InventoryAdjustment:
    locked = InventoryAdjustment.objects.select_for_update().get(pk=adjustment.pk)
    if locked.status != InventoryAdjustment.Status.PENDING:
        raise ValidationError("Este ajuste ya fue decidido.")
    if locked.requested_by_id == getattr(approver, "pk", None):
        raise ValidationError("Quien solicita un ajuste no puede aprobarlo.")
    locked.status = (
        InventoryAdjustment.Status.APPROVED if approve else InventoryAdjustment.Status.REJECTED
    )
    locked.decided_by = approver
    locked.decided_at = timezone.now()
    locked.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
    if approve:
        set_stock(
            locked.variant,
            locked.store,
            locked.counted_quantity,
            actor=approver,
            note=f"Ajuste {locked.public_id}: {locked.reason}"[:200],
        )
    record_event(
        "inventory.adjustment_approved" if approve else "inventory.adjustment_rejected",
        actor=approver,
        target=locked,
    )
    adjustment.status = locked.status
    return locked


def request_transfer(
    variant: ProductVariant, from_store: Store, to_store: Store, quantity: int, *, actor: Any
) -> StockTransfer:
    if from_store.pk == to_store.pk:
        raise ValidationError("El origen y el destino deben ser distintos.")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise ValidationError("La cantidad debe ser al menos 1.")
    transfer = StockTransfer.objects.create(
        variant=variant,
        from_store=from_store,
        to_store=to_store,
        quantity=quantity,
        requested_by=actor,
    )
    record_event(
        "inventory.transfer_requested",
        actor=actor,
        target=transfer,
        changes={"sku": variant.sku, "quantity": quantity},
    )
    return transfer


@transaction.atomic
def ship_transfer(transfer: StockTransfer, *, actor: Any) -> StockTransfer:
    locked = StockTransfer.objects.select_for_update().get(pk=transfer.pk)
    if locked.status != StockTransfer.Status.REQUESTED:
        raise ValidationError("El traslado no está pendiente de despacho.")
    move_stock(
        locked.variant,
        locked.from_store,
        -locked.quantity,
        StockMovement.Reason.TRANSFER_OUT,
        actor=actor,
        reference=str(locked.public_id),
    )
    locked.status = StockTransfer.Status.SHIPPED
    locked.shipped_at = timezone.now()
    locked.save(update_fields=["status", "shipped_at", "updated_at"])
    record_event("inventory.transfer_shipped", actor=actor, target=locked)
    transfer.status = locked.status
    return locked


@transaction.atomic
def receive_transfer(transfer: StockTransfer, *, actor: Any) -> StockTransfer:
    locked = StockTransfer.objects.select_for_update().get(pk=transfer.pk)
    if locked.status != StockTransfer.Status.SHIPPED:
        raise ValidationError("El traslado no está en tránsito.")
    move_stock(
        locked.variant,
        locked.to_store,
        locked.quantity,
        StockMovement.Reason.TRANSFER_IN,
        actor=actor,
        reference=str(locked.public_id),
    )
    locked.status = StockTransfer.Status.RECEIVED
    locked.received_at = timezone.now()
    locked.save(update_fields=["status", "received_at", "updated_at"])
    record_event("inventory.transfer_received", actor=actor, target=locked)
    transfer.status = locked.status
    return locked
