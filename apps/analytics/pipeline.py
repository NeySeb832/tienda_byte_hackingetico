"""Medallion pipeline with DuckDB over Parquet files (ADR-0017).

Files are attached through DuckDB's relational API and every SQL statement is a constant:
no path or value is ever interpolated into SQL text.

* **Bronze**: raw extracts — synthetic history (CSV) and OLTP exports (pseudonymised).
* **Silver**: typed, de-duplicated, validated sales lines and dimensions.
* **Gold**: star schema (``fact_sales`` + ``dim_date``, ``dim_product``, ``dim_store``,
  ``dim_customer``) and model outputs (RFM segments, monthly forecast).

No personal data reaches the lake: customers are HMAC keys (blind index), never emails.
Every file is written to a temporary name and then renamed (atomic per table).
"""

import csv
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
from django.conf import settings
from django.utils import timezone

from apps.catalog.models import ProductVariant
from apps.core.crypto import blind_index
from apps.inventory.models import Store
from apps.orders.models import OrderLine

SOLD = ("paid", "preparing", "ready_for_pickup", "shipped", "delivered")
MONTHS_ES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def lake() -> Path:
    path = Path(settings.BYTE_DATA_LAKE_DIR)
    for layer in ("bronze", "silver", "gold"):
        (path / layer).mkdir(parents=True, exist_ok=True)
    return path


def _scalar(con: duckdb.DuckDBPyConnection, sql: str) -> Any:
    row = con.execute(sql).fetchone()
    return row[0] if row else None


def _register(con: duckdb.DuckDBPyConnection, name: str, path: Path) -> None:
    """Expose a Parquet file as a view; paths go through the API, never into SQL text."""
    con.read_parquet(str(path)).create_view(name, replace=True)


def _save(con: duckdb.DuckDBPyConnection, sql: str, target: Path) -> None:
    tmp = target.with_suffix(".tmp.parquet")
    con.sql(sql).write_parquet(str(tmp))
    os.replace(tmp, target)


# --- Bronze -----------------------------------------------------------------------------------


def extract_oltp(base: Path) -> dict[str, int]:
    """Export catalogue, stores and sold lines from PostgreSQL to bronze CSV files."""
    bronze = base / "bronze"
    counts = {}
    with (bronze / "products.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["sku", "product", "category", "brand", "product_type", "condition", "price"]
        )
        rows = 0
        for variant in ProductVariant.objects.select_related(
            "product__category", "product__brand"
        ).prefetch_related("values__attribute"):
            condition = next(
                (v.value for v in variant.values.all() if v.attribute.code == "condition"), "Nuevo"
            )
            product = variant.product
            writer.writerow(
                [
                    variant.sku,
                    product.name,
                    product.category.name,
                    product.brand.name if product.brand else "Sin marca",
                    product.get_product_type_display(),
                    condition,
                    variant.price,
                ]
            )
            rows += 1
        counts["products"] = rows
    with (bronze / "stores.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["store_code", "store", "city", "department"])
        writer.writerow(["WEB", "Tienda en línea", "Nacional", "Nacional"])
        for store in Store.objects.select_related("city__department"):
            writer.writerow([store.code, store.name, store.city.name, store.city.department.name])
        counts["stores"] = Store.objects.count() + 1
    with (bronze / "oltp_sales.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
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
        )
        rows = 0
        lines = (
            OrderLine.objects.filter(order__status__in=SOLD, order__paid_at__isnull=False)
            .select_related("order__pickup_store")
            .order_by("order_id", "pk")
        )
        for index, line in enumerate(lines, start=1):
            order = line.order
            store_code = (
                order.pickup_store.code if order.channel == "pos" and order.pickup_store else "WEB"
            )
            # Pseudonymised customer: keyed HMAC of the user id, never the email.
            customer = "K" + blind_index(str(order.user_id))[:16] if order.user_id else "ANON"
            writer.writerow(
                [
                    order.number,
                    index,
                    timezone.localdate(order.paid_at).isoformat(),
                    order.channel,
                    store_code,
                    customer,
                    line.sku,
                    line.quantity,
                    line.unit_price,
                    "oltp",
                ]
            )
            rows += 1
        counts["oltp_lines"] = rows
    return counts


# --- Silver and gold ----------------------------------------------------------------------------


SILVER_SALES = """
SELECT DISTINCT
    order_id, CAST(line_no AS INTEGER) AS line_no, CAST(order_date AS DATE) AS order_date,
    lower(channel) AS channel, upper(store_code) AS store_code, customer_key, upper(sku) AS sku,
    CAST(quantity AS INTEGER) AS quantity, CAST(unit_price AS DECIMAL(14,2)) AS unit_price, source
FROM bronze_sales
WHERE TRY_CAST(quantity AS INTEGER) > 0 AND TRY_CAST(unit_price AS DECIMAL(14,2)) > 0
  AND TRY_CAST(order_date AS DATE) IS NOT NULL AND channel IN ('web', 'pos')
"""

DIM_DATE = """
WITH bounds AS (SELECT min(order_date) AS lo, max(order_date) AS hi FROM sales),
     days AS (SELECT CAST(d AS DATE) AS d FROM bounds, range(lo, hi + INTERVAL 1 DAY, INTERVAL 1 DAY) t(d)),
     names(m, name) AS (VALUES (1, 'ene'), (2, 'feb'), (3, 'mar'), (4, 'abr'), (5, 'may'), (6, 'jun'),
                               (7, 'jul'), (8, 'ago'), (9, 'sep'), (10, 'oct'), (11, 'nov'), (12, 'dic'))
SELECT CAST(strftime(d, '%Y%m%d') AS INTEGER) AS date_key, d AS date, year(d) AS year,
       quarter(d) AS quarter, month(d) AS month, names.name AS month_name, weekofyear(d) AS week,
       isodow(d) AS weekday, isodow(d) >= 6 AS is_weekend
FROM days JOIN names ON names.m = month(d)
"""

FACT_SALES = """
SELECT CAST(strftime(s.order_date, '%Y%m%d') AS INTEGER) AS date_key, p.product_key, st.store_key,
       s.channel, s.customer_key, s.order_id, s.quantity,
       CAST(s.quantity * s.unit_price AS DECIMAL(14,2)) AS revenue,
       CAST(round(s.quantity * s.unit_price - s.quantity * s.unit_price / 1.19, 2) AS DECIMAL(14,2)) AS vat,
       s.source
FROM sales s JOIN dim_product p USING (sku) JOIN dim_store st USING (store_code)
"""

DIM_CUSTOMER = """
WITH per AS (
    SELECT f.customer_key, max(d.date) AS last_purchase, count(DISTINCT f.order_id) AS frequency,
           sum(f.revenue) AS monetary
    FROM fact_sales f JOIN dim_date d USING (date_key)
    WHERE f.customer_key <> 'ANON' GROUP BY 1),
scored AS (
    SELECT *, (SELECT max(last_purchase) FROM per) - last_purchase AS recency_days,
           ntile(5) OVER (ORDER BY last_purchase) AS r, ntile(5) OVER (ORDER BY frequency) AS f,
           ntile(5) OVER (ORDER BY monetary) AS m FROM per)
SELECT customer_key, last_purchase, recency_days, frequency, monetary, r, f, m,
       CASE WHEN r >= 4 AND f >= 4 THEN 'Campeones'
            WHEN f >= 4 THEN 'Leales'
            WHEN r >= 4 AND f <= 2 THEN 'Nuevos'
            WHEN r <= 2 AND f >= 3 THEN 'En riesgo'
            WHEN r <= 2 THEN 'Hibernando'
            ELSE 'Potenciales' END AS segment
FROM scored
"""

MONTHLY = """
SELECT d.year, d.month, sum(f.revenue) FROM fact_sales f JOIN dim_date d USING (date_key)
GROUP BY 1, 2 ORDER BY 1, 2
"""


def build(base: Path | None = None) -> dict[str, Any]:
    base = base or lake()
    bronze, silver, gold = base / "bronze", base / "silver", base / "gold"
    con = duckdb.connect()
    con.execute("SET threads TO 2")
    sources = [p for p in (bronze / "synthetic_sales.csv", bronze / "oltp_sales.csv") if p.exists()]
    if not sources:
        raise FileNotFoundError("No hay datos en la capa bronce: ejecuta seed_bigdata o extract.")
    relation = con.read_csv(str(sources[0]), header=True, all_varchar=True)
    for extra in sources[1:]:
        relation = relation.union(con.read_csv(str(extra), header=True, all_varchar=True))
    relation.create_view("bronze_sales", replace=True)
    con.read_csv(str(bronze / "products.csv"), header=True).create_view(
        "bronze_products", replace=True
    )
    con.read_csv(str(bronze / "stores.csv"), header=True).create_view("bronze_stores", replace=True)

    _save(con, SILVER_SALES, silver / "sales_lines.parquet")
    _save(con, "SELECT DISTINCT * FROM bronze_products", silver / "products.parquet")
    _save(con, "SELECT DISTINCT * FROM bronze_stores", silver / "stores.parquet")
    for name, file in (("sales", "sales_lines"), ("products", "products"), ("stores", "stores")):
        _register(con, name, silver / f"{file}.parquet")

    _save(con, DIM_DATE, gold / "dim_date.parquet")
    _save(
        con,
        "SELECT row_number() OVER (ORDER BY sku) AS product_key, * EXCLUDE (price) FROM products",
        gold / "dim_product.parquet",
    )
    _save(
        con,
        "SELECT row_number() OVER (ORDER BY store_code) AS store_key, * FROM stores",
        gold / "dim_store.parquet",
    )
    for name in ("dim_date", "dim_product", "dim_store"):
        _register(con, name, gold / f"{name}.parquet")
    _save(con, FACT_SALES, gold / "fact_sales.parquet")
    _register(con, "fact_sales", gold / "fact_sales.parquet")
    _save(con, DIM_CUSTOMER, gold / "dim_customer.parquet")

    monthly = con.execute(MONTHLY).fetchall()
    forecast = forecast_monthly([(int(y), int(m), float(v)) for y, m, v in monthly])
    con.execute(
        "CREATE TABLE fc (year INTEGER, month INTEGER, revenue DOUBLE, low DOUBLE, high DOUBLE)"
    )
    con.executemany(
        "INSERT INTO fc VALUES (?, ?, ?, ?, ?)",
        [(f.year, f.month, f.revenue, f.low, f.high) for f in forecast],
    )
    _save(con, "SELECT * FROM fc", gold / "forecast_monthly.parquet")
    _register(con, "dim_customer", gold / "dim_customer.parquet")
    stats = {
        "fact_rows": _scalar(con, "SELECT count(*) FROM fact_sales"),
        "customers": _scalar(con, "SELECT count(*) FROM dim_customer"),
        "forecast_months": len(forecast),
    }
    con.close()
    return stats


@dataclass(frozen=True, slots=True)
class Forecast:
    year: int
    month: int
    revenue: float
    low: float
    high: float


def forecast_monthly(history: list[tuple[int, int, float]], horizon: int = 3) -> list[Forecast]:
    """Linear trend times a monthly seasonal index (classical decomposition), +/- 1.96 sigma band.

    Only complete months are used: the first and last months of the history are usually partial.
    """
    full = history[1:-1] if len(history) > 3 else history
    if len(full) < 3:
        return []
    n = len(full)
    xs = list(range(n))
    ys = [value for _, _, value in full]
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / sum(
        (x - mean_x) ** 2 for x in xs
    )
    intercept = mean_y - slope * mean_x
    trend = [intercept + slope * x for x in xs]
    ratios: dict[int, list[float]] = {}
    for (_, month, value), base in zip(full, trend, strict=True):
        ratios.setdefault(month, []).append(value / base if base else 1.0)
    season = {month: sum(r) / len(r) for month, r in ratios.items()}
    fitted = [trend[i] * season.get(full[i][1], 1.0) for i in range(n)]
    sigma = math.sqrt(sum((y - f) ** 2 for y, f in zip(ys, fitted, strict=True)) / max(n - 2, 1))
    year, month = full[-1][0], full[-1][1]
    out = []
    for step in range(1, horizon + 1):
        month += 1
        if month > 12:
            year, month = year + 1, 1
        value = max((intercept + slope * (n - 1 + step)) * season.get(month, 1.0), 0.0)
        out.append(
            Forecast(
                year,
                month,
                round(value, 2),
                round(max(value - 1.96 * sigma, 0.0), 2),
                round(value + 1.96 * sigma, 2),
            )
        )
    return out


def run(*, include_oltp: bool = True) -> dict[str, Any]:
    base = lake()
    counts = extract_oltp(base) if include_oltp else {}
    return {**counts, **build(base), "built_at": timezone.localdate().isoformat()}
