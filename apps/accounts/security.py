"""Helpers for django-axes and brute-force protection."""

from typing import Any

from axes.models import AccessAttempt
from django.db.models import Sum
from django.http import HttpRequest

from apps.accounts.models import normalize_email_address
from apps.audit.services import client_ip


def axes_username(request: HttpRequest, credentials: dict[str, Any] | None) -> str:
    """Normalised login used by axes, so "Ana@X.co" and "ana@x.co" share the counter."""
    credentials = credentials or {}
    value = (
        credentials.get("login")
        or credentials.get("email")
        or credentials.get("username")
        or (request.POST.get("login", "") if request is not None else "")
    )
    return normalize_email_address(str(value))


def recent_failures(request: HttpRequest | None) -> int:
    """Failed logins recorded by axes for the client IP (drives the login CAPTCHA)."""
    ip = client_ip(request)
    if not ip:
        return 0
    total = AccessAttempt.objects.filter(ip_address=ip).aggregate(total=Sum("failures_since_start"))
    return int(total["total"] or 0)
