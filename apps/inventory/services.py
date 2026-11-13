"""Business logic (write side) for the inventory app.

Services are the only place allowed to change domain state: they validate
business rules, run inside transactions and record audit events.

Stock rows are always locked with ``select_for_update()`` inside ``transaction.atomic()``;
when several rows are touched they are locked in primary-key order to avoid deadlocks.
The movement ledger (kardex) and transfers between stores arrive with the panel.
"""

from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.services import record_event
from apps.catalog.models import ProductVariant
from apps.inventory.models import StockItem, Store


@transaction.atomic
def set_stock(
    variant: ProductVariant, store: Store, quantity: int, *, actor: Any = None, note: str = ""
) -> StockItem:
    """Set the physical units of a variant in a store (stock count)."""
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
        raise ValidationError("La cantidad debe ser un entero mayor o igual a cero.")
    StockItem.objects.get_or_create(variant=variant, store=store)
    item = StockItem.objects.select_for_update().get(variant=variant, store=store)
    if quantity < item.reserved:
        raise ValidationError("No se puede dejar menos unidades que las reservadas.")
    previous = item.quantity
    if previous == quantity:
        return item
    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    record_event(
        "inventory.stock_set",
        actor=actor,
        target=item,
        changes={
            "sku": variant.sku,
            "store": store.code,
            "from": previous,
            "to": quantity,
            "note": note[:120],
        },
    )
    return item
