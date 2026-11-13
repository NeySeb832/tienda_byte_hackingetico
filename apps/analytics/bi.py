"""Read-side of the BI module: dashboard datasets from the gold layer (read-only DuckDB)."""

from pathlib import Path
from typing import Any

import duckdb

from apps.analytics.pipeline import MONTHS_ES, lake

TABLES = ("fact_sales", "dim_date", "dim_product", "dim_store", "dim_customer", "forecast_monthly")


def gold_ready(base: Path | None = None) -> bool:
    gold = (base or lake()) / "gold"
    return all((gold / f"{name}.parquet").exists() for name in TABLES)


def dashboard(base: Path | None = None) -> dict[str, Any]:
    gold = (base or lake()) / "gold"
    con = duckdb.connect()
    for name in TABLES:
        con.read_parquet(str(gold / f"{name}.parquet")).create_view(name, replace=True)

    def rows(sql: str) -> list[tuple[Any, ...]]:
        return con.execute(sql).fetchall()

    kpi = rows("""SELECT sum(revenue), count(DISTINCT order_id), sum(quantity),
                  sum(revenue) / nullif(count(DISTINCT order_id), 0)
           FROM fact_sales f JOIN dim_date d USING (date_key)
           WHERE d.date > (SELECT max(date) FROM dim_date) - INTERVAL 365 DAY""")[0]
    monthly = rows(
        """SELECT d.year, d.month, sum(f.revenue) FROM fact_sales f JOIN dim_date d USING (date_key)
           GROUP BY 1, 2 ORDER BY 1, 2"""
    )
    forecast = rows("SELECT year, month, revenue, low, high FROM forecast_monthly ORDER BY 1, 2")
    # The forecast starts after the last complete month: drop partial months it overlaps.
    if forecast:
        first = (forecast[0][0], forecast[0][1])
        monthly = [row for row in monthly if (row[0], row[1]) < first]
    data = {
        "kpis": {
            "revenue": float(kpi[0] or 0),
            "orders": int(kpi[1] or 0),
            "units": int(kpi[2] or 0),
            "ticket": float(kpi[3] or 0),
        },
        "monthly": {
            "labels": [f"{MONTHS_ES[m]} {y}" for y, m, _ in monthly]
            + [f"{MONTHS_ES[m]} {y}" for y, m, *_ in forecast],
            "actual": [round(float(v)) for *_, v in monthly] + [None] * len(forecast),
            "forecast": [None] * (len(monthly) - 1)
            + [round(float(monthly[-1][2])) if monthly else None]
            + [round(float(v)) for _, _, v, _, _ in forecast],
        },
        "categories": [
            {"name": name, "value": round(float(value))}
            for name, value in rows(
                """SELECT p.category, sum(f.revenue) FROM fact_sales f JOIN dim_product p USING (product_key)
                   GROUP BY 1 ORDER BY 2 DESC LIMIT 8"""
            )
        ],
        "stores": [
            {"name": name, "value": round(float(value))}
            for name, value in rows(
                """SELECT s.store, sum(f.revenue) FROM fact_sales f JOIN dim_store s USING (store_key)
                   GROUP BY 1 ORDER BY 2 DESC"""
            )
        ],
        "channels": [
            {
                "name": "Tienda en línea" if channel == "web" else "Punto de venta",
                "value": round(float(value)),
            }
            for channel, value in rows(
                "SELECT channel, sum(revenue) FROM fact_sales GROUP BY 1 ORDER BY 2 DESC"
            )
        ],
        "segments": [
            {"name": name, "value": int(count)}
            for name, count in rows(
                "SELECT segment, count(*) FROM dim_customer GROUP BY 1 ORDER BY 2 DESC"
            )
        ],
        "weekdays": [
            {
                "name": ["", "lun", "mar", "mié", "jue", "vie", "sáb", "dom"][int(day)],
                "value": round(float(value)),
            }
            for day, value in rows("""SELECT d.weekday, avg(daily) FROM (
                       SELECT date_key, sum(revenue) AS daily FROM fact_sales GROUP BY 1) t
                   JOIN dim_date d USING (date_key) GROUP BY 1 ORDER BY 1""")
        ],
        "top_products": [
            {"name": name, "units": int(units), "revenue": round(float(revenue))}
            for name, units, revenue in rows(
                """SELECT p.product, sum(f.quantity), sum(f.revenue) FROM fact_sales f
                   JOIN dim_product p USING (product_key) GROUP BY 1 ORDER BY 3 DESC LIMIT 10"""
            )
        ],
    }
    con.close()
    return data
