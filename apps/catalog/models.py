"""Data models for the catalog app: products, configurable variants and their attributes.

Prices are COP with VAT included (ADR-0004). A product is sold through one or more
``ProductVariant`` rows (one SKU each); the variant price is maintained by the pricing
engine in ``apps.pricing.services`` and every change is kept in ``PriceHistory``.
"""

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class Brand(models.Model):
    name = models.CharField(_("nombre"), max_length=80, unique=True)
    slug = models.SlugField(_("slug"), max_length=80, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("marca")
        verbose_name_plural = _("marcas")

    def __str__(self) -> str:
        return self.name


class Platform(models.Model):
    """A console family (PS5, Switch 2...). Games and accessories declare compatibility."""

    name = models.CharField(_("nombre"), max_length=80, unique=True)
    slug = models.SlugField(_("slug"), max_length=80, unique=True)
    brand = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.PROTECT)
    # Words customers use in searches ("play 5", "ps5"...).
    aliases = models.CharField(_("sinónimos de búsqueda"), max_length=200, blank=True)
    is_retro = models.BooleanField(_("retro"), default=False)
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort", "name"]
        verbose_name = _("plataforma")
        verbose_name_plural = _("plataformas")

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    name = models.CharField(_("nombre"), max_length=80)
    slug = models.SlugField(_("slug"), max_length=80, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    description = models.CharField(_("descripción"), max_length=255, blank=True)
    image_slug = models.CharField(_("foto (créditos)"), max_length=60, blank=True)
    theme = models.CharField(_("color del mosaico"), max_length=12, blank=True)
    show_on_home = models.BooleanField(_("mostrar en el inicio"), default=False)
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort", "name"]
        verbose_name = _("categoría")
        verbose_name_plural = _("categorías")

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("catalog:category", args=[self.slug])


class Genre(models.Model):
    name = models.CharField(_("nombre"), max_length=60, unique=True)
    slug = models.SlugField(_("slug"), max_length=60, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("género")
        verbose_name_plural = _("géneros")

    def __str__(self) -> str:
        return self.name


class Attribute(models.Model):
    """Configurable dimension of a product (version, storage, colour, condition...)."""

    class Code(models.TextChoices):
        VERSION = "version", _("Versión")
        EDITION = "edition", _("Edición")
        PLATFORM = "platform", _("Plataforma")
        STORAGE = "storage", _("Almacenamiento")
        COLOR = "color", _("Color")
        PACKAGING = "packaging", _("Presentación")
        CONDITION = "condition", _("Condición")

    code = models.CharField(_("código"), max_length=20, choices=Code.choices, unique=True)
    name = models.CharField(_("nombre"), max_length=60)
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort"]
        verbose_name = _("atributo")
        verbose_name_plural = _("atributos")

    def __str__(self) -> str:
        return str(self.name)


class AttributeValue(models.Model):
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE, related_name="values")
    value = models.CharField(_("valor"), max_length=80)
    slug = models.SlugField(_("slug"), max_length=80)
    sort = models.PositiveSmallIntegerField(default=0)
    # e.g. condition: {"warranty_months": 3, "description": "..."}
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["attribute__sort", "sort", "value"]
        verbose_name = _("valor de atributo")
        verbose_name_plural = _("valores de atributo")
        constraints = [
            models.UniqueConstraint(fields=["attribute", "slug"], name="catalog_attrvalue_unique")
        ]

    def __str__(self) -> str:
        return self.value


class Product(BaseModel):
    class Type(models.TextChoices):
        CONSOLE = "console", _("Consola")
        GAME = "game", _("Videojuego")
        ACCESSORY = "accessory", _("Accesorio")
        COLLECTIBLE = "collectible", _("Coleccionable")

    class PricingMode(models.TextChoices):
        FIXED = "fixed", _("Precio fijo por variante")
        MODIFIERS = "modifiers", _("Precio base + modificadores")

    class TaxClass(models.TextChoices):
        STANDARD = "iva_19", _("IVA 19 %")
        EXCLUDED = "excluido", _("Excluido de IVA")

    name = models.CharField(_("nombre"), max_length=160)
    slug = models.SlugField(_("slug"), max_length=160, unique=True)
    product_type = models.CharField(_("tipo"), max_length=20, choices=Type.choices)
    brand = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    platforms = models.ManyToManyField(
        Platform, blank=True, related_name="products", verbose_name=_("plataformas compatibles")
    )
    short_description = models.CharField(_("resumen"), max_length=200, blank=True)
    description = models.TextField(_("descripción"), blank=True)
    # Technical sheet as ordered [label, value] pairs: [["Almacenamiento", "1 TB"], ...].
    specs = models.JSONField(_("ficha técnica"), default=list, blank=True)
    search_keywords = models.CharField(_("palabras clave"), max_length=200, blank=True)
    pricing_mode = models.CharField(
        _("modo de precio"), max_length=12, choices=PricingMode.choices, default=PricingMode.FIXED
    )
    base_price = models.DecimalField(
        _("precio base (IVA incluido)"), null=True, blank=True, max_digits=14, decimal_places=2
    )
    tax_class = models.CharField(
        _("impuesto"), max_length=10, choices=TaxClass.choices, default=TaxClass.STANDARD
    )
    image_slug = models.CharField(_("foto (créditos)"), max_length=60, blank=True)
    is_active = models.BooleanField(_("activo"), default=True)
    is_featured = models.BooleanField(_("destacado"), default=False)
    popularity = models.PositiveIntegerField(_("popularidad"), default=0)
    release_date = models.DateField(_("fecha de lanzamiento"), null=True, blank=True)
    is_preorder = models.BooleanField(_("preventa"), default=False)
    max_per_order = models.PositiveSmallIntegerField(_("máximo por pedido"), default=5)
    search_vector = SearchVectorField(null=True, editable=False)
    search_text = models.CharField(max_length=600, blank=True, editable=False)

    class Meta:
        ordering = ["name"]
        verbose_name = _("producto")
        verbose_name_plural = _("productos")
        indexes = [
            GinIndex(fields=["search_vector"], name="catalog_product_search_vector"),
            GinIndex(
                fields=["search_text"],
                name="catalog_product_search_trgm",
                opclasses=["gin_trgm_ops"],
            ),
            models.Index(fields=["is_active", "category"], name="catalog_product_active_cat"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(base_price__isnull=True) | models.Q(base_price__gt=0),
                name="catalog_product_base_price_positive",
            ),
            models.CheckConstraint(
                condition=~models.Q(pricing_mode="modifiers") | models.Q(base_price__isnull=False),
                name="catalog_product_modifiers_need_base",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("catalog:product", args=[self.slug])


class GameDetails(models.Model):
    class Format(models.TextChoices):
        PHYSICAL = "physical", _("Físico")
        DIGITAL = "digital", _("Digital (código)")

    class Esrb(models.TextChoices):
        E = "E", _("E (Todos)")
        E10 = "E10+", _("E10+ (10 años o más)")
        T = "T", _("T (Adolescentes)")
        M = "M", _("M (Maduro 17+)")
        RP = "RP", _("RP (Clasificación pendiente)")

    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="game")
    genres = models.ManyToManyField(Genre, blank=True, related_name="games")
    esrb = models.CharField(_("clasificación ESRB"), max_length=4, choices=Esrb.choices)
    pegi = models.PositiveSmallIntegerField(_("PEGI"), null=True, blank=True)
    languages = models.CharField(_("idiomas"), max_length=120, blank=True)
    multiplayer = models.CharField(_("multijugador"), max_length=80, blank=True)
    developer = models.CharField(_("desarrollador"), max_length=120, blank=True)
    publisher = models.CharField(_("editor"), max_length=120, blank=True)
    format = models.CharField(
        _("formato"), max_length=10, choices=Format.choices, default=Format.PHYSICAL
    )

    class Meta:
        verbose_name = _("ficha de videojuego")
        verbose_name_plural = _("fichas de videojuego")

    def __str__(self) -> str:
        return f"Ficha de {self.product}"


class ProductOption(models.Model):
    """An attribute a product is configurable by, e.g. "Almacenamiento" for the Steam Deck."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="options")
    attribute = models.ForeignKey(Attribute, on_delete=models.PROTECT)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        verbose_name = _("opción de producto")
        verbose_name_plural = _("opciones de producto")
        constraints = [
            models.UniqueConstraint(fields=["product", "attribute"], name="catalog_option_unique")
        ]

    def __str__(self) -> str:
        return f"{self.product}: {self.attribute}"


class ProductOptionValue(models.Model):
    option = models.ForeignKey(ProductOption, on_delete=models.CASCADE, related_name="values")
    value = models.ForeignKey(AttributeValue, on_delete=models.PROTECT)
    # Only used in "modifiers" pricing mode: added to the product base price (can be negative).
    price_modifier = models.DecimalField(
        _("modificador de precio"), default=0, max_digits=14, decimal_places=2
    )
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        verbose_name = _("valor de opción")
        verbose_name_plural = _("valores de opción")
        constraints = [
            models.UniqueConstraint(fields=["option", "value"], name="catalog_option_value_unique")
        ]

    def __str__(self) -> str:
        return str(self.value)


class ProductVariant(BaseModel):
    """A concrete, sellable configuration (one SKU).

    ``combination_key`` is the sorted list of attribute value ids, computed by
    ``apps.catalog.services``; the unique constraint forbids duplicate combinations.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(_("SKU"), max_length=40, unique=True)
    barcode = models.CharField(_("código de barras"), max_length=32, blank=True)
    values = models.ManyToManyField(AttributeValue, blank=True, related_name="variants")
    combination_key = models.CharField(max_length=255, editable=False)
    price = models.DecimalField(_("precio vigente (IVA incluido)"), max_digits=14, decimal_places=2)
    price_override = models.DecimalField(
        _("precio fijo"), null=True, blank=True, max_digits=14, decimal_places=2
    )
    image_slug = models.CharField(_("foto propia (créditos)"), max_length=60, blank=True)
    is_active = models.BooleanField(_("activa"), default=True)
    weight_grams = models.PositiveIntegerField(_("peso (g)"), default=0)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "price"]
        verbose_name = _("variante")
        verbose_name_plural = _("variantes")
        constraints = [
            models.UniqueConstraint(
                fields=["product", "combination_key"], name="catalog_variant_combination_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(price__gt=0), name="catalog_variant_price_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(price_override__isnull=True) | models.Q(price_override__gt=0),
                name="catalog_variant_override_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.product} ({self.sku})"
