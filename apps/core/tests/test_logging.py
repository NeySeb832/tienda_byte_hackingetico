"""Structured logging: correlation id and masking of sensitive data (OWASP A09)."""

import io
import json
import logging

from pythonjsonlogger.json import JsonFormatter

from apps.core.logging import (
    MASK,
    RequestIDFilter,
    SensitiveDataFilter,
    mask_sensitive,
    request_id_var,
)


def test_mask_sensitive_is_recursive():
    data = {
        "password": "hunter2",
        "profile": {"phone": "3001234567", "name": "Ana"},
        "items": [{"access_token": "abc"}],
    }
    assert mask_sensitive(data) == {
        "password": MASK,
        "profile": {"phone": MASK, "name": "Ana"},
        "items": [{"access_token": MASK}],
    }


def test_sensitive_filter_masks_extra_fields_and_requests():
    class FakeRequest:
        method = "POST"
        path = "/cuenta/clave/"

    record = logging.makeLogRecord(
        {
            "msg": "evento",
            "password": "hunter2",
            "payload": {"document_number": "1020304050", "city": "Medellín"},
            "request": FakeRequest(),
        }
    )
    assert SensitiveDataFilter().filter(record) is True
    fields = vars(record)
    assert fields["password"] == MASK
    assert fields["payload"] == {"document_number": MASK, "city": "Medellín"}
    assert fields["request"] == "POST /cuenta/clave/"


def test_json_log_line_has_request_id_and_no_secrets():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter("%(levelname)s %(name)s %(message)s %(request_id)s"))
    handler.addFilter(RequestIDFilter())
    handler.addFilter(SensitiveDataFilter())
    logger = logging.getLogger("byte.tests.logging")
    logger.addHandler(handler)
    logger.propagate = False
    token = request_id_var.set("abc123")
    try:
        logger.warning("intento de acceso", extra={"password": "hunter2", "email": "x@y.co"})
    finally:
        request_id_var.reset(token)
        logger.removeHandler(handler)
    line = json.loads(stream.getvalue())
    assert line["request_id"] == "abc123"
    assert line["password"] == MASK
    assert "hunter2" not in stream.getvalue()
