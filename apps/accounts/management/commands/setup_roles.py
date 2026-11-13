"""Create (or update) the groups of every role with exactly their permissions."""

from typing import Any

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.roles import ALL_ROLES, ROLE_PERMISSIONS


def resolve_permission(dotted: str) -> Permission:
    app_label, _, codename = dotted.partition(".")
    try:
        return Permission.objects.get(content_type__app_label=app_label, codename=codename)
    except Permission.DoesNotExist as exc:
        raise CommandError(f"Permiso inexistente: {dotted}") from exc


class Command(BaseCommand):
    help = "Crea los grupos de roles y sus permisos (idempotente)."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        for role in ALL_ROLES:
            group, created = Group.objects.get_or_create(name=role)
            permissions = [resolve_permission(p) for p in sorted(ROLE_PERMISSIONS[role])]
            group.permissions.set(permissions)
            state = "creado" if created else "actualizado"
            self.stdout.write(f"{role}: {state} ({len(permissions)} permisos)")
        self.stdout.write(self.style.SUCCESS("Roles configurados."))
