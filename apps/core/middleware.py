"""Cross-cutting middleware: correlation id and extra security headers."""

import uuid
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from apps.core.logging import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware:
    """Give every request a correlation id (logs, error pages and response header).

    The id is always generated server-side; client-supplied values are ignored to
    avoid log injection.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        token = request_id_var.set(uuid.uuid4().hex)
        try:
            response = self.get_response(request)
            response[REQUEST_ID_HEADER] = request_id_var.get()
        finally:
            request_id_var.reset(token)
        return response


class SecurityHeadersMiddleware:
    """Headers Django does not set natively (Permissions-Policy, CORP, ...)."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.permissions_policy: str = settings.BYTE_PERMISSIONS_POLICY

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", self.permissions_policy)
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        return response
