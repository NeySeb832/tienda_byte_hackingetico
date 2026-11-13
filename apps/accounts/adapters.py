"""django-allauth adapter: where users land after login."""

from allauth.account.adapter import DefaultAccountAdapter
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest
from django.urls import reverse

from apps.core.net import client_ip


class AccountAdapter(DefaultAccountAdapter):
    def get_client_ip(self, request: HttpRequest) -> str:
        """allauth's rate limits key on the same trusted client IP as axes (pentest PT-01)."""
        ip = client_ip(request)
        if not ip:
            raise PermissionDenied("Unable to determine client IP address")
        return ip

    def get_login_redirect_url(self, request: HttpRequest) -> str:
        user = request.user
        if user.is_staff and user.has_perm("accounts.access_panel"):
            return reverse("panel:dashboard")
        return str(super().get_login_redirect_url(request))
