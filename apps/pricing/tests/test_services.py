"""Price engine: manual, recalculated and scheduled changes; append-only history."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.catalog.models import Product, ProductOptionValue
from apps.pricing import services
from apps.pricing.models import PriceHistory, ScheduledPriceChange
from apps.pricing.tasks import apply_scheduled_price_changes
from tests.factories import make_product, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def variant():
    return make_product(
        "Consola", variants=[("CONSOLA-N", {"condition": "Nuevo"}, 1000000)]
    ).variants.get()


def test_manual_change_writes_history_and_audit(variant):
    actor = make_user()
    entry = services.change_variant_price(variant, 950000, actor=actor, note="Ajuste")
    assert entry is not None
    variant.refresh_from_db()
    assert variant.price == variant.price_override == Decimal("950000.00")
    assert entry.previous_price == Decimal("1000000.00")
    assert entry.reason == PriceHistory.Reason.MANUAL
    assert entry.changed_by == actor
    assert AuditLog.objects.filter(action="pricing.price_changed").count() == 1


def test_same_price_is_a_no_op(variant):
    assert services.change_variant_price(variant, "1000000") is None
    assert variant.price_history.count() == 1


@pytest.mark.parametrize("price", [0, -1, "abc"])
def test_invalid_prices_are_rejected(variant, price):
    with pytest.raises((ValidationError, ValueError)):
        services.change_variant_price(variant, price)


def test_recalculate_after_changing_a_modifier():
    product = make_product(
        "Series S",
        mode=Product.PricingMode.MODIFIERS,
        base=1800000,
        options={"storage": [("512 GB", 0), ("1 TB", 50000)], "condition": ["Nuevo"]},
        variants=[
            ("XSS-512", {"storage": "512 GB", "condition": "Nuevo"}, None),
            ("XSS-1TB", {"storage": "1 TB", "condition": "Nuevo"}, None),
        ],
    )
    pinned = product.variants.get(sku="XSS-512")
    services.change_variant_price(pinned, 1790000)
    ProductOptionValue.objects.filter(value__slug="1-tb").update(price_modifier=80000)
    Product.objects.filter(pk=product.pk).update(base_price=1850000)
    product.refresh_from_db()
    assert services.recalculate_product_prices(product) == 1
    prices = dict(product.variants.values_list("sku", "price"))
    assert prices == {"XSS-512": Decimal("1790000.00"), "XSS-1TB": Decimal("1930000.00")}
    entry = product.variants.get(sku="XSS-1TB").price_history.last()
    assert entry is not None
    assert entry.reason == PriceHistory.Reason.RECALCULATED
    assert services.recalculate_product_prices(product) == 0


def test_recalculate_ignores_fixed_mode(variant):
    assert services.recalculate_product_prices(variant.product) == 0


def test_compute_variant_price_in_fixed_mode_needs_override(variant):
    variant.price_override = None
    with pytest.raises(ValidationError):
        services.compute_variant_price(variant)


def test_schedule_validation(variant):
    with pytest.raises(ValidationError, match="futura"):
        services.schedule_price_change(variant, 900000, timezone.now() - timedelta(minutes=1))
    with pytest.raises(ValidationError, match="zona horaria"):
        services.schedule_price_change(variant, 900000, timezone.now().replace(tzinfo=None))
    with pytest.raises(ValidationError):
        services.schedule_price_change(variant, 0, timezone.now() + timedelta(days=1))


def test_scheduled_changes_apply_only_when_due(variant):
    actor = make_user()
    soon = services.schedule_price_change(
        variant, 900000, timezone.now() + timedelta(hours=1), actor=actor
    )
    later = services.schedule_price_change(variant, 800000, timezone.now() + timedelta(days=2))
    cancelled = services.schedule_price_change(variant, 700000, timezone.now() + timedelta(hours=2))
    services.cancel_scheduled_change(cancelled)
    with pytest.raises(ValidationError):
        services.cancel_scheduled_change(cancelled)

    assert services.apply_due_price_changes() == 0
    assert services.apply_due_price_changes(now=timezone.now() + timedelta(hours=3)) == 1
    variant.refresh_from_db()
    assert variant.price == Decimal("900000.00")
    soon.refresh_from_db()
    later.refresh_from_db()
    assert soon.status == ScheduledPriceChange.Status.APPLIED
    assert soon.applied_at is not None
    assert later.status == ScheduledPriceChange.Status.PENDING
    entry = variant.price_history.last()
    assert entry is not None
    assert entry.reason == PriceHistory.Reason.SCHEDULED
    assert entry.changed_by == actor
    # Idempotent: applied changes are not applied twice.
    assert services.apply_due_price_changes(now=timezone.now() + timedelta(hours=3)) == 0


def test_beat_task_runs_the_service(variant):
    ScheduledPriceChange.objects.create(
        variant=variant,
        new_price=Decimal("990000"),
        starts_at=timezone.now() - timedelta(minutes=5),
    )
    assert apply_scheduled_price_changes.delay().get() == 1


def test_price_history_is_append_only_in_the_orm(variant):
    entry = variant.price_history.get()
    entry.note = "editado"
    with pytest.raises(PermissionError):
        entry.save()
    with pytest.raises(PermissionError):
        entry.delete()
    with pytest.raises(PermissionError):
        PriceHistory.objects.filter(pk=entry.pk).update(price=1)
    with pytest.raises(PermissionError):
        PriceHistory.objects.all().delete()


def test_price_history_is_append_only_in_the_database(variant):
    entry = variant.price_history.get()
    for sql in (
        "UPDATE pricing_pricehistory SET price = 1 WHERE id = %s",
        "DELETE FROM pricing_pricehistory WHERE id = %s",
    ):
        with (
            pytest.raises(DatabaseError, match="append-only"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(sql, [entry.pk])


def test_removing_the_author_keeps_the_history(variant):
    actor = make_user()
    services.change_variant_price(variant, 950000, actor=actor)
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE pricing_pricehistory SET changed_by_id = NULL WHERE changed_by_id = %s",
            [actor.pk],
        )
    assert variant.price_history.filter(changed_by=None).count() == 2
