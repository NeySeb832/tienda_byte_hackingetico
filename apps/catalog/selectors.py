"""Read-side queries for the catalog: listings, search, facets, configurator and comparator.

* Only active products with at least one active variant are ever shown.
* Search combines PostgreSQL full text (Spanish stemming over accent-free text) with
  trigram similarity, so "pokemon", "plaistation" or "play 5" still find results.
* Every user-supplied value reaches the ORM as a bound parameter; sort keys are whitelisted.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramWordSimilarity
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q, QuerySet, Subquery, Sum
from django.db.models.functions import Coalesce

from apps.catalog.models import (
    Attribute,
    AttributeValue,
    Brand,
    Category,
    Platform,
    Product,
    ProductOption,
    ProductVariant,
)
from apps.catalog.services import normalize_text
from apps.cms.selectors import ImageCredit, picture
from apps.inventory.models import StockItem

CONDITIONS = ("Nuevo", "Usado", "Reacondicionado")
TRIGRAM_THRESHOLD = 0.55
SORTS: dict[str, tuple[str, ...]] = {
    "relevancia": (),
    "precio-asc": ("min_price", "name"),
    "precio-desc": ("-min_price", "name"),
    "populares": ("-popularity", "name"),
    "recientes": ("-created_at", "name"),
    "nombre": ("name",),
}
SORT_LABELS = {
    "relevancia": "Relevancia",
    "precio-asc": "Menor precio",
    "precio-desc": "Mayor precio",
    "populares": "Más populares",
    "recientes": "Más recientes",
    "nombre": "Nombre (A-Z)",
}
COVER_THEMES = {"playstation": "cyan", "xbox": "lime", "nintendo": "pink", "sega": "amber"}


# --- Cards ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProductCard:
    name: str
    url: str
    specs: str
    brand: str
    condition: str
    price: Decimal
    image: ImageCredit | None
    price_is_from: bool = False
    in_stock: bool = True
    public_id: str = ""
    slug: str = ""
    platform: str = ""
    cover_theme: str = "violet"
    is_preorder: bool = False

    @property
    def condition_class(self) -> str:
        key = self.condition.lower()
        return f"condition-{key}" if self.condition in CONDITIONS else "condition-mixed"

    @property
    def free_shipping(self) -> bool:
        return self.price >= Decimal(settings.BYTE_FREE_SHIPPING_FROM)


def _active_variants() -> QuerySet[ProductVariant]:
    return (
        ProductVariant.objects.filter(is_active=True)
        .annotate(
            available=Coalesce(
                Sum(
                    F("stock_items__quantity") - F("stock_items__reserved"),
                    filter=Q(stock_items__store__is_active=True),
                ),
                0,
            )
        )
        .prefetch_related("values__attribute")
        .order_by("position", "price", "pk")
    )


def sellable_products() -> QuerySet[Product]:
    """Active products with at least one active variant, annotated for listings."""
    variants = ProductVariant.objects.filter(product=OuterRef("pk"), is_active=True)
    stock = StockItem.objects.filter(
        variant__product=OuterRef("pk"),
        variant__is_active=True,
        store__is_active=True,
        quantity__gt=F("reserved"),
    )
    return (
        Product.objects.filter(is_active=True)
        .filter(Exists(variants))
        .annotate(
            min_price=Subquery(variants.order_by("price").values("price")[:1]),
            max_price=Subquery(variants.order_by("-price").values("price")[:1]),
            in_stock=Exists(stock),
        )
        .select_related("brand", "category")
    )


def with_card_data(queryset: QuerySet[Product]) -> QuerySet[Product]:
    return queryset.prefetch_related(
        "platforms",
        Prefetch("variants", queryset=_active_variants(), to_attr="active_variants"),
    )


def _image(slug: str) -> ImageCredit | None:
    try:
        return picture(slug) if slug else None
    except KeyError:
        return None


def _conditions(variants: Iterable[ProductVariant]) -> list[str]:
    found = {
        value.value: value.sort
        for variant in variants
        for value in variant.values.all()
        if value.attribute.code == Attribute.Code.CONDITION
    }
    return sorted(found, key=lambda name: found[name]) or ["Nuevo"]


def product_cards(products: Iterable[Product]) -> list[ProductCard]:
    """Turn annotated products (``with_card_data``) into the cards the templates render."""
    cards = []
    for product in products:
        variants = getattr(product, "active_variants", None) or list(
            _active_variants().filter(product=product)
        )
        if not variants:
            continue
        prices = [variant.price for variant in variants]
        brand_slug = product.brand.slug if product.brand else ""
        platforms = list(product.platforms.all())
        cards.append(
            ProductCard(
                name=product.name,
                url=product.get_absolute_url(),
                specs=product.short_description,
                brand=product.brand.name if product.brand else "",
                condition=" · ".join(_conditions(variants)),
                price=min(prices),
                image=_image(product.image_slug),
                price_is_from=len(set(prices)) > 1,
                in_stock=any(getattr(variant, "available", 0) > 0 for variant in variants),
                public_id=str(product.public_id),
                slug=product.slug,
                platform=platforms[0].name if platforms else "",
                cover_theme=COVER_THEMES.get(brand_slug, "violet"),
                is_preorder=product.is_preorder,
            )
        )
    return cards


# --- Home ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CategoryTile:
    key: str
    name: str
    description: str
    image: ImageCredit
    theme: str
    url: str


def home_categories() -> list[CategoryTile]:
    tiles = []
    for category in Category.objects.filter(show_on_home=True).order_by("sort", "name"):
        image = _image(category.image_slug)
        if image:
            tiles.append(
                CategoryTile(
                    key=category.slug,
                    name=category.name,
                    description=category.description,
                    image=image,
                    theme=category.theme or "violet",
                    url=category.get_absolute_url(),
                )
            )
    return tiles


def featured_products(limit: int = 8) -> list[ProductCard]:
    queryset = sellable_products().filter(
        is_featured=True, product_type=Product.Type.CONSOLE, in_stock=True  # type: ignore[misc]
    )
    return product_cards(with_card_data(queryset.order_by("-popularity", "name"))[:limit])


def featured_accessories(limit: int = 4) -> list[ProductCard]:
    queryset = sellable_products().filter(
        is_featured=True, product_type=Product.Type.ACCESSORY, in_stock=True  # type: ignore[misc]
    )
    return product_cards(with_card_data(queryset.order_by("-popularity", "name"))[:limit])


# --- Listing, search and facets ------------------------------------------------------------


@dataclass(slots=True)
class CatalogFilters:
    q: str = ""
    category: Category | None = None
    brands: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    types: list[str] = field(default_factory=list)
    price_min: int | None = None
    price_max: int | None = None
    in_stock: bool = False
    sort: str = "relevancia"


@dataclass(frozen=True, slots=True)
class FacetOption:
    slug: str
    label: str
    count: int
    selected: bool


@dataclass(frozen=True, slots=True)
class Facets:
    brands: list[FacetOption]
    platforms: list[FacetOption]
    conditions: list[FacetOption]
    types: list[FacetOption]


def _search(queryset: QuerySet[Product], q: str) -> QuerySet[Product]:
    term = normalize_text(q)[:80]
    if not term:
        return queryset
    query = SearchQuery(term, config="spanish", search_type="websearch")
    return queryset.annotate(
        rank=SearchRank(F("search_vector"), query),
        similarity=TrigramWordSimilarity(term, "search_text"),
    ).filter(
        Q(search_vector=query)
        | Q(search_text__contains=term)
        | Q(similarity__gte=TRIGRAM_THRESHOLD)
    )


def _filtered(filters: CatalogFilters, *, skip: str = "") -> QuerySet[Product]:
    queryset = _search(sellable_products(), filters.q)
    if filters.category is not None:
        queryset = queryset.filter(
            Q(category=filters.category) | Q(category__parent=filters.category)
        )
    if filters.brands and skip != "brands":
        queryset = queryset.filter(brand__slug__in=filters.brands)
    if filters.platforms and skip != "platforms":
        queryset = queryset.filter(
            Exists(
                Product.platforms.through.objects.filter(
                    product_id=OuterRef("pk"), platform__slug__in=filters.platforms
                )
            )
        )
    if filters.conditions and skip != "conditions":
        queryset = queryset.filter(
            Exists(
                ProductVariant.objects.filter(
                    product=OuterRef("pk"),
                    is_active=True,
                    values__attribute__code=Attribute.Code.CONDITION,
                    values__slug__in=filters.conditions,
                )
            )
        )
    if filters.types and skip != "types":
        queryset = queryset.filter(product_type__in=filters.types)
    if filters.price_min is not None:
        queryset = queryset.filter(min_price__gte=filters.price_min)  # type: ignore[misc]
    if filters.price_max is not None:
        queryset = queryset.filter(min_price__lte=filters.price_max)  # type: ignore[misc]
    if filters.in_stock:
        queryset = queryset.filter(in_stock=True)  # type: ignore[misc]
    return queryset


def filter_products(filters: CatalogFilters) -> QuerySet[Product]:
    queryset = _filtered(filters)
    ordering = SORTS.get(filters.sort, ())
    if ordering:
        return with_card_data(queryset.order_by(*ordering, "pk"))
    if normalize_text(filters.q):
        return with_card_data(queryset.order_by("-rank", "-similarity", "-popularity", "pk"))
    return with_card_data(queryset.order_by("-is_featured", "-popularity", "name", "pk"))


def facet_counts(filters: CatalogFilters) -> Facets:
    """Counts per facet value, each computed with every other active filter applied."""

    def ids(skip: str) -> QuerySet[Product]:
        return Product.objects.filter(pk__in=_filtered(filters, skip=skip).values("pk"))

    brands = [
        FacetOption(
            row["brand__slug"], row["brand__name"], row["n"], row["brand__slug"] in filters.brands
        )
        for row in ids("brands")
        .exclude(brand=None)
        .values("brand__slug", "brand__name")
        .annotate(n=Count("pk", distinct=True))
        .order_by("brand__name")
    ]
    platforms = [
        FacetOption(row["slug"], row["name"], row["n"], row["slug"] in filters.platforms)
        for row in Platform.objects.filter(products__in=ids("platforms"))
        .values("slug", "name", "sort")
        .annotate(n=Count("products", distinct=True))
        .order_by("sort", "name")
    ]
    conditions = [
        FacetOption(row["slug"], row["value"], row["n"], row["slug"] in filters.conditions)
        for row in AttributeValue.objects.filter(
            attribute__code=Attribute.Code.CONDITION,
            variants__is_active=True,
            variants__product__in=ids("conditions"),
        )
        .values("slug", "value", "sort")
        .annotate(n=Count("variants__product", distinct=True))
        .order_by("sort")
    ]
    labels = dict(Product.Type.choices)
    types = [
        FacetOption(
            row["product_type"],
            str(labels[row["product_type"]]),
            row["n"],
            row["product_type"] in filters.types,
        )
        for row in ids("types")
        .values("product_type")
        .annotate(n=Count("pk"))
        .order_by("product_type")
    ]
    return Facets(brands=brands, platforms=platforms, conditions=conditions, types=types)


def facet_choices() -> dict[str, list[tuple[str, str]]]:
    """Valid values for the filter form (anything else is ignored)."""
    return {
        "brands": list(Brand.objects.values_list("slug", "name")),
        "platforms": list(Platform.objects.values_list("slug", "name")),
        "conditions": list(
            AttributeValue.objects.filter(attribute__code=Attribute.Code.CONDITION).values_list(
                "slug", "value"
            )
        ),
        "types": [(key, str(label)) for key, label in Product.Type.choices],
    }


def suggestions(q: str, limit: int = 6) -> list[ProductCard]:
    term = normalize_text(q)[:80]
    if len(term) < 2:
        return []
    queryset = (
        sellable_products()
        .annotate(similarity=TrigramWordSimilarity(term, "search_text"))
        .filter(Q(search_text__contains=term) | Q(similarity__gte=TRIGRAM_THRESHOLD))
        .order_by("-similarity", "-popularity", "pk")
    )
    return product_cards(with_card_data(queryset)[:limit])


# --- Product page and configurator ---------------------------------------------------------


def product_for_detail(slug: str) -> Product | None:
    return (
        Product.objects.filter(slug=slug, is_active=True)
        .select_related("brand", "category__parent", "game")
        .prefetch_related(
            "platforms",
            "game__genres",
            Prefetch(
                "options",
                queryset=ProductOption.objects.select_related("attribute").prefetch_related(
                    "values__value"
                ),
            ),
            Prefetch(
                "variants",
                queryset=_active_variants().prefetch_related("price_history"),
                to_attr="active_variants",
            ),
        )
        .first()
    )


@dataclass(frozen=True, slots=True)
class ValueChoice:
    label: str
    sku: str | None
    state: str  # selected | available | out_of_stock | unavailable

    @property
    def selectable(self) -> bool:
        return self.sku is not None and self.state != "selected"


@dataclass(frozen=True, slots=True)
class OptionChoices:
    name: str
    code: str
    selected: str
    choices: list[ValueChoice]


@dataclass(frozen=True, slots=True)
class Configuration:
    variant: ProductVariant
    options: list[OptionChoices]
    image: ImageCredit | None
    condition: AttributeValue | None
    cover_label: str = ""

    @property
    def available(self) -> int:
        return max(getattr(self.variant, "available", 0), 0)


def _values_by_attribute(variant: ProductVariant) -> dict[int, AttributeValue]:
    return {value.attribute_id: value for value in variant.values.all()}


def configure(product: Product, sku: str | None = None) -> Configuration | None:
    """Selected variant plus, for every option value, where clicking it leads.

    A value whose exact combination does not exist is disabled, except in the first option,
    where it jumps to the closest existing variant (so every variant stays reachable).
    """
    variants: list[ProductVariant] = list(getattr(product, "active_variants", None) or [])
    if not variants:
        return None
    by_sku = {variant.sku: variant for variant in variants}
    selected = by_sku.get((sku or "").strip().upper())
    if selected is None:
        selected = next((v for v in variants if getattr(v, "available", 0) > 0), variants[0])
    combos = {frozenset(v.pk for v in variant.values.all()): variant for variant in variants}
    current = _values_by_attribute(selected)

    def best_with(value_pk: int, attribute_id: int) -> ProductVariant | None:
        candidates = [
            variant
            for variant in variants
            if _values_by_attribute(variant).get(attribute_id) is not None
            and _values_by_attribute(variant)[attribute_id].pk == value_pk
        ]
        if not candidates:
            return None

        def score(variant: ProductVariant) -> tuple[int, int, int]:
            values = _values_by_attribute(variant)
            matches = sum(1 for attr, value in current.items() if values.get(attr) == value)
            return (
                -matches,
                0 if getattr(variant, "available", 0) > 0 else 1,
                variants.index(variant),
            )

        return min(candidates, key=score)

    options: list[OptionChoices] = []
    for index, option in enumerate(product.options.all()):
        attribute_id = option.attribute_id
        choices = []
        for option_value in option.values.all():
            value = option_value.value
            if current.get(attribute_id) == value:
                choices.append(ValueChoice(value.value, selected.sku, "selected"))
                continue
            target_values = {attr: val.pk for attr, val in current.items()}
            target_values[attribute_id] = value.pk
            target = combos.get(frozenset(target_values.values()))
            if target is None and index == 0:
                target = best_with(value.pk, attribute_id)
            if target is None:
                if best_with(value.pk, attribute_id) is not None:
                    choices.append(ValueChoice(value.value, None, "unavailable"))
                continue
            state = "available" if getattr(target, "available", 0) > 0 else "out_of_stock"
            choices.append(ValueChoice(value.value, target.sku, state))
        chosen = current.get(attribute_id)
        options.append(
            OptionChoices(
                name=option.attribute.name,
                code=option.attribute.code,
                selected=chosen.value if chosen else "",
                choices=choices,
            )
        )
    condition = next(
        (
            value
            for value in selected.values.all()
            if value.attribute.code == Attribute.Code.CONDITION
        ),
        None,
    )
    image = _image(selected.image_slug) or _image(product.image_slug)
    platforms = list(product.platforms.all())
    cover_label = platforms[0].name if platforms else (product.brand.name if product.brand else "")
    return Configuration(
        variant=selected, options=options, image=image, condition=condition, cover_label=cover_label
    )


def related_products(product: Product, limit: int = 4) -> list[ProductCard]:
    queryset = (
        sellable_products()
        .filter(category=product.category)
        .exclude(pk=product.pk)
        .order_by("-in_stock", "-popularity", "name")
    )
    return product_cards(with_card_data(queryset)[:limit])


def products_by_public_ids(public_ids: Sequence[str]) -> list[Product]:
    """Sellable products in the given order (unknown or inactive ids are skipped)."""
    found = {
        str(product.public_id): product
        for product in with_card_data(sellable_products().filter(public_id__in=list(public_ids)))
    }
    return [found[item] for item in public_ids if item in found]


# --- Comparator ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CompareRow:
    label: str
    cells: list[str]


def compare_rows(products: Sequence[Product]) -> list[CompareRow]:
    rows = [
        CompareRow("Marca", [p.brand.name if p.brand else "—" for p in products]),
        CompareRow("Tipo", [p.get_product_type_display() for p in products]),
        CompareRow(
            "Plataformas",
            [", ".join(platform.name for platform in p.platforms.all()) or "—" for p in products],
        ),
        CompareRow(
            "Condición",
            [", ".join(_conditions(getattr(p, "active_variants", []))) for p in products],
        ),
        CompareRow(
            "Opciones",
            [str(len(getattr(p, "active_variants", []))) for p in products],
        ),
    ]
    labels: list[str] = []
    for product in products:
        for label, _ in product.specs:
            if label not in labels:
                labels.append(label)
    for label in labels:
        rows.append(
            CompareRow(label, [dict(map(tuple, p.specs)).get(label, "—") for p in products])
        )
    return rows
