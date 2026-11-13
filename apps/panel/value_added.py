"""Back office for value-added services: trade-in inspection, repair tickets and returns."""

from typing import Any

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.accounts import selectors as account_selectors
from apps.accounts.models import User
from apps.accounts.permissions import StaffRequiredMixin, authenticated_user
from apps.orders import returns
from apps.orders.models import ReturnRequest
from apps.services_desk import services as tickets
from apps.services_desk.models import ServiceTicket, TechnicalService
from apps.tradein import services as tradein
from apps.tradein.models import TradeInRequest


def _fail(request: HttpRequest, error: ValidationError) -> None:
    messages.error(request, error.messages[0] if error.messages else "Operación no válida.")


def _stores(request: HttpRequest) -> Any:
    return account_selectors.stores_for(authenticated_user(request))


class TicketForm(forms.Form):
    sede: forms.ModelChoiceField = forms.ModelChoiceField(
        queryset=None, to_field_name="code", label="Sede"
    )
    nombre = forms.CharField(max_length=120, label="Cliente")
    correo = forms.EmailField(label="Correo del cliente")
    equipo = forms.CharField(max_length=120, label="Equipo")
    serial = forms.CharField(max_length=60, required=False, label="Serial")
    servicio = forms.ModelChoiceField(
        queryset=TechnicalService.objects.filter(is_active=True),
        required=False,
        label="Servicio (opcional)",
    )
    falla = forms.CharField(
        max_length=1000, widget=forms.Textarea(attrs={"rows": 3}), label="Falla reportada"
    )

    def __init__(self, *args: Any, stores: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["sede"].queryset = stores  # type: ignore[attr-defined]


class TradeInPanelView(StaffRequiredMixin, View):
    required_permissions = ("tradein.inspect_tradein",)

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            "panel/tradeins.html",
            {
                "requests": TradeInRequest.objects.select_related(
                    "user", "product", "inspected_by"
                )[:60],
                "stores": _stores(request),
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        trade = get_object_or_404(TradeInRequest, public_id=request.POST.get("retoma", ""))
        store = _stores(request).filter(code=request.POST.get("sede", "")).first()
        value = request.POST.get("oferta", "").strip()
        try:
            if store is None or not value.isdigit():
                raise ValidationError("Indica la sede y una oferta en pesos.")
            tradein.inspect(
                trade,
                inspector=authenticated_user(request),
                store=store,
                final_value=value,
                notes=request.POST.get("notas", ""),
            )
            messages.success(request, "Oferta final registrada; el cliente la verá en su cuenta.")
        except ValidationError as error:
            _fail(request, error)
        return redirect("panel:tradeins")


class TicketListView(StaffRequiredMixin, View):
    required_permissions = ("services_desk.manage_tickets",)

    def _context(self, request: HttpRequest, form: Any) -> dict[str, Any]:
        return {
            "form": form,
            "tickets": ServiceTicket.objects.filter(store__in=_stores(request)).select_related(
                "store", "technician"
            )[:60],
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            "panel/tickets.html",
            self._context(request, TicketForm(stores=_stores(request))),
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        form = TicketForm(request.POST, stores=_stores(request))
        if form.is_valid():
            data = form.cleaned_data
            customer = User.objects.filter(email=data["correo"].lower(), is_staff=False).first()
            ticket = tickets.open_ticket(
                store=data["sede"],
                actor=authenticated_user(request),
                customer_name=data["nombre"],
                customer_email=data["correo"],
                device=data["equipo"],
                issue=data["falla"],
                serial_number=data["serial"],
                service=data["servicio"],
                customer=customer,
            )
            messages.success(request, f"Orden {ticket.code} creada. Entrega el código al cliente.")
            return redirect("panel:ticket", public_id=ticket.public_id)
        return render(request, "panel/tickets.html", self._context(request, form), status=400)


class TicketDetailView(StaffRequiredMixin, View):
    required_permissions = ("services_desk.manage_tickets",)

    def _ticket(self, request: HttpRequest, public_id: str) -> ServiceTicket:
        return get_object_or_404(
            ServiceTicket.objects.select_related("store", "service", "technician").prefetch_related(
                "events"
            ),
            public_id=public_id,
            store__in=_stores(request),
        )

    def get(self, request: HttpRequest, public_id: str) -> HttpResponse:
        ticket = self._ticket(request, public_id)
        labels = dict(ServiceTicket.Status.choices)
        options = [
            (status, labels[status])
            for status in tickets.STAFF_TRANSITIONS.get(ticket.status, set())
        ]
        return render(
            request,
            "panel/ticket_detail.html",
            {"ticket": ticket, "options": sorted(options), "labels": labels},
        )

    def post(self, request: HttpRequest, public_id: str) -> HttpResponse:
        ticket = self._ticket(request, public_id)
        quote = request.POST.get("cotizacion", "").strip()
        try:
            tickets.advance(
                ticket,
                request.POST.get("estado", ""),
                actor=authenticated_user(request),
                note=request.POST.get("nota", ""),
                diagnosis=request.POST.get("diagnostico", ""),
                quote=quote if quote.isdigit() else None,
            )
            messages.success(request, "Orden actualizada.")
        except ValidationError as error:
            _fail(request, error)
        return redirect("panel:ticket", public_id=ticket.public_id)


class ReturnsPanelView(StaffRequiredMixin, View):
    required_permissions = ("orders.receive_return",)

    def get(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        return render(
            request,
            "panel/returns.html",
            {
                "returns": ReturnRequest.objects.select_related(
                    "order", "received_by", "decided_by"
                ).prefetch_related("lines__line")[:60],
                "stores": _stores(request),
                "can_approve": user.has_perm("orders.approve_refund"),
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        item = get_object_or_404(ReturnRequest, public_id=request.POST.get("devolucion", ""))
        action = request.POST.get("accion")
        try:
            if action == "recibir":
                store = _stores(request).filter(code=request.POST.get("sede", "")).first()
                if store is None:
                    raise ValidationError("Elige la sede que recibe el producto.")
                returns.receive_return(
                    item, actor=user, store=store, restock=request.POST.get("reingresar") == "on"
                )
                messages.success(
                    request, "Devolución recibida. Otra persona debe aprobar el reembolso."
                )
            elif action in ("aprobar", "rechazar") and user.has_perm("orders.approve_refund"):
                returns.decide_refund(
                    item,
                    approver=user,
                    approve=action == "aprobar",
                    note=request.POST.get("nota", ""),
                )
                messages.success(request, "Decisión registrada.")
            else:
                return HttpResponse(status=403)
        except ValidationError as error:
            _fail(request, error)
        return redirect("panel:returns")
