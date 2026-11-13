"""Point of sale: open/close cash sessions and in-store sales (ADR-0008: no account needed).

A POS sale is a regular ``Order`` (channel ``pos``) paid on the spot: stock leaves the session's
store through the same reservation → consumption path as web orders, so the kardex and the
"no overselling" guarantees are identical.
"""

import secrets
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.services import record_event
from apps.catalog.models import Product, ProductVariant
from apps.core.money import VAT_EXCLUDED, VAT_STANDARD, MoneyInput, split_vat, to_money
from apps.inventory import services as inventory
from apps.inventory.models import Store
from apps.orders import services as orders
from apps.orders.models import Order, OrderLine, OrderStatusEvent
from apps.payments.models import Payment
from apps.pos.models import CashSession
from apps.promotions import services as promotions

CASH = "cash"
CARD = "card_terminal"
CREDIT = "store_credit"
METHODS = {CASH: "Efectivo", CARD: "Datáfono", CREDIT: "Saldo a favor"}


@transaction.atomic
def open_session(store: Store, *, actor: Any, opening_float: MoneyInput) -> CashSession:
    amount = to_money(opening_float)
    if amount < 0:
        raise ValidationError("La base no puede ser negativa.")
    if CashSession.objects.filter(store=store, opened_by=actor, closed_at=None).exists():
        raise ValidationError("Ya tienes un turno abierto en esta sede.")
    session = CashSession.objects.create(store=store, opened_by=actor, opening_float=amount)
    record_event("pos.session_opened", actor=actor, target=session, changes={"float": str(amount)})
    return session


def cash_sales(session: CashSession) -> Decimal:
    total = Payment.objects.filter(
        order__cash_session=session, gateway=CASH, status=Payment.Status.APPROVED
    ).aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0")


@transaction.atomic
def close_session(session: CashSession, *, actor: Any, counted_cash: MoneyInput) -> CashSession:
    locked = CashSession.objects.select_for_update().get(pk=session.pk)
    if locked.closed_at is not None:
        raise ValidationError("El turno ya está cerrado.")
    if locked.opened_by_id != getattr(actor, "pk", None):
        raise ValidationError("Solo quien abrió el turno puede cerrarlo.")
    locked.expected_cash = locked.opening_float + cash_sales(locked)
    locked.counted_cash = to_money(counted_cash)
    locked.closed_by = actor
    locked.closed_at = timezone.now()
    locked.save(
        update_fields=["expected_cash", "counted_cash", "closed_by", "closed_at", "updated_at"]
    )
    record_event(
        "pos.session_closed",
        actor=actor,
        target=locked,
        changes={"expected": str(locked.expected_cash), "counted": str(locked.counted_cash)},
    )
    return locked


@transaction.atomic
def sell(
    session: CashSession,
    items: Sequence[tuple[ProductVariant, int]],
    *,
    actor: Any,
    method: str,
    cash_received: MoneyInput | None = None,
    customer_email: str = "",
) -> tuple[Order, Decimal]:
    """Register an in-store sale. Returns the order and the change to give back."""
    if not session.is_open or session.opened_by_id != getattr(actor, "pk", None):
        raise ValidationError("Abre tu turno de caja para vender.")
    if method not in METHODS:
        raise ValidationError("Medio de pago inválido.")
    if not items:
        raise ValidationError("Agrega al menos un producto.")
    lines = []
    for variant, quantity in items:
        if not variant.is_active or not variant.product.is_active:
            raise ValidationError(f"{variant.sku} no está disponible.")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise ValidationError("Cantidad inválida.")
        rate = (
            VAT_EXCLUDED if variant.product.tax_class == Product.TaxClass.EXCLUDED else VAT_STANDARD
        )
        lines.append((variant, quantity, variant.price, rate))
    total = sum((price * quantity for _, quantity, price, _ in lines), Decimal("0"))
    change = Decimal("0")
    if method == CASH:
        received = to_money(cash_received if cash_received is not None else "0")
        if received < total:
            raise ValidationError("El efectivo recibido no alcanza para el total.")
        change = received - total
    customer = (
        User.objects.filter(email=customer_email.strip().lower(), is_staff=False).first()
        if customer_email
        else None
    )
    if method == CREDIT:
        if customer is None:
            raise ValidationError("Para pagar con saldo a favor indica el correo del cliente.")
        if promotions.credit_balance(customer) < total:
            raise ValidationError("El cliente no tiene saldo suficiente.")
    order = Order.objects.create(
        number=orders._next_number("orders_order_number_seq", f"POS-{timezone.now():%Y}-"),
        user=customer,
        email=customer_email.strip().lower()[:254],
        channel=Order.Channel.POS,
        fulfillment=Order.Fulfillment.PICKUP,
        pickup_store=session.store,
        cash_session=session,
        sold_by=actor,
        subtotal=total,
        total=total,
        tax_total=sum(
            (split_vat(price * quantity, rate).vat for _, quantity, price, rate in lines),
            Decimal("0"),
        ),
        terms_accepted_at=timezone.now(),
        expires_at=timezone.now(),
    )
    OrderLine.objects.bulk_create(
        OrderLine(
            order=order,
            variant=variant,
            sku=variant.sku,
            name=variant.product.name,
            variant_label=" · ".join(value.value for value in variant.values.all())[:255],
            quantity=quantity,
            unit_price=price,
            tax_rate=rate,
            line_total=price * quantity,
        )
        for variant, quantity, price, rate in lines
    )
    OrderStatusEvent.objects.create(
        order=order, to_status=Order.Status.PENDING_PAYMENT, actor=actor
    )
    inventory.reserve_for_order(
        order,
        [(variant, quantity) for variant, quantity, _, _ in lines],
        expires_at=timezone.now(),
        preferred_store=session.store,
    )
    Payment.objects.create(
        order=order,
        reference=f"{order.number}-{secrets.token_hex(3).upper()}",
        gateway=method,
        amount=total,
        status=Payment.Status.APPROVED,
        approved_at=timezone.now(),
    )
    inventory.consume_reservations(order, actor=actor)
    orders.transition(
        order, Order.Status.PAID, actor=actor, note=f"Venta en tienda ({METHODS[method]})"
    )
    orders.transition(order, Order.Status.DELIVERED, actor=actor, note="Entregado en mostrador")
    orders.issue_invoice(order)
    if method == CREDIT and customer is not None:
        promotions.spend_credit(customer, int(total), actor=actor, reference=order.number)
    promotions.award_points(order)
    record_event(
        "pos.sale", actor=actor, target=order, changes={"total": str(total), "method": method}
    )
    return order, change
