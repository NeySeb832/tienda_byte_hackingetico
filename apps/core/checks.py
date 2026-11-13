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
TURNSTILE_TEST_SECRETS = frozenset(
    {
        "1x0000000000000000000000000000000AA",
        "2x0000000000000000000000000000000AA",
        "3x0000000000000000000000000000000AA",
    }
)


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


@register(Tags.security, deploy=True)
def check_production_secrets(app_configs: Any, **kwargs: Any) -> list[CheckMessage]:
    messages: list[CheckMessage] = []
    if not [key for key in settings.BYTE_FIELD_ENCRYPTION_KEYS if key]:
        messages.append(
            Error("BYTE_FIELD_ENCRYPTION_KEYS must be set in production.", id="byte.E002")
        )
    if not settings.BYTE_BLIND_INDEX_KEY:
        messages.append(Error("BYTE_BLIND_INDEX_KEY must be set in production.", id="byte.E003"))
    if settings.BYTE_CAPTCHA_ENABLED and settings.TURNSTILE_SECRET_KEY in TURNSTILE_TEST_SECRETS:
        messages.append(
            Warning("Turnstile is using Cloudflare's public test keys.", id="byte.W003")
        )
    if not settings.BYTE_CLIENT_IP_HEADER and settings.BYTE_TRUSTED_PROXY_COUNT <= 0:
        messages.append(
            Warning(
                "Client IP comes from REMOTE_ADDR: behind a proxy, lockout and rate limits "
                "see the proxy, not the client. Set BYTE_CLIENT_IP_HEADER or "
                "BYTE_TRUSTED_PROXY_COUNT.",
                id="byte.W005",
            )
        )
    if settings.BYTE_PAYMENT_GATEWAY == "wompi":
        missing = [
            name
            for name in ("WOMPI_PUBLIC_KEY", "WOMPI_INTEGRITY_SECRET", "WOMPI_EVENTS_SECRET")
            if not getattr(settings, name)
        ]
        if missing:
            messages.append(Error(f"Missing Wompi settings: {', '.join(missing)}.", id="byte.E004"))
    elif settings.BYTE_PAYMENT_GATEWAY == "fake":
        messages.append(
            Warning(
                "Payments use the built-in simulator (BYTE_PAYMENT_GATEWAY=fake).", id="byte.W004"
            )
        )
    else:
        messages.append(Error("BYTE_PAYMENT_GATEWAY must be 'wompi' or 'fake'.", id="byte.E004"))
    return messages
