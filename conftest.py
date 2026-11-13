"""Shared pytest fixtures."""

import pytest
from django.core.cache import cache
from django.core.management import call_command

from apps.accounts import roles
from tests.factories import UserFactory, enable_mfa, make_user_with_role


@pytest.fixture(autouse=True)
def _clear_cache():
    """Rate limits, lockout counters and burst detectors live in the cache."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def setup_roles(db):
    call_command("setup_roles", verbosity=0)


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def customer(setup_roles):
    return make_user_with_role(roles.CUSTOMER)


@pytest.fixture
def staff_user(setup_roles):
    return make_user_with_role(roles.SELLER)


@pytest.fixture
def superuser(setup_roles):
    return make_user_with_role(roles.SUPERADMIN)


@pytest.fixture
def role_user(setup_roles):
    """Factory: ``role_user(role, mfa=True)``."""
    return make_user_with_role


__all__ = ["enable_mfa"]
