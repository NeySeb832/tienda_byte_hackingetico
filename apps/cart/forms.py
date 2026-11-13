"""Forms for the cart app (server-side validation)."""

from django import forms

from apps.cart.models import MAX_QUANTITY_PER_LINE


class AddToCartForm(forms.Form):
    sku = forms.CharField(max_length=40)
    cantidad = forms.IntegerField(min_value=1, max_value=MAX_QUANTITY_PER_LINE, initial=1)


class QuantityForm(forms.Form):
    cantidad = forms.IntegerField(min_value=0, max_value=MAX_QUANTITY_PER_LINE)
