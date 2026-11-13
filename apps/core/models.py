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


class BaseModel(PublicIdModel, TimeStampedModel):
    """Convenience base: public id + timestamps."""

    class Meta:
        abstract = True
