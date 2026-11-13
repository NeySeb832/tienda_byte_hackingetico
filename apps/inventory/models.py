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
