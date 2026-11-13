"""Checkout, payment result and "Mis pedidos" (customer area). Owner-only (anti-IDOR)."""

from typing import Any

from allauth.account.models import EmailAddress
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit

from apps.accounts.permissions import authenticated_user
from apps.accounts.selectors import addresses_for
from apps.cart import selectors as cart_selectors
from apps.cart import services as cart_services
from apps.inventory.models import Store
from apps.orders import selectors, services
from apps.orders.forms import CheckoutForm
from apps.orders.invoice_pdf import render_invoice
from apps.orders.models import Order
from apps.payments import services as payments
from apps.payments.gateways import GatewayError


def _pickup_stores() -> Any:
    return Store.objects.filter(is_active=True, is_pickup_point=True).select_related("city")


@method_decorator(ratelimit(key="user_or_ip", rate="20/m", method="POST", block=True), name="post")
class CheckoutView(LoginRequiredMixin, View):
    template_name = "orders/checkout.html"

    def _context(
        self, request: HttpRequest, form: CheckoutForm, totals: Any = None
    ) -> dict[str, Any]:
        user = authenticated_user(request)
        cart = cart_services.get_cart(request.session, user)
        return {
            "form": form,
            "summary": cart_selectors.cart_summary(cart),
            "totals": totals,
            "verified": EmailAddress.objects.filter(user=user, verified=True).exists(),
        }

    def _form(self, request: HttpRequest, data: Any = None) -> CheckoutForm:
        user = authenticated_user(request)
        return CheckoutForm(data, addresses=addresses_for(user), stores=_pickup_stores())

    def get(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        cart = cart_services.get_cart(request.session, user)
        if not cart_selectors.cart_summary(cart).lines:
            messages.info(request, "Tu carrito está vacío.")
            return redirect("cart:detail")
        form = self._form(request)
        return render(request, self.template_name, self._context(request, form))

    def post(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        cart = cart_services.get_cart(request.session, user)
        form = self._form(request, request.POST)
        if cart is None or not form.is_valid():
            return render(request, self.template_name, self._context(request, form), status=400)
        if not EmailAddress.objects.filter(user=user, verified=True).exists():
            messages.error(request, "Verifica tu correo antes de pagar.")
            return redirect("orders:checkout")
        data = form.cleaned_data
        try:
            totals = services.compute_totals(
                cart,
                user=user,
                fulfillment=data["entrega"],
                address=data.get("direccion"),
                coupon_code=data.get("cupon", ""),
            )
            if request.POST.get("accion") != "pagar":
                return render(request, self.template_name, self._context(request, form, totals))
            order = services.place_order(
                user=user,
                cart=cart,
                fulfillment=data["entrega"],
                address=data.get("direccion"),
                pickup_store=data.get("tienda"),
                coupon_code=data.get("cupon", ""),
                accepted_terms=data["acepto"],
            )
        except ValidationError as exc:
            form.add_error(None, exc.messages[0])
            return render(request, self.template_name, self._context(request, form), status=400)
        redirect_url = request.build_absolute_uri(reverse("orders:result", args=[order.public_id]))
        _, url = payments.start_payment(order, redirect_url=redirect_url)
        return redirect(url)


class PaymentResultView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, public_id: str) -> HttpResponse:
        order = selectors.order_for(authenticated_user(request), public_id)
        transaction_id = request.GET.get("id", "")
        if transaction_id and order.status == Order.Status.PENDING_PAYMENT:
            try:
                payments.sync_from_gateway(order, transaction_id)
                order.refresh_from_db()
            except GatewayError:
                messages.warning(
                    request, "Aún no tenemos la confirmación del pago. Revisa en unos minutos."
                )
        return render(request, "orders/result.html", {"order": order})


class OrderListView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            "orders/order_list.html",
            {"orders": selectors.orders_for(authenticated_user(request))},
        )


class OrderDetailView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, public_id: str) -> HttpResponse:
        order = selectors.order_for(authenticated_user(request), public_id)
        return render(
            request,
            "orders/order_detail.html",
            {
                "order": order,
                "address": selectors.address_of(order),
                "timeline": selectors.timeline(order),
            },
        )


class InvoicePdfView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest, public_id: str) -> HttpResponse:
        order = selectors.order_for(authenticated_user(request), public_id, with_invoice=True)
        response = HttpResponse(render_invoice(order), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="factura-{order.invoice.number}.pdf"'
        response["Cache-Control"] = "private, no-store"
        return response
