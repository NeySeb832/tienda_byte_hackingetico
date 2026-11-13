"""Data models for the cms app."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class LegalDocument(TimeStampedModel):
    """Versioned legal text (privacy policy, terms). Consent references a version."""

    class Kind(models.TextChoices):
        PRIVACY = "privacy", _("Política de tratamiento de datos personales")
        TERMS = "terms", _("Términos y condiciones")

    kind = models.CharField(_("tipo"), max_length=20, choices=Kind.choices)
    version = models.CharField(_("versión"), max_length=20)
    title = models.CharField(_("título"), max_length=200)
    body = models.TextField(_("contenido"))
    published_at = models.DateTimeField(_("publicado"))

    class Meta:
        ordering = ["kind", "-published_at"]
        verbose_name = _("documento legal")
        verbose_name_plural = _("documentos legales")
        constraints = [
            models.UniqueConstraint(fields=["kind", "version"], name="cms_legal_kind_version")
        ]

    def __str__(self) -> str:
        return f"{self.title} v{self.version}"
