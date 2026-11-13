"""Price rules, scheduled price changes and price history."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PricingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pricing"
    label = "pricing"
    verbose_name = _("Precios")
