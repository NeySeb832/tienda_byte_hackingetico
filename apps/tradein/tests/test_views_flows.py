"""End-to-end flows through the pages: trade-in offer, points redemption, repair ticket, returns."""

from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounts import roles
from apps.accounts.models import StaffStoreAssignment
from apps.cart import services as cart_services
from apps.orders import services as orders
from apps.orders.models import Order, ReturnRequest
from apps.payments import services as payments
from apps.promotions import services as promotions
from apps.services_desk.models import ServiceTicket
from apps.tradein.models import TradeInRequest
from tests.factories import make_product, make_store, make_user, make_user_with_role

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(setup_roles):
    store = make_store(name="Bogotá", code="BOG", is_pickup_point=True)
    console = make_product(
        "PlayStation 5",
        store=store,
        options={"condition": ["Nuevo", "Usado"]},
        variants=[
            ("PS5-N", {"condition": "Nuevo"}, 2750000),
            ("PS5-U", {"condition": "Usado"}, 2000000),
        ],
    )
    manager = make_user_with_role(roles.MANAGER)
    seller = make_user_with_role(roles.SELLER)
    for user in (manager, seller):
        StaffStoreAssignment.objects.create(user=user, store=store)
    return {
        "store": store,
        "console": console,
        "manager": manager,
        "seller": seller,
        "customer": make_user(),
    }


def test_trade_in_through_the_pages(client, world):
    customer = world["customer"]
    client.force_login(customer)
    client.post(
        reverse("tradein:list"),
        {"consola": world["console"].slug, "estado": "good", "control": "on"},
    )
    trade = TradeInRequest.objects.get()
    client.force_login(world["seller"])
    assert "PlayStation 5" in client.get(reverse("panel:tradeins")).content.decode()
    client.post(
        reverse("panel:tradeins"), {"retoma": str(trade.public_id), "sede": "BOG", "oferta": "abc"}
    )
    trade.refresh_from_db()
    assert trade.status == TradeInRequest.Status.ESTIMATED
    client.post(
        reverse("panel:tradeins"),
        {"retoma": str(trade.public_id), "sede": "BOG", "oferta": "700000", "notas": "OK"},
    )
    client.force_login(customer)
    assert "Oferta final" in client.get(reverse("tradein:list")).content.decode()
    client.post(
        reverse("tradein:answer", args=[trade.public_id]), {"respuesta": "aceptar", "pago": "cash"}
    )
    trade.refresh_from_db()
    assert trade.status == TradeInRequest.Status.ACCEPTED
    response = client.post(reverse("tradein:list"), {"consola": "no-existe", "estado": "good"})
    assert response.status_code == 400


def test_points_page_redeem(client, world):
    customer = world["customer"]
    promotions.add_credit(customer, 5000, "trade_in")
    client.force_login(customer)
    response = client.post(reverse("tradein:points"), {"bloques": "1"}, follow=True)
    assert "Saldo insuficiente" in response.content.decode()
    client.post(reverse("tradein:points"), {"bloques": "x"})
    assert "5.000" in client.get(reverse("tradein:points")).content.decode()


def test_ticket_through_the_pages(client, world):
    client.force_login(world["manager"])
    client.post(
        reverse("panel:tickets"),
        {
            "sede": "BOG",
            "nombre": "Ana",
            "correo": world["customer"].email,
            "equipo": "Switch",
            "falla": "No carga",
        },
    )
    ticket = ServiceTicket.objects.get()
    assert ticket.customer == world["customer"]
    detail = reverse("panel:ticket", args=[ticket.public_id])
    assert ticket.code in client.get(detail).content.decode()
    client.post(detail, {"estado": "diagnosing"})
    client.post(
        detail, {"estado": "quoted", "diagnostico": "Puerto USB-C dañado", "cotizacion": "120000"}
    )
    ticket.refresh_from_db()
    assert ticket.quote == Decimal("120000.00")
    client.post(detail, {"estado": "delivered"})  # invalid jump
    client.force_login(world["customer"])
    assert "120.000" in client.get(reverse("tradein:tickets")).content.decode()
    client.post(
        reverse("tradein:tickets"), {"orden": str(ticket.public_id), "respuesta": "aprobar"}
    )
    ticket.refresh_from_db()
    assert ticket.status == ServiceTicket.Status.REPAIRING
    response = client.post(
        reverse("tradein:track"), {"codigo": ticket.code, "correo": world["customer"].email}
    )
    assert "En reparación" in response.content.decode()
    assert (
        client.post(
            reverse("tradein:track"), {"codigo": ticket.code, "correo": "otro@x.co"}
        ).status_code
        == 400
    )


def test_return_through_the_pages(client, world):
    customer = world["customer"]
    cart = cart_services.get_cart({}, customer, create=True)
    assert cart is not None
    cart_services.add_item(cart, world["console"].variants.get(sku="PS5-N"), 1)
    order = orders.place_order(
        user=customer,
        cart=cart,
        fulfillment=Order.Fulfillment.PICKUP,
        pickup_store=world["store"],
        accepted_terms=True,
    )
    payments.simulate(payments.start_payment(order, redirect_url="/")[0], approve=True)
    for status in (Order.Status.PREPARING, Order.Status.READY_FOR_PICKUP, Order.Status.DELIVERED):
        orders.transition(order, status)
    client.force_login(customer)
    url = reverse("tradein:return", args=[order.public_id])
    assert "Retracto" in client.get(url).content.decode()
    line = order.lines.get()
    bad = client.post(
        url, {"tipo": "withdrawal", "motivo": "x", "reembolso": "original", f"linea-{line.pk}": "0"}
    )
    assert bad.status_code == 400
    client.post(
        url,
        {
            "tipo": "withdrawal",
            "motivo": "No era lo que esperaba",
            "reembolso": "credit",
            f"linea-{line.pk}": "1",
        },
    )
    rma = ReturnRequest.objects.get()
    client.force_login(world["seller"])
    client.post(
        reverse("panel:returns"),
        {"devolucion": str(rma.public_id), "accion": "recibir", "sede": "BOG", "reingresar": "on"},
    )
    assert (
        client.post(
            reverse("panel:returns"), {"devolucion": str(rma.public_id), "accion": "aprobar"}
        ).status_code
        == 403
    )
    client.force_login(world["manager"])
    assert "No era lo que esperaba" in client.get(reverse("panel:returns")).content.decode()
    client.post(
        reverse("panel:returns"),
        {"devolucion": str(rma.public_id), "accion": "aprobar", "nota": "OK"},
    )
    rma.refresh_from_db()
    assert rma.status == ReturnRequest.Status.APPROVED
    assert promotions.credit_balance(customer) == 2750000
    assert (
        client.get(reverse("tradein:return", args=[order.public_id])).status_code == 404
    )  # not the owner


def test_alerts_page(client, world):
    client.force_login(world["customer"])
    client.post(reverse("tradein:alerts"), {"sku": "PS5-N", "tipo": "stock"})
    alert = world["customer"].product_alerts.get()
    assert "Avísame cuando llegue" in client.get(reverse("tradein:alerts")).content.decode()
    client.post(reverse("tradein:alerts"), {"accion": "quitar", "alerta": str(alert.public_id)})
    assert not world["customer"].product_alerts.exists()
