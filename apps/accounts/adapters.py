"""django-allauth adapter: where users land after login."""

from allauth.account.adapter import DefaultAccountAdapter
from django.http import HttpRequest
from django.urls import reverse


class AccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request: HttpRequest) -> str:
        user = request.user
        if user.is_staff and user.has_perm("accounts.access_panel"):
            return reverse("panel:dashboard")
        return str(super().get_login_redirect_url(request))
