from django.urls import path

from apps.panel import operations as ops
from apps.panel import value_added as va
from apps.panel import views

app_name = "panel"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("personal/", views.StaffListView.as_view(), name="staff"),
    path("auditoria/", views.AuditLogListView.as_view(), name="audit"),
    path("seguridad/", views.SecurityEventListView.as_view(), name="security"),
    path("pedidos/", ops.OrderListView.as_view(), name="orders"),
    path("pedidos/<uuid:public_id>/", ops.OrderDetailView.as_view(), name="order_detail"),
    path("inventario/", ops.StockView.as_view(), name="stock"),
    path("inventario/kardex/<str:sku>/", ops.KardexView.as_view(), name="kardex"),
    path("inventario/ajustes/", ops.AdjustmentsView.as_view(), name="adjustments"),
    path(
        "inventario/ajustes/<uuid:public_id>/",
        ops.AdjustmentDecisionView.as_view(),
        name="adjustment_decision",
    ),
    path("inventario/traslados/", ops.TransfersView.as_view(), name="transfers"),
    path(
        "inventario/traslados/<uuid:public_id>/",
        ops.TransferActionView.as_view(),
        name="transfer_action",
    ),
    path("compras/", ops.PurchaseOrderListView.as_view(), name="purchase_orders"),
    path("compras/<uuid:public_id>/", ops.PurchaseOrderDetailView.as_view(), name="purchase_order"),
    path("compras/proveedores/", ops.SupplierView.as_view(), name="suppliers"),
    path("pos/", ops.PosView.as_view(), name="pos"),
    path("clientes/", ops.CustomerListView.as_view(), name="customers"),
    path("clientes/<uuid:public_id>/", ops.CustomerDetailView.as_view(), name="customer_detail"),
    path("precios/", ops.PricesView.as_view(), name="prices"),
    path("cupones/", ops.CouponsView.as_view(), name="coupons"),
    path("reportes/", ops.ReportsView.as_view(), name="reports"),
    path("retomas/", va.TradeInPanelView.as_view(), name="tradeins"),
    path("servicio-tecnico/", va.TicketListView.as_view(), name="tickets"),
    path("servicio-tecnico/<uuid:public_id>/", va.TicketDetailView.as_view(), name="ticket"),
    path("devoluciones/", va.ReturnsPanelView.as_view(), name="returns"),
]
