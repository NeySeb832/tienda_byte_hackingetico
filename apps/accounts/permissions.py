"""Access-control building blocks used by every app (ADR-0003). Deny by default."""

from typing import Any

from allauth.mfa.utils import is_mfa_enabled
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import HttpRequest, HttpResponseBase

from apps.accounts.models import User


def authenticated_user(request: HttpRequest) -> User:
    """``request.user`` as a real ``User`` (views behind login); anything else is a 403."""
    user = request.user
    if not isinstance(user, User) or not user.is_authenticated:
        raise PermissionDenied
    return user


class RoleRequiredMixin(AccessMixin):
    """Login + every permission in ``required_permissions``; otherwise 403.

    A view that forgets to declare permissions fails loudly instead of being public.
    """

    required_permissions: tuple[str, ...] = ()

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        if not self.required_permissions:
            raise ImproperlyConfigured(f"{type(self).__name__} must declare required_permissions.")
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.has_perms(self.required_permissions):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)  # type: ignore[misc]


class StaffRequiredMixin(RoleRequiredMixin):
    """Back-office views: staff + panel permission + MFA enabled."""

    required_permissions: tuple[str, ...] = ("accounts.access_panel",)

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        user = request.user
        if user.is_authenticated and (not user.is_staff or not is_mfa_enabled(user)):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def ensure_segregation_of_duties(creator: Any, approver: Any) -> None:
    """Whoever creates an operation cannot approve it (adjustments, discounts, refunds)."""
    if creator is None or approver is None or creator.pk == approver.pk:
        raise PermissionDenied("La misma persona no puede crear y aprobar esta operación.")
