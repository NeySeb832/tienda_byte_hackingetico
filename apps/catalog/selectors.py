"""Read-side queries for the catalog app.

Until the catalogue models exist (Phase 3), the home page showcase is a curated
static selection based on the store's master price list. Prices are COP with VAT
included (ADR-0004). Templates consume the same shape a queryset will return.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings

from apps.cms.selectors import ImageCredit, picture

CONDITIONS = ("Nuevo", "Usado", "Reacondicionado")


@dataclass(frozen=True, slots=True)
class ProductCard:
    name: str
    specs: str
    brand: str
    condition: str
    price: Decimal
    image: ImageCredit

    @property
    def condition_class(self) -> str:
        return f"condition-{self.condition.lower()}"

    @property
    def free_shipping(self) -> bool:
        return self.price >= Decimal(settings.BYTE_FREE_SHIPPING_FROM)


def featured_products() -> list[ProductCard]:
    return [
        ProductCard(
            "PlayStation 5 Slim con lector de discos",
            "1 TB · Control DualSense",
            "PlayStation",
            "Nuevo",
            Decimal("2750000"),
            picture("playstation-5-slim"),
        ),
        ProductCard(
            "Xbox Series X con lector de discos",
            "1 TB · Control inalámbrico",
            "Xbox",
            "Nuevo",
            Decimal("2890000"),
            picture("xbox-series-x"),
        ),
        ProductCard(
            "Nintendo Switch 2",
            "256 GB · Joy-Con 2",
            "Nintendo",
            "Nuevo",
            Decimal("2150000"),
            picture("nintendo-switch-2"),
        ),
        ProductCard(
            "Nintendo Switch OLED",
            "64 GB · Pantalla OLED de 7 pulgadas",
            "Nintendo",
            "Nuevo",
            Decimal("1390000"),
            picture("nintendo-switch-oled"),
        ),
        ProductCard(
            "Steam Deck",
            "512 GB · PC portátil",
            "Valve",
            "Nuevo",
            Decimal("1850000"),
            picture("steam-deck"),
        ),
        ProductCard(
            "Xbox Series S",
            "512 GB · 100 % digital",
            "Xbox",
            "Nuevo",
            Decimal("1800000"),
            picture("xbox-series-s"),
        ),
        ProductCard(
            "PlayStation 5 modelo original",
            "1 TB · Sin caja, revisada",
            "PlayStation",
            "Usado",
            Decimal("1950000"),
            picture("playstation-5"),
        ),
        ProductCard(
            "Super Nintendo",
            "Consola retro · 1 control",
            "Nintendo",
            "Usado",
            Decimal("330000"),
            picture("super-nintendo"),
        ),
    ]


def featured_controllers() -> list[ProductCard]:
    return [
        ProductCard(
            "Control DualSense blanco",
            "PlayStation 5 · Inalámbrico",
            "PlayStation",
            "Nuevo",
            Decimal("285000"),
            picture("dualsense"),
        ),
        ProductCard(
            "Control DualSense azul cobalto",
            "PlayStation 5 · Inalámbrico",
            "PlayStation",
            "Nuevo",
            Decimal("295000"),
            picture("dualsense-cobalt"),
        ),
        ProductCard(
            "Control Pro para Nintendo Switch",
            "Inalámbrico · Batería recargable",
            "Nintendo",
            "Nuevo",
            Decimal("235000"),
            picture("switch-pro-controller"),
        ),
        ProductCard(
            "Control inalámbrico Xbox One",
            "Compatible con Xbox Series X|S y PC",
            "Xbox",
            "Usado",
            Decimal("180000"),
            picture("control-xbox"),
        ),
    ]
