"""Back office: adjustments and purchases with segregation of duties, transfers, POS, orders,
CRM, prices, coupons and reports. Access is denied by default and scoped by store."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.accounts import roles
from apps.accounts.models import StaffStoreAssignment
from apps.analytics.selectors import safe_cell, to_csv
from apps.audit.models import AuditLog
from apps.inventory import services as inventory
from apps.inventory.models import InventoryAdjustment, StockItem, StockMovement, StockTransfer
from apps.orders.models import Order
from apps.pos import services as pos
from apps.purchasing import services as purchasing
from apps.purchasing.models import PurchaseOrder, Supplier
from tests.factories import make_product, make_store, make_user_with_role

pytestmark = pytest.mark.django_db


@pytest.fixture
def stores():
    return make_store(name="Bogotá", code="BOG"), make_store(name="Medellín", code="MED")


@pytest.fixture
def variant(stores):
    return make_product(
        "Control",
        store=stores[0],
        variants=[("PAD-N", {"condition": "Nuevo"}, 100000)],
        stock={"PAD-N": 5},
    ).variants.get()


def staff(role, *stores):
    user = make_user_with_role(role)
    for store in stores:
        StaffStoreAssignment.objects.create(user=user, store=store)
    return user


def stock(variant, store):
    return StockItem.objects.get_or_create(variant=variant, store=store)[0]


# --- Services ----------------------------------------------------------------------------------


def test_adjustment_needs_a_second_person(setup_roles, stores, variant):
    clerk, manager = staff(roles.WAREHOUSE, stores[0]), staff(roles.MANAGER, stores[0])
    adjustment = inventory.request_adjustment(
        variant, stores[0], 3, reason="Conteo físico", actor=clerk
    )
    with pytest.raises(ValidationError, match="no puede aprobarlo"):
        inventory.decide_adjustment(adjustment, approver=clerk, approve=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        InventoryAdjustment.objects.filter(pk=adjustment.pk).update(decided_by=clerk)
    inventory.decide_adjustment(adjustment, approver=manager, approve=True)
    assert stock(variant, stores[0]).quantity == 3
    assert StockMovement.objects.filter(reason="adjustment", delta=-2).exists()
    with pytest.raises(ValidationError, match="ya fue decidido"):
        inventory.decide_adjustment(adjustment, approver=manager, approve=False)


def test_transfer_moves_units_through_the_kardex(setup_roles, stores, variant):
    user = staff(roles.WAREHOUSE, *stores)
    transfer = inventory.request_transfer(variant, stores[0], stores[1], 2, actor=user)
    with pytest.raises(ValidationError, match="no está en tránsito"):
        inventory.receive_transfer(transfer, actor=user)
    inventory.ship_transfer(transfer, actor=user)
    assert stock(variant, stores[0]).quantity == 3
    inventory.receive_transfer(transfer, actor=user)
    assert stock(variant, stores[1]).quantity == 2
    reasons = set(StockMovement.objects.values_list("reason", flat=True))
    assert {"transfer_out", "transfer_in"} <= reasons
    with pytest.raises(ValidationError):
        inventory.request_transfer(variant, stores[0], stores[0], 1, actor=user)
    big = inventory.request_transfer(variant, stores[0], stores[1], 99, actor=user)
    with pytest.raises(ValidationError):
        inventory.ship_transfer(big, actor=user)


def test_purchase_order_flow(setup_roles, stores, variant):
    buyer, manager = staff(roles.MANAGER, stores[0]), staff(roles.ADMIN)
    supplier = Supplier.objects.create(name="Distribuidora", tax_id="900123456-1")
    order = purchasing.create_purchase_order(
        supplier, stores[0], [(variant, 4, "80000")], actor=buyer
    )
    assert order.number.startswith("OC-")
    with pytest.raises(ValidationError, match="no está aprobada"):
        purchasing.receive_goods(order, {order.lines.get().pk: 1}, actor=buyer)
    with pytest.raises(ValidationError, match="no puede aprobarla"):
        purchasing.approve_purchase_order(order, approver=buyer)
    purchasing.approve_purchase_order(order, approver=manager)
    line = order.lines.get()
    purchasing.receive_goods(order, {line.pk: 1}, actor=buyer)
    assert PurchaseOrder.objects.get(pk=order.pk).status == "partial"
    with pytest.raises(ValidationError, match="supera"):
        purchasing.receive_goods(order, {line.pk: 4}, actor=buyer)
    purchasing.receive_goods(order, {line.pk: 3}, actor=buyer)
    assert PurchaseOrder.objects.get(pk=order.pk).status == "received"
    assert stock(variant, stores[0]).quantity == 9
    assert StockMovement.objects.filter(reason="purchase", reference=order.number).count() == 2
    with pytest.raises(ValidationError):
        purchasing.create_purchase_order(supplier, stores[0], [(variant, 1, 0)], actor=buyer)


def test_pos_sale_and_cash_closing(setup_roles, stores, variant):
    seller = staff(roles.SELLER, stores[0])
    session = pos.open_session(stores[0], actor=seller, opening_float=200000)
    with pytest.raises(ValidationError, match="Ya tienes un turno"):
        pos.open_session(stores[0], actor=seller, opening_float=0)
    with pytest.raises(ValidationError, match="no alcanza"):
        pos.sell(session, [(variant, 1)], actor=seller, method=pos.CASH, cash_received=50000)
    order, change = pos.sell(
        session, [(variant, 2)], actor=seller, method=pos.CASH, cash_received=250000
    )
    assert change == Decimal("50000.00")
    assert order.channel == Order.Channel.POS
    assert order.status == Order.Status.DELIVERED
    assert order.invoice.number
    assert stock(variant, stores[0]).quantity == 3
    pos.sell(session, [(variant, 1)], actor=seller, method=pos.CARD)
    other = staff(roles.SELLER, stores[0])
    with pytest.raises(ValidationError, match="Abre tu turno"):
        pos.sell(session, [(variant, 1)], actor=other, method=pos.CARD)
    with pytest.raises(ValidationError, match="Solo quien abrió"):
        pos.close_session(session, actor=other, counted_cash=0)
    closed = pos.close_session(session, actor=seller, counted_cash=395000)
    assert closed.expected_cash == Decimal("400000.00")  # card sales are not cash
    assert closed.difference == Decimal("-5000.00")
    with pytest.raises(ValidationError):
        pos.sell(closed, [(variant, 1)], actor=seller, method=pos.CASH, cash_received=1000000)


def test_csv_cells_cannot_become_formulas():
    assert safe_cell("=HYPERLINK(1)") == "'=HYPERLINK(1)"
    assert safe_cell("+1") == "'+1"
    assert safe_cell("Normal") == "Normal"
    assert to_csv(["a"], [["@SUM(A1)"]]).splitlines()[1] == "'@SUM(A1)"


# --- Views: access control and scoping ---------------------------------------------------------

PAGES = [
    ("panel:orders", (), "orders.view_order"),
    ("panel:stock", (), "inventory.view_stockitem"),
    ("panel:adjustments", (), "inventory.request_adjustment"),
    ("panel:transfers", (), "inventory.manage_transfers"),
    ("panel:purchase_orders", (), "purchasing.view_purchaseorder"),
    ("panel:suppliers", (), "purchasing.view_supplier"),
    ("panel:pos", (), "pos.use_pos"),
    ("panel:customers", (), "accounts.view_customers"),
    ("panel:prices", (), "pricing.change_price"),
    ("panel:coupons", (), "promotions.view_coupon"),
    ("panel:reports", (), "orders.view_sales_report"),
]


@pytest.mark.security
@pytest.mark.parametrize("role", roles.STAFF_ROLES)
@pytest.mark.parametrize(("name", "args", "permission"), PAGES)
def test_panel_pages_follow_the_role_matrix(client, setup_roles, role, name, args, permission):
    user = make_user_with_role(role)
    client.force_login(user)
    status = client.get(reverse(name, args=args)).status_code
    assert status == (
        200 if permission in roles.ROLE_PERMISSIONS[role] or role == roles.SUPERADMIN else 403
    )


@pytest.mark.security
def test_customers_cannot_open_the_panel(client, customer):
    client.force_login(customer)
    for name, args, _ in PAGES:
        assert client.get(reverse(name, args=args)).status_code == 403


@pytest.mark.security
def test_stock_and_orders_are_scoped_to_the_staff_stores(client, setup_roles, stores, variant):
    other = make_product(
        "Otro", store=stores[1], variants=[("OTRO-N", {"condition": "Nuevo"}, 50000)]
    ).variants.get()
    seller = staff(roles.SELLER, stores[0])
    client.force_login(seller)
    html = client.get(reverse("panel:stock")).content.decode()
    assert "PAD-N" in html
    assert "OTRO-N" not in html
    session = pos.open_session(stores[1], actor=make_user_with_role(roles.SELLER), opening_float=0)
    foreign = pos.sell(session, [(other, 1)], actor=session.opened_by, method=pos.CARD)[0]
    assert client.get(reverse("panel:order_detail", args=[foreign.public_id])).status_code == 404
    transfer = StockTransfer.objects.create(
        variant=other, from_store=stores[1], to_store=stores[0], quantity=1
    )
    client.force_login(staff(roles.WAREHOUSE, stores[0]))
    response = client.post(
        reverse("panel:transfer_action", args=[transfer.public_id]), {"accion": "despachar"}
    )
    assert response.status_code == 404  # only the origin store ships


def test_order_fulfillment_from_the_panel(client, setup_roles, stores, variant):
    seller = staff(roles.SELLER, stores[0])
    session = pos.open_session(stores[0], actor=seller, opening_float=0)
    order = pos.sell(session, [(variant, 1)], actor=seller, method=pos.CARD)[0]
    client.force_login(seller)
    page = client.get(reverse("panel:order_detail", args=[order.public_id]))
    assert order.number in page.content.decode()
    response = client.post(
        reverse("panel:order_detail", args=[order.public_id]), {"estado": "shipped"}
    )
    assert response.status_code == 302
    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERED  # invalid transition ignored


def test_customer_detail_is_audited(client, setup_roles, customer):
    manager = make_user_with_role(roles.MANAGER)
    client.force_login(manager)
    assert (
        client.get(reverse("panel:customer_detail", args=[customer.public_id])).status_code == 200
    )
    assert AuditLog.objects.filter(
        action="crm.customer_viewed", target_id=str(customer.public_id)
    ).exists()
    assert client.get(reverse("panel:customer_detail", args=[manager.public_id])).status_code == 404


def test_pos_and_prices_views(client, setup_roles, stores, variant):
    manager = staff(roles.MANAGER, stores[0])
    client.force_login(manager)
    client.post(reverse("panel:pos"), {"accion": "abrir", "sede": "BOG", "base": "100000"})
    client.post(
        reverse("panel:pos"),
        {"accion": "vender", "productos": "pad-n x 2", "medio": "cash", "recibido": "200000"},
    )
    assert stock(variant, stores[0]).quantity == 3
    client.post(reverse("panel:pos"), {"accion": "cerrar", "contado": "300000"})
    client.post(
        reverse("panel:prices"), {"sku": "PAD-N", "precio": "95000", "nota": "Ajuste de mercado"}
    )
    variant.refresh_from_db()
    assert variant.price == Decimal("95000.00")
    response = client.get(reverse("panel:reports") + "?formato=csv")
    assert response["Content-Type"].startswith("text/csv")
    assert "fecha,pedidos,total" in response.content.decode()


def test_adjustment_and_purchase_views(client, setup_roles, stores, variant):
    clerk = staff(roles.WAREHOUSE, stores[0])
    client.force_login(clerk)
    client.post(
        reverse("panel:adjustments"),
        {"sku": "PAD-N", "sede": "BOG", "cantidad": 4, "motivo": "Conteo"},
    )
    adjustment = InventoryAdjustment.objects.get()
    response = client.post(
        reverse("panel:adjustment_decision", args=[adjustment.public_id]), {"decision": "aprobar"}
    )
    assert response.status_code == 403  # warehouse cannot approve
    manager = staff(roles.MANAGER, stores[0])
    client.force_login(manager)
    client.post(
        reverse("panel:adjustment_decision", args=[adjustment.public_id]), {"decision": "aprobar"}
    )
    assert stock(variant, stores[0]).quantity == 4
    Supplier.objects.create(name="Proveedor", tax_id="900")
    client.post(
        reverse("panel:purchase_orders"),
        {"proveedor": "900", "sede": "BOG", "lineas": "PAD-N x 3 @ 70000", "notas": ""},
    )
    order = PurchaseOrder.objects.get()
    client.post(reverse("panel:purchase_order", args=[order.public_id]), {"accion": "aprobar"})
    assert PurchaseOrder.objects.get().status == "draft"  # creator cannot approve
