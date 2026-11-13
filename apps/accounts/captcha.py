"""Cloudflare Turnstile CAPTCHA (A07). Verification fails closed (A10)."""

import logging
from typing import Any

import httpx
from django import forms
from django.conf import settings

logger = logging.getLogger(__name__)
VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(token: str | None, remote_ip: str | None = None) -> bool:
    if not token:
        return False
    data = {"secret": settings.TURNSTILE_SECRET_KEY, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        response = httpx.post(VERIFY_URL, data=data, timeout=5.0)
        response.raise_for_status()
        return bool(response.json().get("success"))
    except (httpx.HTTPError, ValueError):
        logger.warning("Turnstile verification unavailable; request rejected")
        return False


class TurnstileWidget(forms.Widget):
    template_name = "accounts/widgets/turnstile.html"

    def get_context(self, name: str, value: Any, attrs: Any) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["site_key"] = settings.TURNSTILE_SITE_KEY
        return context


class TurnstileField(forms.Field):
    widget = TurnstileWidget

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("label", "Verificación de seguridad")
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)
        self.remote_ip: str | None = None

    def clean(self, value: Any) -> Any:
        if not verify_turnstile(value, self.remote_ip):
            raise forms.ValidationError(
                "No pudimos verificar que eres una persona. Inténtalo de nuevo.", code="captcha"
            )
        return value
