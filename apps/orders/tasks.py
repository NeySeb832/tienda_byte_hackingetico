"""Celery tasks of the orders app (JSON arguments only, ADR-0009)."""

from celery import shared_task

from apps.orders.services import expire_unpaid_orders as expire


@shared_task(name="orders.expire_unpaid_orders")
def expire_unpaid_orders() -> int:
    return expire()
