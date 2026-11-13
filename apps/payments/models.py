"""Data models for the payments app (ADR-0007).

Only gateway references and statuses are stored: never card data.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class Payment(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pendiente")
        APPROVED = "approved", _("Aprobado")
        DECLINED = "declined", _("Rechazado")
        VOIDED = "voided", _("Anulado")
        ERROR = "error", _("Error")

    FINAL = (Status.APPROVED, Status.DECLINED, Status.VOIDED, Status.ERROR)

    order = models.ForeignKey("orders.Order", on_delete=models.PROTECT, related_name="payments")
    reference = models.CharField(_("referencia"), max_length=64, unique=True)
    gateway = models.CharField(_("pasarela"), max_length=20)
    gateway_txn_id = models.CharField(_("transacción en la pasarela"), max_length=64, blank=True)
    amount = models.DecimalField(_("monto"), max_digits=14, decimal_places=2)
    currency = models.CharField(_("moneda"), max_length=3, default="COP")
    status = models.CharField(
        _("estado"), max_length=10, choices=Status.choices, default=Status.PENDING
    )
    status_message = models.CharField(_("detalle"), max_length=255, blank=True)
    approved_at = models.DateTimeField(_("aprobado"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("pago")
        verbose_name_plural = _("pagos")
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="payments_amount_gt_0"),
        ]

    def __str__(self) -> str:
        return self.reference


class WebhookEvent(models.Model):
    """Every gateway notification received, valid or not. ``event_id`` makes them idempotent."""

    gateway = models.CharField(max_length=20)
    event_id = models.CharField(max_length=128, unique=True)
    event_type = models.CharField(max_length=60, blank=True)
    signature_valid = models.BooleanField(default=False)
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    result = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-received_at"]
        verbose_name = _("evento de la pasarela")
        verbose_name_plural = _("eventos de la pasarela")

    def __str__(self) -> str:
        return self.event_id


class Refund(BaseModel):
    """Money returned to the original payment. Requested and approved by different people."""

    class Status(models.TextChoices):
        APPROVED = "approved", _("Aprobado")
        PENDING_GATEWAY = "pending_gateway", _("Pendiente en la pasarela")
        COMPLETED = "completed", _("Completado")

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refunds")
    amount = models.DecimalField(_("valor"), max_digits=14, decimal_places=2)
    status = models.CharField(_("estado"), max_length=16, choices=Status.choices)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("reembolso")
        verbose_name_plural = _("reembolsos")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="payments_refund_amount_gt_0"
            ),
            models.CheckConstraint(
                condition=models.Q(approved_by__isnull=True)
                | models.Q(requested_by__isnull=True)
                | ~models.Q(approved_by=models.F("requested_by")),
                name="payments_refund_sod",
            ),
        ]

    def __str__(self) -> str:
        return f"Reembolso {self.amount} de {self.payment_id}"
