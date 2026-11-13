"""Business logic for orders: checkout, status machine, invoices and expiry.

Checkout (``place_order``) runs in one transaction: it re-reads current prices, applies the
coupon, quotes shipping, snapshots lines and address, reserves stock (all-or-nothing) and
records everything. Amounts are always computed here, never taken from the browser.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import Address
from apps.audit.services import record_event
from apps.cart.models import Cart
from apps.cart.selectors import cart_summary
from apps.catalog.models import Product
from apps.core.money import VAT_EXCLUDED, VAT_STANDARD, split_vat
from apps.inventory import services as inventory
from apps.inventory.models import Store
from apps.orders.models import Invoice, Order, OrderLine, OrderStatusEvent
from apps.promotions import services as promotions
from apps.promotions.models import CouponRedemption
from apps.shipping import services as shipping

S = Order.Status

TRANSITIONS: dict[str, set[str]] = {
    S.PENDING_PAYMENT: {S.PAID, S.PAYMENT_FAILED, S.EXPIRED, S.CANCELLED},
    S.PAID: {S.PREPARING, S.CANCELLED},
    S.PREPARING: {S.SHIPPED, S.READY_FOR_PICKUP, S.CANCELLED},
    S.READY_FOR_PICKUP: {S.DELIVERED},
    S.SHIPPED: {S.DELIVERED},
    S.PAYMENT_FAILED: set(),
    S.EXPIRED: set(),
    S.DELIVERED: set(),
    S.CANCELLED: set(),
}


def _next_number(sequence: str, prefix: str) -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval(%s)", [sequence])
        value = cursor.fetchone()[0]
    return f"{prefix}{value:06d}"


@transaction.atomic
def transition(order: Order, to_status: str, *, actor: Any = None, note: str = "") -> Order:
    locked = Order.objects.select_for_update().get(pk=order.pk)
    if to_status not in TRANSITIONS[locked.status]:
        raise ValidationError(
            f"No se puede pasar de «{locked.get_status_display()}» a «{S(to_status).label}»."
        )
    previous = locked.status
    locked.status = to_status
    fields = ["status", "updated_at"]
    if to_status == S.PAID:
        locked.paid_at = timezone.now()
        fields.append("paid_at")
    locked.save(update_fields=fields)
    OrderStatusEvent.objects.create(
        order=locked,
        from_status=previous,
        to_status=to_status,
        note=note[:255],
        actor=actor if getattr(actor, "pk", None) else None,
    )
    record_event(
        "orders.status_changed",
        actor=actor,
        target=locked,
        changes={"from": previous, "to": to_status},
    )
    order.status, order.paid_at = locked.status, locked.paid_at
    return locked


@dataclass(frozen=True, slots=True)
class CheckoutTotals:
    subtotal: Decimal
    discount: Decimal
    shipping: Decimal
    tax: Decimal
    total: Decimal
    coupon_code: str = ""
    shipping_days: str = ""


def _tax(
    lines: list[tuple[Decimal, Decimal]], discount: Decimal, shipping_total: Decimal
) -> Decimal:
    """VAT included in the total: the discount is spread over the lines in proportion."""
    subtotal = sum((amount for amount, _ in lines), Decimal("0"))
    ratio = (subtotal - discount) / subtotal if subtotal else Decimal("0")
    tax = sum(
        (
            split_vat((amount * ratio).quantize(Decimal("0.01"), ROUND_HALF_UP), rate).vat
            for amount, rate in lines
        ),
        Decimal("0"),
    )
    if shipping_total:
        tax += split_vat(shipping_total, VAT_STANDARD).vat
    return tax


def _rate(product: Product) -> Decimal:
    return VAT_EXCLUDED if product.tax_class == Product.TaxClass.EXCLUDED else VAT_STANDARD


def compute_totals(
    cart: Cart,
    *,
    user: Any,
    fulfillment: str,
    address: Address | None = None,
    coupon_code: str = "",
) -> CheckoutTotals:
    summary = cart_summary(cart)
    if not summary.lines:
        raise ValidationError("Tu carrito está vacío.")
    subtotal = summary.subtotal
    discount = Decimal("0")
    free_shipping = False
    code = ""
    if coupon_code:
        result = promotions.evaluate(coupon_code, user=user, subtotal=subtotal)
        discount, free_shipping, code = result.discount, result.free_shipping, result.coupon.code
    shipping_total = Decimal("0")
    days = ""
    if fulfillment == Order.Fulfillment.SHIPPING:
        if address is None:
            raise ValidationError("Elige una dirección de envío.")
        quote = shipping.quote(address.city, subtotal - discount)
        shipping_total = Decimal("0") if free_shipping else quote.price
        days = quote.days_label
    lines = [(line.line_total, _rate(line.item.variant.product)) for line in summary.lines]
    return CheckoutTotals(
        subtotal=subtotal,
        discount=discount,
        shipping=shipping_total,
        tax=_tax(lines, discount, shipping_total),
        total=subtotal - discount + shipping_total,
        coupon_code=code,
        shipping_days=days,
    )


def _address_snapshot(address: Address) -> str:
    return json.dumps(
        {
            "recipient": address.recipient_name,
            "phone": address.phone,
            "line1": address.line1,
            "line2": address.line2,
            "neighborhood": address.neighborhood,
            "city": address.city.name,
            "department": address.city.department.name,
            "notes": address.notes,
        },
        ensure_ascii=False,
    )


@transaction.atomic
def place_order(
    *,
    user: Any,
    cart: Cart,
    fulfillment: str,
    address: Address | None = None,
    pickup_store: Store | None = None,
    coupon_code: str = "",
    accepted_terms: bool = False,
) -> Order:
    """Create a ``pending_payment`` order with reserved stock. Raises ``ValidationError``."""
    if not accepted_terms:
        raise ValidationError("Debes aceptar los términos y condiciones.")
    if fulfillment not in Order.Fulfillment.values:
        raise ValidationError("Forma de entrega inválida.")
    if address is not None and address.user_id != user.pk:
        raise ValidationError("Dirección inválida.")
    if fulfillment == Order.Fulfillment.PICKUP and (
        pickup_store is None or not pickup_store.is_active or not pickup_store.is_pickup_point
    ):
        raise ValidationError("Elige una tienda para recoger.")
    summary = cart_summary(cart)
    if not summary.can_checkout:
        raise ValidationError(
            "Revisa tu carrito: hay productos agotados o sin unidades suficientes."
        )
    if coupon_code:
        promotions.evaluate(coupon_code, user=user, subtotal=summary.subtotal, lock=True)
    totals = compute_totals(
        cart, user=user, fulfillment=fulfillment, address=address, coupon_code=coupon_code
    )
    ttl = timedelta(minutes=settings.BYTE_STOCK_RESERVATION_TTL_MINUTES)
    expires_at = timezone.now() + ttl
    order = Order.objects.create(
        number=_next_number("orders_order_number_seq", f"BYT-{timezone.now():%Y}-"),
        user=user,
        email=user.email,
        fulfillment=fulfillment,
        pickup_store=pickup_store if fulfillment == Order.Fulfillment.PICKUP else None,
        city=address.city if address and fulfillment == Order.Fulfillment.SHIPPING else None,
        address_snapshot=(
            _address_snapshot(address)
            if address and fulfillment == Order.Fulfillment.SHIPPING
            else ""
        ),
        subtotal=totals.subtotal,
        discount_total=totals.discount,
        shipping_total=totals.shipping,
        tax_total=totals.tax,
        total=totals.total,
        coupon_code=totals.coupon_code,
        terms_accepted_at=timezone.now(),
        expires_at=expires_at,
    )
    OrderLine.objects.bulk_create(
        [
            OrderLine(
                order=order,
                variant=line.item.variant,
                sku=line.sku,
                name=line.name,
                variant_label=line.variant_label[:255],
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_rate=_rate(line.item.variant.product),
                line_total=line.line_total,
            )
            for line in summary.lines
        ]
    )
    inventory.reserve_for_order(
        order,
        [(line.item.variant, line.quantity) for line in summary.lines],
        expires_at=expires_at,
        preferred_store=order.pickup_store,
    )
    if totals.coupon_code:
        coupon = promotions.evaluate(totals.coupon_code, user=user, subtotal=totals.subtotal).coupon
        CouponRedemption.objects.create(
            coupon=coupon, order=order, user=user, discount=totals.discount
        )
    OrderStatusEvent.objects.create(order=order, to_status=S.PENDING_PAYMENT, actor=user)
    record_event(
        "orders.placed",
        actor=user,
        target=order,
        changes={"number": order.number, "total": str(order.total), "lines": len(summary.lines)},
    )
    return order


@transaction.atomic
def issue_invoice(order: Order) -> Invoice:
    """Test electronic invoice (simulated CUFE, no DIAN validity)."""
    existing = Invoice.objects.filter(order=order).first()
    if existing:
        return existing
    number = _next_number("orders_invoice_number_seq", "FPRU-")
    issued = timezone.now()
    cufe = hashlib.sha384(
        f"{number}{issued.isoformat()}{order.total}{order.tax_total}{order.number}".encode()
    ).hexdigest()
    return Invoice.objects.create(order=order, number=number, cufe=cufe, issued_at=issued)


def expire_unpaid_orders(*, now: Any = None) -> int:
    """Celery Beat: orders not paid in time release their stock."""
    now = now or timezone.now()
    expired = 0
    for order_id in Order.objects.filter(status=S.PENDING_PAYMENT, expires_at__lte=now).values_list(
        "pk", flat=True
    ):
        with transaction.atomic():
            order = Order.objects.select_for_update(skip_locked=True).filter(pk=order_id).first()
            if order is None or order.status != S.PENDING_PAYMENT:
                continue
            inventory.release_reservations(order)
            order.payments.filter(status="pending").update(
                status="voided", status_message="Vencido sin pago"
            )
            transition(order, S.EXPIRED, note="Tiempo de pago agotado")
            expired += 1
    return expired
