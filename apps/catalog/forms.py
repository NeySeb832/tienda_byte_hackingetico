"""Forms for the catalog app. Validation here is authoritative (server side).

The filter form is lenient on purpose: an unknown brand, a malformed price or an
unexpected sort key is dropped instead of failing the whole page, so tampered query
strings only ever narrow down to valid, whitelisted values.
"""

from typing import Any, cast

from django import forms

from apps.catalog.models import Category
from apps.catalog.selectors import SORT_LABELS, CatalogFilters, facet_choices

MAX_QUERY_LENGTH = 80
MAX_PRICE = 100_000_000


class LenientMultipleChoiceField(forms.MultipleChoiceField):
    """Keeps only the valid choices instead of raising a validation error."""

    def clean(self, value: Any) -> list[str]:
        values = self.to_python(value)
        return [item for item in dict.fromkeys(values) if self.valid_value(item)][:20]


class CatalogFilterForm(forms.Form):
    q = forms.CharField(required=False, strip=True, label="Buscar")
    marca = LenientMultipleChoiceField(required=False, label="Marca")
    plataforma = LenientMultipleChoiceField(required=False, label="Plataforma")
    condicion = LenientMultipleChoiceField(required=False, label="Condición")
    tipo = LenientMultipleChoiceField(required=False, label="Tipo de producto")
    precio_min = forms.IntegerField(required=False, min_value=0, max_value=MAX_PRICE, label="Desde")
    precio_max = forms.IntegerField(required=False, min_value=0, max_value=MAX_PRICE, label="Hasta")
    disponible = forms.BooleanField(required=False, label="Solo disponibles")
    orden = forms.ChoiceField(
        required=False, choices=list(SORT_LABELS.items()), label="Ordenar por"
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        choices = facet_choices()
        for name, key in (
            ("marca", "brands"),
            ("plataforma", "platforms"),
            ("condicion", "conditions"),
            ("tipo", "types"),
        ):
            cast(forms.ChoiceField, self.fields[name]).choices = choices[key]

    def clean_q(self) -> str:
        value: str = self.cleaned_data.get("q") or ""
        printable = "".join(ch for ch in value if ch.isprintable())
        return printable[:MAX_QUERY_LENGTH].strip()

    def to_filters(self, category: Category | None = None) -> CatalogFilters:
        self.is_valid()  # invalid fields are simply left out of cleaned_data
        data = getattr(self, "cleaned_data", {})
        price_min, price_max = data.get("precio_min"), data.get("precio_max")
        if price_min is not None and price_max is not None and price_min > price_max:
            price_min, price_max = price_max, price_min
        return CatalogFilters(
            q=data.get("q", ""),
            category=category,
            brands=data.get("marca", []),
            platforms=data.get("plataforma", []),
            conditions=data.get("condicion", []),
            types=data.get("tipo", []),
            price_min=price_min,
            price_max=price_max,
            in_stock=bool(data.get("disponible")),
            sort=data.get("orden") or "relevancia",
        )
