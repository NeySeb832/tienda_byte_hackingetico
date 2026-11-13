"""Money helpers (ADR-0004)."""

from decimal import Decimal

import pytest

from apps.core.money import VAT_EXCLUDED, format_cop, round_to_peso, split_vat, to_money

NBSP = "\u00a0"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("10"), Decimal("10.00")),
        (10, Decimal("10.00")),
        ("1234.565", Decimal("1234.57")),
        ("0.005", Decimal("0.01")),
        (" 99.9 ", Decimal("99.90")),
    ],
)
def test_to_money_accepts_exact_types(value, expected):
    assert to_money(value) == expected


@pytest.mark.parametrize("value", [10.5, True, None, [1]])
def test_to_money_rejects_floats_and_other_types(value):
    with pytest.raises(TypeError):
        to_money(value)


@pytest.mark.parametrize("value", ["abc", "", "NaN", "Infinity"])
def test_to_money_rejects_non_numeric_values(value):
    with pytest.raises(ValueError, match="money amount"):
        to_money(value)


@pytest.mark.parametrize(
    ("value", "expected"), [("1000.50", Decimal("1001")), ("1000.49", Decimal("1000"))]
)
def test_round_to_peso_is_half_up(value, expected):
    assert round_to_peso(value) == expected


def test_split_vat_standard_rate():
    breakdown = split_vat("2399900")
    assert breakdown.base == Decimal("2016722.69")
    assert breakdown.vat == Decimal("383177.31")
    assert breakdown.base + breakdown.vat == breakdown.gross


@pytest.mark.parametrize("gross", ["1", "99.99", "149900", "2399900", "7777777.77", "0"])
def test_split_vat_never_loses_a_cent(gross):
    breakdown = split_vat(gross)
    assert breakdown.base + breakdown.vat == to_money(gross)


def test_split_vat_excluded_products():
    breakdown = split_vat("200000", rate=VAT_EXCLUDED)
    assert breakdown.base == Decimal("200000.00")
    assert breakdown.vat == Decimal("0.00")


def test_split_vat_rejects_negative_amounts():
    with pytest.raises(ValueError, match="cannot be negative"):
        split_vat("-1")


@pytest.mark.parametrize("rate", [Decimal("1"), Decimal("-0.1"), 0.19])
def test_split_vat_rejects_invalid_rates(rate):
    with pytest.raises(ValueError, match="VAT rate"):
        split_vat("1000", rate=rate)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("2399900"), f"${NBSP}2.399.900"),
        ("1234.5", f"${NBSP}1.234,50"),
        (0, f"${NBSP}0"),
        (999, f"${NBSP}999"),
        ("-1000", f"-${NBSP}1.000"),
    ],
)
def test_format_cop(value, expected):
    assert format_cop(value) == expected
