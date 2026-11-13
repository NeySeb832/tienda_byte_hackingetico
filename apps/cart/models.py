"""Data models for the cart app.

Guests keep their cart id in the session; it is merged into the user's cart at login
(ADR-0008). Prices are never stored here: the checkout always reads the current price.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel, TimeStampedModel

MAX_QUANTITY_PER_LINE = 10


class Cart(BaseModel):
    class Status(models.TextChoices):
        OPEN = "open", _("Abierto")
        MERGED = "merged", _("Fusionado")
        CONVERTED = "converted", _("Convertido en pedido")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="carts",
    )
    status = models.CharField(
        _("estado"), max_length=10, choices=Status.choices, default=Status.OPEN
    )

    class Meta:
        verbose_name = _("carrito")
        verbose_name_plural = _("carritos")
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="open", user__isnull=False),
                name="cart_one_open_cart_per_user",
            )
        ]

    def __str__(self) -> str:
        return f"Carrito {self.public_id}"


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.CASCADE, related_name="cart_items"
    )
    quantity = models.PositiveSmallIntegerField(_("cantidad"), default=1)

    class Meta:
        ordering = ["created_at", "pk"]
        verbose_name = _("ítem del carrito")
        verbose_name_plural = _("ítems del carrito")
        constraints = [
            models.UniqueConstraint(fields=["cart", "variant"], name="cart_item_unique_variant"),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1) & models.Q(quantity__lte=MAX_QUANTITY_PER_LINE),
                name="cart_item_quantity_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.variant_id}"
