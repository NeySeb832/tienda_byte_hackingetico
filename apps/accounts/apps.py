"""Users, profiles, addresses, data-processing consent, MFA and staff store assignments."""

from datetime import timedelta

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = _("Cuentas")

    def ready(self) -> None:
        # axes.conf cannot be imported from settings (it reads settings at import time),
        # so the progressive lockout tiers are materialised here.
        from axes.conf import LockoutTier
        from django.conf import settings

        settings.AXES_LOCKOUT_TIERS = [
            LockoutTier(failures=failures, cooloff=timedelta(minutes=minutes))
            for failures, minutes in settings.BYTE_LOCKOUT_TIERS
        ]
