from django.urls import path

from apps.cart import views

app_name = "cart"

urlpatterns = [
    path("", views.CartView.as_view(), name="detail"),
    path("agregar/", views.AddToCartView.as_view(), name="add"),
    path("actualizar/<str:sku>/", views.UpdateCartView.as_view(), name="update"),
    path("quitar/<str:sku>/", views.RemoveFromCartView.as_view(), name="remove"),
]
