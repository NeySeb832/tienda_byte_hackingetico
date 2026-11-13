"""Forms for the customer value-added services (server-side validation)."""

from django import forms

from apps.catalog.models import Product
from apps.orders.models import ReturnRequest
from apps.tradein.models import TradeInRequest


class TradeInForm(forms.Form):
    consola = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True, product_type=Product.Type.CONSOLE).order_by(
            "name"
        ),
        to_field_name="slug",
        label="Consola",
        empty_label="Elige tu consola",
    )
    estado = forms.ChoiceField(
        choices=TradeInRequest.Condition.choices, widget=forms.RadioSelect, label="Estado"
    )
    caja = forms.BooleanField(required=False, label="Tengo la caja original")
    control = forms.BooleanField(required=False, initial=True, label="Incluye el control original")


class ReturnForm(forms.Form):
    tipo = forms.ChoiceField(choices=ReturnRequest.Kind.choices, label="Tipo de solicitud")
    motivo = forms.CharField(
        max_length=500, widget=forms.Textarea(attrs={"rows": 3}), label="Motivo"
    )
    reembolso = forms.ChoiceField(
        choices=ReturnRequest.Refund.choices, label="¿Cómo quieres el reembolso?"
    )


class TrackingForm(forms.Form):
    codigo = forms.CharField(max_length=12, label="Código de la orden (ST-…)")
    correo = forms.EmailField(label="Correo con el que dejaste el equipo")
