"""Read-side queries for the services_desk app.

Until repair tickets and the services catalogue exist (Phase 6), the price list
of technical services shown on the home page is a curated static definition
taken from the store's master price list (COP, VAT included).
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ServiceOffer:
    name: str
    detail: str
    price: Decimal


def technical_services() -> list[ServiceOffer]:
    return [
        ServiceOffer(
            "Cambio de joystick", "Controles de PS5 y Xbox Series, por unidad", Decimal("35000")
        ),
        ServiceOffer(
            "Cambio de joystick en Joy-Con", "Nintendo Switch, por unidad", Decimal("35000")
        ),
        ServiceOffer(
            "Cambio de joystick en controles pro",
            "DualSense Edge y Xbox Elite, por unidad",
            Decimal("45000"),
        ),
        ServiceOffer(
            "Mantenimiento preventivo",
            "PS4 y Xbox One: limpieza interna y cambio de pasta térmica",
            Decimal("90000"),
        ),
    ]
