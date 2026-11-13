"""Trade-ins: the customer gets an online estimate; the store inspects and makes the final offer."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class TradeInRequest(BaseModel):
    class Condition(models.TextChoices):
        EXCELLENT = "excellent", _("Como nueva: sin rayones, todo funciona")
        GOOD = "good", _("Buen estado: rayones leves, todo funciona")
        FAIR = "fair", _("Uso visible: funciona con detalles menores")

    class Status(models.TextChoices):
        ESTIMATED = "estimated", _("Cotizada en línea")
        INSPECTED = "inspected", _("Oferta final")
        ACCEPTED = "accepted", _("Aceptada")
        REJECTED = "rejected", _("Rechazada")
        PAID = "paid", _("Pagada")

    class Payout(models.TextChoices):
        CREDIT = "credit", _("Saldo a favor (+10 %)")
        CASH = "cash", _("Efectivo")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="trade_ins"
    )
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    condition = models.CharField(_("estado declarado"), max_length=10, choices=Condition.choices)
    has_box = models.BooleanField(_("con caja"), default=False)
    has_controller = models.BooleanField(_("con control original"), default=True)
    estimated_value = models.DecimalField(_("cotización en línea"), max_digits=14, decimal_places=2)
    final_value = models.DecimalField(
        _("oferta final"), max_digits=14, decimal_places=2, null=True, blank=True
    )
    inspection_notes = models.CharField(_("diagnóstico"), max_length=255, blank=True)
    status = models.CharField(
        _("estado"), max_length=10, choices=Status.choices, default=Status.ESTIMATED
    )
    payout = models.CharField(_("forma de pago"), max_length=6, choices=Payout.choices, blank=True)
    store = models.ForeignKey(
        "inventory.Store", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("retoma")
        verbose_name_plural = _("retomas")
        permissions = [("inspect_tradein", "Puede evaluar retomas y hacer la oferta final")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estimated_value__gte=0), name="tradein_estimate_gte_0"
            ),
            models.CheckConstraint(
                condition=models.Q(final_value__isnull=True) | models.Q(final_value__gte=0),
                name="tradein_final_gte_0",
            ),
        ]

    def __str__(self) -> str:
        return f"Retoma {self.product_id} ({self.get_status_display()})"
