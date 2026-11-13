"""PostgreSQL backup and restore for Byte (custom format, compressed).

    uv run python scripts/backup.py respaldar                 # -> backups/byte-AAAAMMDD-HHMMSS.dump
    uv run python scripts/backup.py restaurar backups/x.dump  # pide confirmación escrita
    uv run python scripts/backup.py verificar backups/x.dump  # lista el contenido sin restaurar

Reads DATABASE_URL from the environment (or .env). Uses the local pg_dump/pg_restore, or the
PostgreSQL container of docker compose when they are not installed. After a restore it runs
``verify_audit_chain`` so a tampered or partial dump is detected.
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
BACKUPS = ROOT / "backups"


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    env_file = ROOT / ".env"
    if not url and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
    if not url:
        raise SystemExit("DATABASE_URL no está definido.")
    return url


def tool(name: str, url: str) -> tuple[list[str], dict[str, str]]:
    """Command prefix and environment (password via PGPASSWORD, never on the command line)."""
    parsed = urlparse(url)
    env = {**os.environ, "PGPASSWORD": parsed.password or ""}
    args = [
        "-h",
        parsed.hostname or "localhost",
        "-p",
        str(parsed.port or 5432),
        "-U",
        parsed.username or "",
        "-d",
        parsed.path.lstrip("/"),
    ]
    if shutil.which(name):
        return [name, *args], env
    # Fallback: run inside the compose database container (talks to its own localhost).
    container_args = ["-U", parsed.username or "", "-d", parsed.path.lstrip("/")]
    return [
        "docker",
        "compose",
        "exec",
        "-T",
        "-e",
        f"PGPASSWORD={parsed.password or ''}",
        "db",
        name,
        *container_args,
    ], env


def backup(url: str) -> Path:
    BACKUPS.mkdir(exist_ok=True)
    target = BACKUPS / f"byte-{datetime.now(UTC):%Y%m%d-%H%M%S}.dump"
    command, env = tool("pg_dump", url)
    with target.open("wb") as handle:
        subprocess.run(
            [*command, "--format=custom", "--no-owner", "--no-privileges"],
            check=True,
            stdout=handle,
            env=env,
        )
    print(f"Respaldo: {target.relative_to(ROOT)} ({target.stat().st_size / 1024:.0f} KB)")
    return target


def verify(dump: Path) -> None:
    """List the dump contents (no database connection needed)."""
    if shutil.which("pg_restore"):
        listing = subprocess.run(
            ["pg_restore", "--list", str(dump)], capture_output=True, check=True
        )
    else:
        listing = subprocess.run(
            ["docker", "compose", "exec", "-T", "db", "pg_restore", "--list"],
            input=dump.read_bytes(),
            capture_output=True,
            check=True,
        )
    tables = [
        line
        for line in listing.stdout.decode(errors="replace").splitlines()
        if " TABLE DATA " in line
    ]
    print(f"{dump.name}: {len(tables)} tablas con datos")


def restore(dump: Path, url: str) -> None:
    answer = input(
        f"Esto reemplaza la base de datos {urlparse(url).path.lstrip('/')}. Escribe RESTAURAR: "
    )
    if answer.strip() != "RESTAURAR":
        raise SystemExit("Cancelado.")
    command, env = tool("pg_restore", url)
    subprocess.run(
        [*command, "--clean", "--if-exists", "--no-owner", "--single-transaction"],
        input=dump.read_bytes(),
        check=True,
        env=env,
    )
    subprocess.run([sys.executable, "manage.py", "verify_audit_chain"], cwd=ROOT, check=True)
    print("Restauración completa y cadena de auditoría íntegra.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Respaldo y restauración de PostgreSQL")
    sub = parser.add_subparsers(dest="accion", required=True)
    sub.add_parser("respaldar")
    for name in ("restaurar", "verificar"):
        sub.add_parser(name).add_argument("archivo", type=Path)
    args = parser.parse_args()
    url = database_url()
    if args.accion == "respaldar":
        backup(url)
    elif args.accion == "verificar":
        verify(args.archivo)
    else:
        restore(args.archivo, url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
