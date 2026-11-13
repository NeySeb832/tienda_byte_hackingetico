"""Celery tasks of the pricing app (JSON-serialisable arguments only, ADR-0009)."""

from celery import shared_task

from apps.pricing.services import apply_due_price_changes


@shared_task(name="pricing.apply_scheduled_price_changes")
def apply_scheduled_price_changes() -> int:
    """Run by Celery Beat every few minutes (see ``CELERY_BEAT_SCHEDULE``)."""
    return apply_due_price_changes()
