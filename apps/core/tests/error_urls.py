"""URLconf used by test_errors.py to trigger each error handler."""

from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import HttpRequest, HttpResponse
from django.urls import include, path


def boom(request: HttpRequest) -> HttpResponse:
    raise RuntimeError("internal detail that must never reach the user")


def forbidden(request: HttpRequest) -> HttpResponse:
    raise PermissionDenied


def suspicious(request: HttpRequest) -> HttpResponse:
    raise SuspiciousOperation("tampered input")


def form(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok")


urlpatterns = [
    path("", include("apps.core.urls")),  # error templates link back to core:home
    path("boom/", boom),
    path("forbidden/", forbidden),
    path("suspicious/", suspicious),
    path("form/", form),
]

handler400 = "apps.core.views.bad_request"
handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"
