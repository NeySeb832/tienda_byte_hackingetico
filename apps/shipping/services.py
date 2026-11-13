"""Shipping quotes by department (national rates by zone, VAT included)."""

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.core.models import City
from apps.shipping.models import ShippingZone


@dataclass(frozen=True, slots=True)
class ShippingQuote:
    zone: str
    price: Decimal
    min_days: int
    max_days: int
    free: bool

    @property
    def days_label(self) -> str:
        if self.min_days == self.max_days:
            return f"{self.min_days} día{'s' if self.min_days != 1 else ''} hábil{'es' if self.min_days != 1 else ''}"
        return f"{self.min_days} a {self.max_days} días hábiles"


def quote(city: City, subtotal: Decimal) -> ShippingQuote:
    """Price and delivery time for ``city``. Raises ``ValidationError`` if not covered."""
    zone = (
        ShippingZone.objects.filter(is_active=True, departments=city.department_id)
        .order_by("sort")
        .first()
    )
    if zone is None:
        raise ValidationError("Por ahora no enviamos a esa ciudad. Puedes recoger en tienda.")
    free = zone.free_from is not None and subtotal >= zone.free_from
    return ShippingQuote(
        zone=zone.name,
        price=Decimal("0") if free else zone.price,
        min_days=zone.min_days,
        max_days=zone.max_days,
        free=free,
    )
