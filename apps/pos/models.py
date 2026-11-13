"""Point of sale: cash sessions per store. Sales are regular orders with channel "pos"."""

from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class CashSession(BaseModel):
    store = models.ForeignKey(
        "inventory.Store", on_delete=models.PROTECT, related_name="cash_sessions"
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    opened_at = models.DateTimeField(_("apertura"), default=timezone.now)
    opening_float = models.DecimalField(_("base de caja"), max_digits=14, decimal_places=2)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    closed_at = models.DateTimeField(_("cierre"), null=True, blank=True)
    expected_cash = models.DecimalField(
        _("efectivo esperado"), max_digits=14, decimal_places=2, null=True, blank=True
    )
    counted_cash = models.DecimalField(
        _("efectivo contado"), max_digits=14, decimal_places=2, null=True, blank=True
    )

    class Meta:
        ordering = ["-opened_at"]
        verbose_name = _("turno de caja")
        verbose_name_plural = _("turnos de caja")
        permissions = [("use_pos", "Puede vender en el punto de venta")]
        constraints = [
            models.UniqueConstraint(
                fields=["store", "opened_by"],
                condition=models.Q(closed_at__isnull=True),
                name="pos_one_open_session_per_cashier_store",
            ),
            models.CheckConstraint(
                condition=models.Q(opening_float__gte=0), name="pos_opening_float_gte_0"
            ),
        ]

    def __str__(self) -> str:
        return f"Caja {self.store_id} {self.opened_at:%Y-%m-%d %H:%M}"

    @property
    def is_open(self) -> bool:
        return self.closed_at is None

    @property
    def difference(self) -> Any:
        if self.counted_cash is None or self.expected_cash is None:
            return None
        return self.counted_cash - self.expected_cash
