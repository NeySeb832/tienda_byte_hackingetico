"""Gateway webhook and the sandbox payment simulator."""

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.accounts.permissions import authenticated_user
from apps.payments import services
from apps.payments.models import Payment

MAX_WEBHOOK_BYTES = 64 * 1024


@csrf_exempt  # authenticated by the gateway signature, not by a session
@require_POST
@ratelimit(key="ip", rate="120/m", block=True)
def webhook(request: HttpRequest) -> JsonResponse:
    if len(request.body) > MAX_WEBHOOK_BYTES:
        return JsonResponse({"ok": False}, status=413)
    headers = {key.lower(): value for key, value in request.headers.items()}
    status, message = services.process_notification(request.body, headers)
    return JsonResponse({"ok": status == 200, "detail": message}, status=status)


def _simulator_enabled() -> None:
    if settings.BYTE_PAYMENT_GATEWAY != "fake":
        raise Http404


class SimulatorView(LoginRequiredMixin, View):
    """Sandbox only: stands in for the gateway's hosted page (no card data is asked)."""

    def _payment(self, request: HttpRequest, reference: str) -> Payment:
        _simulator_enabled()
        return get_object_or_404(
            Payment.objects.select_related("order"),
            reference=reference,
            order__user=authenticated_user(request),
            status=Payment.Status.PENDING,
        )

    def get(self, request: HttpRequest, reference: str) -> HttpResponse:
        return render(
            request, "payments/simulator.html", {"payment": self._payment(request, reference)}
        )

    def post(self, request: HttpRequest, reference: str) -> HttpResponse:
        payment = self._payment(request, reference)
        services.simulate(payment, approve=request.POST.get("resultado") == "aprobar")
        return redirect("orders:result", payment.order.public_id)
