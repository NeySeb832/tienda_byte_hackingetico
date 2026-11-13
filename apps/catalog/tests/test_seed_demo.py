"""The demo catalogue respects the business rules (prices, licences, no pirated consoles)."""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.catalog import demo_data
from apps.catalog.models import Product, ProductVariant
from apps.cms.selectors import image_credits
from apps.inventory.models import StockItem, Store
from apps.pricing.models import PriceHistory

FORBIDDEN = ("programad", "copia", "chip", "emulador", "liberaci")


def test_demo_data_excludes_unlicensed_software():
    for spec in demo_data.PRODUCTS:
        text = " ".join([spec["name"], spec.get("short", ""), spec.get("description", "")]).lower()
        for word in FORBIDDEN:
            assert word not in text, (spec["slug"], word)


def test_demo_data_is_consistent():
    slugs = [spec["slug"] for spec in demo_data.PRODUCTS]
    skus = [row[0] for spec in demo_data.PRODUCTS for row in spec["variants"]]
    assert len(slugs) == len(set(slugs))
    assert len(skus) == len(set(skus))
    photos = {credit.slug for credit in image_credits()}
    categories = {row[0] for row in demo_data.CATEGORIES}
    for spec in demo_data.PRODUCTS:
        assert spec["category"] in categories
        if spec.get("image"):
            assert spec["image"] in photos, spec["slug"]
        for row in spec["variants"]:
            price = row[2]
            if spec["mode"] == "fixed":
                assert isinstance(price, int), row[0]
                assert price > 0, row[0]
            else:
                assert price is None, row[0]
                assert spec["base"] > 0, row[0]
            if len(row) > 3 and "image" in row[3]:
                assert row[3]["image"] in photos


@pytest.mark.django_db
def test_seed_demo_is_idempotent(monkeypatch):
    subset = [
        spec
        for spec in demo_data.PRODUCTS
        if spec["slug"] in {"xbox-series-s", "control-dualsense", "astro-bot"}
    ]
    monkeypatch.setattr(demo_data, "PRODUCTS", subset)
    out = StringIO()
    call_command("seed_demo", stdout=out)
    assert "3 productos" in out.getvalue()
    counts = (
        Product.objects.count(),
        ProductVariant.objects.count(),
        StockItem.objects.count(),
        PriceHistory.objects.count(),
    )
    call_command("seed_demo", stdout=StringIO())
    assert counts == (
        Product.objects.count(),
        ProductVariant.objects.count(),
        StockItem.objects.count(),
        PriceHistory.objects.count(),
    )
    assert Store.objects.count() == len(demo_data.STORES)
    assert ProductVariant.objects.get(sku="XSS-512-U").price == 1700000  # modifiers mode
    assert Product.objects.get(slug="astro-bot").game.esrb == "E10+"
    assert Product.objects.get(slug="control-dualsense").search_text
