"""Back-office menu filtered by the permissions of the current user."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class MenuItem:
    label: str
    url_name: str
    permission: str


MENU = (
    MenuItem("Resumen", "panel:dashboard", "accounts.access_panel"),
    MenuItem("Personal y roles", "panel:staff", "accounts.manage_staff"),
    MenuItem("Auditoría", "panel:audit", "audit.view_auditlog"),
    MenuItem("Eventos de seguridad", "panel:security", "audit.view_securityevent"),
)


def menu_for(user: Any) -> list[MenuItem]:
    return [item for item in MENU if user.has_perm(item.permission)]
