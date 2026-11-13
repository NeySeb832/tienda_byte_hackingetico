"""Custom user model: email login, normalisation and public id (ADR-0011)."""

import uuid

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import User

pytestmark = pytest.mark.django_db

PASSWORD = "ClaveSegura-2026!"


def test_create_user_normalises_email_and_hashes_password():
    user = User.objects.create_user("  Ana.Perez@Example.COM ", PASSWORD)
    assert user.email == "ana.perez@example.com"
    assert user.password != PASSWORD
    assert user.check_password(PASSWORD)
    assert not user.is_staff
    assert not user.is_superuser


def test_create_user_without_password_gets_an_unusable_password():
    assert not User.objects.create_user("sin.clave@example.com").has_usable_password()


def test_email_is_required():
    with pytest.raises(ValueError, match="email address is required"):
        User.objects.create_user("", PASSWORD)


def test_login_lookup_is_case_insensitive():
    user = User.objects.create_user("ana@example.com", PASSWORD)
    assert User.objects.get_by_natural_key("  ANA@Example.com") == user


def test_duplicate_email_with_different_case_is_rejected():
    User.objects.create_user("ana@example.com", PASSWORD)
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("ANA@example.com", PASSWORD)


def test_database_rejects_mixed_case_email_even_bypassing_the_orm_save():
    user = User.objects.create_user("ana@example.com", PASSWORD)
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.filter(pk=user.pk).update(email="Ana@Example.com")


def test_public_id_is_a_random_uuid4():
    first = User.objects.create_user("uno@example.com")
    second = User.objects.create_user("dos@example.com")
    assert isinstance(first.public_id, uuid.UUID)
    assert first.public_id.version == 4
    assert first.public_id != second.public_id


def test_create_superuser_sets_flags():
    admin = User.objects.create_superuser("root@example.com", PASSWORD)
    assert admin.is_staff
    assert admin.is_superuser


@pytest.mark.parametrize("flag", ["is_staff", "is_superuser"])
def test_create_superuser_rejects_missing_flags(flag):
    with pytest.raises(ValueError, match="Superuser must have"):
        User.objects.create_superuser("root@example.com", PASSWORD, **{flag: False})


def test_clean_normalises_email():
    user = User(email="  Mixto@Example.CO ")
    user.clean()
    assert user.email == "mixto@example.co"
    assert str(user) == "mixto@example.co"
