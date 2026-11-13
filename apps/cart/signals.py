"""Merge the guest cart into the customer's cart at login (ADR-0008)."""

from typing import Any

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from apps.cart.services import merge_session_cart


@receiver(user_logged_in)
def merge_cart_on_login(sender: Any, request: Any, user: Any, **kwargs: Any) -> None:
    if request is not None and hasattr(request, "session"):
        merge_session_cart(request.session, user)
