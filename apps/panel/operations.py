"""Back-office operations: orders, stock, adjustments, transfers, purchases, POS, customers,
prices, coupons and reports. Every view declares its permissions (deny by default) and every
queryset is limited to the stores of the user (anti-IDOR); objects outside scope are 404.
"""

from decimal import Decimal
from typing import Any

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Max, Q, QuerySet, Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views import View

from apps.accounts import selectors as account_selectors
from apps.accounts.models import User
from apps.accounts.permissions import StaffRequiredMixin, authenticated_user
from apps.analytics import selectors as reports
from apps.audit.services import record_event
from apps.catalog.models import ProductVariant
from apps.inventory import services as inventory
from apps.inventory.models import (
    InventoryAdjustment,
    StockItem,
    StockMovement,
    StockTransfer,
    Store,
)
from apps.orders import services as orders
from apps.orders.models import Order
from apps.panel import forms
from apps.pos import services as pos
from apps.pos.models import CashSession
from apps.pricing import services as pricing
from apps.promotions import services as promotions
from apps.promotions.models import Coupon
from apps.purchasing import services as purchasing
from apps.purchasing.models import PurchaseOrder, Supplier

PAGE = 30


def _stores(request: HttpRequest) -> QuerySet[Store]:
    return account_selectors.stores_for(authenticated_user(request))


def _page(request: HttpRequest, queryset: Any) -> Any:
    return Paginator(queryset, PAGE).get_page(request.GET.get("pagina"))


def _variant(sku: str) -> ProductVariant:
    return get_object_or_404(
        ProductVariant.objects.select_related("product"), sku=sku.strip().upper()[:40]
    )


def _fail(request: HttpRequest, error: ValidationError) -> None:
    messages.error(request, error.messages[0] if error.messages else "Operación no válida.")


# --- Orders ------------------------------------------------------------------------------------


def orders_in_scope(request: HttpRequest) -> QuerySet[Order]:
    stores = _stores(request)
    return (
        Order.objects.filter(Q(pickup_store__in=stores) | Q(fulfillment=Order.Fulfillment.SHIPPING))
        .select_related("pickup_store", "user")
        .distinct()
    )


FULFILLMENT_ACTIONS: dict[str, list[tuple[str, str]]] = {
    Order.Status.PAID: [(Order.Status.PREPARING, "Empezar a preparar")],
    Order.Status.PREPARING: [
        (Order.Status.SHIPPED, "Marcar como enviado"),
        (Order.Status.READY_FOR_PICKUP, "Listo para recoger"),
    ],
    Order.Status.SHIPPED: [(Order.Status.DELIVERED, "Marcar como entregado")],
    Order.Status.READY_FOR_PICKUP: [(Order.Status.DELIVERED, "Entregado al cliente")],
}


class OrderListView(StaffRequiredMixin, View):
    required_permissions = ("orders.view_order",)

    def get(self, request: HttpRequest) -> HttpResponse:
        queryset = orders_in_scope(request)
        status = request.GET.get("estado", "")
        if status in Order.Status.values:
            queryset = queryset.filter(status=status)
        channel = request.GET.get("canal", "")
        if channel in Order.Channel.values:
            queryset = queryset.filter(channel=channel)
        query = request.GET.get("q", "").strip()[:40]
        if query:
            queryset = queryset.filter(Q(number__icontains=query) | Q(email__icontains=query))
        return render(
            request,
            "panel/orders.html",
            {
                "page": _page(request, queryset.order_by("-created_at")),
                "statuses": Order.Status.choices,
                "channels": Order.Channel.choices,
                "status": status,
                "channel": channel,
                "q": query,
            },
        )


class OrderDetailView(StaffRequiredMixin, View):
    required_permissions = ("orders.view_order",)

    def _order(self, request: HttpRequest, public_id: str) -> Order:
        return get_object_or_404(orders_in_scope(request), public_id=public_id)

    def get(self, request: HttpRequest, public_id: str) -> HttpResponse:
        order = self._order(request, public_id)
        user = authenticated_user(request)
        actions = (
            FULFILLMENT_ACTIONS.get(order.status, [])
            if user.has_perm("orders.manage_fulfillment")
            else []
        )
        if order.fulfillment == Order.Fulfillment.PICKUP:
            actions = [a for a in actions if a[0] != Order.Status.SHIPPED]
        else:
            actions = [a for a in actions if a[0] != Order.Status.READY_FOR_PICKUP]
        from apps.orders.selectors import address_of, timeline

        return render(
            request,
            "panel/order_detail.html",
            {
                "order": order,
                "actions": actions,
                "address": address_of(order),
                "timeline": timeline(order),
            },
        )

    def post(self, request: HttpRequest, public_id: str) -> HttpResponse:
        user = authenticated_user(request)
        if not user.has_perm("orders.manage_fulfillment"):
            return HttpResponse(status=403)
        order = self._order(request, public_id)
        target = request.POST.get("estado", "")
        allowed = {status for status, _ in FULFILLMENT_ACTIONS.get(order.status, [])}
        if target not in allowed:
            messages.error(request, "Acción no permitida para este pedido.")
            return redirect("panel:order_detail", public_id=order.public_id)
        try:
            orders.transition(order, target, actor=user, note=request.POST.get("nota", "")[:200])
            messages.success(request, "Pedido actualizado.")
        except ValidationError as error:
            _fail(request, error)
        return redirect("panel:order_detail", public_id=order.public_id)


# --- Stock, kardex, adjustments and transfers --------------------------------------------------


class StockView(StaffRequiredMixin, View):
    required_permissions = ("inventory.view_stockitem",)

    def get(self, request: HttpRequest) -> HttpResponse:
        stores = _stores(request)
        queryset = (
            StockItem.objects.filter(store__in=stores)
            .select_related("variant__product", "store")
            .annotate(free=F("quantity") - F("reserved"))
            .order_by("variant__product__name", "variant__sku", "store__name")
        )
        query = request.GET.get("q", "").strip()[:60]
        if query:
            queryset = queryset.filter(
                Q(variant__sku__icontains=query) | Q(variant__product__name__icontains=query)
            )
        store = request.GET.get("sede", "")
        if store:
            queryset = queryset.filter(store__code=store)
        if request.GET.get("bajo"):
            queryset = queryset.filter(free__lte=reports.LOW_STOCK)
        return render(
            request,
            "panel/stock.html",
            {
                "page": _page(request, queryset),
                "stores": stores,
                "q": query,
                "store": store,
                "low": bool(request.GET.get("bajo")),
            },
        )


class KardexView(StaffRequiredMixin, View):
    required_permissions = ("inventory.view_stockmovement",)

    def get(self, request: HttpRequest, sku: str) -> HttpResponse:
        variant = _variant(sku)
        movements = (
            StockMovement.objects.filter(variant=variant, store__in=_stores(request))
            .select_related("store", "created_by")
            .order_by("-created_at", "-pk")
        )
        return render(
            request, "panel/kardex.html", {"variant": variant, "page": _page(request, movements)}
        )


class AdjustmentsView(StaffRequiredMixin, View):
    required_permissions = ("inventory.request_adjustment",)

    def _context(self, request: HttpRequest, form: Any) -> dict[str, Any]:
        stores = _stores(request)
        return {
            "form": form,
            "adjustments": InventoryAdjustment.objects.filter(store__in=stores).select_related(
                "variant__product", "store", "requested_by", "decided_by"
            )[:50],
            "can_approve": authenticated_user(request).has_perm("inventory.approve_adjustment"),
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            "panel/adjustments.html",
            self._context(request, forms.AdjustmentForm(stores=_stores(request))),
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        form = forms.AdjustmentForm(request.POST, stores=_stores(request))
        if form.is_valid():
            try:
                inventory.request_adjustment(
                    _variant(form.cleaned_data["sku"]),
                    form.cleaned_data["sede"],
                    form.cleaned_data["cantidad"],
                    reason=form.cleaned_data["motivo"],
                    actor=authenticated_user(request),
                )
                messages.success(request, "Ajuste solicitado. Debe aprobarlo otra persona.")
                return redirect("panel:adjustments")
            except ValidationError as error:
                form.add_error(None, error)
        return render(request, "panel/adjustments.html", self._context(request, form), status=400)


class AdjustmentDecisionView(StaffRequiredMixin, View):
    required_permissions = ("inventory.approve_adjustment",)

    def post(self, request: HttpRequest, public_id: str) -> HttpResponse:
        adjustment = get_object_or_404(
            InventoryAdjustment, public_id=public_id, store__in=_stores(request)
        )
        try:
            inventory.decide_adjustment(
                adjustment,
                approver=authenticated_user(request),
                approve=request.POST.get("decision") == "aprobar",
            )
            messages.success(request, "Ajuste decidido.")
        except ValidationError as error:
            _fail(request, error)
        return redirect("panel:adjustments")


class TransfersView(StaffRequiredMixin, View):
    required_permissions = ("inventory.manage_transfers",)

    def _context(self, request: HttpRequest, form: Any) -> dict[str, Any]:
        stores = _stores(request)
        return {
            "form": form,
            "transfers": StockTransfer.objects.filter(
                Q(from_store__in=stores) | Q(to_store__in=stores)
            )
            .select_related("variant__product", "from_store", "to_store")
            .distinct()[:50],
            "my_stores": set(stores.values_list("pk", flat=True)),
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            "panel/transfers.html",
            self._context(request, forms.TransferForm(stores=_stores(request))),
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        form = forms.TransferForm(request.POST, stores=_stores(request))
        if form.is_valid():
            try:
                inventory.request_transfer(
                    _variant(form.cleaned_data["sku"]),
                    form.cleaned_data["origen"],
                    form.cleaned_data["destino"],
                    form.cleaned_data["cantidad"],
                    actor=authenticated_user(request),
                )
                messages.success(request, "Traslado solicitado.")
                return redirect("panel:transfers")
            except ValidationError as error:
                form.add_error(None, error)
        return render(request, "panel/transfers.html", self._context(request, form), status=400)


class TransferActionView(StaffRequiredMixin, View):
    required_permissions = ("inventory.manage_transfers",)

    def post(self, request: HttpRequest, public_id: str) -> HttpResponse:
        stores = _stores(request)
        action = request.POST.get("accion")
        # Only the origin store ships and only the destination store receives.
        lookup = {"from_store__in": stores} if action == "despachar" else {"to_store__in": stores}
        transfer = get_object_or_404(StockTransfer, public_id=public_id, **lookup)
        try:
            if action == "despachar":
                inventory.ship_transfer(transfer, actor=authenticated_user(request))
            else:
                inventory.receive_transfer(transfer, actor=authenticated_user(request))
            messages.success(request, "Traslado actualizado.")
        except ValidationError as error:
            _fail(request, error)
        return redirect("panel:transfers")


# --- Purchasing --------------------------------------------------------------------------------


class PurchaseOrderListView(StaffRequiredMixin, View):
    required_permissions = ("purchasing.view_purchaseorder",)

    def _context(self, request: HttpRequest, form: Any) -> dict[str, Any]:
        return {
            "form": form,
            "orders": PurchaseOrder.objects.filter(store__in=_stores(request)).select_related(
                "supplier", "store", "created_by", "approved_by"
            )[:50],
            "can_create": authenticated_user(request).has_perm("purchasing.add_purchaseorder"),
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            "panel/purchase_orders.html",
            self._context(request, forms.PurchaseOrderForm(stores=_stores(request))),
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        if not user.has_perm("purchasing.add_purchaseorder"):
            return HttpResponse(status=403)
        form = forms.PurchaseOrderForm(request.POST, stores=_stores(request))
        if form.is_valid():
            try:
                lines = [
                    (_variant(sku), qty, cost) for sku, qty, cost in form.cleaned_data["lineas"]
                ]
                order = purchasing.create_purchase_order(
                    form.cleaned_data["proveedor"],
                    form.cleaned_data["sede"],
                    lines,
                    actor=user,
                    notes=form.cleaned_data["notas"],
                )
                messages.success(
                    request, f"Orden {order.number} creada. Debe aprobarla otra persona."
                )
                return redirect("panel:purchase_order", public_id=order.public_id)
            except ValidationError as error:
                form.add_error(None, error)
        return render(
            request, "panel/purchase_orders.html", self._context(request, form), status=400
        )


class PurchaseOrderDetailView(StaffRequiredMixin, View):
    required_permissions = ("purchasing.view_purchaseorder",)

    def _order(self, request: HttpRequest, public_id: str) -> PurchaseOrder:
        return get_object_or_404(
            PurchaseOrder.objects.select_related("supplier", "store").prefetch_related(
                "lines__variant__product", "receipts"
            ),
            public_id=public_id,
            store__in=_stores(request),
        )

    def get(self, request: HttpRequest, public_id: str) -> HttpResponse:
        order = self._order(request, public_id)
        return render(
            request,
            "panel/purchase_order_detail.html",
            {"order": order, "total": purchasing.total_cost(order)},
        )

    def post(self, request: HttpRequest, public_id: str) -> HttpResponse:
        user = authenticated_user(request)
        order = self._order(request, public_id)
        action = request.POST.get("accion")
        try:
            if action == "aprobar" and user.has_perm("purchasing.approve_purchaseorder"):
                purchasing.approve_purchase_order(order, approver=user)
                messages.success(request, "Orden aprobada.")
            elif action == "recibir" and user.has_perm("purchasing.receive_purchaseorder"):
                quantities = {}
                for line in order.lines.all():
                    raw = request.POST.get(f"linea-{line.pk}", "0").strip() or "0"
                    if not raw.isdigit():
                        raise ValidationError("Las cantidades deben ser números enteros.")
                    quantities[line.pk] = int(raw)
                purchasing.receive_goods(
                    order, quantities, actor=user, note=request.POST.get("nota", "")
                )
                messages.success(request, "Mercancía recibida e ingresada al inventario.")
            else:
                return HttpResponse(status=403)
        except ValidationError as error:
            _fail(request, error)
        return redirect("panel:purchase_order", public_id=order.public_id)


class SupplierView(StaffRequiredMixin, View):
    required_permissions = ("purchasing.view_supplier",)

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(
            request,
            "panel/suppliers.html",
            {"suppliers": Supplier.objects.all(), "form": forms.SupplierForm()},
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        if not user.has_perm("purchasing.add_supplier"):
            return HttpResponse(status=403)
        form = forms.SupplierForm(request.POST)
        if form.is_valid():
            supplier = form.save()
            record_event("purchasing.supplier_created", actor=user, target=supplier)
            messages.success(request, "Proveedor creado.")
            return redirect("panel:suppliers")
        return render(
            request,
            "panel/suppliers.html",
            {"suppliers": Supplier.objects.all(), "form": form},
            status=400,
        )


# --- Point of sale -----------------------------------------------------------------------------


class PosView(StaffRequiredMixin, View):
    required_permissions = ("pos.use_pos",)

    def _session(self, request: HttpRequest) -> CashSession | None:
        return (
            CashSession.objects.filter(opened_by=authenticated_user(request), closed_at=None)
            .select_related("store")
            .first()
        )

    def get(self, request: HttpRequest) -> HttpResponse:
        session = self._session(request)
        return render(
            request,
            "panel/pos.html",
            {
                "session": session,
                "open_form": forms.OpenSessionForm(stores=_stores(request)),
                "sale_form": forms.PosSaleForm(),
                "close_form": forms.CloseSessionForm(),
                "cash_sales": pos.cash_sales(session) if session else None,
                "recent": (
                    Order.objects.filter(cash_session=session).order_by("-created_at")[:10]
                    if session
                    else []
                ),
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        action = request.POST.get("accion")
        session = self._session(request)
        try:
            if action == "abrir":
                form = forms.OpenSessionForm(request.POST, stores=_stores(request))
                if not form.is_valid():
                    raise ValidationError("Revisa la sede y la base de caja.")
                pos.open_session(
                    form.cleaned_data["sede"], actor=user, opening_float=form.cleaned_data["base"]
                )
                messages.success(request, "Turno abierto.")
            elif action == "vender" and session is not None:
                sale = forms.PosSaleForm(request.POST)
                if not sale.is_valid():
                    raise ValidationError("Revisa los productos y el medio de pago.")
                items = [(_variant(sku), qty) for sku, qty in sale.cleaned_data["productos"]]
                order, change = pos.sell(
                    session,
                    items,
                    actor=user,
                    method=sale.cleaned_data["medio"],
                    cash_received=sale.cleaned_data.get("recibido"),
                    customer_email=sale.cleaned_data.get("correo") or "",
                )
                messages.success(
                    request,
                    f"Venta {order.number} registrada. Cambio: $ {change:,.0f}".replace(",", "."),
                )
            elif action == "cerrar" and session is not None:
                closing = forms.CloseSessionForm(request.POST)
                if not closing.is_valid():
                    raise ValidationError("Indica el efectivo contado.")
                closed = pos.close_session(
                    session, actor=user, counted_cash=closing.cleaned_data["contado"]
                )
                messages.info(
                    request,
                    f"Turno cerrado. Diferencia: $ {closed.difference:,.0f}".replace(",", "."),
                )
            else:
                raise ValidationError("Acción no válida.")
        except ValidationError as error:
            _fail(request, error)
        return redirect("panel:pos")


# --- Customers (CRM) ---------------------------------------------------------------------------


class CustomerListView(StaffRequiredMixin, View):
    required_permissions = ("accounts.view_customers",)

    def get(self, request: HttpRequest) -> HttpResponse:
        queryset = (
            User.objects.filter(is_staff=False)
            .annotate(
                order_count=Count("orders", filter=Q(orders__status__in=reports.SOLD)),
                spent=Sum("orders__total", filter=Q(orders__status__in=reports.SOLD)),
                last_order=Max("orders__paid_at"),
            )
            .order_by("-last_order", "email")
        )
        query = request.GET.get("q", "").strip()[:80]
        if query:
            queryset = queryset.filter(
                Q(email__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )
        return render(
            request, "panel/customers.html", {"page": _page(request, queryset), "q": query}
        )


class CustomerDetailView(StaffRequiredMixin, View):
    required_permissions = ("accounts.view_customers",)

    def get(self, request: HttpRequest, public_id: str) -> HttpResponse:
        customer = get_object_or_404(User, public_id=public_id, is_staff=False)
        # Viewing personal data is logged (Ley 1581 accountability).
        record_event(
            "crm.customer_viewed",
            actor=authenticated_user(request),
            target=customer,
            request=request,
        )
        customer_orders = Order.objects.filter(user=customer).order_by("-created_at")
        sold = customer_orders.filter(status__in=reports.SOLD).aggregate(
            total=Sum("total"), n=Count("pk")
        )
        return render(
            request,
            "panel/customer_detail.html",
            {
                "customer": customer,
                "orders": customer_orders[:20],
                "spent": sold["total"] or Decimal("0"),
                "count": sold["n"],
            },
        )


# --- Prices and coupons ------------------------------------------------------------------------


class PricesView(StaffRequiredMixin, View):
    required_permissions = ("pricing.change_price",)

    def get(self, request: HttpRequest) -> HttpResponse:
        query = request.GET.get("q", "").strip()[:60]
        variants = (
            ProductVariant.objects.select_related("product")
            .filter(is_active=True)
            .order_by("product__name", "sku")
        )
        if query:
            variants = variants.filter(Q(sku__icontains=query) | Q(product__name__icontains=query))
        return render(
            request,
            "panel/prices.html",
            {"page": _page(request, variants), "q": query, "form": forms.PriceForm()},
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        form = forms.PriceForm(request.POST)
        user = authenticated_user(request)
        if not form.is_valid():
            messages.error(request, "Revisa el SKU, el precio y la fecha.")
            return redirect("panel:prices")
        variant = _variant(form.cleaned_data["sku"])
        try:
            when = form.cleaned_data.get("desde")
            if when:
                pricing.schedule_price_change(
                    variant,
                    form.cleaned_data["precio"],
                    when,
                    actor=user,
                    note=form.cleaned_data["nota"],
                )
                messages.success(request, f"Cambio programado para {variant.sku}.")
            else:
                pricing.change_variant_price(
                    variant, form.cleaned_data["precio"], actor=user, note=form.cleaned_data["nota"]
                )
                messages.success(request, f"Precio de {variant.sku} actualizado.")
        except ValidationError as error:
            _fail(request, error)
        # Fixed internal URL + encoded query (no user-controlled target).
        return redirect(f"{reverse('panel:prices')}?{urlencode({'q': variant.sku})}")


class CouponsView(StaffRequiredMixin, View):
    required_permissions = ("promotions.view_coupon",)

    def _context(self, request: HttpRequest, form: Any) -> dict[str, Any]:
        user = authenticated_user(request)
        return {
            "form": form,
            "coupons": Coupon.objects.select_related("created_by", "approved_by")[:50],
            "can_add": user.has_perm("promotions.add_coupon"),
            "can_approve": user.has_perm("promotions.approve_coupon"),
            "needs_approval": promotions.needs_approval,
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, "panel/coupons.html", self._context(request, forms.CouponForm()))

    def post(self, request: HttpRequest) -> HttpResponse:
        user = authenticated_user(request)
        if request.POST.get("accion") == "aprobar":
            if not user.has_perm("promotions.approve_coupon"):
                return HttpResponse(status=403)
            coupon = get_object_or_404(Coupon, public_id=request.POST.get("cupon", ""))
            try:
                promotions.approve_coupon(coupon, approver=user)
                messages.success(request, f"Cupón {coupon.code} aprobado.")
            except ValidationError as error:
                _fail(request, error)
            return redirect("panel:coupons")
        if not user.has_perm("promotions.add_coupon"):
            return HttpResponse(status=403)
        form = forms.CouponForm(request.POST)
        if form.is_valid():
            coupon = form.save(commit=False)
            coupon.created_by = user
            coupon.save()
            record_event("promotions.coupon_created", actor=user, target=coupon)
            messages.success(request, f"Cupón {coupon.code} creado.")
            return redirect("panel:coupons")
        return render(request, "panel/coupons.html", self._context(request, form), status=400)


# --- Reports -----------------------------------------------------------------------------------


class ReportsView(StaffRequiredMixin, View):
    required_permissions = ("orders.view_sales_report",)

    def get(self, request: HttpRequest) -> HttpResponse:
        days = reports.sales_by_day(30)
        if request.GET.get("formato") == "csv":
            record_event(
                "reports.exported",
                actor=authenticated_user(request),
                changes={"report": "ventas-30-dias"},
            )
            response = HttpResponse(
                reports.to_csv(
                    ["fecha", "pedidos", "total"],
                    ((d.day.isoformat(), d.orders, d.total) for d in days),
                ),
                content_type="text/csv; charset=utf-8",
            )
            response["Content-Disposition"] = (
                f'attachment; filename="ventas-{timezone.localdate():%Y%m%d}.csv"'
            )
            return response
        peak = max((d.total for d in days), default=Decimal("0")) or Decimal("1")
        return render(
            request,
            "panel/reports.html",
            {
                # Bars as SVG attributes (no inline styles: strict CSP).
                "bars": [_bar(index, d, peak) for index, d in enumerate(days)],
                "total": sum((d.total for d in days), Decimal("0")),
                "orders": sum(d.orders for d in days),
                "channels": reports.sales_by_channel(),
                "products": reports.top_products(),
                "stores": reports.sales_by_store(),
            },
        )


def _bar(index: int, day: Any, peak: Decimal) -> dict[str, Any]:
    height = int(day.total * 96 / peak) if day.total else 0
    return {"day": day, "x": index * 10 + 1, "y": 100 - height, "h": height}
