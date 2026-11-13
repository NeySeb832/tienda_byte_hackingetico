"""Listings, search, facets, cards, configurator and comparator."""

from decimal import Decimal

import pytest
from django.test import override_settings

from apps.catalog import selectors
from apps.catalog.models import Product
from apps.catalog.selectors import CatalogFilters, filter_products
from apps.inventory.models import StockItem
from tests.factories import brand, category, make_product, make_store, platform

pytestmark = pytest.mark.django_db


@pytest.fixture
def store():
    return make_store()


@pytest.fixture
def catalog(store):
    consoles = category("consolas", "Consolas")
    ps = category(
        "playstation",
        "PlayStation",
        parent=consoles,
        show_on_home=True,
        image_slug="playstation-5",
        theme="cyan",
    )
    nin = category(
        "nintendo",
        "Nintendo",
        parent=consoles,
        show_on_home=True,
        image_slug="nintendo-switch-oled",
    )
    pads = category("controles", "Controles")
    ps5 = platform("ps5", "PlayStation 5", aliases="ps5 play 5")
    switch = platform("switch", "Nintendo Switch", aliases="switch")
    return {
        "ps5": make_product(
            "PlayStation 5 Slim",
            store=store,
            category=ps,
            brand=brand("playstation", "PlayStation"),
            platforms=[ps5],
            image_slug="playstation-5-slim",
            is_featured=True,
            popularity=100,
            options={"version": ["Con lector", "Digital"], "condition": ["Nuevo", "Usado"]},
            variants=[
                ("PS5-DISC-N", {"version": "Con lector", "condition": "Nuevo"}, 2750000),
                ("PS5-DIG-N", {"version": "Digital", "condition": "Nuevo"}, 2650000),
                ("PS5-DISC-U", {"version": "Con lector", "condition": "Usado"}, 2150000),
            ],
            stock={"PS5-DIG-N": 0},
        ),
        "oled": make_product(
            "Nintendo Switch OLED Pokémon",
            store=store,
            category=nin,
            brand=brand("nintendo", "Nintendo"),
            platforms=[switch],
            is_featured=True,
            popularity=80,
            variants=[("OLED-N", {"condition": "Nuevo"}, 1390000)],
        ),
        "lite": make_product(
            "Nintendo Switch Lite",
            store=store,
            category=nin,
            brand=brand("nintendo"),
            platforms=[switch],
            options={"condition": ["Usado"]},
            variants=[("LITE-U", {"condition": "Usado"}, 600000)],
            stock={"LITE-U": 0},
        ),
        "pad": make_product(
            "Control DualSense",
            store=store,
            category=pads,
            product_type=Product.Type.ACCESSORY,
            brand=brand("playstation"),
            platforms=[ps5],
            is_featured=True,
            variants=[("DS-N", {"condition": "Nuevo"}, 285000)],
        ),
    }


def names(filters):
    return [product.name for product in filter_products(filters)]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("pokemon", "Nintendo Switch OLED Pokémon"),  # accents
        ("POKÉMON", "Nintendo Switch OLED Pokémon"),  # case
        ("plaistation", "PlayStation 5 Slim"),  # typo (trigram)
        ("play 5", "PlayStation 5 Slim"),  # platform alias
        ("dualsense", "Control DualSense"),
    ],
)
def test_search_is_tolerant(catalog, query, expected):
    assert expected in names(CatalogFilters(q=query))


def test_search_without_matches_and_hostile_input(catalog):
    assert names(CatalogFilters(q="zzqxw")) == []
    assert names(CatalogFilters(q="'; DROP TABLE catalog_product; --")) == []
    assert Product.objects.count() == 4


def test_inactive_products_and_variants_are_hidden(catalog):
    catalog["lite"].is_active = False
    catalog["lite"].save()
    catalog["pad"].variants.update(is_active=False)
    visible = names(CatalogFilters())
    assert "Nintendo Switch Lite" not in visible
    assert "Control DualSense" not in visible


def test_filters(catalog):
    assert set(names(CatalogFilters(brands=["nintendo"]))) == {
        "Nintendo Switch OLED Pokémon",
        "Nintendo Switch Lite",
    }
    assert set(names(CatalogFilters(platforms=["ps5"]))) == {
        "PlayStation 5 Slim",
        "Control DualSense",
    }
    assert set(names(CatalogFilters(conditions=["usado"]))) == {
        "PlayStation 5 Slim",
        "Nintendo Switch Lite",
    }
    assert names(CatalogFilters(types=["accessory"])) == ["Control DualSense"]
    assert set(names(CatalogFilters(price_min=1000000, price_max=2500000))) == {
        "PlayStation 5 Slim",  # from 2.150.000
        "Nintendo Switch OLED Pokémon",
    }
    assert "Nintendo Switch Lite" not in names(CatalogFilters(in_stock=True))
    nintendo = selectors.Category.objects.get(slug="consolas")
    assert len(names(CatalogFilters(category=nintendo))) == 3  # includes subcategories


def test_sorting_is_whitelisted(catalog):
    assert names(CatalogFilters(sort="precio-asc"))[0] == "Control DualSense"
    assert names(CatalogFilters(sort="precio-desc"))[0] == "PlayStation 5 Slim"
    assert names(CatalogFilters(sort="nombre"))[0] == "Control DualSense"
    assert len(names(CatalogFilters(sort="pk; DROP TABLE x"))) == 4


def test_facets_count_with_the_other_filters_applied(catalog):
    facets = selectors.facet_counts(CatalogFilters(brands=["nintendo"]))
    brands = {option.slug: (option.count, option.selected) for option in facets.brands}
    assert brands == {"nintendo": (2, True), "playstation": (2, False)}
    conditions = {option.slug: option.count for option in facets.conditions}
    assert conditions == {"nuevo": 1, "usado": 1}


def test_product_cards(catalog):
    cards = {card.name: card for card in selectors.product_cards(filter_products(CatalogFilters()))}
    ps5 = cards["PlayStation 5 Slim"]
    assert ps5.price == Decimal("2150000.00")
    assert ps5.price_is_from
    assert ps5.condition == "Nuevo · Usado"
    assert ps5.condition_class == "condition-mixed"
    assert ps5.image is not None
    assert ps5.url == "/producto/playstation-5-slim/"
    lite = cards["Nintendo Switch Lite"]
    assert not lite.in_stock
    assert lite.condition_class == "condition-usado"
    assert cards["Nintendo Switch OLED Pokémon"].image is None  # generic cover


@override_settings(BYTE_FREE_SHIPPING_FROM=300_000)
def test_free_shipping_threshold(catalog):
    cards = {card.name: card for card in selectors.product_cards(filter_products(CatalogFilters()))}
    assert cards["PlayStation 5 Slim"].free_shipping
    assert not cards["Control DualSense"].free_shipping


def test_home_selectors(catalog):
    featured = [card.name for card in selectors.featured_products()]
    assert featured == ["PlayStation 5 Slim", "Nintendo Switch OLED Pokémon"]
    assert [card.name for card in selectors.featured_accessories()] == ["Control DualSense"]
    tiles = selectors.home_categories()
    assert [tile.key for tile in tiles] == ["nintendo", "playstation"]
    assert tiles[1].url == "/categoria/playstation/"


def test_featured_products_skip_sold_out(catalog):
    StockItem.objects.filter(variant__product=catalog["oled"]).update(quantity=0)
    assert "Nintendo Switch OLED Pokémon" not in [c.name for c in selectors.featured_products()]


def test_suggestions(catalog):
    assert selectors.suggestions("p") == []
    assert [card.name for card in selectors.suggestions("switch")][:1] in (
        ["Nintendo Switch OLED Pokémon"],
        ["Nintendo Switch Lite"],
    )


# --- configurator ----------------------------------------------------------------------


def detail(slug):
    product = selectors.product_for_detail(slug)
    assert product is not None
    return product


def configure(slug, sku=None):
    config = selectors.configure(detail(slug), sku)
    assert config is not None
    return config


def states(config):
    return {
        option.code: {choice.label: (choice.state, choice.sku) for choice in option.choices}
        for option in config.options
    }


def test_configure_defaults_to_first_variant_in_stock(catalog):
    config = configure("playstation-5-slim")
    assert config.variant.sku == "PS5-DISC-N"
    assert config.available == 5
    assert config.condition.value == "Nuevo"
    assert config.image.slug == "playstation-5-slim"


def test_configure_marks_disabled_and_sold_out_options(catalog):
    config = configure("playstation-5-slim", "ps5-disc-u")
    assert config.variant.sku == "PS5-DISC-U"
    result = states(config)
    # First option jumps to the closest existing variant (Digital only exists as new).
    assert result["version"]["Digital"] == ("out_of_stock", "PS5-DIG-N")
    assert result["version"]["Con lector"] == ("selected", "PS5-DISC-U")
    assert result["condition"]["Nuevo"] == ("available", "PS5-DISC-N")
    config = configure("playstation-5-slim", "PS5-DIG-N")
    # Digital + Usado does not exist: disabled, not clickable.
    assert states(config)["condition"]["Usado"] == ("unavailable", None)


def test_configure_ignores_unknown_sku(catalog):
    assert configure("playstation-5-slim", "NO-EXISTE").variant.sku == "PS5-DISC-N"


def test_product_for_detail_hides_inactive(catalog):
    Product.objects.filter(slug="playstation-5-slim").update(is_active=False)
    assert selectors.product_for_detail("playstation-5-slim") is None


def test_compare_rows_and_order(catalog):
    catalog["ps5"].specs = [["Almacenamiento", "1 TB"]]
    catalog["ps5"].save()
    ids = [
        str(catalog["oled"].public_id),
        str(catalog["ps5"].public_id),
        "00000000-0000-4000-8000-000000000000",
    ]
    products = selectors.products_by_public_ids(ids)
    assert [p.name for p in products] == ["Nintendo Switch OLED Pokémon", "PlayStation 5 Slim"]
    rows = {row.label: row.cells for row in selectors.compare_rows(products)}
    assert rows["Marca"] == ["Nintendo", "PlayStation"]
    assert rows["Almacenamiento"] == ["—", "1 TB"]
    assert rows["Condición"] == ["Nuevo", "Nuevo, Usado"]


def test_related_products_share_the_category(catalog):
    related = [card.name for card in selectors.related_products(catalog["oled"])]
    assert related == ["Nintendo Switch Lite"]
