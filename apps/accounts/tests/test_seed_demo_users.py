"""seed_demo_users: the public demo TOTP secret never reaches production (pentest PT-04)."""

import pytest
from allauth.mfa.models import Authenticator
from django.core.management import call_command

from apps.accounts.management.commands.seed_demo_users import DEMO_TOTP_SECRET
from apps.accounts.models import User
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db

STAFF_EMAIL = "vendedor@byte.test"


def _totp(email):
    return Authenticator.objects.filter(user__email=email, type=Authenticator.Type.TOTP)


@pytest.fixture
def demo_password(settings):
    settings.BYTE_DEMO_PASSWORD = "Demo-only-password-2026"


def test_development_seeds_the_known_secret(settings, demo_password):
    settings.DEBUG = True
    call_command("seed_demo_users")
    assert _totp(STAFF_EMAIL).get().data["secret"] == DEMO_TOTP_SECRET
    assert not _totp("cliente@byte.test").exists()


def test_production_does_not_seed_a_totp_secret(settings, demo_password):
    settings.DEBUG = False
    call_command("seed_demo_users", "--force")
    assert not _totp(STAFF_EMAIL).exists()
    assert User.objects.get(email=STAFF_EMAIL).is_staff


def test_production_removes_a_previously_seeded_public_secret(settings, demo_password):
    settings.DEBUG = True
    call_command("seed_demo_users")
    user = User.objects.get(email=STAFF_EMAIL)
    Authenticator.objects.create(user=user, type=Authenticator.Type.RECOVERY_CODES, data={})

    settings.DEBUG = False
    call_command("seed_demo_users", "--force")

    assert not Authenticator.objects.filter(user=user).exists()
    assert AuditLog.objects.filter(action="accounts.demo_mfa_reset").exists()


def test_production_keeps_an_authenticator_the_user_enrolled(settings, demo_password):
    settings.DEBUG = False
    call_command("seed_demo_users", "--force")
    user = User.objects.get(email=STAFF_EMAIL)
    Authenticator.objects.create(
        user=user, type=Authenticator.Type.TOTP, data={"secret": "USERCHOSENSECRETX"}
    )

    call_command("seed_demo_users", "--force")

    assert _totp(STAFF_EMAIL).get().data["secret"] == "USERCHOSENSECRETX"
