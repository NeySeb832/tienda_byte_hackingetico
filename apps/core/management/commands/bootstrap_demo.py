"""Load the full demo in one step: roles, catalogue, demo users and BI history (idempotent).

Usage (Render shell or local): ``python manage.py bootstrap_demo [--dias 365]``.
Demo users need ``BYTE_DEMO_PASSWORD``; without it they are skipped.
"""

from typing import Any

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Carga la demo completa: roles, catálogo, usuarios demo e histórico de BI."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--dias", type=int, default=365, help="días de histórico sintético")
        parser.add_argument("--sin-bi", action="store_true", help="no generar el data lake")

    def handle(self, *args: Any, **options: Any) -> None:
        call_command("setup_roles", stdout=self.stdout)
        call_command("seed_demo", stdout=self.stdout)
        if settings.BYTE_DEMO_PASSWORD:
            call_command("seed_demo_users", "--force", stdout=self.stdout)
        else:
            self.stdout.write(
                self.style.WARNING("Sin BYTE_DEMO_PASSWORD: no se crean usuarios demo.")
            )
        if not options["sin_bi"]:
            call_command("seed_bigdata", "--dias", str(options["dias"]), stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("Demo lista."))
