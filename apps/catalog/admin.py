"""Django admin for the catalogue (superadmin only, see apps.accounts.admin).

Prices are read-only here: they change through the pricing engine (scheduled price
changes below, or the panel) so that every change lands in the append-only history.
"""

from django.contrib import admin

from apps.catalog.models import (
    Attribute,
    AttributeValue,
    Brand,
    Category,
    GameDetails,
    Genre,
    Platform,
    Product,
    ProductVariant,
)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "is_retro", "sort")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "show_on_home", "sort")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Genre)
class GenreAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}


class AttributeValueInline(admin.TabularInline):
    model = AttributeValue
    extra = 0


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "sort")
    inlines = [AttributeValueInline]


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0
    fields = ("sku", "price", "price_override", "is_active", "position")
    readonly_fields = ("sku", "price", "price_override")
    can_delete = False
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False  # variants are created by the catalogue services (combination rules)


class GameDetailsInline(admin.StackedInline):
    model = GameDetails
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "product_type", "category", "brand", "is_active", "is_featured")
    list_filter = ("product_type", "category", "brand", "is_active", "is_featured")
    search_fields = ("name", "slug", "variants__sku")
    readonly_fields = ("public_id", "pricing_mode", "base_price")
    inlines = [GameDetailsInline, VariantInline]
    filter_horizontal = ("platforms",)
