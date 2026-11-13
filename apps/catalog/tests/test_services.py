"""Catalogue write rules: variants, combinations, pricing modes, search index, visitor lists."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.catalog import services
from apps.catalog.models import Product
from apps.pricing.models import PriceHistory
from tests.factories import attribute, attribute_value, make_product, platform

pytestmark = pytest.mark.django_db


def test_normalize_text_removes_accents_case_and_extra_spaces():
    assert services.normalize_text("  Pokémon   LEYENDAS Z-A ") == "pokemon leyendas z-a"


def test_combination_key_is_order_independent():
    assert services.combination_key([3, 1, 2]) == services.combination_key([2, 3, 1]) == "1-2-3"
    assert services.combination_key([]) == "default"


def test_validate_specs():
    assert services.validate_specs([["Almacenamiento", " 1 TB "]]) == [["Almacenamiento", "1 TB"]]
    for bad in ("texto", [["solo etiqueta"]], [["", "valor"]], [[1, 2]]):
        with pytest.raises(ValidationError):
            services.validate_specs(bad)


@pytest.fixture
def ps5():
    return make_product(
        "PS5 de prueba",
        options={"version": ["Disco", "Digital"], "condition": ["Nuevo", "Usado"]},
        variants=[
            ("PS5-DISC-N", {"version": "Disco", "condition": "Nuevo"}, 2750000),
            ("PS5-DIG-N", {"version": "Digital", "condition": "Nuevo"}, 2650000),
        ],
    )


def test_create_variant_records_initial_price_and_audit(ps5):
    variant = ps5.variants.get(sku="PS5-DISC-N")
    assert variant.price == Decimal("2750000.00")
    history = PriceHistory.objects.get(variant=variant)
    assert history.reason == PriceHistory.Reason.INITIAL
    assert history.previous_price is None
    assert AuditLog.objects.filter(
        action="catalog.variant_created", target_id=str(variant.public_id)
    ).exists()


def test_fixed_mode_requires_a_price(ps5):
    with pytest.raises(ValidationError, match="precio fijo"):
        services.create_variant(
            ps5,
            sku="PS5-DISC-U",
            values=[attribute_value("version", "Disco"), attribute_value("condition", "Usado")],
        )


@pytest.mark.parametrize(
    ("sku", "values", "message"),
    [
        ("PS5 DISC", [("version", "Disco"), ("condition", "Usado")], "SKU inválido"),
        ("PS5-X", [("version", "Disco")], "un valor para cada opción"),
        ("PS5-X", [("version", "Disco"), ("version", "Digital")], "dos valores"),
        ("PS5-X", [("version", "Disco"), ("condition", "Nuevo")], "Ya existe"),
        ("PS5-X", [("version", "Pro"), ("condition", "Nuevo")], "no está permitido"),
    ],
)
def test_create_variant_validates_the_combination(ps5, sku, values, message):
    with pytest.raises(ValidationError, match=message):
        services.create_variant(
            ps5, sku=sku, values=[attribute_value(c, v) for c, v in values], price=100000
        )


def test_modifiers_mode_prices_from_base_and_modifiers():
    product = make_product(
        "Series S de prueba",
        mode=Product.PricingMode.MODIFIERS,
        base=1800000,
        options={
            "storage": [("512 GB", 0), ("1 TB", 50000)],
            "condition": [("Nuevo", 0), ("Usado", -100000)],
        },
        variants=[
            ("XSS-512-N", {"storage": "512 GB", "condition": "Nuevo"}, None),
            ("XSS-1TB-U", {"storage": "1 TB", "condition": "Usado"}, None),
        ],
    )
    prices = dict(product.variants.values_list("sku", "price"))
    assert prices == {"XSS-512-N": Decimal("1800000.00"), "XSS-1TB-U": Decimal("1750000.00")}
    assert product.variants.get(sku="XSS-1TB-U").price_override is None


def test_modifiers_cannot_make_a_price_non_positive():
    product = make_product(
        "Accesorio barato",
        mode=Product.PricingMode.MODIFIERS,
        base=50000,
        options={"condition": [("Nuevo", 0), ("Usado", -60000)]},
        variants=[("ACC-N", {"condition": "Nuevo"}, None)],
    )
    with pytest.raises(ValidationError, match="mayor que cero"):
        services.create_variant(
            product, sku="ACC-U", values=[attribute_value("condition", "Usado")]
        )


def test_add_option_rejects_values_of_another_attribute(ps5):
    with pytest.raises(ValidationError):
        services.add_option(ps5, attribute("color"), [attribute_value("version", "Disco")])


def test_search_index_is_accent_free_and_includes_platform_aliases():
    product = make_product(
        "Pokémon Leyendas",
        search_keywords="pokemon za",
        platforms=[platform("switch-2", "Nintendo Switch 2", aliases="sw2 switch 2")],
    )
    product.refresh_from_db()
    assert "pokemon leyendas" in product.search_text
    assert "sw2" in product.search_text
    assert product.search_vector is not None


# --- session lists ----------------------------------------------------------------------


def _products(count):
    return [make_product(f"Producto {i}") for i in range(count)]


def test_compare_list_holds_four_products_without_duplicates():
    session: dict = {}
    first, *others = _products(5)
    services.add_to_compare(session, first)
    services.add_to_compare(session, first)
    for product in others[:3]:
        services.add_to_compare(session, product)
    assert len(services.compare_ids(session)) == services.COMPARE_MAX
    with pytest.raises(services.CompareListFullError):
        services.add_to_compare(session, others[3])
    services.remove_from_compare(session, first)
    assert str(first.public_id) not in services.compare_ids(session)
    services.clear_compare(session)
    assert services.compare_ids(session) == []


def test_tampered_session_values_are_ignored():
    session: dict[str, object] = {services.COMPARE_SESSION_KEY: ["1", "<script>", 7, "x"]}
    assert services.compare_ids(session) == []
    session = {services.VIEWED_SESSION_KEY: "no es una lista"}
    assert services.viewed_ids(session) == []


def test_recently_viewed_keeps_the_latest_first_and_is_bounded():
    session: dict = {}
    products = _products(services.VIEWED_MAX + 2)
    for product in products:
        services.remember_viewed(session, product)
    services.remember_viewed(session, products[3])
    ids = services.viewed_ids(session)
    assert len(ids) == services.VIEWED_MAX
    assert ids[0] == str(products[3].public_id)
    assert ids.count(str(products[3].public_id)) == 1
