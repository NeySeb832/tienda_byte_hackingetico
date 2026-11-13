"""Repair and warranty tickets."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ServicesDeskConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.services_desk"
    label = "services_desk"
    verbose_name = _("Servicio técnico")
