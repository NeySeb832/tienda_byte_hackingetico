from django.urls import path

from apps.tradein import views

app_name = "tradein"

urlpatterns = [
    path("cuenta/retomas/", views.TradeInView.as_view(), name="list"),
    path(
        "cuenta/retomas/<uuid:public_id>/responder/",
        views.TradeInAnswerView.as_view(),
        name="answer",
    ),
    path("cuenta/puntos/", views.PointsView.as_view(), name="points"),
    path("cuenta/alertas/", views.AlertsView.as_view(), name="alerts"),
    path("cuenta/servicio-tecnico/", views.MyTicketsView.as_view(), name="tickets"),
    path(
        "cuenta/pedidos/<uuid:public_id>/devolucion/",
        views.ReturnRequestView.as_view(),
        name="return",
    ),
    path("servicio-tecnico/seguimiento/", views.TrackTicketView.as_view(), name="track"),
]
