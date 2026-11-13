"""Panel pages render with data and their forms reject invalid input without side effects."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts import roles
from apps.accounts.models import StaffStoreAssignment
from apps.inventory import services as inventory
from apps.inventory.models import StockItem, StockTransfer
from apps.pos import services as pos
from apps.promotions.models import Coupon
from apps.purchasing import services as purchasing
from apps.purchasing.models import PurchaseOrder, Supplier
from tests.factories import make_product, make_store, make_user_with_role

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(setup_roles):
    bog, med = make_store(name="Bogotá", code="BOG"), make_store(name="Medellín", code="MED")
    variant = make_product(
        "Control",
        store=bog,
        variants=[("PAD-N", {"condition": "Nuevo"}, 100000)],
        stock={"PAD-N": 5},
    ).variants.get()
    admin = make_user_with_role(roles.ADMIN)
    manager = make_user_with_role(roles.MANAGER)
    for store in (bog, med):
        StaffStoreAssignment.objects.create(user=manager, store=store)
    return {"bog": bog, "med": med, "variant": variant, "admin": admin, "manager": manager}


def test_dashboard_kpis_and_lists(client, world):
    session = pos.open_session(world["bog"], actor=world["manager"], opening_float=0)
    order = pos.sell(session, [(world["variant"], 1)], actor=world["manager"], method=pos.CARD)[0]
    client.force_login(world["admin"])
    dashboard = client.get(reverse("panel:dashboard")).content.decode()
    assert "Ventas de hoy" in dashboard
    orders = client.get(
        reverse("panel:orders"), {"estado": "delivered", "canal": "pos", "q": order.number[:8]}
    )
    assert order.number in orders.content.decode()
    assert (
        "PAD-N" in client.get(reverse("panel:stock"), {"q": "pad", "sede": "BOG"}).content.decode()
    )
    kardex = client.get(reverse("panel:kardex", args=["PAD-N"])).content.decode()
    assert "Venta" in kardex
    report = client.get(reverse("panel:reports")).content.decode()
    assert "Productos más vendidos" in report
    assert "Control" in report
    assert client.get(reverse("panel:kardex", args=["NO-EXISTE"])).status_code == 404


def test_transfer_views(client, world):
    client.force_login(world["manager"])
    client.post(
        reverse("panel:transfers"),
        {"sku": "PAD-N", "origen": "BOG", "destino": "MED", "cantidad": 2},
    )
    transfer = StockTransfer.objects.get()
    client.post(
        reverse("panel:transfer_action", args=[transfer.public_id]), {"accion": "despachar"}
    )
    client.post(reverse("panel:transfer_action", args=[transfer.public_id]), {"accion": "recibir"})
    assert StockItem.objects.get(variant=world["variant"], store=world["med"]).quantity == 2
    bad = client.post(
        reverse("panel:transfers"),
        {"sku": "PAD-N", "origen": "BOG", "destino": "BOG", "cantidad": 1},
    )
    assert bad.status_code == 400


def test_purchase_views_receive_goods(client, world):
    supplier = Supplier.objects.create(name="Proveedor", tax_id="900")
    order = purchasing.create_purchase_order(
        supplier, world["bog"], [(world["variant"], 3, "70000")], actor=world["admin"]
    )
    purchasing.approve_purchase_order(order, approver=world["manager"])
    client.force_login(world["manager"])
    detail = reverse("panel:purchase_order", args=[order.public_id])
    assert order.number in client.get(detail).content.decode()
    line = order.lines.get()
    client.post(detail, {"accion": "recibir", f"linea-{line.pk}": "abc"})
    assert PurchaseOrder.objects.get().status == "approved"  # rejected input, nothing received
    client.post(detail, {"accion": "recibir", f"linea-{line.pk}": "3", "nota": "Factura 123"})
    assert PurchaseOrder.objects.get().status == "received"
    assert StockItem.objects.get(variant=world["variant"], store=world["bog"]).quantity == 8
    bad = client.post(
        reverse("panel:purchase_orders"),
        {"proveedor": "900", "sede": "BOG", "lineas": "formato raro"},
    )
    assert bad.status_code == 400
    client.post(
        reverse("panel:suppliers"),
        {"name": "Nuevo proveedor", "tax_id": "901", "email": "", "phone": ""},
    )
    assert Supplier.objects.filter(tax_id="901").exists()
    assert "Nuevo proveedor" in client.get(reverse("panel:suppliers")).content.decode()


def test_adjustment_rejection_view(client, world):
    clerk = make_user_with_role(roles.WAREHOUSE)
    StaffStoreAssignment.objects.create(user=clerk, store=world["bog"])
    adjustment = inventory.request_adjustment(
        world["variant"], world["bog"], 1, reason="Conteo", actor=clerk
    )
    client.force_login(world["manager"])
    assert "Conteo" in client.get(reverse("panel:adjustments")).content.decode()
    client.post(
        reverse("panel:adjustment_decision", args=[adjustment.public_id]), {"decision": "rechazar"}
    )
    adjustment.refresh_from_db()
    assert adjustment.status == "rejected"
    assert StockItem.objects.get(variant=world["variant"], store=world["bog"]).quantity == 5
    bad = client.post(
        reverse("panel:adjustments"), {"sku": "PAD-N", "sede": "BOG", "cantidad": -1, "motivo": "x"}
    )
    assert bad.status_code == 400


def test_coupon_views_enforce_segregation(client, world):
    client.force_login(world["manager"])
    client.post(
        reverse("panel:coupons"),
        {
            "code": "black-friday",
            "description": "Black Friday",
            "kind": "percent",
            "value": "30",
            "min_subtotal": "0",
            "starts_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "per_user_limit": "1",
        },
    )
    coupon = Coupon.objects.get(code="BLACK-FRIDAY")
    client.post(reverse("panel:coupons"), {"accion": "aprobar", "cupon": str(coupon.public_id)})
    coupon.refresh_from_db()
    assert coupon.approved_by is None  # the creator cannot approve
    client.force_login(world["admin"])
    client.post(reverse("panel:coupons"), {"accion": "aprobar", "cupon": str(coupon.public_id)})
    coupon.refresh_from_db()
    assert coupon.approved_by == world["admin"]
    assert "BLACK-FRIDAY" in client.get(reverse("panel:coupons")).content.decode()


def test_prices_view_schedules_and_validates(client, world):
    client.force_login(world["manager"])
    assert "PAD-N" in client.get(reverse("panel:prices"), {"q": "pad"}).content.decode()
    future = (timezone.localtime() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M")
    client.post(
        reverse("panel:prices"),
        {"sku": "PAD-N", "precio": "90000", "desde": future, "nota": "Promo"},
    )
    assert world["variant"].scheduled_prices.get().new_price == Decimal("90000.00")
    client.post(reverse("panel:prices"), {"sku": "PAD-N", "precio": "-5"})
    world["variant"].refresh_from_db()
    assert world["variant"].price == Decimal("100000.00")


def test_customer_search(client, world, customer):
    client.force_login(world["manager"])
    assert (
        customer.email
        in client.get(reverse("panel:customers"), {"q": customer.email[:6]}).content.decode()
    )


def test_pos_view_errors_are_reported(client, world):
    client.force_login(world["manager"])
    client.post(reverse("panel:pos"), {"accion": "abrir", "sede": "BOG", "base": "0"})
    response = client.post(
        reverse("panel:pos"),
        {"accion": "vender", "productos": "NOPE", "medio": "cash"},
        follow=True,
    )
    assert "Revisa los productos" in response.content.decode()
    response = client.post(reverse("panel:pos"), {"accion": "inventada"}, follow=True)
    assert "Acción no válida" in response.content.decode()
