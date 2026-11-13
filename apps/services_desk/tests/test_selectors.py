"""Technical services price list."""

from decimal import Decimal

import pytest

from apps.services_desk.selectors import technical_services

pytestmark = pytest.mark.django_db


def test_services_have_positive_prices():
    services = technical_services()
    assert services
    for service in services:
        assert isinstance(service.price, Decimal)
        assert service.price > 0
        assert service.name
        assert service.detail
