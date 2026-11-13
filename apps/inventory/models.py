"""Data models for the inventory app."""

from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone
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


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs: Any) -> int:
        raise PermissionError("The stock ledger is append-only.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise PermissionError("The stock ledger is append-only.")


class StockMovement(models.Model):
    """Kardex: every change of physical units. Append-only (ORM and database trigger)."""

    class Reason(models.TextChoices):
        INITIAL = "initial", _("Inventario inicial")
        ADJUSTMENT = "adjustment", _("Ajuste por conteo")
        SALE = "sale", _("Venta")
        RETURN = "return", _("Devolución")
        PURCHASE = "purchase", _("Compra a proveedor")
        TRANSFER_IN = "transfer_in", _("Traslado recibido")
        TRANSFER_OUT = "transfer_out", _("Traslado enviado")

    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.PROTECT, related_name="stock_movements"
    )
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="stock_movements")
    delta = models.IntegerField(_("unidades"))
    balance = models.IntegerField(_("saldo"))
    reason = models.CharField(_("motivo"), max_length=12, choices=Reason.choices)
    reference = models.CharField(_("referencia"), max_length=64, blank=True)
    note = models.CharField(_("nota"), max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(_("fecha"), default=timezone.now, db_index=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "pk"]
        verbose_name = _("movimiento de inventario")
        verbose_name_plural = _("kardex")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(delta=0), name="inventory_movement_delta_not_0"
            ),
            models.CheckConstraint(
                condition=models.Q(balance__gte=0), name="inventory_movement_balance_gte_0"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.variant_id} @ {self.store_id}: {self.delta:+d}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise PermissionError("The stock ledger is append-only.")
        super().save(*args, **kwargs)


class StockReservation(BaseModel):
    """Units held for an order awaiting payment (TTL ``BYTE_STOCK_RESERVATION_TTL_MINUTES``)."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Activa")
        CONSUMED = "consumed", _("Vendida")
        RELEASED = "released", _("Liberada")

    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.PROTECT, related_name="reservations"
    )
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="reservations")
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="reservations")
    quantity = models.PositiveIntegerField(_("unidades"))
    status = models.CharField(
        _("estado"), max_length=10, choices=Status.choices, default=Status.ACTIVE
    )
    expires_at = models.DateTimeField(_("vence"))

    class Meta:
        ordering = ["pk"]
        verbose_name = _("reserva de stock")
        verbose_name_plural = _("reservas de stock")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="inventory_reservation_qty_gte_1"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.variant_id} ({self.status})"


class InventoryAdjustment(BaseModel):
    """A stock count correction. Whoever requests it cannot approve it (segregation of duties)."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pendiente")
        APPROVED = "approved", _("Aprobado")
        REJECTED = "rejected", _("Rechazado")

    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.PROTECT, related_name="adjustments"
    )
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="adjustments")
    counted_quantity = models.PositiveIntegerField(_("unidades contadas"))
    reason = models.CharField(_("motivo"), max_length=200)
    status = models.CharField(
        _("estado"), max_length=10, choices=Status.choices, default=Status.PENDING
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(_("decidido"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("ajuste de inventario")
        verbose_name_plural = _("ajustes de inventario")
        permissions = [
            ("request_adjustment", "Puede solicitar ajustes de inventario"),
            ("approve_adjustment", "Puede aprobar ajustes de inventario"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(decided_by__isnull=True)
                | ~models.Q(decided_by=models.F("requested_by")),
                name="inventory_adjustment_sod",
            ),
        ]

    def __str__(self) -> str:
        return f"Ajuste {self.variant_id} @ {self.store_id} → {self.counted_quantity}"


class StockTransfer(BaseModel):
    """Units moved between two stores: requested → shipped (leave origin) → received."""

    class Status(models.TextChoices):
        REQUESTED = "requested", _("Solicitado")
        SHIPPED = "shipped", _("En tránsito")
        RECEIVED = "received", _("Recibido")
        CANCELLED = "cancelled", _("Cancelado")

    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.PROTECT, related_name="transfers"
    )
    from_store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="transfers_out")
    to_store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="transfers_in")
    quantity = models.PositiveIntegerField(_("unidades"))
    status = models.CharField(
        _("estado"), max_length=10, choices=Status.choices, default=Status.REQUESTED
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    shipped_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("traslado")
        verbose_name_plural = _("traslados")
        permissions = [("manage_transfers", "Puede gestionar traslados entre sedes")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="inventory_transfer_qty_gte_1"
            ),
            models.CheckConstraint(
                condition=~models.Q(from_store=models.F("to_store")),
                name="inventory_transfer_distinct_stores",
            ),
        ]

    def __str__(self) -> str:
        return f"Traslado {self.quantity} x {self.variant_id}"
