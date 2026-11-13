"""Core views: home page, health check and error handlers."""

import logging
from typing import Any

from django.http import HttpRequest, HttpResponse, HttpResponseServerError, JsonResponse
from django.shortcuts import render
from django.template import loader
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from apps.catalog.selectors import featured_controllers, featured_products
from apps.cms.selectors import home_categories, home_slides, image_credits
from apps.core.health import run_health_checks
from apps.core.logging import current_request_id
from apps.services_desk.selectors import technical_services

security_logger = logging.getLogger("django.security.csrf")


class HomeView(TemplateView):
    template_name = "core/home.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context.update(
            slides=home_slides(),
            categories=home_categories(),
            featured=featured_products(),
            controllers=featured_controllers(),
            services=technical_services(),
        )
        return context


class ImageCreditsView(TemplateView):
    template_name = "core/creditos.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["credits"] = image_credits()
        return context


@require_GET
@never_cache
def healthz(request: HttpRequest) -> JsonResponse:
    """Liveness/readiness probe: database + cache. Never exposes error details."""
    report = run_health_checks()
    return JsonResponse(
        {
            "status": "ok" if report.healthy else "error",
            "checks": {name: "ok" if ok else "error" for name, ok in report.checks.items()},
        },
        status=200 if report.healthy else 503,
    )


def _render_error(request: HttpRequest, template_name: str, status: int) -> HttpResponse:
    return render(request, template_name, {"request_id": current_request_id()}, status=status)


def bad_request(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return _render_error(request, "errors/400.html", 400)


def permission_denied(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return _render_error(request, "errors/403.html", 403)


def page_not_found(request: HttpRequest, exception: Exception | None = None) -> HttpResponse:
    return _render_error(request, "errors/404.html", 404)


def server_error(request: HttpRequest) -> HttpResponse:
    # Standalone template rendered without the request: it must never fail itself.
    template = loader.get_template("errors/500.html")
    return HttpResponseServerError(template.render({"request_id": current_request_id()}))


def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    security_logger.warning("CSRF verification failed", extra={"path": request.path})
    return _render_error(request, "errors/403_csrf.html", 403)
