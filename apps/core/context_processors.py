"""Template context shared by every page."""

from decimal import Decimal
from typing import Any

from django.conf import settings
from django.http import HttpRequest


def site(request: HttpRequest) -> dict[str, Any]:
    return {
        "site_name": settings.BYTE_SITE_NAME,
        "free_shipping_from": Decimal(settings.BYTE_FREE_SHIPPING_FROM),
    }
