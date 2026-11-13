"""Access control to the hidden admin and the API schema (OWASP A01)."""

import pytest
from django.conf import settings

from apps.accounts.models import User

pytestmark = [pytest.mark.django_db, pytest.mark.security]

ADMIN = f"/{settings.ADMIN_URL}"


def test_default_admin_path_is_not_exposed(client):
    assert client.get("/admin/").status_code == 404


def test_hidden_admin_requires_authentication(client):
    response = client.get(ADMIN)
    assert response.status_code == 302
    assert "/login/" in response["Location"]


def test_hidden_admin_rejects_customers(client, user):
    client.force_login(user)
    response = client.get(f"{ADMIN}accounts/user/")
    assert response.status_code in (302, 403)


def test_hidden_admin_rejects_staff_who_are_not_superadmins(client, staff_user):
    client.force_login(staff_user)
    response = client.get(f"{ADMIN}accounts/user/")
    assert response.status_code in (302, 403)


def test_superuser_manages_users_in_admin(client, superuser):
    client.force_login(superuser)
    assert client.get(f"{ADMIN}accounts/user/").status_code == 200
    response = client.post(
        f"{ADMIN}accounts/user/add/",
        {
            "email": "  Nueva.Cuenta@Example.COM ",
            "usable_password": "true",
            "password1": "Una-Clave-Larga-2026",
            "password2": "Una-Clave-Larga-2026",
        },
    )
    assert response.status_code == 302, response.content
    assert User.objects.filter(email="nueva.cuenta@example.com").exists()


def test_api_schema_is_denied_to_anonymous(client):
    assert client.get("/api/v1/schema/").status_code == 403


def test_api_schema_is_denied_to_customers(client, user):
    client.force_login(user)
    assert client.get("/api/v1/schema/").status_code == 403


def test_api_schema_is_available_to_staff(client, staff_user):
    client.force_login(staff_user)
    response = client.get("/api/v1/schema/")
    assert response.status_code == 200
    assert b"Byte API" in response.content
