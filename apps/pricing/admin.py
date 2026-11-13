"""Django admin for pricing: the history is read-only, scheduled changes record their author."""

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from apps.pricing.models import PriceHistory, ScheduledPriceChange


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("variant", "price", "previous_price", "reason", "changed_by", "changed_at")
    list_filter = ("reason",)
    search_fields = ("variant__sku",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(ScheduledPriceChange)
class ScheduledPriceChangeAdmin(admin.ModelAdmin):
    list_display = ("variant", "new_price", "starts_at", "status", "created_by", "applied_at")
    list_filter = ("status",)
    readonly_fields = ("status", "created_by", "applied_at")
    raw_id_fields = ("variant",)

    def save_model(
        self, request: HttpRequest, obj: ScheduledPriceChange, form: Any, change: bool
    ) -> None:
        if not change:
            obj.created_by = request.user  # type: ignore[assignment]
        super().save_model(request, obj, form, change)
