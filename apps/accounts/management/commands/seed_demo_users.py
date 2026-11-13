"""Create one demo user per role (development/demo environments only)."""

from typing import Any

from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from apps.accounts import roles
from apps.accounts.models import Address, CustomerProfile, User
from apps.accounts.services import record_consent
from apps.core.models import City

DEMO_USERS = {
    roles.CUSTOMER: ("cliente@byte.test", "Camila", "Rojas"),
    roles.SELLER: ("vendedor@byte.test", "Andrés", "Gómez"),
    roles.WAREHOUSE: ("bodega@byte.test", "Luisa", "Martínez"),
    roles.TECHNICIAN: ("tecnico@byte.test", "Julián", "Herrera"),
    roles.MANAGER: ("gerente@byte.test", "Paola", "Castro"),
    roles.ANALYST: ("analista@byte.test", "Daniel", "Ríos"),
    roles.ADMIN: ("admin@byte.test", "Sofía", "Vargas"),
    roles.SUPERADMIN: ("superadmin@byte.test", "Mateo", "Suárez"),
}
# Public, development-only TOTP secret for demo staff (documented in the README).
DEMO_TOTP_SECRET = "JBSWY3DPEHPK3PXP"  # noqa: S105 - public dev-only demo value


class Command(BaseCommand):
    help = "Crea un usuario de demostración por rol (solo desarrollo)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--force", action="store_true", help="permitir con DEBUG=False (demo)")

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        if not settings.DEBUG and not options["force"]:
            raise CommandError("Solo para desarrollo. Usa --force en un entorno de demostración.")
        password = settings.BYTE_DEMO_PASSWORD
        if not password:
            raise CommandError("Define BYTE_DEMO_PASSWORD en el entorno.")
        call_command("setup_roles", verbosity=0)
        for role, (email, first, last) in DEMO_USERS.items():
            user, _ = User.objects.get_or_create(
                email=email, defaults={"first_name": first, "last_name": last}
            )
            user.first_name, user.last_name = first, last
            user.is_staff = role in roles.STAFF_ROLES
            user.is_superuser = role == roles.SUPERADMIN
            user.set_password(password)
            user.save()
            user.groups.set([Group.objects.get(name=role)])
            EmailAddress.objects.update_or_create(
                user=user, email=email, defaults={"verified": True, "primary": True}
            )
            if (
                user.is_staff
                and not Authenticator.objects.filter(
                    user=user, type=Authenticator.Type.TOTP
                ).exists()
            ):
                Authenticator.objects.create(
                    user=user, type=Authenticator.Type.TOTP, data={"secret": DEMO_TOTP_SECRET}
                )
            if role == roles.CUSTOMER:
                self._customer_extras(user)
            self.stdout.write(f"{role}: {email}")
        self.stdout.write(self.style.SUCCESS("Usuarios de demostración listos."))

    @staticmethod
    def _customer_extras(user: User) -> None:
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        profile.document_type, profile.document_number, profile.phone = (
            "CC",
            "1020304050",
            "3001234567",
        )
        profile.save()
        if not user.consents.exists():
            record_consent(user)
        if not user.addresses.exists():
            Address.objects.create(
                user=user,
                label="Casa",
                recipient_name="Camila Rojas",
                phone="3001234567",
                city=City.objects.get(code="05001"),
                line1="Carrera 43A # 1-50",
                line2="Apto 501",
                neighborhood="El Poblado",
                is_default=True,
            )
            Address.objects.create(
                user=user,
                label="Oficina",
                recipient_name="Camila Rojas",
                phone="3109876543",
                city=City.objects.get(code="11001"),
                line1="Calle 93 # 13-24",
                neighborhood="Chicó",
            )
