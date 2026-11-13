"""Read-side queries for the inventory app.

Selectors return querysets already scoped to what the requesting user may see
(deny by default) and use select_related/prefetch_related to avoid N+1 queries."""

from dataclasses import dataclass

from django.db.models import F

from apps.catalog.models import ProductVariant
from apps.inventory.models import StockItem


@dataclass(frozen=True, slots=True)
class StoreAvailability:
    store: str
    city: str
    available: int
    is_pickup_point: bool


def availability_by_store(variant: ProductVariant) -> list[StoreAvailability]:
    """Units customers can buy per active store (physical minus reserved)."""
    rows = (
        StockItem.objects.filter(variant=variant, store__is_active=True)
        .select_related("store__city")
        .annotate(free=F("quantity") - F("reserved"))
        .order_by("-free", "store__name")
    )
    return [
        StoreAvailability(
            store=row.store.name,
            city=row.store.city.name,
            available=max(row.free, 0),
            is_pickup_point=row.store.is_pickup_point,
        )
        for row in rows
    ]
