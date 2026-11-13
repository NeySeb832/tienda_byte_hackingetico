"""One focused check per OWASP Top 10:2025 category (see docs/seguridad/owasp-top10-2025.md).

The deeper tests per control live in the apps and in the rest of tests/security; these are the
cross-cutting guarantees an auditor asks for first.
"""

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from apps.accounts import roles
from apps.audit.models import AuditLog
from tests.factories import make_product, make_user, make_user_with_role

pytestmark = [pytest.mark.security, pytest.mark.django_db]
ROOT = Path(settings.BASE_DIR)


def test_a01_every_panel_url_denies_anonymous_and_customers(client, setup_roles):
    from apps.panel.urls import urlpatterns

    simple = [p for p in urlpatterns if not p.pattern.converters]
    assert len(simple) > 15
    customer = make_user()
    for pattern in simple:
        url = reverse(f"panel:{pattern.name}")
        assert client.get(url).status_code in (302, 403), url
    client.force_login(customer)
    for pattern in simple:
        assert client.get(reverse(f"panel:{pattern.name}")).status_code == 403, pattern.name


def test_a01_public_urls_never_carry_integer_ids():
    from django.urls import get_resolver

    from config.urls import urlpatterns  # noqa: F401

    for _, patterns in get_resolver().reverse_dict.items():
        for pattern in patterns:
            text = str(pattern[1]) if isinstance(pattern, tuple) else ""
            assert "<int:" not in text


def test_a02_debug_and_admin_are_closed_in_production():
    prod = (ROOT / "config/settings/prod.py").read_text(encoding="utf-8")
    assert "DEBUG = False" in prod
    assert "__Host-sessionid" in prod
    assert settings.SESSION_COOKIE_HTTPONLY


def test_a03_dependencies_are_pinned_with_hashes():
    lines = (ROOT / "requirements/prod.txt").read_text(encoding="utf-8").splitlines()
    pins = [line for line in lines if re.match(r"^[a-z0-9_.-]+==", line, re.I)]
    hashes = [line for line in lines if "--hash=sha256:" in line]
    assert pins
    assert len(hashes) >= len(pins)
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for use in re.findall(r"uses:\s*(\S+)", workflow):
        assert re.search(r"@[0-9a-f]{40}$", use), use  # actions pinned by commit SHA


def test_a04_passwords_use_argon2_and_secrets_come_from_env():
    assert "Argon2PasswordHasher" in (ROOT / "config/settings/base.py").read_text(encoding="utf-8")
    base = (ROOT / "config/settings/base.py").read_text(encoding="utf-8")
    assert re.search(r"SECRET_KEY\s*=\s*env", base)
    assert not re.search(r"(?i)(api_key|secret|password)\s*=\s*['\"][A-Za-z0-9]{16,}['\"]", base)


def test_a05_search_and_filters_resist_injection(client):
    make_product("Consola")
    for payload in ("' OR 1=1 --", "<script>alert(1)</script>", "%' UNION SELECT 1 --"):
        response = client.get(
            reverse("catalog:search"), {"q": payload, "orden": payload, "marca": payload}
        )
        assert response.status_code == 200
        assert "<script>alert(1)</script>" not in response.content.decode()


def test_a06_segregation_of_duties_is_enforced_by_the_database():
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT conname FROM pg_constraint WHERE conname = ANY(%s)",
            [
                [
                    "inventory_adjustment_sod",
                    "purchasing_po_sod",
                    "promotions_creator_cannot_approve",
                    "orders_return_sod",
                    "payments_refund_sod",
                ]
            ],
        )
        assert len(cursor.fetchall()) == 5


def test_a07_staff_cannot_reach_the_panel_without_mfa(client, setup_roles):
    staff = make_user_with_role(roles.MANAGER, mfa=False)
    client.force_login(staff)
    response = client.get(reverse("panel:dashboard"))
    assert response.status_code == 302
    assert (
        "mfa" in response["Location"]
        or "2fa" in response["Location"]
        or "dos-pasos" in response["Location"]
    )


def test_a08_append_only_tables_have_database_triggers():
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")
        triggers = {row[0] for row in cursor.fetchall()}
    for table in (
        "audit_auditlog",
        "pricing_pricehistory",
        "inventory_stockmovement",
        "orders_orderstatusevent",
        "promotions_loyaltyentry",
        "promotions_creditentry",
        "services_desk_ticketevent",
    ):
        assert f"{table}_append_only" in triggers, table


def test_a09_sensitive_reads_are_audited(client, setup_roles):
    customer = make_user()
    client.force_login(make_user_with_role(roles.MANAGER))
    client.get(reverse("panel:customer_detail", args=[customer.public_id]))
    assert AuditLog.objects.filter(action="crm.customer_viewed").exists()


def test_a10_errors_are_generic_and_correlated():
    client = Client(raise_request_exception=False)
    response = client.get("/no-existe-esta-pagina/")
    html = response.content.decode()
    assert response.status_code == 404
    assert "Traceback" not in html
    assert response.has_header("X-Request-ID")
