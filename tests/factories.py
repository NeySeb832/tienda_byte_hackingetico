"""factory_boy factories and helpers shared by the test suite."""

from typing import TYPE_CHECKING, cast

import factory
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from django.contrib.auth.models import Group

from apps.accounts import roles
from apps.accounts.models import User
from apps.core.models import City
from apps.inventory.models import Store

if TYPE_CHECKING:
    from apps.catalog.models import Attribute, AttributeValue, Brand, Category, Platform, Product

TEST_PASSWORD = "ClaveDePrueba-2026!"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"usuario{n}@example.com")
    first_name = factory.Faker("first_name", locale="es_CO")
    last_name = factory.Faker("last_name", locale="es_CO")
    password = factory.django.Password(TEST_PASSWORD)

    @factory.post_generation
    def verified_email(self, create: bool, extracted: object, **kwargs: object) -> None:
        if create:
            EmailAddress.objects.create(user=self, email=self.email, verified=True, primary=True)


def enable_mfa(user: User) -> User:
    Authenticator.objects.create(
        user=user, type=Authenticator.Type.TOTP, data={"secret": "JBSWY3DPEHPK3PXP"}
    )
    return user


def make_user_with_role(role: str, *, mfa: bool = True) -> User:
    user = cast(
        User, UserFactory(is_staff=role in roles.STAFF_ROLES, is_superuser=role == roles.SUPERADMIN)
    )
    user.groups.add(Group.objects.get(name=role))
    if mfa and user.is_staff:
        enable_mfa(user)
    return user


class StoreFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Store

    code = factory.Sequence(lambda n: f"S{n:03d}")
    name = factory.Sequence(lambda n: f"Byte Sede {n}")
    city = factory.LazyFunction(lambda: City.objects.get(code="11001"))
    address = "Calle 100 # 10-20"


def make_store(**fields: object) -> Store:
    return cast(Store, StoreFactory(**fields))


def make_user(**fields: object) -> User:
    return cast(User, UserFactory(**fields))


# --- Catalogue helpers (built through the services, like real data) -----------------------

CONDITION_META = {
    "Nuevo": (0, {"warranty_months": 12}),
    "Reacondicionado": (1, {"warranty_months": 6}),
    "Usado": (2, {"warranty_months": 3}),
}


def attribute(code: str) -> "Attribute":
    from apps.catalog.models import Attribute

    return Attribute.objects.get_or_create(
        code=code,
        defaults={"name": str(Attribute.Code(code).label), "sort": 9 if code == "condition" else 0},
    )[0]


def attribute_value(code: str, label: str) -> "AttributeValue":
    from django.utils.text import slugify

    from apps.catalog.models import AttributeValue

    sort, meta = CONDITION_META.get(label, (0, {})) if code == "condition" else (0, {})
    return AttributeValue.objects.get_or_create(
        attribute=attribute(code),
        slug=slugify(label),
        defaults={"value": label, "sort": sort, "meta": meta},
    )[0]


def category(
    slug: str = "consolas", name: str | None = None, parent: object = None, **extra: object
) -> "Category":
    from apps.catalog.models import Category

    return Category.objects.get_or_create(
        slug=slug, defaults={"name": name or slug.title(), "parent": parent, **extra}
    )[0]


def brand(slug: str = "playstation", name: str | None = None) -> "Brand":
    from apps.catalog.models import Brand

    return Brand.objects.get_or_create(slug=slug, defaults={"name": name or slug.title()})[0]


def platform(slug: str = "ps5", name: str | None = None, aliases: str = "") -> "Platform":
    from apps.catalog.models import Platform

    return Platform.objects.get_or_create(
        slug=slug, defaults={"name": name or slug.upper(), "aliases": aliases}
    )[0]


def make_product(
    name: str = "Consola de prueba",
    *,
    variants: list[tuple] | None = None,
    options: dict[str, list] | None = None,
    stock: dict[str, int] | None = None,
    store: Store | None = None,
    mode: str = "fixed",
    base: int | None = None,
    **fields: object,
) -> "Product":
    """Create a product with options and variants through the catalogue services.

    ``options``: {"condition": ["Nuevo", ("Usado", -100000)], ...}
    ``variants``: [("SKU-1", {"condition": "Nuevo"}, 100000), ...]  (price None in modifiers mode)
    ``stock``: {"SKU-1": 3}; variants not listed get 5 units.
    """
    from django.utils.text import slugify

    from apps.catalog import services
    from apps.catalog.models import Product
    from apps.inventory.services import set_stock

    options = options if options is not None else {"condition": ["Nuevo"]}
    variants = (
        variants
        if variants is not None
        else [(f"SKU-{slugify(name)[:20].upper()}", {"condition": "Nuevo"}, 100000)]
    )
    fields.setdefault("slug", slugify(name))
    fields.setdefault("product_type", Product.Type.CONSOLE)
    fields.setdefault("category", category())
    platforms = fields.pop("platforms", [])
    product = Product.objects.create(name=name, pricing_mode=mode, base_price=base, **fields)
    product.platforms.set(cast(list, platforms))
    for code, labels in options.items():
        items = [
            (
                (attribute_value(code, item[0]), item[1])
                if isinstance(item, tuple)
                else attribute_value(code, item)
            )
            for item in labels
        ]
        services.add_option(product, attribute(code), items)
    store = store or make_store()
    for position, (sku, choice, price) in enumerate(variants):
        variant = services.create_variant(
            product,
            sku=sku,
            values=[attribute_value(code, label) for code, label in choice.items()],
            price=price,
            position=position,
        )
        set_stock(variant, store, (stock or {}).get(sku, 5))
    services.refresh_search_index(product)
    return product
