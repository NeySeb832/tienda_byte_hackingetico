"""Suppliers, purchase orders (approved by someone else) and partial goods receipts."""

from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class Supplier(BaseModel):
    name = models.CharField(_("razón social"), max_length=160, unique=True)
    tax_id = models.CharField(_("NIT"), max_length=20, unique=True)
    email = models.EmailField(_("correo"), blank=True)
    phone = models.CharField(_("teléfono"), max_length=30, blank=True)
    is_active = models.BooleanField(_("activo"), default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("proveedor")
        verbose_name_plural = _("proveedores")

    def __str__(self) -> str:
        return self.name


class PurchaseOrder(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Por aprobar")
        APPROVED = "approved", _("Aprobada")
        PARTIAL = "partial", _("Recibida parcialmente")
        RECEIVED = "received", _("Recibida")
        CANCELLED = "cancelled", _("Cancelada")

    number = models.CharField(_("número"), max_length=20, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    store = models.ForeignKey(
        "inventory.Store", on_delete=models.PROTECT, related_name="purchase_orders"
    )
    status = models.CharField(
        _("estado"), max_length=10, choices=Status.choices, default=Status.DRAFT
    )
    notes = models.CharField(_("notas"), max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(_("aprobada"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("orden de compra")
        verbose_name_plural = _("órdenes de compra")
        permissions = [
            ("approve_purchaseorder", "Puede aprobar órdenes de compra"),
            ("receive_purchaseorder", "Puede recibir mercancía"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(approved_by__isnull=True)
                | ~models.Q(approved_by=models.F("created_by")),
                name="purchasing_po_sod",
            ),
        ]

    def __str__(self) -> str:
        return self.number

    @property
    def total(self) -> Any:
        return sum((line.quantity * line.unit_cost for line in self.lines.all()), 0)


class PurchaseOrderLine(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="lines"
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.PROTECT, related_name="+"
    )
    quantity = models.PositiveIntegerField(_("cantidad"))
    received_quantity = models.PositiveIntegerField(_("recibido"), default=0)
    unit_cost = models.DecimalField(_("costo unitario"), max_digits=14, decimal_places=2)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="purchasing_line_qty_gte_1"
            ),
            models.CheckConstraint(
                condition=models.Q(received_quantity__lte=models.F("quantity")),
                name="purchasing_line_received_lte_qty",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_cost__gt=0), name="purchasing_line_cost_gt_0"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.variant_id}"

    @property
    def pending(self) -> int:
        return self.quantity - self.received_quantity


class GoodsReceipt(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.PROTECT, related_name="receipts"
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    received_at = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-received_at"]
        verbose_name = _("recepción de mercancía")
        verbose_name_plural = _("recepciones de mercancía")

    def __str__(self) -> str:
        return f"Recepción {self.pk} de {self.purchase_order_id}"


class GoodsReceiptLine(models.Model):
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="lines")
    line = models.ForeignKey(PurchaseOrderLine, on_delete=models.PROTECT, related_name="receipts")
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="purchasing_receipt_qty_gte_1"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.line_id}"
