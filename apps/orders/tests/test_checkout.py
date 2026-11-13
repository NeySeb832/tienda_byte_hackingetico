"""End-to-end checkout: cart → order with reserved stock → payment → paid/failed/expired."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Address
from apps.cart import services as cart_services
from apps.cart.models import Cart
from apps.core.models import City
from apps.inventory.models import StockItem, StockMovement, StockReservation
from apps.inventory.services import OutOfStockError
from apps.orders import services
from apps.orders.models import Order
from apps.payments import services as payments
from apps.payments.models import Payment
from tests.factories import make_product, make_store, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def store():
    return make_store(name="Byte Bogotá Centro", is_pickup_point=True)


@pytest.fixture
def variant(store):
    product = make_product(
        "PlayStation 5 Slim",
        store=store,
        variants=[("PS5-N", {"condition": "Nuevo"}, 2750000)],
        stock={"PS5-N": 2},
    )
    return product.variants.get()


@pytest.fixture
def buyer():
    user = make_user()
    Address.objects.create(
        user=user,
        label="Casa",
        recipient_name="Ana Pérez",
        phone="3001234567",
        city=City.objects.get(code="11001"),
        line1="Calle 100 # 10-20",
        is_default=True,
    )
    return user


def new_cart(user):
    cart = cart_services.get_cart({}, user, create=True)
    assert cart is not None
    return cart


def cart_with(user, variant, quantity=1):
    cart = new_cart(user)
    cart_services.add_item(cart, variant, quantity)
    return cart


def place(user, cart, **kwargs):
    defaults = {
        "fulfillment": Order.Fulfillment.SHIPPING,
        "address": user.addresses.get(),
        "accepted_terms": True,
    }
    return services.place_order(user=user, cart=cart, **{**defaults, **kwargs})


def stock(variant):
    return StockItem.objects.get(variant=variant)


def test_place_order_snapshots_lines_and_reserves_stock(buyer, variant):
    order = place(buyer, cart_with(buyer, variant))
    assert order.number.startswith(f"BYT-{timezone.now():%Y}-")
    assert order.status == Order.Status.PENDING_PAYMENT
    assert order.total == Decimal("2750000.00")  # free shipping from 300.000
    assert order.shipping_total == 0
    assert order.tax_total == Decimal("439075.63")
    line = order.lines.get()
    assert (line.sku, line.name, line.quantity) == ("PS5-N", "PlayStation 5 Slim", 1)
    assert "Calle 100" in order.address_snapshot  # encrypted at rest, readable in the app
    assert stock(variant).reserved == 1
    assert order.events.get().to_status == Order.Status.PENDING_PAYMENT


def test_order_requires_terms_and_own_address(buyer, variant):
    cart = cart_with(buyer, variant)
    with pytest.raises(Exception, match="términos"):
        place(buyer, cart, accepted_terms=False)
    other = make_user()
    foreign = Address.objects.create(
        user=other,
        label="x",
        recipient_name="x",
        phone="1",
        city=City.objects.get(code="11001"),
        line1="x",
    )
    with pytest.raises(Exception, match="Dirección inválida"):
        place(buyer, cart, address=foreign)


def test_no_overselling(buyer, variant):
    other = make_user()
    place(buyer, cart_with(buyer, variant, 2))
    cart = new_cart(other)
    from apps.cart.models import CartItem

    CartItem.objects.create(
        cart=cart, variant=variant, quantity=1
    )  # bypass the cart limit on purpose
    with pytest.raises(Exception, match=r"agotados|Solo quedan"):
        services.place_order(
            user=other,
            cart=cart,
            fulfillment=Order.Fulfillment.PICKUP,
            pickup_store=stock(variant).store,
            accepted_terms=True,
        )
    assert stock(variant).reserved == 2


def test_reserve_is_all_or_nothing(buyer, variant, store):
    order = place(buyer, cart_with(buyer, variant))
    second = make_product("Control", store=store, stock={"SKU-CONTROL": 0}).variants.get()
    from apps.inventory.services import reserve_for_order

    with pytest.raises(OutOfStockError):
        reserve_for_order(order, [(variant, 1), (second, 1)], expires_at=timezone.now())
    assert stock(variant).reserved == 1  # unchanged by the failed attempt


def test_approved_payment_completes_the_order(buyer, variant, django_capture_on_commit_callbacks):
    order = place(buyer, cart_with(buyer, variant))
    payment, url = payments.start_payment(order, redirect_url="http://testserver/")
    assert url == reverse("payments:simulator", args=[payment.reference])
    with django_capture_on_commit_callbacks(execute=True):
        assert payments.simulate(payment, approve=True) == "aprobado"
    order.refresh_from_db()
    payment.refresh_from_db()
    assert order.status == Order.Status.PAID
    assert order.paid_at is not None
    assert payment.status == Payment.Status.APPROVED
    item = stock(variant)
    assert (item.quantity, item.reserved) == (1, 0)
    sale = StockMovement.objects.get(reason=StockMovement.Reason.SALE)
    assert (sale.delta, sale.balance, sale.reference) == (-1, 1, order.number)
    assert order.invoice.number.startswith("FPRU-")
    assert Cart.objects.get(user=buyer).status == Cart.Status.CONVERTED
    assert len(mail.outbox) == 1
    assert order.number in mail.outbox[0].subject
    assert "no tiene validez fiscal" in mail.outbox[0].body


def test_declined_payment_releases_stock(buyer, variant):
    order = place(buyer, cart_with(buyer, variant))
    payment, _ = payments.start_payment(order, redirect_url="http://testserver/")
    assert payments.simulate(payment, approve=False) == "rechazado"
    order.refresh_from_db()
    assert order.status == Order.Status.PAYMENT_FAILED
    assert stock(variant).reserved == 0
    assert StockReservation.objects.get(order=order).status == StockReservation.Status.RELEASED
    assert Cart.objects.get(user=buyer).status == Cart.Status.OPEN  # the customer can retry


def test_unpaid_orders_expire(buyer, variant):
    order = place(buyer, cart_with(buyer, variant))
    payments.start_payment(order, redirect_url="http://testserver/")
    assert services.expire_unpaid_orders() == 0
    assert services.expire_unpaid_orders(now=timezone.now() + timedelta(minutes=16)) == 1
    order.refresh_from_db()
    assert order.status == Order.Status.EXPIRED
    assert stock(variant).reserved == 0
    assert order.payments.get().status == Payment.Status.VOIDED
    with pytest.raises(ValueError, match="no admite pagos"):
        payments.start_payment(order, redirect_url="http://testserver/")


def test_status_machine_rejects_invalid_transitions(buyer, variant):
    order = place(buyer, cart_with(buyer, variant))
    with pytest.raises(Exception, match="No se puede pasar"):
        services.transition(order, Order.Status.SHIPPED)
    with pytest.raises(PermissionError):
        order.events.update(note="x")


def test_shipping_cost_below_free_threshold(buyer, store):
    cheap = make_product(
        "Forro", store=store, variants=[("FORRO-N", {"condition": "Nuevo"}, 60000)]
    ).variants.get()
    order = place(buyer, cart_with(buyer, cheap))
    assert order.shipping_total == Decimal("12000.00")  # Bogotá zone
    assert order.total == Decimal("72000.00")


def test_pickup_order(buyer, variant, store):
    order = place(
        buyer,
        cart_with(buyer, variant),
        fulfillment=Order.Fulfillment.PICKUP,
        address=None,
        pickup_store=store,
    )
    assert order.shipping_total == 0
    assert order.address_snapshot == ""
    assert StockReservation.objects.get(order=order).store == store
