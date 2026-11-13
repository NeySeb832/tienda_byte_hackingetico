"""Rebuild the lake from the current bronze files plus a fresh OLTP extract."""

from typing import Any

from django.core.management.base import BaseCommand

from apps.analytics import pipeline


class Command(BaseCommand):
    help = "Extrae la BD transaccional y reconstruye las capas plata y oro."

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write(self.style.SUCCESS(f"Pipeline: {pipeline.run()}"))
