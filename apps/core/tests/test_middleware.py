"""Correlation id and extra security headers."""

import re

from apps.core.logging import current_request_id


def test_every_response_has_a_request_id(client):
    response = client.get("/")
    assert re.fullmatch(r"[0-9a-f]{32}", response["X-Request-ID"])


def test_request_ids_are_unique(client):
    assert client.get("/")["X-Request-ID"] != client.get("/")["X-Request-ID"]


def test_client_supplied_request_id_is_ignored(client):
    response = client.get("/", HTTP_X_REQUEST_ID="forged\ninjected-log-line")
    assert response["X-Request-ID"] != "forged\ninjected-log-line"
    assert re.fullmatch(r"[0-9a-f]{32}", response["X-Request-ID"])


def test_request_id_context_is_cleared_after_the_request(client):
    client.get("/")
    assert current_request_id() == "-"
