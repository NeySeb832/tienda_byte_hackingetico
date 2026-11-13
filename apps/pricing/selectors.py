"""Read-side queries for pricing: lowest recent price, honest reference price, sparkline.

Consumer rule (Ley 1480 de 2011 and SIC guidance on promotions): a product may only be
shown with a struck-through "before" price when that price was really charged. Byte shows
it only after a real price drop in the last 30 days, and the reference is the lowest price
charged in the 30 days before that drop.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone

from apps.catalog.models import ProductVariant

WINDOW_DAYS = 30

Entry = tuple[datetime, Decimal, Decimal | None]


@dataclass(frozen=True, slots=True)
class PriceInsight:
    current: Decimal
    lowest_30d: Decimal
    reference: Decimal | None = None

    @property
    def saving(self) -> Decimal:
        return self.reference - self.current if self.reference else Decimal("0")

    @property
    def saving_pct(self) -> int:
        if not self.reference:
            return 0
        return int((self.saving * 100 / self.reference).to_integral_value())


@dataclass(frozen=True, slots=True)
class Sparkline:
    points: str
    width: int
    height: int
    low: Decimal
    high: Decimal
    changes: int
    days: int
    since: datetime

    @property
    def is_flat(self) -> bool:
        return self.low == self.high


def _entries(variant: ProductVariant) -> list[Entry]:
    return [
        (entry.changed_at, entry.price, entry.previous_price)
        for entry in sorted(variant.price_history.all(), key=lambda e: (e.changed_at, e.pk))
    ]


def _prices_between(entries: list[Entry], start: datetime, end: datetime) -> list[Decimal]:
    """Prices in effect at some moment of [start, end)."""
    prices = [price for at, price, _ in entries if start < at < end]
    before = [price for at, price, _ in entries if at <= start]
    if before:
        prices.append(before[-1])
    return prices


def price_insight(variant: ProductVariant, *, now: datetime | None = None) -> PriceInsight:
    now = now or timezone.now()
    window = timedelta(days=WINDOW_DAYS)
    entries = _entries(variant)
    current = variant.price
    lowest = min([current, *_prices_between(entries, now - window, now)])
    reference = None
    if entries:
        last_at, last_price, previous = entries[-1]
        dropped = previous is not None and last_price < previous and last_price == current
        if dropped and last_at >= now - window:
            before_drop = _prices_between(entries[:-1], last_at - window, last_at)
            if before_drop and min(before_drop) > current:
                reference = min(before_drop)
    return PriceInsight(current=current, lowest_30d=lowest, reference=reference)


def price_sparkline(
    variant: ProductVariant,
    *,
    days: int = 90,
    now: datetime | None = None,
    width: int = 240,
    height: int = 48,
) -> Sparkline:
    """Step line of the price over the last ``days`` days, as SVG polyline points."""
    now = now or timezone.now()
    start = now - timedelta(days=days)
    entries = _entries(variant)
    before = [price for at, price, _ in entries if at <= start]
    in_window = [(at, price, prev) for at, price, prev in entries if start < at <= now]
    if before:
        series = [(start, before[-1])] + [(at, price) for at, price, _ in in_window]
    elif in_window:
        series = [(at, price) for at, price, _ in in_window]
    else:
        series = [(start, variant.price)]
    prices = [price for _, price in series] + [variant.price]
    low, high = min(prices), max(prices)
    pad = 4
    span = (now - start).total_seconds()

    def x(at: datetime) -> float:
        return round((at - start).total_seconds() / span * width, 1)

    def y(price: Decimal) -> float:
        if high == low:
            return height / 2
        return round(pad + float((high - price) / (high - low)) * (height - 2 * pad), 1)

    points: list[str] = []
    previous: Decimal | None = None
    for at, price in series:
        if previous is not None:
            points.append(f"{x(at)},{y(previous)}")
        points.append(f"{x(at)},{y(price)}")
        previous = price
    points.append(f"{float(width)},{y(variant.price)}")
    return Sparkline(
        points=" ".join(points),
        width=width,
        height=height,
        low=low,
        high=high,
        changes=sum(1 for _, _, prev in in_window if prev is not None),
        days=days,
        since=series[0][0],
    )
