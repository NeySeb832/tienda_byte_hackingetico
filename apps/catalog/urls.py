from django.urls import path

from apps.catalog import views

app_name = "catalog"

urlpatterns = [
    path("catalogo/", views.CatalogListView.as_view(), name="list"),
    path("categoria/<slug:slug>/", views.CatalogListView.as_view(), name="category"),
    path("buscar/", views.SearchView.as_view(), name="search"),
    path("buscar/sugerencias/", views.SuggestionsView.as_view(), name="suggest"),
    path("producto/<slug:slug>/", views.ProductDetailView.as_view(), name="product"),
    path("comparar/", views.CompareView.as_view(), name="compare"),
    path("comparar/vaciar/", views.compare_clear, name="compare_clear"),
    path("comparar/<slug:slug>/", views.compare_toggle, name="compare_toggle"),
]
