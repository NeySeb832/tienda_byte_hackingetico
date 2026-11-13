"""Centralised error handling: generic message + correlation id (OWASP A10)."""

import pytest
from django.test import Client

pytestmark = pytest.mark.urls("apps.core.tests.error_urls")


def test_404_uses_custom_page_with_request_id(client):
    response = client.get("/no-existe/")
    assert response.status_code == 404
    html = response.content.decode()
    assert "Game over" in html
    assert response["X-Request-ID"] in html


def test_500_hides_internal_details():
    client = Client(raise_request_exception=False)
    response = client.get("/boom/")
    assert response.status_code == 500
    html = response.content.decode()
    assert "Algo salió mal" in html
    assert response["X-Request-ID"] in html
    assert "internal detail" not in html
    assert "Traceback" not in html


def test_403_page(client):
    response = client.get("/forbidden/")
    assert response.status_code == 403
    assert "Acceso denegado" in response.content.decode()


def test_400_page(client):
    response = client.get("/suspicious/")
    assert response.status_code == 400
    assert "Solicitud inválida" in response.content.decode()


def test_csrf_failure_page():
    client = Client(enforce_csrf_checks=True)
    response = client.post("/form/", {"campo": "valor"})
    assert response.status_code == 403
    assert "La sesión del formulario expiró" in response.content.decode()
