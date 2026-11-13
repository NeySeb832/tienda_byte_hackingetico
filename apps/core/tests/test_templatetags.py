"""The ``cop`` template filter."""

from decimal import Decimal

import pytest
from django.template import Context, Template


def render(value) -> str:
    return Template("{% load money %}{{ value|cop }}").render(Context({"value": value}))


def test_cop_filter_formats_pesos():
    assert render(Decimal("2399900")) == "$\u00a02.399.900"


@pytest.mark.parametrize("value", [1.5, "abc", None])
def test_cop_filter_fails_safe(value):
    assert render(value) == ""
