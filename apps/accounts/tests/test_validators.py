"""Password validators and Turnstile verification."""

import hashlib

import httpx
import pytest
from django.core.exceptions import ValidationError

from apps.accounts.captcha import verify_turnstile
from apps.accounts.validators import (
    PwnedPasswordValidator,
    StaffMinimumLengthValidator,
    pwned_count,
)
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_staff_need_twelve_characters():
    validator = StaffMinimumLengthValidator(12)
    with pytest.raises(ValidationError):
        validator.validate("Corta-2026!", UserFactory(is_staff=True))
    validator.validate("Corta-2026!", UserFactory(is_staff=False))
    validator.validate("Suficiente-2026", UserFactory(is_staff=True))


def _hibp_response(password: str, count: int) -> httpx.Response:
    suffix = (
        hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()[5:]
    )  # nosemgrep
    return httpx.Response(
        200,
        text=f"0000000000000000000000000000000000A:1\r\n{suffix}:{count}\r\n",
        request=httpx.Request("GET", "https://x"),
    )


def test_pwned_password_is_rejected(monkeypatch, settings):
    settings.BYTE_HIBP_ENABLED = True
    monkeypatch.setattr(
        "apps.accounts.validators.httpx.get", lambda *a, **k: _hibp_response("password123", 42)
    )
    assert pwned_count("password123") == 42
    with pytest.raises(ValidationError):
        PwnedPasswordValidator().validate("password123")


def test_only_the_hash_prefix_leaves_the_server(monkeypatch, settings):
    settings.BYTE_HIBP_ENABLED = True
    seen = {}

    def fake_get(url, **kwargs):
        seen["url"] = url
        return _hibp_response("otra", 0)

    monkeypatch.setattr("apps.accounts.validators.httpx.get", fake_get)
    pwned_count("Una-Clave-Secreta-2026")
    full = (
        hashlib.sha1(b"Una-Clave-Secreta-2026", usedforsecurity=False).hexdigest().upper()
    )  # nosemgrep
    assert seen["url"].endswith(full[:5])
    assert full[5:] not in seen["url"]


def test_hibp_outage_does_not_block_signups(monkeypatch, settings):
    settings.BYTE_HIBP_ENABLED = True

    def boom(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr("apps.accounts.validators.httpx.get", boom)
    PwnedPasswordValidator().validate("Una-Clave-Secreta-2026")


def test_turnstile_fails_closed(monkeypatch):
    def boom(*args, **kwargs):
        raise httpx.ConnectError("down")

    monkeypatch.setattr("apps.accounts.captcha.httpx.post", boom)
    assert verify_turnstile("token", "127.0.0.1") is False
    assert verify_turnstile("", "127.0.0.1") is False


def test_turnstile_accepts_valid_token(monkeypatch):
    ok = httpx.Response(200, json={"success": True}, request=httpx.Request("POST", "https://x"))
    monkeypatch.setattr("apps.accounts.captcha.httpx.post", lambda *a, **k: ok)
    assert verify_turnstile("token") is True
