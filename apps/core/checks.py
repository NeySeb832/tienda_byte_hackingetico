"""Custom system checks (run by ``manage.py check`` and ``check --deploy``)."""

import re
from typing import Any

from django.conf import settings
from django.core.checks import CheckMessage, Error, Tags, Warning, register

ADMIN_URL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,63}/$")
PREDICTABLE_ADMIN_PATHS = frozenset(
    {
        "admin",
        "administrator",
        "administrador",
        "django-admin",
        "backend",
        "dashboard",
        "panel",
        "login",
    }
)
MIN_ADMIN_URL_LENGTH = 12


@register(Tags.security)
def check_admin_url_format(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    admin_url: str = settings.ADMIN_URL
    if admin_url and not ADMIN_URL_RE.match(admin_url):
        return [
            Error(
                "DJANGO_ADMIN_URL must be a single path segment ending in '/' "
                "(letters, digits, '-' or '_').",
                id="byte.E001",
            )
        ]
    return []


@register(Tags.security, deploy=True)
def check_admin_url_unpredictable(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    admin_url: str = settings.ADMIN_URL.rstrip("/")
    if not admin_url:
        return []
    if admin_url.lower() in PREDICTABLE_ADMIN_PATHS:
        return [Warning("DJANGO_ADMIN_URL is predictable; use a random path.", id="byte.W001")]
    if len(admin_url) < MIN_ADMIN_URL_LENGTH:
        return [
            Warning(
                f"DJANGO_ADMIN_URL should have at least {MIN_ADMIN_URL_LENGTH} random characters.",
                id="byte.W002",
            )
        ]
    return []
