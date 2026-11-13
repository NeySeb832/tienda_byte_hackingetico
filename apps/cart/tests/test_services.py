"""Cart rules: availability, limits, quantities and guest-cart merge."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.cart import services
from apps.cart.models import Cart, CartItem
from apps.cart.selectors import cart_count, cart_summary
from apps.catalog.models import Product
from apps.inventory.models import StockItem
from apps.orders.models import Order
from apps.payments import services as payments
from apps.promotions import services as promotions
from apps.promotions.models import Coupon
from tests.factories import make_product, make_store, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def variant():
    return make_product(
        "Control", variants=[("PAD-N", {"condition": "Nuevo"}, 100000)], stock={"PAD-N": 4}
    ).variants.get()


def open_cart(user=None, session=None):
    cart = services.get_cart(session if session is not None else {}, user, create=True)
    assert cart is not None
    return cart


def test_limits_on_add_and_update(variant):
    cart = open_cart()
    services.add_item(cart, variant, 3)
    with pytest.raises(ValidationError, match="máximo 4"):
        services.add_item(cart, variant, 2)
    for bad in (0, -1, True, "2"):
        with pytest.raises(ValidationError):
            services.add_item(cart, variant, bad)  # type: ignore[arg-type]
    services.set_quantity(cart, variant, 4)
    with pytest.raises(ValidationError, match="máximo 4"):
        services.set_quantity(cart, variant, 5)
    with pytest.raises(ValidationError):
        services.set_quantity(cart, variant, -1)
    assert services.set_quantity(cart, variant, 0) is None
    with pytest.raises(ValidationError, match="no está en tu carrito"):
        services.set_quantity(cart, variant, 1)


def test_max_per_order_and_sold_out(variant):
    Product.objects.filter(pk=variant.product_id).update(max_per_order=2)
    variant.refresh_from_db()
    cart = open_cart()
    with pytest.raises(ValidationError, match="máximo 2"):
        services.add_item(cart, variant, 3)
    StockItem.objects.filter(variant=variant).update(quantity=0)
    with pytest.raises(ValidationError, match="agotado"):
        services.add_item(cart, variant, 1)


def test_inactive_products_cannot_be_added(variant):
    Product.objects.filter(pk=variant.product_id).update(is_active=False)
    variant.refresh_from_db()
    with pytest.raises(ValidationError, match="ya no está disponible"):
        services.add_item(open_cart(), variant, 1)


def test_summary_flags_lines_without_stock(variant):
    cart = open_cart()
    services.add_item(cart, variant, 2)
    StockItem.objects.filter(variant=variant).update(quantity=1)
    summary = cart_summary(cart)
    assert summary.lines[0].problem == "Solo hay 1 disponible(s)."
    assert not summary.can_checkout
    assert summary.subtotal == Decimal("200000.00")
    assert cart_count(cart) == 2
    services.remove_item(cart, variant)
    assert cart_count(cart) == 0


def test_session_cart_and_tampered_ids(variant):
    session: dict = {services.SESSION_KEY: "no-es-un-uuid"}
    assert services.get_cart(session, None) is None
    cart = open_cart(session=session)
    assert services.get_cart(session, None) == cart


def test_merge_caps_quantities_and_skips_sold_out(variant):
    user = make_user()
    session: dict = {}
    guest = open_cart(session=session)
    services.add_item(guest, variant, 3)
    services.add_item(open_cart(user), variant, 3)
    merged = services.merge_session_cart(session, user)
    assert merged is not None
    assert merged.items.get().quantity == 4  # 3 + 3 capped at the free stock
    assert Cart.objects.get(pk=guest.pk).status == Cart.Status.MERGED
    assert services.SESSION_KEY not in session
    assert services.merge_session_cart({}, user) == merged  # nothing to merge


def test_one_open_cart_per_user(variant):
    user = make_user()
    assert open_cart(user) == open_cart(user)


def test_per_user_coupon_limit_counts_only_live_orders(variant):
    store = make_store(is_pickup_point=True)
    StockItem.objects.filter(variant=variant).update(store=store)
    user = make_user()
    Coupon.objects.create(code="UNAVEZ", kind=Coupon.Kind.FIXED, value=Decimal("10000"))
    from apps.orders import services as orders

    def buy():
        cart = open_cart(user)
        CartItem.objects.get_or_create(cart=cart, variant=variant, defaults={"quantity": 1})
        return orders.place_order(
            user=user,
            cart=cart,
            fulfillment=Order.Fulfillment.PICKUP,
            pickup_store=store,
            coupon_code="unavez",
            accepted_terms=True,
        )

    first = buy()
    assert first.discount_total == Decimal("10000.00")
    with pytest.raises(ValidationError, match="no es válido"):
        buy()
    payment, _ = payments.start_payment(first, redirect_url="http://x/")
    payments.simulate(payment, approve=False)  # failed orders free the coupon again
    assert buy().coupon_code == "UNAVEZ"


def test_first_order_only_coupon(variant):
    user = make_user()
    Coupon.objects.create(code="BIENVENIDA", kind=Coupon.Kind.FREE_SHIPPING, first_order_only=True)
    assert promotions.evaluate("BIENVENIDA", user=user, subtotal=Decimal("1")).free_shipping
    Order.objects.create(
        number="BYT-X-1",
        user=user,
        email=user.email,
        fulfillment=Order.Fulfillment.SHIPPING,
        subtotal=Decimal("1"),
        total=Decimal("1"),
        paid_at=timezone.now() - timedelta(days=1),
    )
    with pytest.raises(ValidationError):
        promotions.evaluate("BIENVENIDA", user=user, subtotal=Decimal("1"))
