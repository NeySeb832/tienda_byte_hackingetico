"""Number of units in the visitor's cart (header badge)."""

from typing import Any

from django.http import HttpRequest

from apps.cart.selectors import cart_count
from apps.cart.services import get_cart


def cart(request: HttpRequest) -> dict[str, Any]:
    session = getattr(request, "session", None)
    if session is None:
        return {"cart_count": 0}
    return {"cart_count": cart_count(get_cart(session, getattr(request, "user", None)))}
