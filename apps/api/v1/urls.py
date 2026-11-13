"""Routes of API v1. Endpoints are added per phase; the schema is staff-only."""

from django.urls import path
from drf_spectacular.views import SpectacularAPIView

app_name = "api-v1"

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
]
