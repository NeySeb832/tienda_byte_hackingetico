"""Stock counts: validation, reservations, audit and per-store availability."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.audit.models import AuditLog
from apps.inventory.models import StockItem
from apps.inventory.selectors import availability_by_store
from apps.inventory.services import set_stock
from tests.factories import make_product, make_store

pytestmark = pytest.mark.django_db


@pytest.fixture
def variant():
    return make_product("Consola", stock={"SKU-CONSOLA": 0}).variants.get()


def test_set_stock_creates_updates_and_audits(variant):
    store = make_store()
    item = set_stock(variant, store, 4, note="Conteo")
    assert (item.quantity, item.reserved, item.available) == (4, 0, 4)
    set_stock(variant, store, 4)  # unchanged: no extra audit row
    set_stock(variant, store, 2)
    events = AuditLog.objects.filter(action="inventory.stock_set", changes__store=store.code)
    assert [e.changes["to"] for e in events.order_by("pk")] == [4, 2]


@pytest.mark.parametrize("quantity", [-1, 1.5, True, "3"])
def test_set_stock_rejects_invalid_quantities(variant, quantity):
    with pytest.raises(ValidationError):
        set_stock(variant, make_store(), quantity)


def test_cannot_go_below_reserved_units(variant):
    store = make_store()
    item = set_stock(variant, store, 5)
    StockItem.objects.filter(pk=item.pk).update(reserved=3)
    with pytest.raises(ValidationError, match="reservadas"):
        set_stock(variant, store, 2)


def test_database_constraints_protect_stock(variant):
    item = set_stock(variant, make_store(), 2)
    for changes in ({"quantity": -1}, {"reserved": 3}, {"reserved": -1}):
        with pytest.raises(IntegrityError), transaction.atomic():
            StockItem.objects.filter(pk=item.pk).update(**changes)


def test_availability_by_store_skips_inactive_stores(variant):
    open_store, closed_store = make_store(name="Abierta"), make_store(
        name="Cerrada", is_active=False
    )
    set_stock(variant, open_store, 3)
    set_stock(variant, closed_store, 9)
    lines = availability_by_store(variant)
    names = [line.store for line in lines]
    assert "Abierta" in names
    assert "Cerrada" not in names
    assert lines[0].available == 3
