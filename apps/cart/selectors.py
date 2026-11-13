"""Read-side queries for the cart app: lines with current prices and totals."""

from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum

from apps.cart.models import Cart, CartItem
from apps.cart.services import max_quantity
from apps.catalog.selectors import _image
from apps.cms.selectors import ImageCredit


@dataclass(frozen=True, slots=True)
class CartLine:
    item: CartItem
    name: str
    url: str
    variant_label: str
    sku: str
    unit_price: Decimal
    quantity: int
    max_quantity: int
    image: ImageCredit | None

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity

    @property
    def problem(self) -> str:
        if self.max_quantity == 0:
            return "Agotado: quítalo para continuar."
        if self.quantity > self.max_quantity:
            return f"Solo hay {self.max_quantity} disponible(s)."
        return ""


@dataclass(frozen=True, slots=True)
class CartSummary:
    lines: list[CartLine]

    @property
    def count(self) -> int:
        return sum(line.quantity for line in self.lines)

    @property
    def subtotal(self) -> Decimal:
        return sum((line.line_total for line in self.lines), Decimal("0"))

    @property
    def can_checkout(self) -> bool:
        return bool(self.lines) and not any(line.problem for line in self.lines)

    @property
    def missing_for_free_shipping(self) -> Decimal:
        return max(Decimal(settings.BYTE_FREE_SHIPPING_FROM) - self.subtotal, Decimal("0"))


def variant_label(item: CartItem) -> str:
    return " · ".join(value.value for value in item.variant.values.all())


def cart_summary(cart: Cart | None) -> CartSummary:
    if cart is None:
        return CartSummary(lines=[])
    items = cart.items.select_related("variant__product").prefetch_related("variant__values")
    lines = [
        CartLine(
            item=item,
            name=item.variant.product.name,
            url=f"{item.variant.product.get_absolute_url()}?sku={item.variant.sku}",
            variant_label=variant_label(item),
            sku=item.variant.sku,
            unit_price=item.variant.price,
            quantity=item.quantity,
            max_quantity=max_quantity(item.variant),
            image=_image(item.variant.image_slug) or _image(item.variant.product.image_slug),
        )
        for item in items
    ]
    return CartSummary(lines=lines)


def cart_count(cart: Cart | None) -> int:
    if cart is None:
        return 0
    return int(cart.items.aggregate(total=Sum("quantity"))["total"] or 0)
