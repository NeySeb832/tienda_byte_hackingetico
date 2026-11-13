"""Money helpers for COP amounts (ADR-0004).

Rules:
* Amounts are ``Decimal`` with two decimal places; ``float`` is rejected.
* Catalogue prices include VAT; ``split_vat`` derives base and VAT per line.
* Rounding is ROUND_HALF_UP.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
PESO = Decimal("1")
VAT_STANDARD = Decimal("0.19")
VAT_EXCLUDED = Decimal("0")

MoneyInput = Decimal | int | str


def to_money(value: MoneyInput) -> Decimal:
    """Convert ``value`` to a Decimal rounded to cents.

    Raises ``TypeError`` for floats/booleans/other types and ``ValueError`` for
    values that are not finite numbers.
    """
    if isinstance(value, bool) or not isinstance(value, Decimal | int | str):
        raise TypeError("Money values must be Decimal, int or str (never float).")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid money amount: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError("Invalid money amount: it must be a finite number.")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def round_to_peso(value: MoneyInput) -> Decimal:
    """Round to whole pesos (prices shown to customers)."""
    return to_money(value).quantize(PESO, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class VatBreakdown:
    gross: Decimal
    base: Decimal
    vat: Decimal
    rate: Decimal


def split_vat(gross: MoneyInput, rate: Decimal = VAT_STANDARD) -> VatBreakdown:
    """Split a VAT-inclusive amount into taxable base and VAT.

    ``base + vat == gross`` always holds, so invoices never drift by a cent.
    """
    amount = to_money(gross)
    if amount < 0:
        raise ValueError("Gross amount cannot be negative.")
    if not isinstance(rate, Decimal) or rate < 0 or rate >= 1:
        raise ValueError("VAT rate must be a Decimal in the range [0, 1).")
    base = (amount / (Decimal(1) + rate)).quantize(CENT, rounding=ROUND_HALF_UP)
    return VatBreakdown(gross=amount, base=base, vat=amount - base, rate=rate)


def format_cop(value: MoneyInput) -> str:
    """Format as Colombian pesos: ``$ 1.299.900`` or ``$ 1.234,50`` (non-breaking space)."""
    amount = to_money(value)
    sign = "-" if amount < 0 else ""
    whole, fraction = divmod(abs(amount), 1)
    integer = f"{int(whole):,}".replace(",", ".")
    text = f"{sign}$\u00a0{integer}"
    if fraction:
        text += f",{int(fraction * 100):02d}"
    return text
