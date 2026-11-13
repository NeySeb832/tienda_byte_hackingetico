"""Purchase orders: whoever creates one cannot approve it; receipts can be partial."""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.catalog.models import ProductVariant
from apps.core.money import MoneyInput, to_money
from apps.inventory.models import StockMovement, Store
from apps.inventory.services import move_stock
from apps.purchasing.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    Supplier,
)

S = PurchaseOrder.Status


def _number() -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('purchasing_po_number_seq')")
        value = cursor.fetchone()[0]
    return f"OC-{timezone.now():%Y}-{value:05d}"


@transaction.atomic
def create_purchase_order(
    supplier: Supplier,
    store: Store,
    lines: Sequence[tuple[ProductVariant, int, MoneyInput]],
    *,
    actor: Any,
    notes: str = "",
) -> PurchaseOrder:
    if not supplier.is_active:
        raise ValidationError("El proveedor está inactivo.")
    if not lines:
        raise ValidationError("La orden necesita al menos una línea.")
    seen: set[int] = set()
    for variant, quantity, cost in lines:
        if variant.pk in seen:
            raise ValidationError(f"{variant.sku} está repetido.")
        seen.add(variant.pk)
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise ValidationError("Las cantidades deben ser enteros positivos.")
        if to_money(cost) <= 0:
            raise ValidationError("El costo debe ser mayor que cero.")
    order = PurchaseOrder.objects.create(
        number=_number(), supplier=supplier, store=store, created_by=actor, notes=notes[:255]
    )
    PurchaseOrderLine.objects.bulk_create(
        PurchaseOrderLine(
            purchase_order=order, variant=variant, quantity=quantity, unit_cost=to_money(cost)
        )
        for variant, quantity, cost in lines
    )
    record_event(
        "purchasing.po_created",
        actor=actor,
        target=order,
        changes={"number": order.number, "lines": len(lines)},
    )
    return order


@transaction.atomic
def approve_purchase_order(order: PurchaseOrder, *, approver: Any) -> PurchaseOrder:
    locked = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    if locked.status != S.DRAFT:
        raise ValidationError("Solo se aprueban órdenes por aprobar.")
    if locked.created_by_id == getattr(approver, "pk", None):
        raise ValidationError("Quien crea una orden de compra no puede aprobarla.")
    locked.status = S.APPROVED
    locked.approved_by = approver
    locked.approved_at = timezone.now()
    locked.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    record_event("purchasing.po_approved", actor=approver, target=locked)
    order.status = locked.status
    return locked


@transaction.atomic
def receive_goods(
    order: PurchaseOrder, quantities: Mapping[int, int], *, actor: Any, note: str = ""
) -> GoodsReceipt:
    """Receive ``{line_id: units}``; stock enters the PO store and the kardex records it."""
    locked = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    if locked.status not in (S.APPROVED, S.PARTIAL):
        raise ValidationError("La orden no está aprobada o ya se recibió completa.")
    lines = {line.pk: line for line in locked.lines.select_for_update().select_related("variant")}
    wanted = {line_id: qty for line_id, qty in quantities.items() if qty}
    if not wanted:
        raise ValidationError("Indica al menos una cantidad recibida.")
    for line_id, quantity in wanted.items():
        line = lines.get(line_id)
        if line is None or quantity < 0 or quantity > line.pending:
            raise ValidationError("Una cantidad supera lo pendiente o no pertenece a la orden.")
    receipt = GoodsReceipt.objects.create(purchase_order=locked, received_by=actor, note=note[:200])
    for line_id, quantity in wanted.items():
        line = lines[line_id]
        GoodsReceiptLine.objects.create(receipt=receipt, line=line, quantity=quantity)
        line.received_quantity += quantity
        line.save(update_fields=["received_quantity"])
        move_stock(
            line.variant,
            locked.store,
            quantity,
            StockMovement.Reason.PURCHASE,
            actor=actor,
            reference=locked.number,
        )
    locked.status = S.RECEIVED if all(line.pending == 0 for line in lines.values()) else S.PARTIAL
    locked.save(update_fields=["status", "updated_at"])
    record_event(
        "purchasing.goods_received",
        actor=actor,
        target=locked,
        changes={"units": sum(wanted.values()), "status": locked.status},
    )
    order.status = locked.status
    return receipt


def total_cost(order: PurchaseOrder) -> Decimal:
    return sum((line.quantity * line.unit_cost for line in order.lines.all()), Decimal("0"))
