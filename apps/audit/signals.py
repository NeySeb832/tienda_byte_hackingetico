"""Authentication events feeding the audit trail and security events."""

from typing import Any

from axes.signals import user_locked_out
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.http import HttpRequest

from apps.audit.models import SecurityEvent
from apps.audit.services import mask_email, record_event, record_security_event


@receiver(user_logged_in)
def on_login(sender: Any, request: HttpRequest, user: Any, **kwargs: Any) -> None:
    record_event("auth.login", actor=user, target=user, request=request)


@receiver(user_logged_out)
def on_logout(sender: Any, request: HttpRequest, user: Any, **kwargs: Any) -> None:
    if user is not None:
        record_event("auth.logout", actor=user, target=user, request=request)


@receiver(user_login_failed)
def on_login_failed(
    sender: Any, credentials: dict[str, Any], request: HttpRequest | None = None, **kwargs: Any
) -> None:
    login = str(
        credentials.get("email") or credentials.get("login") or credentials.get("username") or ""
    )
    record_security_event(
        SecurityEvent.Kind.LOGIN_FAILED,
        SecurityEvent.Severity.LOW,
        request=request,
        details={"login": mask_email(login)},
    )


@receiver(user_locked_out)
def on_locked_out(
    sender: Any, request: HttpRequest, username: str, ip_address: str, **kwargs: Any
) -> None:
    record_security_event(
        SecurityEvent.Kind.LOCKOUT,
        SecurityEvent.Severity.HIGH,
        request=request,
        details={"login": mask_email(username or "")},
    )
