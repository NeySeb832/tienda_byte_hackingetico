"""Data models for the shipping app: national rates by zone (groups of departments)."""

from django.db import models
from django.utils.translation import gettext_lazy as _


class ShippingZone(models.Model):
    name = models.CharField(_("nombre"), max_length=80, unique=True)
    departments = models.ManyToManyField(
        "core.Department", related_name="shipping_zones", verbose_name=_("departamentos")
    )
    price = models.DecimalField(_("tarifa (IVA incluido)"), max_digits=14, decimal_places=2)
    free_from = models.DecimalField(
        _("envío gratis desde"), max_digits=14, decimal_places=2, null=True, blank=True
    )
    min_days = models.PositiveSmallIntegerField(_("días mínimos"))
    max_days = models.PositiveSmallIntegerField(_("días máximos"))
    is_active = models.BooleanField(_("activa"), default=True)
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort", "name"]
        verbose_name = _("zona de envío")
        verbose_name_plural = _("zonas de envío")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0), name="shipping_zone_price_gte_0"
            ),
            models.CheckConstraint(
                condition=models.Q(max_days__gte=models.F("min_days")),
                name="shipping_zone_days_range",
            ),
        ]

    def __str__(self) -> str:
        return self.name
