"""Staff session hardening: mandatory MFA and idle timeout (A07)."""

import time
from collections.abc import Callable

from allauth.mfa.utils import is_mfa_enabled
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

LAST_ACTIVITY_KEY = "byte_staff_last_activity"
MFA_SETUP_URL_NAMES = frozenset(
    {
        "mfa_index",
        "mfa_activate_totp",
        "mfa_view_recovery_codes",
        "mfa_generate_recovery_codes",
        "mfa_download_recovery_codes",
        "mfa_authenticate",
        "mfa_reauthenticate",
        "account_reauthenticate",
        "account_logout",
        "healthz",
    }
)


class StaffSecurityMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.is_staff:
            response = self._enforce(request)
            if response is not None:
                return response
        return self.get_response(request)

    def _enforce(self, request: HttpRequest) -> HttpResponse | None:
        now = time.time()
        last = request.session.get(LAST_ACTIVITY_KEY)
        if last and now - float(last) > settings.BYTE_STAFF_IDLE_TIMEOUT_MINUTES * 60:
            logout(request)
            messages.info(request, "Tu sesión se cerró por inactividad. Ingresa de nuevo.")
            # redirect_to_login URL-encodes "next" (no parameter injection / open redirect).
            return redirect_to_login(request.get_full_path(), reverse("account_login"))
        request.session[LAST_ACTIVITY_KEY] = now
        if is_mfa_enabled(request.user) or self._is_exempt(request):
            return None
        messages.warning(
            request,
            "Por seguridad, el personal debe activar la verificación en dos pasos antes de continuar.",
        )
        return redirect("mfa_activate_totp")

    @staticmethod
    def _is_exempt(request: HttpRequest) -> bool:
        if request.path.startswith((settings.STATIC_URL, "/" + settings.STATIC_URL.lstrip("/"))):
            return True
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return False
        return match.url_name in MFA_SETUP_URL_NAMES
