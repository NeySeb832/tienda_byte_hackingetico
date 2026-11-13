"""/healthz (platform health check)."""

import pytest
from django.db import OperationalError

pytestmark = pytest.mark.django_db


def test_healthz_reports_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "cache": "ok"}}
    assert "no-cache" in response["Cache-Control"]


def test_healthz_reports_cache_failure_without_details(client, monkeypatch):
    def broken_set(*args, **kwargs):
        raise ConnectionError("valkey down at 10.0.0.5")

    monkeypatch.setattr("apps.core.health.cache.set", broken_set)
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json()["checks"]["cache"] == "error"
    assert b"10.0.0.5" not in response.content


def test_healthz_reports_database_failure(client, monkeypatch):
    class BrokenConnection:
        def cursor(self):
            raise OperationalError("db down")

    monkeypatch.setattr("apps.core.health.connections", {"default": BrokenConnection()})
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "checks": {"database": "error", "cache": "ok"}}


def test_healthz_only_allows_get(client):
    assert client.post("/healthz").status_code == 405
