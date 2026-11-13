"""Role changes, encrypted profile data and Habeas Data rights."""

import json

import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.urls import reverse

from apps.accounts import roles, services
from apps.accounts.models import Address, CustomerProfile, User
from apps.audit.models import AuditLog, SecurityEvent
from apps.core.crypto import blind_index
from tests.factories import TEST_PASSWORD

pytestmark = pytest.mark.django_db


def test_admin_promotes_customer_to_seller(role_user, customer):
    admin = role_user(roles.ADMIN)
    services.assign_role(actor=admin, user=customer, role=roles.SELLER)
    customer.refresh_from_db()
    assert customer.is_staff is True
    assert services.role_of(customer) == roles.SELLER
    entry = AuditLog.objects.get(action="accounts.role_changed")
    assert entry.changes == {"before": roles.CUSTOMER, "after": roles.SELLER}


@pytest.mark.security
def test_nobody_changes_their_own_role(role_user):
    admin = role_user(roles.ADMIN)
    with pytest.raises(PermissionDenied):
        services.assign_role(actor=admin, user=admin, role=roles.SUPERADMIN)


@pytest.mark.security
def test_admin_cannot_create_superadmins(role_user, customer):
    with pytest.raises(PermissionDenied):
        services.assign_role(actor=role_user(roles.ADMIN), user=customer, role=roles.SUPERADMIN)


@pytest.mark.security
def test_admin_cannot_touch_superadmins(role_user, superuser):
    with pytest.raises(PermissionDenied):
        services.assign_role(actor=role_user(roles.ADMIN), user=superuser, role=roles.CUSTOMER)


@pytest.mark.security
def test_sellers_cannot_assign_roles(role_user, customer):
    with pytest.raises(PermissionDenied):
        services.assign_role(actor=role_user(roles.SELLER), user=customer, role=roles.ADMIN)


@pytest.mark.security
def test_privilege_escalation_is_alerted(superuser, customer, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        services.assign_role(actor=superuser, user=customer, role=roles.ADMIN)
    event = SecurityEvent.objects.get(kind=SecurityEvent.Kind.ROLE_ESCALATION)
    assert event.user == customer
    assert any("Alerta de seguridad" in m.subject for m in mail.outbox)


@pytest.mark.security
def test_role_change_ends_the_users_sessions(
    client, superuser, customer, django_capture_on_commit_callbacks
):
    client.force_login(customer)
    assert client.get(reverse("accounts:dashboard")).status_code == 200
    with django_capture_on_commit_callbacks(execute=True):
        services.assign_role(actor=superuser, user=customer, role=roles.SELLER)
    assert client.get(reverse("accounts:dashboard")).status_code == 302


@pytest.mark.security
def test_document_and_phone_are_encrypted_at_rest(customer):
    services.update_profile(
        customer,
        {
            "first_name": "Ana",
            "last_name": "Pérez",
            "document_type": "CC",
            "document_number": "1020304050",
            "phone": "3001234567",
            "marketing_opt_in": False,
        },
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT document_number, phone FROM accounts_customerprofile WHERE user_id = %s",
            [customer.pk],
        )
        stored_document, stored_phone = cursor.fetchone()
    assert "1020304050" not in stored_document
    assert "3001234567" not in stored_phone
    profile = CustomerProfile.objects.get(user=customer)
    assert profile.document_number == "1020304050"
    assert profile.document_index == blind_index("CC:1020304050")
    assert CustomerProfile.objects.filter(document_index=blind_index("CC: 1020304050")).exists()


def test_profile_view_updates_data(client, customer):
    client.force_login(customer)
    response = client.post(
        reverse("accounts:profile"),
        {
            "first_name": "Ana",
            "last_name": "Gómez",
            "document_type": "CC",
            "document_number": "123456",
            "phone": "+57 300 123 4567",
        },
    )
    assert response.status_code == 302
    customer.refresh_from_db()
    assert customer.last_name == "Gómez"
    assert CustomerProfile.objects.get(user=customer).phone == "3001234567"


def test_data_export_contains_only_own_data(client, customer, role_user):
    other = role_user(roles.CUSTOMER)
    client.force_login(customer)
    response = client.get(reverse("accounts:data_export"))
    assert response["Content-Disposition"].startswith("attachment")
    data = json.loads(response.content)
    assert data["cuenta"]["correo"] == customer.email
    assert other.email not in response.content.decode()
    assert "password" not in response.content.decode()
    assert AuditLog.objects.filter(action="accounts.data_exported", actor=customer).exists()


@pytest.mark.security
def test_data_export_is_rate_limited(client, customer):
    client.force_login(customer)
    statuses = [client.get(reverse("accounts:data_export")).status_code for _ in range(6)]
    assert statuses[:5] == [200] * 5
    assert statuses[5] == 403


def test_account_deletion_anonymises_and_logs_out(client, customer):
    Address.objects.create(
        user=customer,
        label="Casa",
        recipient_name="Ana",
        phone="3001234567",
        city_id=1,
        line1="Calle 1",
        is_default=True,
    )
    client.force_login(customer)
    response = client.post(
        reverse("accounts:privacy"), {"password": TEST_PASSWORD, "confirmation": "ELIMINAR"}
    )
    assert response.status_code == 302
    customer.refresh_from_db()
    assert customer.email.startswith("eliminado-")
    assert customer.is_active is False
    assert not customer.has_usable_password()
    assert not Address.objects.filter(user=customer).exists()
    assert client.get(reverse("accounts:dashboard")).status_code == 302


def test_account_deletion_requires_password(client, customer):
    client.force_login(customer)
    response = client.post(
        reverse("accounts:privacy"), {"password": "incorrecta", "confirmation": "ELIMINAR"}
    )
    assert response.status_code == 200
    assert User.objects.get(pk=customer.pk).is_active
