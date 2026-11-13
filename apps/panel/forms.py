"""Back-office forms. Store choices are always limited to the stores of the user (anti-IDOR)."""

import re
from decimal import Decimal
from typing import Any

from django import forms
from django.utils import timezone

from apps.pos.services import METHODS
from apps.promotions.models import Coupon
from apps.purchasing.models import Supplier

LINE_RE = re.compile(r"^\s*([A-Za-z0-9-]{2,40})\s*[xX*]\s*(\d{1,4})\s*(?:@\s*([\d.,]+))?\s*$")


def parse_lines(text: str, *, with_cost: bool) -> list[tuple[Any, ...]]:
    """``SKU x cantidad`` (and ``@ costo`` for purchases), one per line."""
    rows: list[tuple[Any, ...]] = []
    for number, raw in enumerate(text.strip().splitlines(), start=1):
        if not raw.strip():
            continue
        match = LINE_RE.match(raw)
        if not match or (with_cost and not match.group(3)):
            example = "PS5-N x 2 @ 2300000" if with_cost else "PS5-N x 2"
            raise forms.ValidationError(f"Línea {number}: usa el formato «{example}».")
        sku, quantity = match.group(1).upper(), int(match.group(2))
        if quantity < 1:
            raise forms.ValidationError(f"Línea {number}: la cantidad debe ser al menos 1.")
        if with_cost:
            cost = Decimal(match.group(3).replace(".", "").replace(",", "."))
            rows.append((sku, quantity, cost))
        else:
            rows.append((sku, quantity))
    if not rows:
        raise forms.ValidationError("Agrega al menos una línea.")
    if len(rows) > 50:
        raise forms.ValidationError("Máximo 50 líneas.")
    return rows


class StoreScopedForm(forms.Form):
    store_fields: tuple[str, ...] = ()

    def __init__(self, *args: Any, stores: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for name in self.store_fields:
            self.fields[name].queryset = stores  # type: ignore[attr-defined]


class AdjustmentForm(StoreScopedForm):
    store_fields = ("sede",)
    sku = forms.CharField(max_length=40, label="SKU")
    sede: forms.ModelChoiceField = forms.ModelChoiceField(
        queryset=None, to_field_name="code", label="Sede"
    )
    cantidad = forms.IntegerField(min_value=0, max_value=100000, label="Unidades contadas")
    motivo = forms.CharField(max_length=200, label="Motivo")


class TransferForm(StoreScopedForm):
    store_fields = ("origen", "destino")
    sku = forms.CharField(max_length=40, label="SKU")
    origen: forms.ModelChoiceField = forms.ModelChoiceField(
        queryset=None, to_field_name="code", label="Desde"
    )
    destino: forms.ModelChoiceField = forms.ModelChoiceField(
        queryset=None, to_field_name="code", label="Hacia"
    )
    cantidad = forms.IntegerField(min_value=1, max_value=10000, label="Unidades")


class PurchaseOrderForm(StoreScopedForm):
    store_fields = ("sede",)
    proveedor = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True), to_field_name="tax_id", label="Proveedor"
    )
    sede: forms.ModelChoiceField = forms.ModelChoiceField(
        queryset=None, to_field_name="code", label="Sede de destino"
    )
    lineas = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "PS5S-DISC-STD-N x 5 @ 2300000"}),
        label="Productos (SKU x cantidad @ costo unitario)",
    )
    notas = forms.CharField(max_length=255, required=False, label="Notas")

    def clean_lineas(self) -> list[tuple[Any, ...]]:
        return parse_lines(self.cleaned_data["lineas"], with_cost=True)


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "tax_id", "email", "phone"]


class OpenSessionForm(StoreScopedForm):
    store_fields = ("sede",)
    sede: forms.ModelChoiceField = forms.ModelChoiceField(
        queryset=None, to_field_name="code", label="Sede"
    )
    base = forms.DecimalField(min_value=0, max_digits=12, decimal_places=0, label="Base de caja")


class PosSaleForm(forms.Form):
    productos = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "DS-WHT-N x 1"}),
        label="Productos (SKU x cantidad)",
    )
    medio = forms.ChoiceField(choices=list(METHODS.items()), label="Medio de pago")
    recibido = forms.DecimalField(
        min_value=0, max_digits=12, decimal_places=0, required=False, label="Efectivo recibido"
    )
    correo = forms.EmailField(
        required=False, label="Correo del cliente (opcional, para la factura)"
    )

    def clean_productos(self) -> list[tuple[Any, ...]]:
        return parse_lines(self.cleaned_data["productos"], with_cost=False)


class CloseSessionForm(forms.Form):
    contado = forms.DecimalField(
        min_value=0, max_digits=12, decimal_places=0, label="Efectivo contado"
    )


class PriceForm(forms.Form):
    sku = forms.CharField(max_length=40)
    precio = forms.DecimalField(
        min_value=1, max_digits=12, decimal_places=0, label="Nuevo precio (IVA incluido)"
    )
    desde = forms.DateTimeField(
        required=False,
        label="Programar para",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    nota = forms.CharField(max_length=200, required=False)

    def clean_desde(self) -> Any:
        value = self.cleaned_data.get("desde")
        if value and timezone.is_naive(value):
            value = timezone.make_aware(value)
        return value


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = [
            "code",
            "description",
            "kind",
            "value",
            "max_discount",
            "min_subtotal",
            "starts_at",
            "ends_at",
            "usage_limit",
            "per_user_limit",
            "first_order_only",
        ]
        widgets = {
            "starts_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
            "ends_at": forms.DateTimeInput(
                format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}
            ),
        }

    def clean_code(self) -> str:
        from apps.promotions.services import normalize_code

        code = normalize_code(self.cleaned_data["code"])
        if len(code) < 4:
            raise forms.ValidationError("El código debe tener al menos 4 caracteres.")
        return code
