"""Returns (RMA) and refunds.

* Retracto (Ley 1480, art. 47): 5 business days after delivery, full refund of the products.
* Commercial return: 30 calendar days. Warranty: 12 months (repairs or replacement first).
Business days skip weekends; national holidays are not modelled (documented limitation).

Whoever registers the received goods cannot approve the refund (segregation of duties).
"""

from collections.abc import Mapping
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.services import record_event
from apps.inventory.models import StockMovement
from apps.inventory.services import move_stock
from apps.orders.models import Order, OrderStatusEvent, ReturnLine, ReturnRequest
from apps.payments.models import Payment, Refund
from apps.promotions import services as promotions
from apps.promotions.models import CreditEntry

K = ReturnRequest.Kind
WITHDRAWAL_BUSINESS_DAYS = 5
COMMERCIAL_DAYS = 30
WARRANTY_DAYS = 365


def add_business_days(start: date, days: int) -> date:
    current = start
    while days > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days -= 1
    return current


def delivered_on(order: Order) -> date | None:
    event = order.events.filter(to_status=Order.Status.DELIVERED).order_by("-created_at").first()
    return timezone.localdate(event.created_at) if event else None


def deadline(order: Order, kind: str) -> date | None:
    start = delivered_on(order)
    if start is None:
        return None
    if kind == K.WITHDRAWAL:
        return add_business_days(start, WITHDRAWAL_BUSINESS_DAYS)
    return start + timedelta(days=COMMERCIAL_DAYS if kind == K.COMMERCIAL else WARRANTY_DAYS)


def returnable_quantity(line: Any) -> int:
    taken = (
        ReturnLine.objects.filter(line=line)
        .exclude(request__status=ReturnRequest.Status.REJECTED)
        .aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    return line.quantity - taken


@transaction.atomic
def request_return(
    order: Order,
    *,
    user: Any,
    quantities: Mapping[int, int],
    kind: str,
    reason: str,
    refund_method: str = ReturnRequest.Refund.ORIGINAL,
) -> ReturnRequest:
    if order.user_id != getattr(user, "pk", None):
        raise ValidationError("Pedido inválido.")
    if kind not in K.values or refund_method not in ReturnRequest.Refund.values:
        raise ValidationError("Tipo de devolución inválido.")
    limit = deadline(order, kind)
    if limit is None:
        raise ValidationError("El pedido aún no ha sido entregado.")
    if timezone.localdate() > limit:
        raise ValidationError(f"El plazo para esta solicitud venció el {limit:%d/%m/%Y}.")
    if not reason.strip():
        raise ValidationError("Cuéntanos el motivo.")
    lines = {line.pk: line for line in order.lines.select_for_update()}
    wanted = {pk: qty for pk, qty in quantities.items() if qty}
    if not wanted:
        raise ValidationError("Elige al menos un producto.")
    for pk, qty in wanted.items():
        if pk not in lines or qty < 0 or qty > returnable_quantity(lines[pk]):
            raise ValidationError("Una cantidad no es válida para este pedido.")
    request = ReturnRequest.objects.create(
        order=order, kind=kind, reason=reason.strip()[:500], refund_method=refund_method
    )
    ReturnLine.objects.bulk_create(
        ReturnLine(request=request, line=lines[pk], quantity=qty) for pk, qty in wanted.items()
    )
    record_event(
        "returns.requested",
        actor=user,
        target=request,
        changes={"order": order.number, "kind": kind},
    )
    return request


def refund_value(request: ReturnRequest) -> Decimal:
    """Products returned at the price paid (the order discount is spread proportionally)."""
    order = request.order
    ratio = (
        (order.subtotal - order.discount_total) / order.subtotal if order.subtotal else Decimal("0")
    )
    gross = sum(
        (rl.line.unit_price * rl.quantity for rl in request.lines.select_related("line")),
        Decimal("0"),
    )
    return (gross * ratio).quantize(Decimal("1"), rounding=ROUND_HALF_UP)


@transaction.atomic
def receive_return(
    request: ReturnRequest, *, actor: Any, store: Any, restock: bool
) -> ReturnRequest:
    locked = ReturnRequest.objects.select_for_update().get(pk=request.pk)
    if locked.status != ReturnRequest.Status.REQUESTED:
        raise ValidationError("La devolución ya fue recibida o decidida.")
    if restock:
        for return_line in locked.lines.select_related("line__variant"):
            move_stock(
                return_line.line.variant,
                store,
                return_line.quantity,
                StockMovement.Reason.RETURN,
                actor=actor,
                reference=locked.order.number,
            )
    locked.status = ReturnRequest.Status.RECEIVED
    locked.received_by = actor
    locked.refund_amount = refund_value(locked)
    locked.save()
    record_event(
        "returns.received",
        actor=actor,
        target=locked,
        changes={"restock": restock, "amount": str(locked.refund_amount)},
    )
    return locked


@transaction.atomic
def decide_refund(
    request: ReturnRequest, *, approver: Any, approve: bool, note: str = ""
) -> ReturnRequest:
    locked = (
        ReturnRequest.objects.select_for_update(of=("self",))
        .select_related("order__user")
        .get(pk=request.pk)
    )
    if locked.status != ReturnRequest.Status.RECEIVED:
        raise ValidationError("Primero se debe recibir el producto.")
    if locked.received_by_id == getattr(approver, "pk", None):
        raise ValidationError("Quien recibe la devolución no puede aprobar el reembolso.")
    locked.decided_by = approver
    locked.decided_at = timezone.now()
    locked.decision_note = note[:255]
    order = locked.order
    if not approve:
        locked.status = ReturnRequest.Status.REJECTED
        locked.save()
        record_event("returns.rejected", actor=approver, target=locked)
        return locked
    locked.status = ReturnRequest.Status.APPROVED
    locked.save()
    amount = locked.refund_amount
    if amount > 0:
        if locked.refund_method == ReturnRequest.Refund.CREDIT and order.user is not None:
            promotions.add_credit(
                order.user,
                int(amount),
                CreditEntry.Reason.REFUND,
                actor=approver,
                reference=order.number,
            )
        else:
            payment = (
                order.payments.filter(status=Payment.Status.APPROVED)
                .order_by("-approved_at")
                .first()
            )
            if payment is None:
                raise ValidationError("El pedido no tiene un pago aprobado para reembolsar.")
            Refund.objects.create(
                payment=payment,
                amount=amount,
                requested_by=locked.received_by,
                approved_by=approver,
                status=(
                    Refund.Status.APPROVED
                    if payment.gateway in ("fake", "cash", "card_terminal")
                    else Refund.Status.PENDING_GATEWAY
                ),
            )
        if order.user is not None and order.total:
            promotions.reverse_points(order, fraction=min(amount / order.total, Decimal("1")))
    OrderStatusEvent.objects.create(
        order=order,
        from_status=order.status,
        to_status=order.status,
        note=f"Reembolso aprobado: {amount}",
        actor=approver,
    )
    record_event(
        "returns.refund_approved",
        actor=approver,
        target=locked,
        changes={"amount": str(amount), "method": locked.refund_method},
    )
    return locked
