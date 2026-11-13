"""Product alerts: customers subscribe; changes in stock or price notify them once, after commit."""

from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.catalog.models import ProductVariant
from apps.notifications.models import ProductAlert

MAX_PENDING_ALERTS = 20


def subscribe(user: Any, variant: ProductVariant, kind: str) -> ProductAlert:
    if kind not in ProductAlert.Kind.values:
        raise ValidationError("Tipo de alerta inválido.")
    if ProductAlert.objects.filter(user=user, notified_at=None).count() >= MAX_PENDING_ALERTS:
        raise ValidationError(f"Puedes tener hasta {MAX_PENDING_ALERTS} alertas activas.")
    try:
        with transaction.atomic():
            return ProductAlert.objects.create(
                user=user, variant=variant, kind=kind, price_at_signup=variant.price
            )
    except IntegrityError:  # already subscribed
        return ProductAlert.objects.get(user=user, variant=variant, kind=kind, notified_at=None)


def unsubscribe(user: Any, public_id: Any) -> None:
    ProductAlert.objects.filter(user=user, public_id=public_id, notified_at=None).delete()


def stock_became_available(variant_id: int) -> None:
    """Called after a stock increase; the task decides whether anything changed."""
    from apps.notifications.tasks import process_alerts

    transaction.on_commit(lambda: process_alerts.delay(variant_id))


def price_changed(variant_id: int) -> None:
    from apps.notifications.tasks import process_alerts

    transaction.on_commit(lambda: process_alerts.delay(variant_id))
