"""Append-only audit trail and security events (OWASP A09)."""

import uuid
from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs: Any) -> int:
        raise PermissionError("The audit log is append-only.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise PermissionError("The audit log is append-only.")


class AuditLog(models.Model):
    """Who did what, when, from where; each row is chained to the previous one by hash.

    Rows can never be updated or deleted: the ORM refuses and a PostgreSQL trigger
    (migration 0002) blocks it at database level too.
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(_("fecha"), default=timezone.now, db_index=True)
    # No FK constraint: deleting a user must never rewrite history.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        related_name="+",
    )
    actor_repr = models.CharField(_("actor"), max_length=255, blank=True)
    action = models.CharField(_("acción"), max_length=80, db_index=True)
    target_type = models.CharField(_("tipo de objeto"), max_length=100, blank=True)
    target_id = models.CharField(_("objeto"), max_length=64, blank=True)
    target_repr = models.CharField(_("descripción"), max_length=255, blank=True)
    changes = models.JSONField(_("cambios"), default=dict, blank=True)
    ip = models.GenericIPAddressField(_("IP"), null=True, blank=True)
    user_agent = models.CharField(_("navegador"), max_length=255, blank=True)
    request_id = models.CharField(_("ID de correlación"), max_length=64, blank=True)
    prev_hash = models.CharField(max_length=64)
    row_hash = models.CharField(max_length=64, unique=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["-id"]
        default_permissions = ("view",)
        verbose_name = _("registro de auditoría")
        verbose_name_plural = _("bitácora de auditoría")

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise PermissionError("The audit log is append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise PermissionError("The audit log is append-only.")


class SecurityEvent(models.Model):
    class Kind(models.TextChoices):
        LOGIN_FAILED = "login_failed", _("Inicio de sesión fallido")
        LOCKOUT = "lockout", _("Bloqueo por fuerza bruta")
        FORBIDDEN_BURST = "forbidden_burst", _("Ráfaga de accesos denegados (403)")
        ROLE_ESCALATION = "role_escalation", _("Asignación de rol privilegiado")
        CSRF_FAILURE = "csrf_failure", _("Fallo de verificación CSRF")
        MASS_EXPORT = "mass_export", _("Exportación masiva de datos")
        HONEYPOT = "honeypot", _("Formulario enviado por un bot")

    class Severity(models.TextChoices):
        LOW = "low", _("Baja")
        MEDIUM = "medium", _("Media")
        HIGH = "high", _("Alta")
        CRITICAL = "critical", _("Crítica")

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(_("fecha"), default=timezone.now, db_index=True)
    kind = models.CharField(_("tipo"), max_length=30, choices=Kind.choices, db_index=True)
    severity = models.CharField(_("severidad"), max_length=10, choices=Severity.choices)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="security_events",
    )
    ip = models.GenericIPAddressField(_("IP"), null=True, blank=True)
    details = models.JSONField(_("detalles"), default=dict, blank=True)
    alerted_at = models.DateTimeField(_("alerta enviada"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        default_permissions = ("view",)
        verbose_name = _("evento de seguridad")
        verbose_name_plural = _("eventos de seguridad")

    def __str__(self) -> str:
        return f"{self.get_kind_display()} ({self.get_severity_display()})"
