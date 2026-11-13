"""Load the curated demo catalogue: brands, platforms, categories, products, stores and stock.

Idempotent: existing products, variants and stock rows are left untouched (prices and
stock are never overwritten), so it is safe to run again after adding products to the data.
Usage: ``python manage.py seed_demo``.
"""

import hashlib
import random
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.catalog import demo_data as data
from apps.catalog import services
from apps.catalog.models import (
    Attribute,
    AttributeValue,
    Brand,
    Category,
    GameDetails,
    Genre,
    Platform,
    Product,
    ProductVariant,
)
from apps.core.models import City
from apps.inventory.models import StockItem, Store
from apps.inventory.services import set_stock


def stock_plan(sku: str, store_codes: list[str], override: int | None = None) -> dict[str, int]:
    """Deterministic demo stock per store (same SKU → same numbers on every machine)."""
    if override is not None:
        return dict.fromkeys(store_codes, override)
    seed = int(hashlib.sha256(sku.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)  # noqa: S311 - demo data, not security sensitive
    plan = {code: rng.choice([0, 0, 1, 2, 3, 4, 6]) for code in store_codes}
    if not any(plan.values()):
        plan[store_codes[-1]] = 3  # the warehouse always has a few units
    return plan


class Command(BaseCommand):
    help = "Carga el catálogo de demostración (idempotente)."

    def handle(self, *args: Any, **options: Any) -> None:
        with transaction.atomic():
            stores = self._stores()
            self._taxonomy()
            created = sum(self._product(spec, stores) for spec in data.PRODUCTS)
        self.stdout.write(
            self.style.SUCCESS(
                f"Catálogo listo: {Product.objects.count()} productos, "
                f"{ProductVariant.objects.count()} variantes ({created} productos nuevos), "
                f"{Store.objects.count()} sedes."
            )
        )

    # --- reference data ------------------------------------------------------------------

    def _stores(self) -> list[Store]:
        stores = []
        for code, name, city, kind, address, pickup in data.STORES:
            store, _ = Store.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "city": City.objects.get(code=city),
                    "kind": kind,
                    "address": address,
                    "is_pickup_point": pickup,
                },
            )
            stores.append(store)
        return stores

    def _taxonomy(self) -> None:
        for slug, name in data.BRANDS:
            Brand.objects.get_or_create(slug=slug, defaults={"name": name})
        for sort, (slug, name, brand, aliases, retro) in enumerate(data.PLATFORMS):
            Platform.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "brand": Brand.objects.get(slug=brand) if brand else None,
                    "aliases": aliases,
                    "is_retro": retro,
                    "sort": sort,
                },
            )
        for sort, (slug, name, parent, description, image, theme, home) in enumerate(
            data.CATEGORIES
        ):
            Category.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "parent": Category.objects.get(slug=parent) if parent else None,
                    "description": description,
                    "image_slug": image,
                    "theme": theme,
                    "show_on_home": home,
                    "sort": sort,
                },
            )
        for code, name, sort in data.ATTRIBUTES:
            Attribute.objects.get_or_create(code=code, defaults={"name": name, "sort": sort})
        condition = Attribute.objects.get(code=Attribute.Code.CONDITION)
        for slug, value, sort, meta in data.CONDITIONS:
            AttributeValue.objects.get_or_create(
                attribute=condition,
                slug=slug,
                defaults={"value": value, "sort": sort, "meta": meta},
            )

    def _value(self, attribute: Attribute, label: str, sort: int) -> AttributeValue:
        value, _ = AttributeValue.objects.get_or_create(
            attribute=attribute, slug=slugify(label)[:80], defaults={"value": label, "sort": sort}
        )
        return value

    # --- products ------------------------------------------------------------------------

    def _product(self, spec: dict[str, Any], stores: list[Store]) -> bool:
        product, created = Product.objects.get_or_create(
            slug=spec["slug"],
            defaults={
                "name": spec["name"],
                "product_type": spec["type"],
                "brand": Brand.objects.get(slug=spec["brand"]) if spec.get("brand") else None,
                "category": Category.objects.get(slug=spec["category"]),
                "short_description": spec.get("short", ""),
                "description": spec.get("description", ""),
                "specs": services.validate_specs(spec.get("specs", [])),
                "search_keywords": spec.get("keywords", ""),
                "pricing_mode": spec["mode"],
                "base_price": spec.get("base"),
                "image_slug": spec.get("image", ""),
                "is_featured": spec.get("featured", False),
                "popularity": spec.get("popularity", 0),
            },
        )
        if created:
            product.platforms.set(Platform.objects.filter(slug__in=spec.get("platforms", [])))
            if "game" in spec:
                self._game(product, spec["game"])
        values: dict[tuple[str, str], AttributeValue] = {}
        for code, labels in spec["options"]:
            attribute = Attribute.objects.get(code=code)
            items = []
            for sort, item in enumerate(labels):
                label, modifier = item if isinstance(item, tuple) else (item, 0)
                value = (
                    AttributeValue.objects.get(attribute=attribute, value=label)
                    if code == Attribute.Code.CONDITION
                    else self._value(attribute, label, sort)
                )
                values[(code, label)] = value
                items.append((value, modifier))
            if created:
                services.add_option(product, attribute, items)
        store_codes = [store.code for store in stores]
        for position, row in enumerate(spec["variants"]):
            sku, choice, price = row[0], row[1], row[2]
            extra = row[3] if len(row) > 3 else {}
            variant = ProductVariant.objects.filter(sku=sku).first()
            if variant is None:
                variant = services.create_variant(
                    product,
                    sku=sku,
                    values=[values[(code, label)] for code, label in choice.items()],
                    price=price,
                    image_slug=extra.get("image", ""),
                    position=position,
                )
            plan = stock_plan(sku, store_codes, extra.get("stock"))
            for store in stores:
                if not StockItem.objects.filter(variant=variant, store=store).exists():
                    set_stock(variant, store, plan[store.code], note="Inventario inicial")
        services.refresh_search_index(product)
        return created

    def _game(self, product: Product, info: dict[str, Any]) -> None:
        game = GameDetails.objects.create(
            product=product,
            esrb=info["esrb"],
            pegi=info.get("pegi"),
            languages=info.get("languages", ""),
            multiplayer=info.get("multiplayer", ""),
            developer=info.get("developer", ""),
            publisher=info.get("publisher", ""),
        )
        genres = [
            Genre.objects.get_or_create(slug=slugify(name), defaults={"name": name})[0]
            for name in info.get("genres", [])
        ]
        game.genres.set(genres)
