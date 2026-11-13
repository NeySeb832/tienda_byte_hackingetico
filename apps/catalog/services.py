"""Write-side use cases for the catalog: options, variants, search index and visitor lists.

Business rules enforced here (the database repeats the critical ones as constraints):

* a variant takes exactly one value of each option of its product, and only allowed values;
* two variants of the same product cannot share a combination (``combination_key``);
* in "fixed" pricing mode every variant needs its own price.
"""

import re
import unicodedata
from collections.abc import Iterable, MutableMapping, Sequence
from decimal import Decimal
from typing import Any

from django.contrib.postgres.search import SearchVector
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import TextField, Value

from apps.audit.services import record_event
from apps.catalog.models import (
    Attribute,
    AttributeValue,
    Product,
    ProductOption,
    ProductOptionValue,
    ProductVariant,
)
from apps.core.money import MoneyInput, to_money
from apps.pricing import services as pricing

COMPARE_SESSION_KEY = "catalog_compare"
VIEWED_SESSION_KEY = "catalog_viewed"
COMPARE_MAX = 4
VIEWED_MAX = 8
SEARCH_TEXT_MAX = 600
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


class CompareListFullError(Exception):
    """The comparison list already holds ``COMPARE_MAX`` products."""


def normalize_text(text: str) -> str:
    """Lower-case, accent-free, single-spaced text (search index and queries)."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(stripped.lower().split())


def combination_key(value_ids: Iterable[int]) -> str:
    ids = sorted(set(value_ids))
    return "-".join(map(str, ids)) if ids else "default"


def validate_specs(specs: Any) -> list[list[str]]:
    """Technical sheet: a list of [label, value] string pairs."""
    if not isinstance(specs, list):
        raise ValidationError("La ficha técnica debe ser una lista.")
    clean: list[list[str]] = []
    for row in specs:
        if (
            not isinstance(row, list | tuple)
            or len(row) != 2
            or not all(isinstance(cell, str) and cell.strip() for cell in row)
        ):
            raise ValidationError("Cada fila de la ficha técnica es [etiqueta, valor].")
        clean.append([row[0].strip()[:60], row[1].strip()[:200]])
    return clean


@transaction.atomic
def add_option(
    product: Product,
    attribute: Attribute,
    values: Sequence[AttributeValue | tuple[AttributeValue, MoneyInput]],
) -> ProductOption:
    """Make ``product`` configurable by ``attribute`` with the given values (and modifiers)."""
    option, _ = ProductOption.objects.get_or_create(
        product=product,
        attribute=attribute,
        defaults={"position": product.options.count()},
    )
    for position, item in enumerate(values):
        value, modifier = item if isinstance(item, tuple) else (item, Decimal("0"))
        if value.attribute_id != attribute.pk:
            raise ValidationError(f"«{value}» no es un valor de {attribute}.")
        ProductOptionValue.objects.update_or_create(
            option=option,
            value=value,
            defaults={"price_modifier": to_money(modifier), "position": position},
        )
    return option


def _validate_combination(product: Product, values: Sequence[AttributeValue]) -> None:
    options = {
        option.attribute_id: {ov.value_id for ov in option.values.all()}
        for option in product.options.prefetch_related("values")
    }
    given: dict[int, int] = {}
    for value in values:
        if value.attribute_id in given:
            raise ValidationError(f"Hay dos valores para {value.attribute}.")
        given[value.attribute_id] = value.pk
    if set(given) != set(options):
        raise ValidationError("La variante debe tener un valor para cada opción del producto.")
    for attribute_id, value_id in given.items():
        if value_id not in options[attribute_id]:
            raise ValidationError("Uno de los valores no está permitido para este producto.")


@transaction.atomic
def create_variant(
    product: Product,
    *,
    sku: str,
    values: Sequence[AttributeValue] = (),
    price: MoneyInput | None = None,
    actor: Any = None,
    **fields: Any,
) -> ProductVariant:
    """Create a sellable variant, price it with the engine and record its initial price."""
    sku = sku.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{1,39}", sku):
        raise ValidationError("SKU inválido: use letras, números y guiones.")
    _validate_combination(product, values)
    key = combination_key(value.pk for value in values)
    if product.variants.filter(combination_key=key).exists():
        raise ValidationError("Ya existe una variante con esa combinación.")
    override = to_money(price) if price is not None else None
    if override is None and product.pricing_mode == Product.PricingMode.FIXED:
        raise ValidationError("En modo de precio fijo cada variante necesita su precio.")
    final = (
        override
        if override is not None
        else pricing.price_from_modifiers(product, [v.pk for v in values])
    )
    if final <= 0:
        raise ValidationError("El precio debe ser mayor que cero.")
    variant = ProductVariant.objects.create(
        product=product,
        sku=sku,
        combination_key=key,
        price=final,
        price_override=override,
        **fields,
    )
    variant.values.set(values)
    pricing.record_initial_price(variant, actor=actor)
    record_event(
        "catalog.variant_created",
        actor=actor,
        target=variant,
        changes={"sku": sku, "price": str(final)},
    )
    return variant


def refresh_search_index(product: Product) -> None:
    """Rebuild the accent-free search text and the weighted full-text vector."""
    product = (
        Product.objects.select_related("brand", "category__parent")
        .prefetch_related("platforms", "variants__values")
        .get(pk=product.pk)
    )
    parts = [
        product.name,
        product.search_keywords,
        product.brand.name if product.brand else "",
        product.category.name,
        product.category.parent.name if product.category.parent else "",
        product.get_product_type_display(),
        product.short_description,
    ]
    for platform in product.platforms.all():
        parts += [platform.name, platform.aliases]
    values = {value.value for variant in product.variants.all() for value in variant.values.all()}
    parts += sorted(values)
    text = normalize_text(" ".join(part for part in parts if part))[:SEARCH_TEXT_MAX]
    name = normalize_text(product.name)
    Product.objects.filter(pk=product.pk).update(
        search_text=text,
        search_vector=SearchVector(
            Value(name, output_field=TextField()), weight="A", config="spanish"
        )
        + SearchVector(Value(text, output_field=TextField()), weight="B", config="spanish"),
    )


# --- Visitor lists kept in the session (no personal data, only public ids) ---------------


def _session_ids(session: MutableMapping[str, Any], key: str) -> list[str]:
    raw = session.get(key, [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and _UUID.match(item)]


def compare_ids(session: MutableMapping[str, Any]) -> list[str]:
    return _session_ids(session, COMPARE_SESSION_KEY)[:COMPARE_MAX]


def add_to_compare(session: MutableMapping[str, Any], product: Product) -> list[str]:
    ids = compare_ids(session)
    public_id = str(product.public_id)
    if public_id in ids:
        return ids
    if len(ids) >= COMPARE_MAX:
        raise CompareListFullError
    ids.append(public_id)
    session[COMPARE_SESSION_KEY] = ids
    return ids


def remove_from_compare(session: MutableMapping[str, Any], product: Product) -> list[str]:
    ids = [item for item in compare_ids(session) if item != str(product.public_id)]
    session[COMPARE_SESSION_KEY] = ids
    return ids


def clear_compare(session: MutableMapping[str, Any]) -> None:
    session[COMPARE_SESSION_KEY] = []


def viewed_ids(session: MutableMapping[str, Any]) -> list[str]:
    return _session_ids(session, VIEWED_SESSION_KEY)[:VIEWED_MAX]


def remember_viewed(session: MutableMapping[str, Any], product: Product) -> None:
    public_id = str(product.public_id)
    ids = [item for item in viewed_ids(session) if item != public_id]
    session[VIEWED_SESSION_KEY] = [public_id, *ids][:VIEWED_MAX]
