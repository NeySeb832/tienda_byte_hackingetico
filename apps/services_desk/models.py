"""Technical service: catalogue of services and repair tickets with a public tracking code."""

from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class TechnicalService(models.Model):
    name = models.CharField(_("servicio"), max_length=120)
    detail = models.CharField(_("detalle"), max_length=200, blank=True)
    price = models.DecimalField(_("precio (IVA incluido)"), max_digits=14, decimal_places=2)
    estimated_days = models.PositiveSmallIntegerField(_("días estimados"), default=2)
    is_active = models.BooleanField(_("activo"), default=True)
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort", "name"]
        verbose_name = _("servicio técnico")
        verbose_name_plural = _("servicios técnicos")
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gt=0), name="services_price_gt_0")
        ]

    def __str__(self) -> str:
        return self.name


class ServiceTicket(BaseModel):
    class Status(models.TextChoices):
        RECEIVED = "received", _("Recibido")
        DIAGNOSING = "diagnosing", _("En diagnóstico")
        QUOTED = "quoted", _("Cotizado, esperando aprobación")
        REPAIRING = "repairing", _("En reparación")
        READY = "ready", _("Listo para entregar")
        DELIVERED = "delivered", _("Entregado")
        CANCELLED = "cancelled", _("Cancelado")

    code = models.CharField(_("código de seguimiento"), max_length=12, unique=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="service_tickets",
    )
    customer_name = models.CharField(_("cliente"), max_length=120)
    customer_email = models.EmailField(_("correo"))
    store = models.ForeignKey(
        "inventory.Store", on_delete=models.PROTECT, related_name="service_tickets"
    )
    service = models.ForeignKey(
        TechnicalService, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    device = models.CharField(_("equipo"), max_length=120)
    serial_number = models.CharField(_("serial"), max_length=60, blank=True)
    issue = models.TextField(_("falla reportada"), max_length=1000)
    diagnosis = models.TextField(_("diagnóstico"), max_length=1000, blank=True)
    quote = models.DecimalField(
        _("cotización"), max_digits=14, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        _("estado"), max_length=12, choices=Status.choices, default=Status.RECEIVED
    )
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    warranty_until = models.DateField(_("garantía hasta"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("orden de servicio")
        verbose_name_plural = _("órdenes de servicio")
        permissions = [("manage_tickets", "Puede gestionar órdenes de servicio técnico")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quote__isnull=True) | models.Q(quote__gte=0),
                name="services_quote_gte_0",
            )
        ]

    def __str__(self) -> str:
        return self.code


class TicketEvent(models.Model):
    """Timeline of a ticket (append-only)."""

    ticket = models.ForeignKey(ServiceTicket, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=12)
    note = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self) -> str:
        return f"{self.ticket_id}: {self.status}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise PermissionError("The ticket timeline is append-only.")
        super().save(*args, **kwargs)
