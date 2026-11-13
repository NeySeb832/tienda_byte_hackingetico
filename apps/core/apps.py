"""Cross-cutting foundations: base models, money, middleware, errors and health checks."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"
    verbose_name = _("Núcleo")

    def ready(self) -> None:
        # Register custom system checks (hidden admin URL, ...).
        from apps.core import checks  # noqa: F401
