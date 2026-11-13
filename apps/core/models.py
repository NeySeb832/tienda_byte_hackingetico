"""Abstract base models shared by every app (ADR-0011)."""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """Adds creation and last-update timestamps."""

    created_at = models.DateTimeField(_("creado"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("actualizado"), auto_now=True)

    class Meta:
        abstract = True


class PublicIdModel(models.Model):
    """Adds an opaque public identifier.

    The integer primary key stays internal; URLs, templates and the API only
    ever expose ``public_id`` (or a slug) to prevent enumeration (IDOR).
    """

    public_id = models.UUIDField(
        _("identificador público"), default=uuid.uuid4, unique=True, editable=False
    )

    class Meta:
        abstract = True


class Department(models.Model):
    """Colombian department (DANE DIVIPOLA code)."""

    code = models.CharField(_("código DANE"), max_length=2, unique=True)
    name = models.CharField(_("nombre"), max_length=80)

    class Meta:
        ordering = ["name"]
        verbose_name = _("departamento")
        verbose_name_plural = _("departamentos")

    def __str__(self) -> str:
        return self.name


class City(models.Model):
    """Colombian municipality (DANE DIVIPOLA code)."""

    code = models.CharField(_("código DANE"), max_length=5, unique=True)
    name = models.CharField(_("nombre"), max_length=80)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="cities", verbose_name=_("departamento")
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("ciudad")
        verbose_name_plural = _("ciudades")

    def __str__(self) -> str:
        return self.name


class BaseModel(PublicIdModel, TimeStampedModel):
    """Convenience base: public id + timestamps."""

    class Meta:
        abstract = True
