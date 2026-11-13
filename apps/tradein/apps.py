"""Trade-in quotes and evaluations of used consoles and games."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class TradeinConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tradein"
    label = "tradein"
    verbose_name = _("Retomas")
