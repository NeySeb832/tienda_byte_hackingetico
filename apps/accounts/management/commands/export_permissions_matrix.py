"""Generate docs/matriz-permisos.md from the role definitions in code."""

from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.accounts.management.commands.setup_roles import resolve_permission
from apps.accounts.roles import ALL_ROLES, ROLE_DESCRIPTIONS, ROLE_PERMISSIONS

OUTPUT = Path(settings.BASE_DIR) / "docs" / "matriz-permisos.md"


def render_matrix() -> str:
    permissions = sorted({p for perms in ROLE_PERMISSIONS.values() for p in perms})
    lines = [
        "# Matriz de roles y permisos",
        "",
        "> Archivo generado con `python manage.py export_permissions_matrix` a partir de",
        "> `apps/accounts/roles.py`. No se edita a mano; el CI verifica que esté al día.",
        "",
        "## Roles",
        "",
        "| Rol | Descripción |",
        "|-----|-------------|",
        *[f"| {role} | {ROLE_DESCRIPTIONS[role]} |" for role in ALL_ROLES],
        "",
        "## Permisos por rol",
        "",
        "| Permiso | " + " | ".join(ALL_ROLES) + " |",
        "|---------|" + "|".join(":-:" for _ in ALL_ROLES) + "|",
    ]
    for dotted in permissions:
        name = resolve_permission(dotted).name
        marks = " | ".join("✅" if dotted in ROLE_PERMISSIONS[role] else "—" for role in ALL_ROLES)
        lines.append(f"| {name} (`{dotted}`) | {marks} |")
    lines += [
        "",
        "Además de los permisos, el código aplica estas reglas:",
        "- **Alcance por sede:** el personal solo ve sus sedes asignadas; administradores y superadmins ven todas.",
        "- **Datos propios:** un cliente solo accede a sus direcciones, pedidos, tickets y retomas (404 en otro caso).",
        "- **Separación de funciones:** nadie cambia su propio rol, y solo un superadmin gestiona superadmins.",
        "- **MFA obligatorio:** el personal no entra al panel sin la verificación en dos pasos activa.",
        "",
    ]
    return "\n".join(lines)


class Command(BaseCommand):
    help = "Genera docs/matriz-permisos.md desde el código."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--check", action="store_true", help="falla si el archivo está desactualizado"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        content = render_matrix()
        if options["check"]:
            current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
            if current != content:
                raise CommandError("docs/matriz-permisos.md está desactualizada.")
            self.stdout.write(self.style.SUCCESS("Matriz de permisos al día."))
            return
        OUTPUT.write_text(content, encoding="utf-8", newline="\n")
        self.stdout.write(self.style.SUCCESS(f"Escrita {OUTPUT.relative_to(settings.BASE_DIR)}"))
