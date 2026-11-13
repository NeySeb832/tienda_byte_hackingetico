"""Technical services price list."""

from decimal import Decimal

from apps.services_desk.selectors import technical_services


def test_services_have_positive_prices():
    services = technical_services()
    assert services
    for service in services:
        assert isinstance(service.price, Decimal)
        assert service.price > 0
        assert service.name
        assert service.detail
