"""factory_boy factories shared by the test suite."""

import factory

from apps.accounts.models import User

TEST_PASSWORD = "ClaveDePrueba-2026!"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"usuario{n}@example.com")
    first_name = factory.Faker("first_name", locale="es_CO")
    last_name = factory.Faker("last_name", locale="es_CO")
    password = factory.django.Password(TEST_PASSWORD)
