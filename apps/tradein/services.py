"""Trade-ins: online estimate from the reference price, in-store inspection and payout.

The estimate uses the lowest current price of the same console sold as "Usado" when it exists
(otherwise the lowest price), times a factor for the declared condition. Credit payouts get a 10 %
bonus because the value stays in the store.
"""

from decimal import ROUND_DOWN, Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Min

from apps.audit.services import record_event
from apps.catalog.models import Product
from apps.core.money import to_money
from apps.promotions import services as promotions
from apps.promotions.models import CreditEntry
from apps.tradein.models import TradeInRequest

FACTORS: dict[str, Decimal] = {
    TradeInRequest.Condition.EXCELLENT: Decimal("0.55"),
    TradeInRequest.Condition.GOOD: Decimal("0.45"),
    TradeInRequest.Condition.FAIR: Decimal("0.30"),
}
NO_BOX = Decimal("0.95")
NO_CONTROLLER = Decimal("0.90")
CREDIT_BONUS = Decimal("1.10")
ROUND_TO = Decimal("10000")


def reference_price(product: Product) -> Decimal:
    variants = product.variants.filter(is_active=True)
    used = variants.filter(values__attribute__code="condition", values__slug="usado").aggregate(
        p=Min("price")
    )["p"]
    return used or variants.aggregate(p=Min("price"))["p"] or Decimal("0")


def estimate(product: Product, condition: str, *, has_box: bool, has_controller: bool) -> Decimal:
    if product.product_type != Product.Type.CONSOLE:
        raise ValidationError("Por ahora recibimos consolas en retoma.")
    if condition not in FACTORS:
        raise ValidationError("Estado inválido.")
    value = reference_price(product) * FACTORS[condition]
    if not has_box:
        value *= NO_BOX
    if not has_controller:
        value *= NO_CONTROLLER
    # Offers are rounded down to $10.000.
    return (value / ROUND_TO).to_integral_value(rounding=ROUND_DOWN) * ROUND_TO


def request_quote(
    user: Any, product: Product, condition: str, *, has_box: bool, has_controller: bool
) -> TradeInRequest:
    value = estimate(product, condition, has_box=has_box, has_controller=has_controller)
    if value <= 0:
        raise ValidationError("No tenemos precio de referencia para esa consola.")
    request = TradeInRequest.objects.create(
        user=user,
        product=product,
        condition=condition,
        has_box=has_box,
        has_controller=has_controller,
        estimated_value=value,
    )
    record_event("tradein.quoted", actor=user, target=request, changes={"value": str(value)})
    return request


@transaction.atomic
def inspect(
    request: TradeInRequest, *, inspector: Any, store: Any, final_value: Any, notes: str
) -> TradeInRequest:
    locked = TradeInRequest.objects.select_for_update().get(pk=request.pk)
    if locked.status != TradeInRequest.Status.ESTIMATED:
        raise ValidationError("Esta retoma ya fue evaluada.")
    if locked.user_id == getattr(inspector, "pk", None):
        raise ValidationError("No puedes evaluar tu propia retoma.")
    value = to_money(final_value)
    if value < 0:
        raise ValidationError("La oferta no puede ser negativa.")
    locked.final_value = value
    locked.inspection_notes = notes[:255]
    locked.inspected_by = inspector
    locked.store = store
    locked.status = TradeInRequest.Status.INSPECTED
    locked.save()
    record_event("tradein.inspected", actor=inspector, target=locked, changes={"value": str(value)})
    return locked


def credit_offer(request: TradeInRequest) -> Decimal:
    return ((request.final_value or Decimal("0")) * CREDIT_BONUS).quantize(Decimal("1"))


@transaction.atomic
def answer_offer(
    request: TradeInRequest, *, user: Any, accept: bool, payout: str = ""
) -> TradeInRequest:
    """The customer accepts (credit or cash) or rejects the final offer."""
    locked = TradeInRequest.objects.select_for_update().get(pk=request.pk)
    if locked.user_id != getattr(user, "pk", None):
        raise ValidationError("Retoma inválida.")
    if locked.status != TradeInRequest.Status.INSPECTED:
        raise ValidationError("La retoma no tiene una oferta pendiente.")
    if not accept:
        locked.status = TradeInRequest.Status.REJECTED
        locked.save(update_fields=["status", "updated_at"])
        record_event("tradein.rejected", actor=user, target=locked)
        return locked
    if payout not in TradeInRequest.Payout.values:
        raise ValidationError("Elige cómo quieres recibir el pago.")
    locked.payout = payout
    if payout == TradeInRequest.Payout.CREDIT:
        promotions.add_credit(
            user,
            int(credit_offer(locked)),
            CreditEntry.Reason.TRADE_IN,
            actor=user,
            reference=str(locked.public_id),
        )
        locked.status = TradeInRequest.Status.PAID
    else:
        locked.status = TradeInRequest.Status.ACCEPTED  # cash is paid at the counter
    locked.save(update_fields=["payout", "status", "updated_at"])
    record_event("tradein.accepted", actor=user, target=locked, changes={"payout": payout})
    return locked
