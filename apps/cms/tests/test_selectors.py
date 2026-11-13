"""Curated home content and licensed product photos."""

from pathlib import Path

from django.conf import settings

from apps.cms.selectors import FREE_LICENSES, home_slides, image_credits

STATIC_DIR = Path(settings.BASE_DIR) / "static"


def test_every_credited_image_exists():
    for credit in image_credits():
        assert (STATIC_DIR / credit.file).is_file(), credit.file
        assert credit.width > 0
        assert credit.height > 0


def test_every_product_photo_has_a_free_licence_and_author():
    credited = {credit.file for credit in image_credits()}
    photos = {f"img/productos/{p.name}" for p in (STATIC_DIR / "img" / "productos").glob("*.webp")}
    assert photos == credited, "every published photo needs a credit entry"
    for credit in image_credits():
        assert credit.license in FREE_LICENSES, credit.slug
        assert credit.author.strip(), credit.slug
        assert credit.source.startswith("https://commons.wikimedia.org/"), credit.slug


def test_home_slides_are_complete():
    slides = home_slides()
    assert len(slides) >= 3
    for slide in slides:
        assert slide.title
        assert slide.text
        assert slide.cta_label
        assert slide.cta_href.startswith("/")
        assert slide.image.alt
