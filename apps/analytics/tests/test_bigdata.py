"""BI: synthetic history, medallion pipeline, star schema, RFM, forecast and dashboard access."""

from datetime import date
from decimal import Decimal

import duckdb
import pytest
from django.urls import reverse

from apps.accounts import roles
from apps.analytics import bi, pipeline, synthetic
from tests.factories import make_product, make_store, make_user_with_role


def test_black_friday_and_seasonality():
    assert synthetic.black_friday(2026) == date(2026, 11, 27)
    start = date(2025, 1, 1)
    assert synthetic.demand_factor(date(2025, 12, 13), start) > synthetic.demand_factor(
        date(2025, 2, 15), start
    )
    assert synthetic.demand_factor(synthetic.black_friday(2025), start) > 3


def test_generator_is_deterministic():
    catalog = [
        synthetic.CatalogItem("A-1", Decimal("100000"), 1.0),
        synthetic.CatalogItem("B-2", Decimal("50000"), 2.0),
    ]
    first = list(synthetic.generate(catalog, ["BOG"], days=30, end=date(2026, 1, 31)))
    second = list(synthetic.generate(catalog, ["BOG"], days=30, end=date(2026, 1, 31)))
    assert first == second
    assert {row[3] for row in first} == {"web", "pos"}
    assert all(row[5].startswith("C") for row in first)  # opaque customer keys, no personal data


def test_forecast_follows_trend_and_seasonality():
    history = [(2024 + (m - 1) // 12, (m - 1) % 12 + 1, 1000.0 + 50 * m) for m in range(1, 27)]
    forecast = pipeline.forecast_monthly(history)
    assert [(f.year, f.month) for f in forecast] == [(2026, 2), (2026, 3), (2026, 4)]
    assert forecast[0].revenue > history[-2][2]
    assert all(f.low <= f.revenue <= f.high for f in forecast)
    assert pipeline.forecast_monthly(history[:2]) == []


@pytest.mark.django_db
def test_pipeline_builds_star_schema_without_personal_data(tmp_path, settings):
    settings.BYTE_DATA_LAKE_DIR = tmp_path
    store = make_store(code="BOG")
    make_product("Consola", store=store, variants=[("CON-N", {"condition": "Nuevo"}, 1000000)])
    make_product("Control", store=store, variants=[("PAD-N", {"condition": "Nuevo"}, 200000)])
    base = pipeline.lake()
    pipeline.extract_oltp(base)
    catalog = [
        synthetic.CatalogItem("CON-N", Decimal("1000000"), 1.0),
        synthetic.CatalogItem("PAD-N", Decimal("200000"), 3.0),
    ]
    rows = synthetic.write_csv(
        base / "bronze" / "synthetic_sales.csv",
        synthetic.generate(catalog, ["BOG"], days=400, end=date(2026, 11, 1), orders_per_day=5),
    )
    # A malformed bronze row must be filtered out by the silver layer.
    with (base / "bronze" / "synthetic_sales.csv").open("a", encoding="utf-8") as handle:
        handle.write("SBAD,1,no-es-fecha,web,WEB,C1,CON-N,-1,0,synthetic\n")
    stats = pipeline.build(base)
    assert stats["fact_rows"] == rows
    assert stats["forecast_months"] == 3
    con = duckdb.connect()
    gold = base / "gold"
    for table in bi.TABLES:
        assert (gold / f"{table}.parquet").exists()
    columns = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{(gold / 'fact_sales.parquet').as_posix()}')"
    ).fetchall()
    assert {c[0] for c in columns} >= {
        "date_key",
        "product_key",
        "store_key",
        "customer_key",
        "revenue",
        "vat",
    }
    for table in bi.TABLES:
        path = (gold / f"{table}.parquet").as_posix()
        text_columns = [
            c[0]
            for c in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()
            if c[1] == "VARCHAR"
        ]
        for column in text_columns:
            leaked = con.execute(
                f"SELECT count(*) FROM read_parquet('{path}') WHERE \"{column}\" LIKE '%@%'"
            ).fetchone()[
                0
            ]  # type: ignore[index]
            assert leaked == 0, (table, column)
    segments = {
        row[0]
        for row in con.execute(
            f"SELECT DISTINCT segment FROM read_parquet('{(gold / 'dim_customer.parquet').as_posix()}')"
        ).fetchall()
    }
    assert segments <= {"Campeones", "Leales", "Nuevos", "En riesgo", "Hibernando", "Potenciales"}
    data = bi.dashboard(base)
    assert data["kpis"]["orders"] > 0
    assert (
        len(data["monthly"]["labels"])
        == len(data["monthly"]["actual"])
        == len(data["monthly"]["forecast"])
    )


@pytest.mark.django_db
def test_dashboard_access(client, setup_roles, tmp_path, settings):
    settings.BYTE_DATA_LAKE_DIR = tmp_path
    analyst = make_user_with_role(roles.ANALYST)
    client.force_login(analyst)
    response = client.get(reverse("panel:bi"))
    assert response.status_code == 200
    assert "seed_bigdata" in response.content.decode()
    client.force_login(make_user_with_role(roles.WAREHOUSE))
    assert client.get(reverse("panel:bi")).status_code == 403
