"""Panel menu for staff (empty for everyone else)."""

from typing import Any

from django.http import HttpRequest

from apps.panel.menu import menu_for


def panel(request: HttpRequest) -> dict[str, Any]:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.is_staff:
        return {"panel_menu": []}
    return {"panel_menu": menu_for(user)}
