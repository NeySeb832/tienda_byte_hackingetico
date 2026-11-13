"""Roles, permissions and the generated permission matrix."""

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command

from apps.accounts.roles import ALL_ROLES, ROLE_PERMISSIONS

pytestmark = pytest.mark.django_db


def _snapshot() -> dict[str, set[str]]:
    return {
        g.name: {f"{p.content_type.app_label}.{p.codename}" for p in g.permissions.all()}
        for g in Group.objects.prefetch_related("permissions__content_type")
    }


def test_setup_roles_is_idempotent_and_exact():
    call_command("setup_roles", verbosity=0)
    first = _snapshot()
    call_command("setup_roles", verbosity=0)
    assert _snapshot() == first
    for role in ALL_ROLES:
        assert first[role] == set(ROLE_PERMISSIONS[role])


def test_customers_have_no_back_office_permissions():
    assert ROLE_PERMISSIONS["Cliente"] == frozenset()


def test_only_superadmin_sees_security_events():
    holders = [r for r, perms in ROLE_PERMISSIONS.items() if "audit.view_securityevent" in perms]
    assert holders == ["Superadmin"]


def test_permission_matrix_document_is_up_to_date():
    call_command("export_permissions_matrix", "--check", verbosity=0)
