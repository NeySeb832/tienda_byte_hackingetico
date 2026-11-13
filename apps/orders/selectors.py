"""Read-side queries for orders: always scoped to the owner (404 otherwise)."""

import json
from typing import Any

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from apps.accounts.models import User
from apps.orders.models import Order


def orders_for(user: User) -> QuerySet[Order]:
    return Order.objects.filter(user=user).prefetch_related("lines").select_related("pickup_store")


def order_for(user: User, public_id: Any, *, with_invoice: bool = False) -> Order:
    queryset = orders_for(user).prefetch_related("events", "payments").select_related("invoice")
    if with_invoice:
        queryset = queryset.filter(invoice__isnull=False)
    return get_object_or_404(queryset, public_id=public_id)


def address_of(order: Order) -> dict[str, str] | None:
    return json.loads(order.address_snapshot) if order.address_snapshot else None


def timeline(order: Order) -> list[dict[str, Any]]:
    labels = dict(Order.Status.choices)
    return [
        {
            "created_at": event.created_at,
            "label": labels.get(event.to_status, event.to_status),
            "note": event.note,
        }
        for event in order.events.all()
    ]
