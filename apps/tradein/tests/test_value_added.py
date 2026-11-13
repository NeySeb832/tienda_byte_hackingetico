"""Value-added services: trade-ins, loyalty points and store credit, alerts, repair tickets,
returns with refunds (segregation of duties) and preorders."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts import roles
from apps.accounts.models import StaffStoreAssignment
from apps.cart import services as cart_services
from apps.catalog.models import Product
from apps.inventory.models import StockItem, StockMovement
from apps.inventory.services import set_stock
from apps.notifications import services as alerts
from apps.notifications.models import ProductAlert
from apps.orders import returns
from apps.orders import services as orders
from apps.orders.models import Order, OrderStatusEvent, ReturnRequest
from apps.payments import services as payments
from apps.payments.models import Refund
from apps.pos import services as pos
from apps.pricing.services import change_variant_price
from apps.promotions import services as promotions
from apps.promotions.models import CreditEntry, LoyaltyEntry
from apps.services_desk import services as tickets
from apps.services_desk.models import ServiceTicket
from apps.tradein import services as tradein
from apps.tradein.models import TradeInRequest
from tests.factories import make_product, make_store, make_user, make_user_with_role

pytestmark = pytest.mark.django_db


@pytest.fixture
def store():
    return make_store(name="Bogotá", code="BOG", is_pickup_point=True)


@pytest.fixture
def console(store):
    return make_product(
        "PlayStation 5",
        store=store,
        options={"condition": ["Nuevo", "Usado"]},
        variants=[
            ("PS5-N", {"condition": "Nuevo"}, 2750000),
            ("PS5-U", {"condition": "Usado"}, 2000000),
        ],
    )


def paid_order(user, variant, store):
    cart = cart_services.get_cart({}, user, create=True)
    assert cart is not None
    cart.items.all().delete()
    cart_services.add_item(cart, variant, 1)
    order = orders.place_order(
        user=user,
        cart=cart,
        fulfillment=Order.Fulfillment.PICKUP,
        pickup_store=store,
        accepted_terms=True,
    )
    payment, _ = payments.start_payment(order, redirect_url="/")
    payments.simulate(payment, approve=True)
    order.refresh_from_db()
    return order


def deliver(order, *, days_ago=0):
    orders.transition(order, Order.Status.PREPARING)
    orders.transition(order, Order.Status.READY_FOR_PICKUP)
    if not days_ago:
        orders.transition(order, Order.Status.DELIVERED)
        return
    # Delivered long ago: the timeline is append-only, so the old event is created directly.
    Order.objects.filter(pk=order.pk).update(status=Order.Status.DELIVERED)
    OrderStatusEvent.objects.create(
        order=order,
        from_status=Order.Status.READY_FOR_PICKUP,
        to_status=Order.Status.DELIVERED,
        created_at=timezone.now() - timedelta(days=days_ago),
    )
    order.refresh_from_db()


# --- Trade-ins ------------------------------------------------------------------------------


def test_trade_in_estimate_inspection_and_credit_payout(setup_roles, console, store):
    customer = make_user()
    quote = tradein.request_quote(customer, console, "good", has_box=False, has_controller=True)
    # 45 % of the used reference price (2.000.000) without box (x0.95) → 855.000 → 850.000
    assert quote.estimated_value == Decimal("850000")
    with pytest.raises(ValidationError):
        tradein.answer_offer(quote, user=customer, accept=True, payout="credit")
    with pytest.raises(ValidationError, match="propia retoma"):
        tradein.inspect(quote, inspector=customer, store=store, final_value=800000, notes="")
    technician = make_user_with_role(roles.TECHNICIAN)
    tradein.inspect(
        quote, inspector=technician, store=store, final_value=800000, notes="Rayón en la tapa"
    )
    other = make_user()
    with pytest.raises(ValidationError, match="inválida"):
        tradein.answer_offer(quote, user=other, accept=True, payout="credit")
    paid = tradein.answer_offer(quote, user=customer, accept=True, payout="credit")
    assert paid.status == TradeInRequest.Status.PAID
    assert promotions.credit_balance(customer) == 880000  # +10 % as store credit


def test_trade_in_only_for_consoles(store):
    pad = make_product("Control", store=store, product_type=Product.Type.ACCESSORY)
    with pytest.raises(ValidationError, match="consolas"):
        tradein.request_quote(make_user(), pad, "good", has_box=True, has_controller=True)


# --- Loyalty and store credit ------------------------------------------------------------------


def test_points_are_awarded_once_and_redeemed_for_credit(console, store):
    customer = make_user()
    order = paid_order(customer, console.variants.get(sku="PS5-N"), store)
    assert promotions.points_balance(customer) == 2750
    assert promotions.award_points(order) is None  # idempotent
    promotions.redeem_points(customer, 2)
    assert promotions.points_balance(customer) == 750
    assert promotions.credit_balance(customer) == 20000
    with pytest.raises(ValidationError, match="insuficiente"):
        promotions.redeem_points(customer, 1)
    with pytest.raises(PermissionError):
        LoyaltyEntry.objects.filter(user=customer).update(delta=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        CreditEntry.objects.create(user=customer, delta=-1, balance=-1, reason="spent")


def test_store_credit_pays_in_the_pos(setup_roles, console, store):
    customer = make_user()
    promotions.add_credit(customer, 3000000, CreditEntry.Reason.TRADE_IN)
    seller = make_user_with_role(roles.SELLER)
    session = pos.open_session(store, actor=seller, opening_float=0)
    variant = console.variants.get(sku="PS5-U")
    with pytest.raises(ValidationError, match="correo"):
        pos.sell(session, [(variant, 1)], actor=seller, method=pos.CREDIT)
    order, _ = pos.sell(
        session, [(variant, 1)], actor=seller, method=pos.CREDIT, customer_email=customer.email
    )
    assert order.user == customer
    assert promotions.credit_balance(customer) == 1000000
    assert promotions.points_balance(customer) == 2000
    with pytest.raises(ValidationError, match="saldo suficiente"):
        pos.sell(
            session,
            [(console.variants.get(sku="PS5-N"), 1)],
            actor=seller,
            method=pos.CREDIT,
            customer_email=customer.email,
        )


# --- Alerts -------------------------------------------------------------------------------------


def test_back_in_stock_and_price_drop_alerts(console, store, django_capture_on_commit_callbacks):
    customer = make_user()
    variant = console.variants.get(sku="PS5-N")
    StockItem.objects.filter(variant=variant).update(quantity=0)
    stock_alert = alerts.subscribe(customer, variant, "stock")
    assert alerts.subscribe(customer, variant, "stock") == stock_alert  # no duplicates
    price_alert = alerts.subscribe(customer, variant, "price")
    with django_capture_on_commit_callbacks(execute=True):
        set_stock(variant, store, 3)
    with django_capture_on_commit_callbacks(execute=True):
        change_variant_price(variant, 2700000)
    stock_alert.refresh_from_db()
    price_alert.refresh_from_db()
    assert stock_alert.notified_at is not None
    assert price_alert.notified_at is not None
    assert len(mail.outbox) == 2
    with django_capture_on_commit_callbacks(execute=True):
        change_variant_price(variant, 2600000)
    assert len(mail.outbox) == 2  # each alert fires once
    with pytest.raises(ValidationError):
        alerts.subscribe(customer, variant, "otro")


# --- Repair tickets -----------------------------------------------------------------------------


def test_ticket_lifecycle_and_public_tracking(
    setup_roles, store, django_capture_on_commit_callbacks
):
    technician = make_user_with_role(roles.TECHNICIAN)
    customer = make_user()
    ticket = tickets.open_ticket(
        store=store,
        actor=technician,
        customer_name="Ana",
        customer_email=customer.email.upper(),
        device="DualSense",
        issue="Drift en el joystick izquierdo",
        customer=customer,
    )
    assert ticket.code.startswith("ST-")
    assert tickets.ticket_by_code(ticket.code.lower(), customer.email) == ticket
    assert tickets.ticket_by_code(ticket.code, "otro@correo.co") is None
    with pytest.raises(ValidationError):
        tickets.advance(ticket, ServiceTicket.Status.READY, actor=technician)
    tickets.advance(ticket, ServiceTicket.Status.DIAGNOSING, actor=technician)
    with django_capture_on_commit_callbacks(execute=True):
        tickets.advance(
            ticket,
            ServiceTicket.Status.QUOTED,
            actor=technician,
            diagnosis="Cambio de joystick",
            quote=35000,
        )
    assert "ST-" in mail.outbox[-1].subject
    tickets.answer_quote(ticket, approve=True, actor=customer)
    tickets.advance(ticket, ServiceTicket.Status.READY, actor=technician)
    ticket = tickets.advance(ticket, ServiceTicket.Status.DELIVERED, actor=technician)
    assert ticket.warranty_until == timezone.localdate() + timedelta(days=90)
    assert list(ticket.events.values_list("status", flat=True)) == [
        "received",
        "diagnosing",
        "quoted",
        "repairing",
        "ready",
        "delivered",
    ]


# --- Returns and refunds ------------------------------------------------------------------------


def test_withdrawal_return_with_refund_segregation(setup_roles, console, store):
    customer = make_user()
    variant = console.variants.get(sku="PS5-N")
    order = paid_order(customer, variant, store)
    line = order.lines.get()
    with pytest.raises(ValidationError, match="no ha sido entregado"):
        returns.request_return(
            order, user=customer, quantities={line.pk: 1}, kind="withdrawal", reason="No me gustó"
        )
    deliver(order)
    with pytest.raises(ValidationError, match="Pedido inválido"):
        returns.request_return(
            order, user=make_user(), quantities={line.pk: 1}, kind="withdrawal", reason="x"
        )
    with pytest.raises(ValidationError, match="cantidad"):
        returns.request_return(
            order, user=customer, quantities={line.pk: 2}, kind="withdrawal", reason="x"
        )
    rma = returns.request_return(
        order, user=customer, quantities={line.pk: 1}, kind="withdrawal", reason="No me gustó"
    )
    clerk, manager = make_user_with_role(roles.SELLER), make_user_with_role(roles.MANAGER)
    before = StockItem.objects.get(variant=variant, store=store).quantity
    returns.receive_return(rma, actor=clerk, store=store, restock=True)
    assert StockItem.objects.get(variant=variant, store=store).quantity == before + 1
    assert StockMovement.objects.filter(reason="return", reference=order.number).exists()
    with pytest.raises(ValidationError, match="no puede aprobar"):
        returns.decide_refund(rma, approver=clerk, approve=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        ReturnRequest.objects.filter(pk=rma.pk).update(decided_by=clerk)
    returns.decide_refund(rma, approver=manager, approve=True)
    refund = Refund.objects.get()
    assert refund.amount == Decimal("2750000.00")
    assert (refund.requested_by, refund.approved_by) == (clerk, manager)
    assert promotions.points_balance(customer) == 0  # points of the refunded purchase are reversed


def test_return_deadlines_and_credit_refunds(setup_roles, console, store):
    customer = make_user()
    order = paid_order(customer, console.variants.get(sku="PS5-U"), store)
    deliver(order, days_ago=40)
    line = order.lines.get()
    for kind in ("withdrawal", "commercial"):
        with pytest.raises(ValidationError, match="plazo"):
            returns.request_return(
                order, user=customer, quantities={line.pk: 1}, kind=kind, reason="x"
            )
    rma = returns.request_return(
        order,
        user=customer,
        quantities={line.pk: 1},
        kind="warranty",
        reason="No enciende",
        refund_method="credit",
    )
    returns.receive_return(rma, actor=make_user_with_role(roles.SELLER), store=store, restock=False)
    returns.decide_refund(rma, approver=make_user_with_role(roles.MANAGER), approve=True)
    assert promotions.credit_balance(customer) == 2000000


def test_business_days_skip_weekends():
    friday = date(2026, 11, 13)
    assert returns.add_business_days(friday, 5).isoformat() == "2026-11-20"


# --- Views ---------------------------------------------------------------------------------------


def test_customer_pages(client, setup_roles, console, store):
    customer = make_user()
    client.force_login(customer)
    for name in ("tradein:list", "tradein:points", "tradein:alerts", "tradein:tickets"):
        assert client.get(reverse(name)).status_code == 200
    client.post(
        reverse("tradein:list"),
        {"consola": console.slug, "estado": "excellent", "caja": "on", "control": "on"},
    )
    assert TradeInRequest.objects.get().estimated_value == Decimal("1100000")
    client.post(reverse("tradein:alerts"), {"sku": "PS5-N", "tipo": "price"})
    assert ProductAlert.objects.filter(user=customer).count() == 1
    assert client.get(reverse("tradein:track")).status_code == 200


def test_panel_pages_follow_permissions(client, setup_roles):
    technician = make_user_with_role(roles.TECHNICIAN)
    client.force_login(technician)
    assert client.get(reverse("panel:tickets")).status_code == 200
    assert client.get(reverse("panel:tradeins")).status_code == 200
    assert client.get(reverse("panel:returns")).status_code == 403
    analyst = make_user_with_role(roles.ANALYST)
    client.force_login(analyst)
    for name in ("panel:tickets", "panel:tradeins", "panel:returns"):
        assert client.get(reverse(name)).status_code == 403


def test_ticket_from_another_store_is_hidden(client, setup_roles, store):
    other_store = make_store(name="Medellín", code="MED")
    technician = make_user_with_role(roles.TECHNICIAN)
    StaffStoreAssignment.objects.create(user=technician, store=store)
    ticket = tickets.open_ticket(
        store=other_store,
        actor=None,
        customer_name="X",
        customer_email="x@x.co",
        device="Switch",
        issue="No carga",
    )
    client.force_login(technician)
    assert client.get(reverse("panel:ticket", args=[ticket.public_id])).status_code == 404
