"""Data models for the pricing app: price history (append-only) and scheduled changes."""

from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs: Any) -> int:
        raise PermissionError("Price history is append-only.")

    def delete(self) -> tuple[int, dict[str, int]]:
        raise PermissionError("Price history is append-only.")


class PriceHistory(models.Model):
    """Every price a variant has had. Corrections are new rows, never edits."""

    class Reason(models.TextChoices):
        INITIAL = "initial", _("Precio inicial")
        MANUAL = "manual", _("Cambio manual")
        SCHEDULED = "scheduled", _("Cambio programado")
        RECALCULATED = "recalculated", _("Recálculo por modificadores")

    # PROTECT: a variant with price history is deactivated, never deleted.
    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.PROTECT, related_name="price_history"
    )
    price = models.DecimalField(_("precio"), max_digits=14, decimal_places=2)
    previous_price = models.DecimalField(
        _("precio anterior"), null=True, blank=True, max_digits=14, decimal_places=2
    )
    reason = models.CharField(_("motivo"), max_length=14, choices=Reason.choices)
    note = models.CharField(_("nota"), max_length=200, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    changed_at = models.DateTimeField(_("fecha"), default=timezone.now, db_index=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        ordering = ["variant", "changed_at", "pk"]
        verbose_name = _("historial de precio")
        verbose_name_plural = _("historial de precios")
        permissions = [("change_price", "Puede cambiar y programar precios")]
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gt=0), name="pricing_history_positive")
        ]

    def __str__(self) -> str:
        return f"{self.variant_id}: {self.price} ({self.changed_at:%Y-%m-%d})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise PermissionError("Price history is append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise PermissionError("Price history is append-only.")


class ScheduledPriceChange(BaseModel):
    """A price that takes effect at ``starts_at`` (applied by a Celery Beat task)."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pendiente")
        APPLIED = "applied", _("Aplicado")
        CANCELLED = "cancelled", _("Cancelado")

    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.CASCADE, related_name="scheduled_prices"
    )
    new_price = models.DecimalField(_("nuevo precio"), max_digits=14, decimal_places=2)
    starts_at = models.DateTimeField(_("aplicar desde"), db_index=True)
    status = models.CharField(
        _("estado"), max_length=10, choices=Status.choices, default=Status.PENDING
    )
    note = models.CharField(_("nota"), max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    applied_at = models.DateTimeField(_("aplicado"), null=True, blank=True)

    class Meta:
        ordering = ["starts_at"]
        verbose_name = _("cambio de precio programado")
        verbose_name_plural = _("cambios de precio programados")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(new_price__gt=0), name="pricing_scheduled_positive"
            ),
            models.CheckConstraint(
                condition=~models.Q(status="applied") | models.Q(applied_at__isnull=False),
                name="pricing_scheduled_applied_has_date",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.variant_id} → {self.new_price} ({self.get_status_display()})"
