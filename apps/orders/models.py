"""Data models for the orders app: orders, snapshot lines, status timeline and invoices.

Orders copy name, SKU, price and address at purchase time, so later catalogue changes never
alter them. The delivery address (with a phone number) is stored encrypted.
"""

from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.crypto import EncryptedTextField
from apps.core.models import BaseModel


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs: Any) -> int:
        raise PermissionError("This history is append-only.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise PermissionError("This history is append-only.")


class Order(BaseModel):
    class Channel(models.TextChoices):
        WEB = "web", _("Tienda en línea")
        POS = "pos", _("Punto de venta")

    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", _("Pendiente de pago")
        PAYMENT_FAILED = "payment_failed", _("Pago rechazado")
        EXPIRED = "expired", _("Vencido sin pago")
        PAID = "paid", _("Pagado")
        PREPARING = "preparing", _("En preparación")
        READY_FOR_PICKUP = "ready_for_pickup", _("Listo para recoger")
        SHIPPED = "shipped", _("Enviado")
        DELIVERED = "delivered", _("Entregado")
        CANCELLED = "cancelled", _("Cancelado")

    class Fulfillment(models.TextChoices):
        SHIPPING = "shipping", _("Envío a domicilio")
        PICKUP = "pickup", _("Recoger en tienda")

    number = models.CharField(_("número"), max_length=20, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    email = models.EmailField(_("correo"), blank=True)
    channel = models.CharField(
        _("canal"), max_length=4, choices=Channel.choices, default=Channel.WEB
    )
    status = models.CharField(
        _("estado"), max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT
    )
    fulfillment = models.CharField(_("entrega"), max_length=10, choices=Fulfillment.choices)
    pickup_store = models.ForeignKey(
        "inventory.Store", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    city = models.ForeignKey(
        "core.City", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    address_snapshot = EncryptedTextField(_("dirección de entrega"), blank=True)
    subtotal = models.DecimalField(_("subtotal"), max_digits=14, decimal_places=2)
    discount_total = models.DecimalField(_("descuento"), max_digits=14, decimal_places=2, default=0)
    shipping_total = models.DecimalField(_("envío"), max_digits=14, decimal_places=2, default=0)
    tax_total = models.DecimalField(_("IVA incluido"), max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(_("total"), max_digits=14, decimal_places=2)
    coupon_code = models.CharField(_("cupón"), max_length=30, blank=True)
    cash_session = models.ForeignKey(
        "pos.CashSession", null=True, blank=True, on_delete=models.PROTECT, related_name="orders"
    )
    sold_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    terms_accepted_at = models.DateTimeField(_("términos aceptados"), null=True, blank=True)
    expires_at = models.DateTimeField(_("vence"), null=True, blank=True)
    paid_at = models.DateTimeField(_("pagado"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("pedido")
        verbose_name_plural = _("pedidos")
        permissions = [
            ("manage_fulfillment", "Puede preparar, despachar y entregar pedidos"),
            ("view_sales_report", "Puede ver los reportes de ventas"),
        ]
        indexes = [models.Index(fields=["status", "expires_at"], name="orders_status_expires")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(subtotal__gte=0)
                & models.Q(discount_total__gte=0)
                & models.Q(shipping_total__gte=0)
                & models.Q(total__gte=0),
                name="orders_amounts_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    total=models.F("subtotal")
                    - models.F("discount_total")
                    + models.F("shipping_total")
                ),
                name="orders_total_consistent",
            ),
            models.CheckConstraint(
                condition=~models.Q(fulfillment="pickup") | models.Q(pickup_store__isnull=False),
                name="orders_pickup_needs_store",
            ),
        ]

    def __str__(self) -> str:
        return self.number

    @property
    def is_open_for_payment(self) -> bool:
        return self.status == self.Status.PENDING_PAYMENT and bool(
            self.expires_at and self.expires_at > timezone.now()
        )


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.PROTECT, related_name="order_lines"
    )
    sku = models.CharField(_("SKU"), max_length=40)
    name = models.CharField(_("producto"), max_length=160)
    variant_label = models.CharField(_("variante"), max_length=255, blank=True)
    quantity = models.PositiveSmallIntegerField(_("cantidad"))
    unit_price = models.DecimalField(
        _("precio unitario (IVA incluido)"), max_digits=14, decimal_places=2
    )
    tax_rate = models.DecimalField(_("tarifa de IVA"), max_digits=4, decimal_places=2)
    line_total = models.DecimalField(_("total de la línea"), max_digits=14, decimal_places=2)

    class Meta:
        ordering = ["pk"]
        verbose_name = _("línea de pedido")
        verbose_name_plural = _("líneas de pedido")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="orders_line_quantity_gte_1"
            ),
            models.CheckConstraint(
                condition=models.Q(line_total=models.F("unit_price") * models.F("quantity")),
                name="orders_line_total_consistent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.sku}"


class OrderStatusEvent(models.Model):
    """Timeline of an order. Append-only."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    note = models.CharField(_("nota"), max_length=255, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(_("fecha"), default=timezone.now)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "pk"]
        verbose_name = _("evento del pedido")
        verbose_name_plural = _("eventos del pedido")

    def __str__(self) -> str:
        return f"{self.order_id}: {self.from_status} → {self.to_status}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise PermissionError("This history is append-only.")
        super().save(*args, **kwargs)


class Invoice(models.Model):
    """Electronic invoice **simulated** for the sandbox (no DIAN validity)."""

    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="invoice")
    number = models.CharField(_("número"), max_length=20, unique=True)
    cufe = models.CharField(_("CUFE (simulado)"), max_length=96, unique=True)
    issued_at = models.DateTimeField(_("emitida"), default=timezone.now)
    is_test = models.BooleanField(_("documento de prueba"), default=True)

    class Meta:
        ordering = ["-issued_at"]
        verbose_name = _("factura")
        verbose_name_plural = _("facturas")

    def __str__(self) -> str:
        return self.number


class ReturnRequest(BaseModel):
    """RMA: right of withdrawal (5 business days, Ley 1480), warranty or commercial return (30 days).

    Whoever approves the refund cannot be the person who registered the receipt (SoD).
    """

    class Kind(models.TextChoices):
        WITHDRAWAL = "withdrawal", _("Retracto (5 días hábiles)")
        COMMERCIAL = "commercial", _("Cambio o devolución comercial (30 días)")
        WARRANTY = "warranty", _("Garantía")

    class Status(models.TextChoices):
        REQUESTED = "requested", _("Solicitada")
        RECEIVED = "received", _("Producto recibido")
        APPROVED = "approved", _("Reembolso aprobado")
        REJECTED = "rejected", _("Rechazada")

    class Refund(models.TextChoices):
        ORIGINAL = "original", _("Al medio de pago original")
        CREDIT = "credit", _("Saldo a favor")

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="returns")
    kind = models.CharField(_("tipo"), max_length=10, choices=Kind.choices)
    reason = models.CharField(_("motivo"), max_length=500)
    refund_method = models.CharField(
        _("reembolso"), max_length=8, choices=Refund.choices, default=Refund.ORIGINAL
    )
    status = models.CharField(
        _("estado"), max_length=10, choices=Status.choices, default=Status.REQUESTED
    )
    refund_amount = models.DecimalField(
        _("valor a reembolsar"), max_digits=14, decimal_places=2, default=0
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    decided_at = models.DateTimeField(_("decidido"), null=True, blank=True)
    decision_note = models.CharField(_("nota de la decisión"), max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("devolución")
        verbose_name_plural = _("devoluciones")
        permissions = [
            ("receive_return", "Puede recibir productos devueltos"),
            ("approve_refund", "Puede aprobar reembolsos"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(refund_amount__gte=0), name="orders_return_refund_gte_0"
            ),
            models.CheckConstraint(
                condition=models.Q(decided_by__isnull=True)
                | models.Q(received_by__isnull=True)
                | ~models.Q(decided_by=models.F("received_by")),
                name="orders_return_sod",
            ),
        ]

    def __str__(self) -> str:
        return f"Devolución {self.order_id} ({self.get_status_display()})"


class ReturnLine(models.Model):
    request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name="lines")
    line = models.ForeignKey(OrderLine, on_delete=models.PROTECT, related_name="returns")
    quantity = models.PositiveSmallIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="orders_return_line_qty_gte_1"
            )
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.line_id}"
