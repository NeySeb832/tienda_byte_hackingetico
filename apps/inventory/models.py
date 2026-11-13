"""Data models for the inventory app."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel, City


class Store(BaseModel):
    """A physical store or warehouse. Staff permissions are scoped by store."""

    class Kind(models.TextChoices):
        STORE = "store", _("Tienda")
        WAREHOUSE = "warehouse", _("Bodega")

    code = models.CharField(_("código"), max_length=12, unique=True)
    name = models.CharField(_("nombre"), max_length=120)
    kind = models.CharField(_("tipo"), max_length=12, choices=Kind.choices, default=Kind.STORE)
    city = models.ForeignKey(City, on_delete=models.PROTECT, verbose_name=_("ciudad"))
    address = models.CharField(_("dirección"), max_length=200)
    is_pickup_point = models.BooleanField(_("punto de recogida"), default=True)
    is_active = models.BooleanField(_("activa"), default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("sede")
        verbose_name_plural = _("sedes")

    def __str__(self) -> str:
        return self.name


class StockItem(models.Model):
    """Units of a variant in one store. ``reserved`` units are held by open carts/orders.

    Changes always go through ``apps.inventory.services`` inside ``transaction.atomic()``
    with ``select_for_update()``; the CHECK constraints are the last line of defence.
    """

    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.CASCADE, related_name="stock_items"
    )
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="stock_items")
    quantity = models.IntegerField(_("unidades"), default=0)
    reserved = models.IntegerField(_("reservadas"), default=0)
    updated_at = models.DateTimeField(_("actualizado"), auto_now=True)

    class Meta:
        ordering = ["store__name"]
        verbose_name = _("existencia")
        verbose_name_plural = _("existencias")
        constraints = [
            models.UniqueConstraint(fields=["variant", "store"], name="inventory_stock_unique"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0), name="inventory_stock_quantity_gte_0"
            ),
            models.CheckConstraint(
                condition=models.Q(reserved__gte=0) & models.Q(reserved__lte=models.F("quantity")),
                name="inventory_stock_reserved_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.variant_id} @ {self.store_id}: {self.quantity}"

    @property
    def available(self) -> int:
        return self.quantity - self.reserved
