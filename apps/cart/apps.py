"""Session and user carts, wishlist and product comparison."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class CartConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cart"

    def ready(self) -> None:
        from apps.cart import signals  # noqa: F401

    label = "cart"
    verbose_name = _("Carrito")
