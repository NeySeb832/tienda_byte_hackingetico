"""HTTP views for the cart app (guests and customers). Writes are POST + CSRF only."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit

from apps.cart import selectors, services
from apps.cart.forms import AddToCartForm, QuantityForm
from apps.catalog.models import ProductVariant


def _variant(sku: str) -> ProductVariant:
    return get_object_or_404(
        ProductVariant.objects.select_related("product"),
        sku=sku.strip().upper()[:40],
        is_active=True,
        product__is_active=True,
    )


class CartView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        cart = services.get_cart(request.session, request.user)
        return render(request, "cart/cart.html", {"summary": selectors.cart_summary(cart)})


@method_decorator(ratelimit(key="ip", rate="60/m", method="POST", block=True), name="post")
class AddToCartView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        form = AddToCartForm(request.POST)
        if not form.is_valid():
            messages.error(request, "No pudimos agregar el producto.")
            return redirect("cart:detail")
        variant = _variant(form.cleaned_data["sku"])
        cart = services.get_cart(request.session, request.user, create=True)
        assert cart is not None  # noqa: S101 - create=True
        try:
            services.add_item(cart, variant, form.cleaned_data["cantidad"])
            messages.success(request, f"Agregaste «{variant.product.name}» al carrito.")
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect(f"{variant.product.get_absolute_url()}?sku={variant.sku}")
        return redirect("cart:detail")


class UpdateCartView(View):
    def post(self, request: HttpRequest, sku: str) -> HttpResponse:
        cart = services.get_cart(request.session, request.user)
        if cart is None:
            return redirect("cart:detail")
        variant = get_object_or_404(ProductVariant, sku=sku.strip().upper()[:40])
        form = QuantityForm(request.POST)
        try:
            if not form.is_valid():
                raise ValidationError("Cantidad inválida.")
            services.set_quantity(cart, variant, form.cleaned_data["cantidad"])
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        return redirect("cart:detail")


class RemoveFromCartView(View):
    def post(self, request: HttpRequest, sku: str) -> HttpResponse:
        cart = services.get_cart(request.session, request.user)
        if cart is not None:
            services.remove_item(
                cart, get_object_or_404(ProductVariant, sku=sku.strip().upper()[:40])
            )
            messages.info(request, "Quitaste el producto del carrito.")
        return redirect("cart:detail")
