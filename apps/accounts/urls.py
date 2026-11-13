from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("", views.AccountDashboardView.as_view(), name="dashboard"),
    path("perfil/", views.ProfileView.as_view(), name="profile"),
    path("direcciones/", views.AddressListView.as_view(), name="addresses"),
    path("direcciones/nueva/", views.AddressFormView.as_view(), name="address_create"),
    path(
        "direcciones/<uuid:public_id>/editar/",
        views.AddressFormView.as_view(),
        name="address_update",
    ),
    path(
        "direcciones/<uuid:public_id>/eliminar/",
        views.AddressDeleteView.as_view(),
        name="address_delete",
    ),
    path("privacidad/", views.PrivacyView.as_view(), name="privacy"),
    path("privacidad/mis-datos.json", views.DataExportView.as_view(), name="data_export"),
]
