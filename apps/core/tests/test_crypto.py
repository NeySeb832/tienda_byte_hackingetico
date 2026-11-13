"""Field encryption, key rotation and production secret checks."""

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from apps.core import crypto
from apps.core.checks import check_production_secrets


@pytest.fixture(autouse=True)
def _reset_keys():
    crypto.reset_key_cache()
    yield
    crypto.reset_key_cache()


def test_round_trip_and_randomised_ciphertext():
    first, second = crypto.encrypt("3001234567"), crypto.encrypt("3001234567")
    assert first != second
    assert crypto.decrypt(first) == "3001234567"


def test_key_rotation_keeps_old_data_readable(settings):
    old_token = crypto.encrypt("1020304050")
    new_key = Fernet.generate_key().decode()
    settings.BYTE_FIELD_ENCRYPTION_KEYS = [new_key, *settings.BYTE_FIELD_ENCRYPTION_KEYS]
    crypto.reset_key_cache()
    assert crypto.decrypt(old_token) == "1020304050"
    assert Fernet(new_key.encode()).decrypt(crypto.encrypt("x").encode()) == b"x"


@override_settings(BYTE_FIELD_ENCRYPTION_KEYS=[])
def test_missing_keys_fail_loudly():
    with pytest.raises(ImproperlyConfigured):
        crypto.encrypt("x")


def test_blind_index_is_normalised():
    assert crypto.blind_index("cc: 123 456") == crypto.blind_index("CC:123456")
    assert crypto.blind_index("CC:1") != crypto.blind_index("CC:2")


@override_settings(
    BYTE_FIELD_ENCRYPTION_KEYS=[],
    BYTE_BLIND_INDEX_KEY="",
    BYTE_CAPTCHA_ENABLED=True,
    TURNSTILE_SECRET_KEY="1x0000000000000000000000000000000AA",
)
def test_deploy_check_flags_missing_secrets():
    assert {m.id for m in check_production_secrets(None)} == {
        "byte.E002",
        "byte.E003",
        "byte.W003",
        "byte.W004",  # payment simulator
    }


def test_deploy_check_requires_wompi_keys(settings):
    settings.BYTE_PAYMENT_GATEWAY = "wompi"
    settings.WOMPI_PUBLIC_KEY = ""
    assert "byte.E004" in {m.id for m in check_production_secrets(None)}
    settings.BYTE_PAYMENT_GATEWAY = "otra"
    assert "byte.E004" in {m.id for m in check_production_secrets(None)}


def test_platform_generated_secrets_become_valid_fernet_keys(settings):
    from apps.core import crypto

    settings.BYTE_FIELD_ENCRYPTION_KEYS = ["dGhpcy1pcy1hLXJhbmRvbS1yZW5kZXItdmFsdWU+/=="]
    crypto.reset_key_cache()
    try:
        assert crypto.decrypt(crypto.encrypt("3001234567")) == "3001234567"
        derived = crypto._as_fernet_key("cualquier-secreto")
        assert derived == crypto._as_fernet_key("cualquier-secreto")
        assert len(derived) == 44
    finally:
        crypto.reset_key_cache()
