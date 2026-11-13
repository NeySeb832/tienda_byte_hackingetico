"""Logging helpers: correlation id and masking of sensitive data (A09)."""

import logging
from collections.abc import Mapping
from contextvars import ContextVar
from typing import Any

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

MASK = "***"
SENSITIVE_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "csrf",
    "api_key",
    "apikey",
    "card",
    "cvv",
    "cvc",
    "document",
    "phone",
    "otp",
    "totp",
)
# Standard LogRecord attributes are never masked.
_RESERVED = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "request_id"}


def current_request_id() -> str:
    """Correlation id of the request being processed (``-`` outside requests)."""
    return request_id_var.get()


def is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in SENSITIVE_FRAGMENTS)


def mask_sensitive(value: Any) -> Any:
    """Return a copy of ``value`` with sensitive keys masked (recursively)."""
    if isinstance(value, Mapping):
        return {
            key: MASK if isinstance(key, str) and is_sensitive(key) else mask_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return type(value)(mask_sensitive(item) for item in value)
    return value


class RequestIDFilter(logging.Filter):
    """Attach the current correlation id to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class SensitiveDataFilter(logging.Filter):
    """Mask sensitive ``extra`` fields and never log full request objects."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in list(record.__dict__.items()):
            if key in _RESERVED:
                continue
            if key == "request":
                # Django attaches the request; keep only method and path (no query string).
                method = getattr(value, "method", "")
                path = getattr(value, "path", "")
                record.request = f"{method} {path}".strip()
            elif is_sensitive(key):
                setattr(record, key, MASK)
            else:
                setattr(record, key, mask_sensitive(value))
        if isinstance(record.args, Mapping):
            record.args = mask_sensitive(record.args)
        return True
