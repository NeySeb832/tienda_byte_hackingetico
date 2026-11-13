"""Operational reports for the panel (sales, products, stores) and the dashboard KPIs.

Only paid orders count as sales (paid, preparing, ready, shipped, delivered).
"""

import csv
import io
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Count, F, Q, QuerySet, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.inventory.models import InventoryAdjustment, StockItem, Store
from apps.orders.models import Order, OrderLine
from apps.promotions.models import Coupon
from apps.purchasing.models import PurchaseOrder

SOLD = (
    Order.Status.PAID,
    Order.Status.PREPARING,
    Order.Status.READY_FOR_PICKUP,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
)
LOW_STOCK = 2


def sales(stores: QuerySet[Store] | None = None) -> QuerySet[Order]:
    queryset = Order.objects.filter(status__in=SOLD)
    if stores is not None:
        queryset = queryset.filter(
            Q(pickup_store__in=stores) | Q(fulfillment=Order.Fulfillment.SHIPPING)
        )
    return queryset


@dataclass(frozen=True, slots=True)
class DayRow:
    day: date
    orders: int
    total: Decimal


def sales_by_day(days: int = 30, *, today: date | None = None) -> list[DayRow]:
    today = today or timezone.localdate()
    start = today - timedelta(days=days - 1)
    rows = {
        row["day"]: row
        for row in sales()
        .filter(paid_at__date__gte=start)
        .annotate(day=TruncDate("paid_at"))
        .values("day")
        .annotate(orders=Count("pk"), total=Sum("total"))
    }
    return [
        DayRow(
            day=start + timedelta(days=offset),
            orders=rows.get(start + timedelta(days=offset), {}).get("orders", 0),
            total=rows.get(start + timedelta(days=offset), {}).get("total") or Decimal("0"),
        )
        for offset in range(days)
    ]


def sales_by_channel(days: int = 30) -> list[dict[str, Any]]:
    since = timezone.now() - timedelta(days=days)
    labels = dict(Order.Channel.choices)
    return [
        {"channel": labels[row["channel"]], "orders": row["orders"], "total": row["total"]}
        for row in sales()
        .filter(paid_at__gte=since)
        .values("channel")
        .annotate(orders=Count("pk"), total=Sum("total"))
        .order_by("-total")
    ]


def top_products(days: int = 30, limit: int = 10) -> list[dict[str, Any]]:
    since = timezone.now() - timedelta(days=days)
    return list(
        OrderLine.objects.filter(order__status__in=SOLD, order__paid_at__gte=since)
        .values("name")
        .annotate(units=Sum("quantity"), total=Sum("line_total"))
        .order_by("-total")[:limit]
    )


def sales_by_store(days: int = 30) -> list[dict[str, Any]]:
    since = timezone.now() - timedelta(days=days)
    return [
        {
            "store": row["pickup_store__name"] or "Envíos a domicilio",
            "orders": row["orders"],
            "total": row["total"],
        }
        for row in sales()
        .filter(paid_at__gte=since)
        .values("pickup_store__name")
        .annotate(orders=Count("pk"), total=Sum("total"))
        .order_by("-total")
    ]


@dataclass(frozen=True, slots=True)
class Kpis:
    sales_today: Decimal
    orders_today: int
    sales_30d: Decimal
    to_prepare: int
    low_stock: int
    pending_approvals: int


def kpis(stores: QuerySet[Store]) -> Kpis:
    today = timezone.localdate()
    sold = sales(stores)
    todays = sold.filter(paid_at__date=today).aggregate(total=Sum("total"), n=Count("pk"))
    month = sold.filter(paid_at__gte=timezone.now() - timedelta(days=30)).aggregate(
        total=Sum("total")
    )
    return Kpis(
        sales_today=todays["total"] or Decimal("0"),
        orders_today=todays["n"] or 0,
        sales_30d=month["total"] or Decimal("0"),
        to_prepare=sold.filter(status__in=(Order.Status.PAID, Order.Status.PREPARING)).count(),
        # Variants (not store rows) whose free units across the user's stores are low.
        low_stock=StockItem.objects.filter(store__in=stores, variant__is_active=True)
        .values("variant")
        .annotate(free=Sum(F("quantity") - F("reserved")))
        .filter(free__lte=LOW_STOCK)
        .count(),
        pending_approvals=InventoryAdjustment.objects.filter(
            status="pending", store__in=stores
        ).count()
        + PurchaseOrder.objects.filter(status="draft", store__in=stores).count()
        + Coupon.objects.filter(
            kind="percent", approved_by=None, is_active=True, value__gt=15
        ).count(),
    )


# --- CSV export (OWASP: CSV/formula injection) -------------------------------------------------

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: Any) -> str:
    """Neutralise spreadsheet formulas: a leading ``=+-@`` becomes literal text."""
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(FORMULA_PREFIXES) else text


def to_csv(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([safe_cell(cell) for cell in header])
    for row in rows:
        writer.writerow([safe_cell(cell) for cell in row])
    return buffer.getvalue()
