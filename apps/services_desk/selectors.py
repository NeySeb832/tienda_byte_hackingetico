"""Read-side queries for the services_desk app: the price list of technical services."""

from dataclasses import dataclass
from decimal import Decimal

from apps.services_desk.models import TechnicalService


@dataclass(frozen=True, slots=True)
class ServiceOffer:
    name: str
    detail: str
    price: Decimal


def technical_services() -> list[ServiceOffer]:
    return [
        ServiceOffer(service.name, service.detail, service.price)
        for service in TechnicalService.objects.filter(is_active=True).order_by("sort", "name")
    ]
