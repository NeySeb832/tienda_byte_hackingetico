"""Customer views for value-added services: trade-ins, points, alerts, returns, repair tickets.

All customer data is filtered by the logged-in owner (anti-IDOR); the public repair tracking
needs the ticket code *and* the email, and is rate limited.
"""

from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit

from apps.accounts.permissions import authenticated_user
from apps.catalog.models import Product, ProductVariant
from apps.notifications import services as alerts
from apps.notifications.models import ProductAlert
from apps.orders import returns
from apps.orders.models import Order, ReturnRequest
from apps.promotions import services as promotions
from apps.promotions.models import CreditEntry, LoyaltyEntry
from apps.services_desk import services as tickets
from apps.services_desk.models import ServiceTicket
from apps.tradein import services as tradein
from apps.tradein.forms import ReturnForm, TrackingForm, TradeInForm
from apps.tradein.models import TradeInRequest


def _fail(request: HttpRequest, error: ValidationError) -> None:
    messages.error(request, error.messages[0] if error.messages else "Operación no válida.")


@method_decorator(ratelimit(key="user_or_ip", rate="20/h", method="POST", block=True), name="post")
class TradeInView(LoginRequiredMixin, View):
    def _context(self, request: HttpRequest, form: Any) -> dict[str, Any]:
        user = authenticated_user(request)
        return {
            "form": form,
            "requests": TradeInRequest.objects.filter(user=user).select_related("product"),
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, "tradein/tradein.html", self._context(request, TradeInForm()))

    def post(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        form = TradeInForm(request.POST)
        if form.is_valid():
            try:
                quote = tradein.request_quote(
                    user,
                    form.cleaned_data["consola"],
                    form.cleaned_data["estado"],
                    has_box=form.cleaned_data["caja"],
                    has_controller=form.cleaned_data["control"],
                )
                messages.success(
                    request,
                    f"Tu {quote.product.name} vale hasta $ {quote.estimated_value:,.0f}. Tráela a una tienda para la oferta final.".replace(
                        ",", "."
                    ),
                )
                return redirect("tradein:list")
            except ValidationError as error:
                form.add_error(None, error)
        return render(request, "tradein/tradein.html", self._context(request, form), status=400)


class TradeInAnswerView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, public_id: str) -> HttpResponse:
        user = authenticated_user(request)
        trade = get_object_or_404(TradeInRequest, public_id=public_id, user=user)
        try:
            tradein.answer_offer(
                trade,
                user=user,
                accept=request.POST.get("respuesta") == "aceptar",
                payout=request.POST.get("pago", ""),
            )
            messages.success(request, "Respuesta registrada.")
        except ValidationError as error:
            _fail(request, error)
        return redirect("tradein:list")


class PointsView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        return render(
            request,
            "tradein/points.html",
            {
                "points": promotions.points_balance(user),
                "credit": promotions.credit_balance(user),
                "points_entries": LoyaltyEntry.objects.filter(user=user).order_by("-created_at")[
                    :20
                ],
                "credit_entries": CreditEntry.objects.filter(user=user).order_by("-created_at")[
                    :20
                ],
                "block": promotions.REDEEM_BLOCK,
                "block_value": promotions.CREDIT_PER_BLOCK,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        raw = request.POST.get("bloques", "")
        try:
            if not raw.isdigit():
                raise ValidationError("Indica cuántos bloques quieres canjear.")
            promotions.redeem_points(user, int(raw))
            messages.success(request, "Canjeaste tus puntos por saldo a favor.")
        except ValidationError as error:
            _fail(request, error)
        return redirect("tradein:points")


class AlertsView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        return render(
            request,
            "tradein/alerts.html",
            {"alerts": ProductAlert.objects.filter(user=user).select_related("variant__product")},
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        if request.POST.get("accion") == "quitar":
            alerts.unsubscribe(user, request.POST.get("alerta", ""))
            messages.info(request, "Alerta eliminada.")
            return redirect("tradein:alerts")
        variant = get_object_or_404(
            ProductVariant.objects.select_related("product"),
            sku=request.POST.get("sku", "")[:40],
            is_active=True,
        )
        try:
            alerts.subscribe(user, variant, request.POST.get("tipo", ""))
            messages.success(request, "Te avisaremos por correo.")
        except ValidationError as error:
            _fail(request, error)
        return redirect(f"{variant.product.get_absolute_url()}?sku={variant.sku}")


class ReturnRequestView(LoginRequiredMixin, View):
    def _order(self, request: HttpRequest, public_id: str) -> Order:
        return get_object_or_404(
            Order.objects.prefetch_related("lines"),
            public_id=public_id,
            user=authenticated_user(request),
        )

    def _context(self, order: Order, form: Any) -> dict[str, Any]:
        return {
            "order": order,
            "form": form,
            "lines": [(line, returns.returnable_quantity(line)) for line in order.lines.all()],
            "deadlines": {
                kind: returns.deadline(order, kind) for kind in ReturnRequest.Kind.values
            },
            "existing": order.returns.all(),
        }

    def get(self, request: HttpRequest, public_id: str) -> HttpResponse:
        order = self._order(request, public_id)
        return render(request, "tradein/return_request.html", self._context(order, ReturnForm()))

    def post(self, request: HttpRequest, public_id: str) -> HttpResponse:
        order = self._order(request, public_id)
        form = ReturnForm(request.POST)
        if form.is_valid():
            quantities = {}
            for line in order.lines.all():
                raw = request.POST.get(f"linea-{line.pk}", "0").strip() or "0"
                quantities[line.pk] = int(raw) if raw.isdigit() else -1
            try:
                returns.request_return(
                    order,
                    user=authenticated_user(request),
                    quantities=quantities,
                    kind=form.cleaned_data["tipo"],
                    reason=form.cleaned_data["motivo"],
                    refund_method=form.cleaned_data["reembolso"],
                )
                messages.success(
                    request,
                    "Recibimos tu solicitud. Lleva el producto a una tienda o espera nuestro contacto.",
                )
                return redirect("orders:detail", public_id=order.public_id)
            except ValidationError as error:
                form.add_error(None, error)
        return render(
            request, "tradein/return_request.html", self._context(order, form), status=400
        )


class MyTicketsView(LoginRequiredMixin, View):
    def get(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        return render(
            request,
            "tradein/my_tickets.html",
            {
                "tickets": ServiceTicket.objects.filter(customer=user)
                .select_related("store")
                .prefetch_related("events")
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        ticket = get_object_or_404(
            ServiceTicket, public_id=request.POST.get("orden", ""), customer=user
        )
        try:
            tickets.answer_quote(
                ticket, approve=request.POST.get("respuesta") == "aprobar", actor=user
            )
            messages.success(request, "Respuesta registrada.")
        except ValidationError as error:
            _fail(request, error)
        return redirect("tradein:tickets")


@method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True), name="post")
class TrackTicketView(View):
    """Public tracking: requires the code and the email used at intake."""

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, "tradein/track.html", {"form": TrackingForm()})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = TrackingForm(request.POST)
        ticket = None
        if form.is_valid():
            ticket = tickets.ticket_by_code(
                form.cleaned_data["codigo"], form.cleaned_data["correo"]
            )
            if ticket is None:
                form.add_error(None, "No encontramos una orden con esos datos.")
        return render(
            request,
            "tradein/track.html",
            {"form": form, "ticket": ticket},
            status=200 if ticket else 400,
        )


def consoles_for_tradein() -> Any:
    return Product.objects.filter(is_active=True, product_type=Product.Type.CONSOLE).order_by(
        "name"
    )
