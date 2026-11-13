"""Verify the integrity of the hash-chained audit trail."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.audit.models import AuditLog
from apps.audit.services import verify_chain


class Command(BaseCommand):
    help = "Verifica que la bitácora de auditoría no haya sido alterada."

    def handle(self, *args: Any, **options: Any) -> None:
        broken = verify_chain()
        if broken is not None:
            raise CommandError(f"Cadena de auditoría rota en el registro {broken}.")
        self.stdout.write(
            self.style.SUCCESS(f"Cadena íntegra: {AuditLog.objects.count()} registros.")
        )
