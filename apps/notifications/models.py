"""Customer alerts: back in stock and price drop (sent once, by email, after the change commits)."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class ProductAlert(BaseModel):
    class Kind(models.TextChoices):
        BACK_IN_STOCK = "stock", _("Avísame cuando llegue")
        PRICE_DROP = "price", _("Avísame si baja de precio")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_alerts"
    )
    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.CASCADE, related_name="alerts"
    )
    kind = models.CharField(_("tipo"), max_length=5, choices=Kind.choices)
    price_at_signup = models.DecimalField(
        _("precio al suscribirse"), max_digits=14, decimal_places=2
    )
    notified_at = models.DateTimeField(_("avisado"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("alerta de producto")
        verbose_name_plural = _("alertas de producto")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "variant", "kind"],
                condition=models.Q(notified_at__isnull=True),
                name="notifications_one_pending_alert",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} · {self.variant_id}"
