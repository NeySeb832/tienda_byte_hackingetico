"""Data models for the promotions app: coupons and their redemptions.

A percentage coupon above ``BYTE_HIGH_DISCOUNT_APPROVAL_PCT`` is not usable until a
different person approves it (segregation of duties, CHECK in the database too).
"""

from django.conf import settings
from django.db import models
from django.db.models.functions import Upper
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class Coupon(BaseModel):
    class Kind(models.TextChoices):
        PERCENT = "percent", _("Porcentaje")
        FIXED = "fixed", _("Valor fijo")
        FREE_SHIPPING = "free_shipping", _("Envío gratis")

    code = models.CharField(_("código"), max_length=30, unique=True)
    description = models.CharField(_("descripción"), max_length=200, blank=True)
    kind = models.CharField(_("tipo"), max_length=14, choices=Kind.choices)
    value = models.DecimalField(_("valor"), max_digits=14, decimal_places=2, default=0)
    max_discount = models.DecimalField(
        _("descuento máximo"), max_digits=14, decimal_places=2, null=True, blank=True
    )
    min_subtotal = models.DecimalField(
        _("compra mínima"), max_digits=14, decimal_places=2, default=0
    )
    starts_at = models.DateTimeField(_("desde"), default=timezone.now)
    ends_at = models.DateTimeField(_("hasta"), null=True, blank=True)
    usage_limit = models.PositiveIntegerField(_("usos totales"), null=True, blank=True)
    per_user_limit = models.PositiveSmallIntegerField(_("usos por cliente"), default=1)
    first_order_only = models.BooleanField(_("solo primera compra"), default=False)
    is_active = models.BooleanField(_("activo"), default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    approved_at = models.DateTimeField(_("aprobado"), null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("cupón")
        verbose_name_plural = _("cupones")
        permissions = [("approve_coupon", "Puede aprobar cupones con descuento alto")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(code=Upper("code")), name="promotions_code_upper"
            ),
            models.CheckConstraint(condition=models.Q(value__gte=0), name="promotions_value_gte_0"),
            models.CheckConstraint(
                condition=~models.Q(kind="percent") | models.Q(value__gt=0, value__lte=100),
                name="promotions_percent_range",
            ),
            models.CheckConstraint(
                condition=models.Q(approved_by__isnull=True)
                | ~models.Q(approved_by=models.F("created_by")),
                name="promotions_creator_cannot_approve",
            ),
        ]

    def __str__(self) -> str:
        return self.code


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE, related_name="coupon_redemption"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    discount = models.DecimalField(_("descuento"), max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(_("fecha"), default=timezone.now)

    class Meta:
        verbose_name = _("uso de cupón")
        verbose_name_plural = _("usos de cupones")

    def __str__(self) -> str:
        return f"{self.coupon_id} → {self.order_id}"
