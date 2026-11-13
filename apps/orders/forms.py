"""Checkout form. Only choices that belong to the user are accepted (anti-IDOR)."""

from typing import Any

from django import forms

from apps.orders.models import Order
from apps.promotions.services import normalize_code


class CheckoutForm(forms.Form):
    entrega = forms.ChoiceField(
        choices=Order.Fulfillment.choices, widget=forms.RadioSelect, label="Entrega"
    )
    direccion: forms.ModelChoiceField = forms.ModelChoiceField(
        queryset=None,
        required=False,
        to_field_name="public_id",
        label="Dirección",
        empty_label=None,
    )
    tienda: forms.ModelChoiceField = forms.ModelChoiceField(
        queryset=None, required=False, to_field_name="public_id", label="Tienda", empty_label=None
    )
    cupon = forms.CharField(required=False, max_length=30, label="Cupón")
    acepto = forms.BooleanField(required=False, label="Acepto los términos y condiciones")

    def __init__(self, *args: Any, addresses: Any, stores: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["direccion"].queryset = addresses  # type: ignore[attr-defined]
        self.fields["tienda"].queryset = stores  # type: ignore[attr-defined]

    def clean_cupon(self) -> str:
        return normalize_code(self.cleaned_data.get("cupon") or "")

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        if data.get("entrega") == Order.Fulfillment.SHIPPING and not data.get("direccion"):
            self.add_error("direccion", "Elige una dirección o agrega una nueva en Mi cuenta.")
        if data.get("entrega") == Order.Fulfillment.PICKUP and not data.get("tienda"):
            self.add_error("tienda", "Elige la tienda donde recogerás.")
        return data
