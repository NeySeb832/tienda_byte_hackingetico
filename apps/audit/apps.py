"""Append-only audit trail and security events."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit"
    label = "audit"
    verbose_name = _("Auditoría")

    def ready(self) -> None:
        from apps.audit import signals  # noqa: F401
