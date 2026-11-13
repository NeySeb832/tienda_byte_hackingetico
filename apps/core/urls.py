from django.urls import path

from apps.core import views

app_name = "core"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("healthz", views.healthz, name="healthz"),
    path("creditos-imagenes/", views.ImageCreditsView.as_view(), name="image_credits"),
]
