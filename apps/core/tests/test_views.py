"""Storefront pages rendered by the core app."""

import re

from apps.catalog.selectors import featured_controllers, featured_products
from apps.cms.selectors import image_credits
from apps.core.money import format_cop
from apps.services_desk.selectors import technical_services


def test_home_page_shows_the_storefront(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.content.decode()
    assert html.count("<h1") == 1
    assert "data-carousel" in html
    for product in [*featured_products(), *featured_controllers()]:
        assert product.name in html
        assert format_cop(product.price) in html
    for service in technical_services():
        assert service.name in html


def test_home_page_reads_like_a_real_store(client):
    """Regression: no development phases or academic notes in the UI."""
    html = client.get("/").content.decode().lower()
    for forbidden in ("fase ", "estado del proyecto", "proyecto académico", "sandbox"):
        assert forbidden not in html, forbidden


def test_every_image_has_alt_and_dimensions(client):
    html = client.get("/").content.decode()
    images = re.findall(r"<img\b[^>]*>", html)
    assert images
    for tag in images:
        assert " alt=" in tag, tag
        assert " width=" in tag, tag
        assert " height=" in tag, tag


def test_footer_links_to_image_credits(client):
    assert 'href="/creditos-imagenes/"' in client.get("/").content.decode()


def test_image_credits_page_lists_every_photo(client):
    response = client.get("/creditos-imagenes/")
    assert response.status_code == 200
    html = response.content.decode()
    for credit in image_credits():
        assert credit.license in html
        assert credit.source in html
    assert 'rel="noopener noreferrer"' in html
