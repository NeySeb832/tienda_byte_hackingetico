"""Role x URL access matrix, MFA enforcement and idle timeout (OWASP A01/A07)."""

import time

import pytest
from django.urls import reverse

from apps.accounts import roles
from apps.accounts.middleware import LAST_ACTIVITY_KEY

pytestmark = [pytest.mark.django_db, pytest.mark.security]

PANEL_ACCESS = {
    "panel:dashboard": set(roles.STAFF_ROLES),
    "panel:staff": {roles.ADMIN, roles.SUPERADMIN},
    "panel:audit": {roles.MANAGER, roles.ADMIN, roles.SUPERADMIN},
    "panel:security": {roles.SUPERADMIN},
}
CASES = [(url, role) for url in PANEL_ACCESS for role in roles.ALL_ROLES]


@pytest.mark.parametrize(("url_name", "role"), CASES)
def test_panel_access_matrix(client, role_user, url_name, role):
    client.force_login(role_user(role))
    response = client.get(reverse(url_name))
    expected = 200 if role in PANEL_ACCESS[url_name] else 403
    assert response.status_code == expected


@pytest.mark.parametrize("url_name", list(PANEL_ACCESS))
def test_panel_requires_login(client, url_name):
    response = client.get(reverse(url_name))
    assert response.status_code == 302
    assert reverse("account_login") in response["Location"]


@pytest.mark.parametrize(
    "url_name", ["accounts:dashboard", "accounts:profile", "accounts:addresses", "accounts:privacy"]
)
def test_account_area_requires_login(client, url_name):
    response = client.get(reverse(url_name))
    assert response.status_code == 302
    assert reverse("account_login") in response["Location"]


def test_staff_without_mfa_is_sent_to_mfa_setup(client, role_user):
    client.force_login(role_user(roles.ADMIN, mfa=False))
    response = client.get(reverse("panel:dashboard"))
    assert response.status_code == 302
    assert response["Location"] == reverse("mfa_activate_totp")


def test_mfa_setup_page_stays_reachable_without_mfa(client, role_user):
    """No redirect loop: MFA setup asks to re-enter the password first (allauth), then loads."""
    client.force_login(role_user(roles.ADMIN, mfa=False))
    response = client.get(reverse("mfa_activate_totp"))
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_reauthenticate"))
    assert client.get(response["Location"]).status_code == 200


def test_staff_session_expires_after_inactivity(client, role_user, settings):
    client.force_login(role_user(roles.SELLER))
    session = client.session
    session[LAST_ACTIVITY_KEY] = time.time() - settings.BYTE_STAFF_IDLE_TIMEOUT_MINUTES * 60 - 5
    session.save()
    response = client.get(reverse("panel:dashboard"))
    assert response.status_code == 302
    assert reverse("account_login") in response["Location"]
    assert "_auth_user_id" not in client.session


def test_customers_are_not_subject_to_staff_idle_timeout(client, customer):
    client.force_login(customer)
    session = client.session
    session[LAST_ACTIVITY_KEY] = time.time() - 10 * 3600
    session.save()
    assert client.get(reverse("accounts:dashboard")).status_code == 200


def test_menu_only_lists_permitted_sections(client, role_user):
    client.force_login(role_user(roles.SELLER))
    html = client.get(reverse("panel:dashboard")).content.decode()
    assert reverse("panel:dashboard") in html
    assert reverse("panel:staff") not in html
    assert reverse("panel:security") not in html


@pytest.mark.parametrize(
    "url_name", ["account_email", "account_change_password", "mfa_index", "usersessions_list"]
)
def test_account_security_pages_render(client, customer, url_name):
    """Regression: allauth templates need django.contrib.humanize (sessions page was a 500)."""
    client.force_login(customer)
    response = client.get(reverse(url_name))
    assert response.status_code == 200
    html = response.content.decode()
    # The page content must render inside the account layout (regression: empty card).
    assert 'class="account-nav"' in html
    assert "<h1" in html


def test_account_pages_render_their_content(client, customer):
    client.force_login(customer)
    assert "Hola" in client.get(reverse("accounts:dashboard")).content.decode()
    assert "Agregar dirección" in client.get(reverse("accounts:addresses")).content.decode()
    assert "Eliminar mi cuenta" in client.get(reverse("accounts:privacy")).content.decode()


def test_idle_timeout_redirect_encodes_next(client, role_user, settings):
    """Regression (semgrep open-redirect): "next" is URL-encoded, no parameter injection."""
    client.force_login(role_user(roles.SELLER))
    session = client.session
    session[LAST_ACTIVITY_KEY] = time.time() - settings.BYTE_STAFF_IDLE_TIMEOUT_MINUTES * 60 - 5
    session.save()
    response = client.get("/panel/?a=1&next=https://evil.example")
    assert response.status_code == 302
    location = response["Location"]
    assert location.startswith(reverse("account_login"))
    assert "next=/panel/%3Fa%3D1%26next%3Dhttps%3A//evil.example" in location
    assert location.count("next=") == 1  # the injected parameter stays inside the encoded value
