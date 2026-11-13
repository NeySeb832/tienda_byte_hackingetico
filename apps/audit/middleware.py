"""Detect bursts of denied requests (HTTP 403) from the same client (A09)."""

from collections.abc import Callable

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse

from apps.audit.models import SecurityEvent
from apps.audit.services import client_ip, record_security_event


class ForbiddenBurstMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        if response.status_code == 403:
            self._count(request)
        return response

    def _count(self, request: HttpRequest) -> None:
        window = settings.BYTE_FORBIDDEN_BURST_WINDOW_SECONDS
        key = f"sec:403:{client_ip(request) or 'unknown'}"
        cache.add(key, 0, timeout=window)
        try:
            count = cache.incr(key)
        except ValueError:  # expired between add and incr
            cache.set(key, 1, timeout=window)
            count = 1
        if count == settings.BYTE_FORBIDDEN_BURST_THRESHOLD:
            record_security_event(
                SecurityEvent.Kind.FORBIDDEN_BURST,
                SecurityEvent.Severity.HIGH,
                user=getattr(request, "user", None),
                request=request,
                details={"count": count, "window_seconds": window, "path": request.path},
            )
