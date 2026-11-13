"""Catalogue security: XSS, CSRF, open redirect, rate limit, no internal ids (OWASP A01/A03/A05)."""

import re

import pytest
from django.test import Client
from django.urls import reverse

from tests.factories import make_product

pytestmark = [pytest.mark.django_db, pytest.mark.security]

PAYLOAD = '<script>alert("x")</script>'


@pytest.fixture
def product():
    return make_product("PlayStation 5 Slim")


def test_search_term_is_escaped(client, product):
    for url in (reverse("catalog:search"), reverse("catalog:suggest")):
        html = client.get(url, {"q": PAYLOAD}).content.decode()
        assert PAYLOAD not in html
        assert "&lt;script&gt;" in html


def test_compare_requires_post_and_csrf(product):
    url = reverse("catalog:compare_toggle", args=[product.slug])
    client = Client(enforce_csrf_checks=True)
    assert client.get(url).status_code == 405
    assert client.post(url).status_code == 403


def test_compare_redirect_cannot_leave_the_site(client, product):
    url = reverse("catalog:compare_toggle", args=[product.slug])
    for target in ("https://evil.example/", "//evil.example/", "javascript:alert(1)"):
        response = client.post(url, {"next": target})
        assert response["Location"] == reverse("catalog:compare")
    response = client.post(url, {"next": "/producto/playstation-5-slim/", "accion": "quitar"})
    assert response["Location"] == "/producto/playstation-5-slim/"


def test_suggestions_are_rate_limited(client, product, settings):
    settings.RATELIMIT_ENABLE = True
    url = reverse("catalog:suggest")
    statuses = [client.get(url, {"q": "play"}).status_code for _ in range(61)]
    assert statuses[:60] == [200] * 60
    assert statuses[60] == 403


def test_catalog_never_exposes_internal_ids(client, product):
    html = client.get(reverse("catalog:product", args=[product.slug])).content.decode()
    html += client.get(reverse("catalog:list")).content.decode()
    assert not re.search(r"/producto/\d+/", html)
    assert f"?id={product.pk}" not in html
    assert f'value="{product.pk}"' not in html
