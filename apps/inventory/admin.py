"""Django admin for stores and stock (stock is read-only: it changes through the services)."""

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from apps.inventory.models import StockItem, Store


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "kind", "city", "is_pickup_point", "is_active")
    list_filter = ("kind", "is_active")


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ("variant", "store", "quantity", "reserved")
    list_filter = ("store",)
    search_fields = ("variant__sku",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False
