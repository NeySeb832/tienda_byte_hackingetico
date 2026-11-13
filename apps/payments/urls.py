from django.urls import path

from apps.payments import views

app_name = "payments"

urlpatterns = [
    path("webhook/", views.webhook, name="webhook"),
    path("simulador/<str:reference>/", views.SimulatorView.as_view(), name="simulator"),
]
