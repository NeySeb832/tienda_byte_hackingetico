"""factory_boy factories and helpers shared by the test suite."""

from typing import cast

import factory
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from django.contrib.auth.models import Group

from apps.accounts import roles
from apps.accounts.models import User
from apps.core.models import City
from apps.inventory.models import Store

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
