"""Deterministic synthetic sales history for the BI module (bronze layer input).

Realistic patterns: weekly cycle (weekends sell more), December and Black Friday peaks,
January slump, gradual growth, product popularity from the catalogue and two channels.
Customers are opaque keys (``C000123``): the synthetic history contains no personal data.
"""

import csv
import random
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

HEADER = [
    "order_id",
    "line_no",
    "order_date",
    "channel",
    "store_code",
    "customer_key",
    "sku",
    "quantity",
    "unit_price",
    "source",
]
MONTH_FACTOR = {
    1: 0.75,
    2: 0.8,
    3: 0.9,
    4: 0.9,
    5: 0.95,
    6: 1.05,
    7: 1.0,
    8: 0.95,
    9: 0.95,
    10: 1.0,
    11: 1.35,
    12: 1.9,
}
WEEKDAY_FACTOR = {0: 0.8, 1: 0.85, 2: 0.9, 3: 0.95, 4: 1.15, 5: 1.35, 6: 1.0}


@dataclass(frozen=True, slots=True)
class CatalogItem:
    sku: str
    price: Decimal
    weight: float


def black_friday(year: int) -> date:
    """Last Friday of November."""
    day = date(year, 11, 30)
    while day.weekday() != 4:
        day -= timedelta(days=1)
    return day


def demand_factor(day: date, start: date) -> float:
    growth = 1 + 0.25 * ((day - start).days / 365)  # +25 % per year
    factor = MONTH_FACTOR[day.month] * WEEKDAY_FACTOR[day.weekday()] * growth
    if day == black_friday(day.year):
        factor *= 3.0
    return factor


def generate(
    catalog: list[CatalogItem],
    stores: list[str],
    *,
    days: int = 730,
    end: date,
    orders_per_day: int = 45,
    customers: int = 6000,
    seed: int = 2026,
) -> Iterator[list[str]]:
    rng = random.Random(seed)  # noqa: S311 - synthetic data, not security sensitive
    start = end - timedelta(days=days - 1)
    skus = [item.sku for item in catalog]
    weights = [item.weight for item in catalog]
    prices = {item.sku: item.price for item in catalog}
    order_id = 0
    for offset in range(days):
        day = start + timedelta(days=offset)
        count = max(1, int(rng.gauss(orders_per_day * demand_factor(day, start), 6)))
        for _ in range(count):
            order_id += 1
            web = rng.random() < 0.6
            store = "WEB" if web else rng.choice(stores)
            customer = f"C{rng.randint(1, customers):06d}"
            for line_no in range(1, rng.choice([1, 1, 1, 2, 2, 3]) + 1):
                sku = rng.choices(skus, weights=weights)[0]
                # Historical prices drift a little around today's price.
                price = (prices[sku] * Decimal(str(round(rng.uniform(0.95, 1.05), 3)))).quantize(
                    Decimal("1")
                )
                yield [
                    f"S{order_id:07d}",
                    str(line_no),
                    day.isoformat(),
                    "web" if web else "pos",
                    store,
                    customer,
                    sku,
                    str(rng.choice([1, 1, 1, 1, 2])),
                    str(price),
                    "synthetic",
                ]


def write_csv(path: Path, rows: Iterator[list[str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for row in rows:
            writer.writerow(row)
            total += 1
    return total
