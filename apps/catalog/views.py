"""HTTP views for the catalog app. Views orchestrate only: no business logic here.

The catalogue is public (read only). The only writes are the visitor's own comparison
list and "recently viewed" list, kept in the session; they change via POST with CSRF.
"""

from typing import Any

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.cart.services import max_quantity
from apps.catalog import selectors, services
from apps.catalog.forms import CatalogFilterForm
from apps.catalog.models import Category, Product
from apps.core.money import split_vat
from apps.inventory.selectors import availability_by_store
from apps.pricing.selectors import price_insight, price_sparkline

PAGE_SIZE = 24


def _is_htmx_target(request: HttpRequest, target: str) -> bool:
    htmx = getattr(request, "htmx", None)
    if not htmx:
        return False
    return bool(htmx.target == target)


class CatalogListView(View):
    """Full catalogue, a category, or search results (same filters and template)."""

    template_name = "catalog/product_list.html"
    partial_template = "catalog/_catalog_body.html"
    mode = "catalog"

    def get(self, request: HttpRequest, slug: str | None = None) -> HttpResponse:
        category = get_object_or_404(Category, slug=slug) if slug else None
        form = CatalogFilterForm(request.GET)
        filters = form.to_filters(category)
        page = Paginator(selectors.filter_products(filters), PAGE_SIZE).get_page(
            request.GET.get("pagina")
        )
        query = request.GET.copy()
        query.pop("pagina", None)
        context: dict[str, Any] = {
            "form": form,
            "filters": filters,
            "category": category,
            "mode": self.mode,
            "page": page,
            "cards": selectors.product_cards(page.object_list),
            "query_string": query.urlencode(),
            "facets": selectors.facet_counts(filters),
            "sort_labels": selectors.SORT_LABELS,
            "subcategories": list(category.children.order_by("sort", "name")) if category else [],
        }
        if _is_htmx_target(request, "catalogo"):
            return render(request, self.partial_template, context)
        return render(request, self.template_name, context)


class SearchView(CatalogListView):
    mode = "search"


@method_decorator(ratelimit(key="ip", rate="60/m", method="GET", block=True), name="get")
class SuggestionsView(View):
    """Search-as-you-type (HTMX). Short or empty queries return an empty list."""

    def get(self, request: HttpRequest) -> HttpResponse:
        q = (request.GET.get("q") or "")[:80]
        return render(
            request,
            "catalog/_suggestions.html",
            {"q": q.strip(), "results": selectors.suggestions(q)},
        )


class ProductDetailView(View):
    template_name = "catalog/product_detail.html"
    partial_template = "catalog/_configurator.html"

    def get(self, request: HttpRequest, slug: str) -> HttpResponse:
        product = selectors.product_for_detail(slug)
        if product is None:
            raise Http404
        config = selectors.configure(product, request.GET.get("sku"))
        if config is None:
            raise Http404
        context: dict[str, Any] = {
            "product": product,
            "config": config,
            "insight": price_insight(config.variant),
            "sparkline": price_sparkline(config.variant),
            "stores": availability_by_store(config.variant),
            "max_quantity": max_quantity(config.variant),
            "in_compare": str(product.public_id) in services.compare_ids(request.session),
            "vat": (
                split_vat(config.variant.price).vat
                if product.tax_class == Product.TaxClass.STANDARD
                else None
            ),
        }
        if _is_htmx_target(request, "configurador"):
            return render(request, self.partial_template, context)
        viewed = [
            item for item in services.viewed_ids(request.session) if item != str(product.public_id)
        ]
        services.remember_viewed(request.session, product)
        context.update(
            related=selectors.related_products(product),
            recently_viewed=selectors.product_cards(selectors.products_by_public_ids(viewed[:4])),
            breadcrumb=[c for c in (product.category.parent, product.category) if c],
        )
        return render(request, self.template_name, context)


class CompareView(View):
    template_name = "catalog/compare.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        products = selectors.products_by_public_ids(services.compare_ids(request.session))
        return render(
            request,
            self.template_name,
            {
                "products": products,
                "cards": selectors.product_cards(products),
                "rows": selectors.compare_rows(products),
                "max_items": services.COMPARE_MAX,
            },
        )


def _safe_next(request: HttpRequest, fallback: str) -> str:
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return fallback


@require_POST
def compare_toggle(request: HttpRequest, slug: str) -> HttpResponse:
    product = get_object_or_404(Product, slug=slug, is_active=True)
    if request.POST.get("accion") == "quitar":
        services.remove_from_compare(request.session, product)
        messages.info(request, f"Quitaste «{product.name}» del comparador.")
    else:
        try:
            services.add_to_compare(request.session, product)
            messages.success(request, f"Agregaste «{product.name}» al comparador.")
        except services.CompareListFullError:
            messages.warning(
                request,
                f"Puedes comparar hasta {services.COMPARE_MAX} productos. Quita uno para agregar otro.",
            )
    return redirect(_safe_next(request, "catalog:compare"))


@require_POST
def compare_clear(request: HttpRequest) -> HttpResponse:
    services.clear_compare(request.session)
    return redirect("catalog:compare")
