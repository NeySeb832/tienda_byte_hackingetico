"""Build the BI lake when the gold layer is missing (container start-up on Render)."""

from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.analytics import bi


class Command(BaseCommand):
    help = "Construye el data lake si falta la capa oro (no hace nada si ya existe)."

    def handle(self, *args: Any, **options: Any) -> None:
        if bi.gold_ready():
            self.stdout.write("Data lake listo.")
            return
        try:
            call_command("seed_bigdata", "--dias", "365", stdout=self.stdout)
        except Exception as exc:
            self.stderr.write(f"No se pudo construir el data lake: {exc}")
