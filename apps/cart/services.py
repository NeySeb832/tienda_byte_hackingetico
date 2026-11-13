"""Business logic (write side) for the cart app.

Rules: only active variants of active products; at most ``MAX_QUANTITY_PER_LINE`` units
per line and never more than the product's ``max_per_order`` nor the free stock. The
guest cart id lives in the session and is merged into the user's cart at login.
"""

import uuid
from collections.abc import MutableMapping
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Sum
from django.db.models.functions import Coalesce

from apps.cart.models import MAX_QUANTITY_PER_LINE, Cart, CartItem
from apps.catalog.models import ProductVariant

SESSION_KEY = "cart"


def free_stock(variant: ProductVariant) -> int:
    total = variant.stock_items.filter(store__is_active=True).aggregate(
        free=Coalesce(Sum(F("quantity") - F("reserved")), 0)
    )["free"]
    return max(int(total), 0)


def max_quantity(variant: ProductVariant) -> int:
    return min(MAX_QUANTITY_PER_LINE, variant.product.max_per_order, free_stock(variant))


def _user(request_user: Any) -> Any:
    return request_user if getattr(request_user, "is_authenticated", False) else None


def get_cart(
    session: MutableMapping[str, Any], user: Any = None, *, create: bool = False
) -> Cart | None:
    """The visitor's open cart (user cart if logged in, otherwise the session cart)."""
    user = _user(user)
    if user is not None:
        cart = Cart.objects.filter(user=user, status=Cart.Status.OPEN).first()
        if cart is None and create:
            try:
                with transaction.atomic():
                    cart = Cart.objects.create(user=user)
            except IntegrityError:  # created concurrently
                cart = Cart.objects.get(user=user, status=Cart.Status.OPEN)
        return cart
    cart = None
    try:
        cart_id = uuid.UUID(str(session.get(SESSION_KEY, "")))
    except ValueError:  # missing or tampered session value
        cart_id = None
    if cart_id is not None:
        cart = Cart.objects.filter(public_id=cart_id, user=None, status=Cart.Status.OPEN).first()
    if cart is None and create:
        cart = Cart.objects.create()
        session[SESSION_KEY] = str(cart.public_id)
    return cart


def _check_variant(variant: ProductVariant) -> None:
    if not variant.is_active or not variant.product.is_active:
        raise ValidationError("Este producto ya no está disponible.")


@transaction.atomic
def add_item(cart: Cart, variant: ProductVariant, quantity: int = 1) -> CartItem:
    _check_variant(variant)
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise ValidationError("La cantidad debe ser al menos 1.")
    item = CartItem.objects.select_for_update().filter(cart=cart, variant=variant).first()
    current = item.quantity if item else 0
    limit = max_quantity(variant)
    if limit == 0:
        raise ValidationError("Este producto está agotado.")
    if current + quantity > limit:
        raise ValidationError(f"Puedes llevar máximo {limit} unidad(es) de este producto.")
    if item is None:
        return CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)
    item.quantity = current + quantity
    item.save(update_fields=["quantity", "updated_at"])
    return item


@transaction.atomic
def set_quantity(cart: Cart, variant: ProductVariant, quantity: int) -> CartItem | None:
    """Set a line quantity (0 removes it)."""
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
        raise ValidationError("Cantidad inválida.")
    item = CartItem.objects.select_for_update().filter(cart=cart, variant=variant).first()
    if item is None:
        raise ValidationError("El producto no está en tu carrito.")
    if quantity == 0:
        item.delete()
        return None
    limit = max_quantity(variant)
    if quantity > limit:
        raise ValidationError(f"Puedes llevar máximo {limit} unidad(es) de este producto.")
    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    return item


def remove_item(cart: Cart, variant: ProductVariant) -> None:
    CartItem.objects.filter(cart=cart, variant=variant).delete()


@transaction.atomic
def merge_session_cart(session: MutableMapping[str, Any], user: Any) -> Cart | None:
    """At login: move the guest cart lines into the user's cart (capped by the limits)."""
    guest = get_cart(session, None)
    session.pop(SESSION_KEY, None)
    if guest is None or not guest.items.exists():
        return get_cart(session, user)
    target = get_cart(session, user, create=True)
    assert target is not None  # noqa: S101 - created above
    for item in guest.items.select_related("variant__product"):
        existing = target.items.filter(variant=item.variant).first()
        wanted = (existing.quantity if existing else 0) + item.quantity
        limit = max_quantity(item.variant)
        if limit <= 0:
            continue
        CartItem.objects.update_or_create(
            cart=target, variant=item.variant, defaults={"quantity": min(wanted, limit)}
        )
    guest.status = Cart.Status.MERGED
    guest.save(update_fields=["status", "updated_at"])
    return target


def mark_converted(cart: Cart) -> None:
    cart.status = Cart.Status.CONVERTED
    cart.save(update_fields=["status", "updated_at"])
