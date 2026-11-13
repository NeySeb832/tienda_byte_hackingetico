"""Cart and checkout pages, payment simulator, "Mis pedidos" and the invoice PDF."""

import pytest
from allauth.account.models import EmailAddress
from django.urls import reverse

from apps.accounts.models import Address
from apps.cart import services as cart_services
from apps.cart.models import Cart
from apps.core.models import City
from apps.orders.models import Order
from tests.factories import make_product, make_store, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def variant():
    store = make_store(is_pickup_point=True)
    return make_product(
        "PlayStation 5 Slim",
        store=store,
        variants=[("PS5-N", {"condition": "Nuevo"}, 2750000)],
        stock={"PS5-N": 3},
    ).variants.get()


@pytest.fixture
def buyer():
    user = make_user()
    Address.objects.create(
        user=user,
        label="Casa",
        recipient_name="Ana",
        phone="3001234567",
        city=City.objects.get(code="05001"),
        line1="Carrera 43A # 9-12",
    )
    return user


def test_guest_cart_flow(client, variant):
    response = client.post(reverse("cart:add"), {"sku": "ps5-n", "cantidad": 2})
    assert response["Location"] == reverse("cart:detail")
    html = client.get(reverse("cart:detail")).content.decode()
    assert "PlayStation 5 Slim" in html
    assert 'class="cart-badge">2<' in html
    client.post(reverse("cart:update", args=["PS5-N"]), {"cantidad": 9})
    assert "máximo 3" in client.get(reverse("cart:detail")).content.decode()
    client.post(reverse("cart:remove", args=["PS5-N"]))
    assert "Tu carrito está vacío" in client.get(reverse("cart:detail")).content.decode()


def test_guest_cart_is_merged_at_login(client, variant, buyer):
    client.post(reverse("cart:add"), {"sku": "PS5-N", "cantidad": 1})
    session = client.session
    cart_services.merge_session_cart(session, buyer)
    assert Cart.objects.get(user=buyer, status=Cart.Status.OPEN).items.get().quantity == 1
    assert Cart.objects.filter(user=None, status=Cart.Status.MERGED).count() == 1


def test_checkout_requires_login_and_verified_email(client, variant, buyer):
    assert client.get(reverse("orders:checkout")).status_code == 302
    client.force_login(buyer)
    client.post(reverse("cart:add"), {"sku": "PS5-N", "cantidad": 1})
    EmailAddress.objects.filter(user=buyer).update(verified=False)
    response = client.post(
        reverse("orders:checkout"),
        {
            "entrega": "shipping",
            "direccion": str(buyer.addresses.get().public_id),
            "acepto": "on",
            "accion": "pagar",
        },
    )
    assert response.status_code == 302
    assert not Order.objects.exists()


def test_full_checkout_with_the_simulator(client, variant, buyer):
    client.force_login(buyer)
    client.post(reverse("cart:add"), {"sku": "PS5-N", "cantidad": 1})
    page = client.get(reverse("orders:checkout")).content.decode()
    assert "sandbox" in page
    data = {
        "entrega": "shipping",
        "direccion": str(buyer.addresses.get().public_id),
        "acepto": "on",
    }
    preview = client.post(
        reverse("orders:checkout"), {**data, "accion": "calcular"}
    ).content.decode()
    assert "Gratis" in preview
    response = client.post(reverse("orders:checkout"), {**data, "accion": "pagar"})
    order = Order.objects.get()
    payment = order.payments.get()
    assert response["Location"] == reverse("payments:simulator", args=[payment.reference])
    assert "Simular pago aprobado" in client.get(response["Location"]).content.decode()
    result = client.post(response["Location"], {"resultado": "aprobar"}, follow=True)
    assert "¡Pago aprobado!" in result.content.decode()
    detail = client.get(reverse("orders:detail", args=[order.public_id])).content.decode()
    assert order.number in detail
    assert "Carrera 43A" in detail
    pdf = client.get(reverse("orders:invoice", args=[order.public_id]))
    assert pdf["Content-Type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")
    assert order.number in client.get(reverse("orders:list")).content.decode()


def test_orders_of_other_customers_are_invisible(client, variant, buyer):
    client.force_login(buyer)
    client.post(reverse("cart:add"), {"sku": "PS5-N", "cantidad": 1})
    client.post(
        reverse("orders:checkout"),
        {
            "entrega": "shipping",
            "direccion": str(buyer.addresses.get().public_id),
            "acepto": "on",
            "accion": "pagar",
        },
    )
    order = Order.objects.get()
    payment = order.payments.get()
    intruder = make_user()
    client.force_login(intruder)
    for url in (
        reverse("orders:detail", args=[order.public_id]),
        reverse("orders:invoice", args=[order.public_id]),
        reverse("orders:result", args=[order.public_id]),
        reverse("payments:simulator", args=[payment.reference]),
    ):
        assert client.get(url).status_code == 404, url
    assert (
        client.post(
            reverse("payments:simulator", args=[payment.reference]), {"resultado": "aprobar"}
        ).status_code
        == 404
    )
    order.refresh_from_db()
    assert order.status == Order.Status.PENDING_PAYMENT


def test_checkout_rejects_addresses_of_others(client, variant, buyer):
    intruder = make_user()
    client.force_login(intruder)
    client.post(reverse("cart:add"), {"sku": "PS5-N", "cantidad": 1})
    response = client.post(
        reverse("orders:checkout"),
        {
            "entrega": "shipping",
            "direccion": str(buyer.addresses.get().public_id),
            "acepto": "on",
            "accion": "pagar",
        },
    )
    assert response.status_code == 400
    assert not Order.objects.exists()


def test_simulator_is_disabled_with_a_real_gateway(client, buyer, settings):
    settings.BYTE_PAYMENT_GATEWAY = "wompi"
    client.force_login(buyer)
    assert client.get(reverse("payments:simulator", args=["X"])).status_code == 404
