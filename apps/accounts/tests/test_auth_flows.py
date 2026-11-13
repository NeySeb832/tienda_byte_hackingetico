"""Sign-up, login, brute-force lockout and CAPTCHA (OWASP A07)."""

import pytest
from django.core import mail
from django.urls import reverse

from apps.accounts import roles
from apps.accounts.models import ConsentRecord, CustomerProfile, User
from apps.audit.models import AuditLog, SecurityEvent
from tests.factories import TEST_PASSWORD

pytestmark = pytest.mark.django_db
SIGNUP = {
    "first_name": "Ana",
    "last_name": "Pérez",
    "email": "Ana.Perez@Example.com",
    "password1": "Una-Clave-Muy-Larga-2026",
    "password2": "Una-Clave-Muy-Larga-2026",
    "accept_privacy": "on",
}


def test_signup_creates_customer_with_consent(client, setup_roles):
    response = client.post(reverse("account_signup"), SIGNUP)
    assert response.status_code == 302
    user = User.objects.get(email="ana.perez@example.com")
    assert user.groups.filter(name=roles.CUSTOMER).exists()
    assert CustomerProfile.objects.filter(user=user).exists()
    consent = ConsentRecord.objects.get(user=user)
    assert consent.document.kind == "privacy"
    assert consent.document.version == "1.0"
    assert AuditLog.objects.filter(action="accounts.signup", actor=user).exists()
    assert any(
        "Confirm" in m.subject or "Confirma" in m.subject or "[Byte]" in m.subject
        for m in mail.outbox
    )


def test_signup_requires_privacy_consent(client, setup_roles):
    data = {**SIGNUP, "accept_privacy": ""}
    response = client.post(reverse("account_signup"), data)
    assert response.status_code == 200
    assert not User.objects.filter(email="ana.perez@example.com").exists()


@pytest.mark.security
def test_signup_honeypot_blocks_bots(client, setup_roles):
    response = client.post(reverse("account_signup"), {**SIGNUP, "website": "http://spam.example"})
    assert response.status_code == 200
    assert not User.objects.filter(email="ana.perez@example.com").exists()


@pytest.mark.security
def test_signup_captcha_fails_closed(client, setup_roles, settings, monkeypatch):
    settings.BYTE_CAPTCHA_ENABLED = True
    monkeypatch.setattr("apps.accounts.captcha.verify_turnstile", lambda token, ip=None: False)
    response = client.post(reverse("account_signup"), {**SIGNUP, "captcha": "token"})
    assert response.status_code == 200
    assert "No pudimos verificar" in response.content.decode()
    assert not User.objects.filter(email="ana.perez@example.com").exists()


@pytest.mark.security
def test_signup_captcha_passes_when_verified(client, setup_roles, settings, monkeypatch):
    settings.BYTE_CAPTCHA_ENABLED = True
    monkeypatch.setattr("apps.accounts.captcha.verify_turnstile", lambda token, ip=None: True)
    response = client.post(reverse("account_signup"), {**SIGNUP, "captcha": "token"})
    assert response.status_code == 302


def test_login_success_is_audited(client, user):
    response = client.post(
        reverse("account_login"), {"login": user.email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 302
    assert AuditLog.objects.filter(action="auth.login", actor=user).exists()


@pytest.mark.security
def test_login_errors_do_not_reveal_whether_the_account_exists(client, user):
    wrong_password = client.post(
        reverse("account_login"), {"login": user.email, "password": "x" * 12}
    )
    unknown_user = client.post(
        reverse("account_login"), {"login": "nadie@example.com", "password": "x" * 12}
    )
    assert wrong_password.status_code == unknown_user.status_code == 200
    errors = [r.context["form"].non_field_errors() for r in (wrong_password, unknown_user)]
    assert errors[0] == errors[1]
    assert SecurityEvent.objects.filter(kind=SecurityEvent.Kind.LOGIN_FAILED).count() == 2


@pytest.mark.security
def test_brute_force_is_locked_out_and_alerted(
    client, user, superuser, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        statuses = [
            client.post(
                reverse("account_login"), {"login": user.email, "password": f"mala-{n}"}
            ).status_code
            for n in range(7)
        ]
    assert 429 in statuses
    lockout = SecurityEvent.objects.filter(kind=SecurityEvent.Kind.LOCKOUT)
    assert lockout.exists()
    assert any("Alerta de seguridad" in m.subject for m in mail.outbox)
    # Even the right password is refused while locked out (axes 429 or allauth's own limiter).
    blocked = client.post(
        reverse("account_login"), {"login": user.email, "password": TEST_PASSWORD}
    )
    assert blocked.status_code in (200, 429)
    assert "_auth_user_id" not in client.session


@pytest.mark.security
def test_login_captcha_appears_after_failures(client, user, settings):
    settings.BYTE_CAPTCHA_ENABLED = True
    login_url = reverse("account_login")
    assert "captcha" not in client.get(login_url).context["form"].fields
    for n in range(settings.BYTE_LOGIN_CAPTCHA_AFTER_FAILURES):
        client.post(login_url, {"login": user.email, "password": f"mala-{n}"})
    assert "captcha" in client.get(login_url).context["form"].fields
