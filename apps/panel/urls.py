from django.urls import path

from apps.panel import views

app_name = "panel"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("personal/", views.StaffListView.as_view(), name="staff"),
    path("auditoria/", views.AuditLogListView.as_view(), name="audit"),
    path("seguridad/", views.SecurityEventListView.as_view(), name="security"),
]
