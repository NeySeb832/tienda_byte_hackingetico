"""Catalogue pages: listing, search, product page (HTMX), comparator and recently viewed."""

import pytest
from django.urls import reverse

from apps.catalog import services
from apps.core.money import format_cop
from tests.factories import category, make_product, make_store

pytestmark = pytest.mark.django_db


@pytest.fixture
def products():
    store = make_store()
    consoles = category("consolas", "Consolas")
    return [
        make_product(
            "PlayStation 5 Slim",
            store=store,
            category=consoles,
            image_slug="playstation-5-slim",
            options={"version": ["Con lector", "Digital"], "condition": ["Nuevo"]},
            variants=[
                ("PS5-DISC-N", {"version": "Con lector", "condition": "Nuevo"}, 2750000),
                ("PS5-DIG-N", {"version": "Digital", "condition": "Nuevo"}, 2650000),
            ],
        ),
        *[make_product(f"Consola {i}", store=store, category=consoles) for i in range(5)],
    ]


def test_catalog_pages(client, products):
    response = client.get(reverse("catalog:list"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "PlayStation 5 Slim" in html
    assert 'href="/producto/playstation-5-slim/"' in html
    assert client.get(reverse("catalog:category", args=["consolas"])).status_code == 200
    assert client.get(reverse("catalog:category", args=["no-existe"])).status_code == 404


def test_search_page_and_empty_state(client, products):
    html = client.get(reverse("catalog:search"), {"q": "playstation"}).content.decode()
    assert "Resultados para «playstation»" in html
    assert "PlayStation 5 Slim" in html
    html = client.get(reverse("catalog:search"), {"q": "zzqxw"}).content.decode()
    assert "No encontramos productos" in html


def test_invalid_filters_are_ignored(client, products):
    response = client.get(
        reverse("catalog:list"),
        {
            "orden": "DROP TABLE",
            "precio_min": "abc",
            "marca": "zzz",
            "pagina": "9999",
            "q": "x" * 500,
        },
    )
    assert response.status_code == 200


def test_htmx_requests_get_only_the_fragment(client, products):
    response = client.get(
        reverse("catalog:list"), HTTP_HX_REQUEST="true", HTTP_HX_TARGET="catalogo"
    )
    html = response.content.decode()
    assert "<html" not in html
    assert 'id="filtros"' in html
    url = reverse("catalog:product", args=["playstation-5-slim"])
    response = client.get(
        url, {"sku": "PS5-DIG-N"}, HTTP_HX_REQUEST="true", HTTP_HX_TARGET="configurador"
    )
    html = response.content.decode()
    assert "<html" not in html
    assert "PS5-DIG-N" in html
    assert format_cop(2650000) in html


def test_product_page(client, products):
    url = reverse("catalog:product", args=["playstation-5-slim"])
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    assert "<h1" in html
    assert "PlayStation 5 Slim" in html
    assert "IVA incluido" in html
    assert 'href="?sku=PS5-DIG-N"' in html
    assert client.get(reverse("catalog:product", args=["no-existe"])).status_code == 404


def test_product_page_tracks_recently_viewed(client, products):
    first, second = products[0], products[1]
    client.get(reverse("catalog:product", args=[first.slug]))
    response = client.get(reverse("catalog:product", args=[second.slug]))
    assert "Vistos recientemente" in response.content.decode()
    assert client.session[services.VIEWED_SESSION_KEY][:2] == [
        str(second.public_id),
        str(first.public_id),
    ]


def test_compare_flow(client, products):
    url = reverse("catalog:compare_toggle", args=[products[0].slug])
    response = client.post(url)
    assert response.status_code == 302
    assert response["Location"] == reverse("catalog:compare")
    html = client.get(reverse("catalog:compare")).content.decode()
    assert "PlayStation 5 Slim" in html
    for product in products[1:4]:
        client.post(reverse("catalog:compare_toggle", args=[product.slug]))
    response = client.post(reverse("catalog:compare_toggle", args=[products[4].slug]), follow=True)
    assert "Puedes comparar hasta 4 productos" in response.content.decode()
    assert len(client.session[services.COMPARE_SESSION_KEY]) == 4
    client.post(url, {"accion": "quitar"})
    assert str(products[0].public_id) not in client.session[services.COMPARE_SESSION_KEY]
    client.post(reverse("catalog:compare_clear"))
    assert client.session[services.COMPARE_SESSION_KEY] == []


def test_compare_page_empty(client, db):
    assert "Aún no agregas productos" in client.get(reverse("catalog:compare")).content.decode()


def test_suggestions(client, products):
    response = client.get(reverse("catalog:suggest"), {"q": "playstation"})
    assert response.status_code == 200
    assert "PlayStation 5 Slim" in response.content.decode()
    assert client.get(reverse("catalog:suggest"), {"q": "p"}).content.decode().strip() == ""


def test_header_search_points_to_the_catalog(client, db):
    html = client.get("/").content.decode()
    assert 'action="/buscar/"' in html
    assert 'hx-get="/buscar/sugerencias/"' in html
