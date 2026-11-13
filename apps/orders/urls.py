from django.urls import path

from apps.orders import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.CheckoutView.as_view(), name="checkout"),
    path("checkout/resultado/<uuid:public_id>/", views.PaymentResultView.as_view(), name="result"),
    path("cuenta/pedidos/", views.OrderListView.as_view(), name="list"),
    path("cuenta/pedidos/<uuid:public_id>/", views.OrderDetailView.as_view(), name="detail"),
    path(
        "cuenta/pedidos/<uuid:public_id>/factura/", views.InvoicePdfView.as_view(), name="invoice"
    ),
]
