"""Run quality and security checks and save their output as evidence (ADR-0010).

For every check the raw output is saved as ``docs/capturas/fase-NN/<slug>.txt`` and
rendered as a terminal-style image ``<slug>.svg`` (rich). A summary table is saved
as ``00-resumen.svg``.

Usage::

    uv run python scripts/evidencia.py --fase 1
    uv run python scripts/evidencia.py --fase 1 --solo pytest,ruff
"""

from __future__ import annotations

import argparse
import base64
import io
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
# Pinned by digest (1.185.0 was still inside the 7-day quarantine, ADR-0005).
SEMGREP_IMAGE = os.environ.get(
    "SEMGREP_IMAGE",
    "semgrep/semgrep:1.184.0@sha256:cc1b68266f267878b39739373ea9985b9a78e5d64497dd875c8de100b22695ed",
)
TRIVY_IMAGE = (
    "aquasec/trivy:0.76.2@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb"
)
RUNTIME_IMAGE = os.environ.get("BYTE_RUNTIME_IMAGE", "byte:local")  # docker build --target runtime


@dataclass(frozen=True)
class Check:
    slug: str
    title: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)


def prod_env() -> dict[str, str]:
    """Throw-away production-like environment for ``check --deploy``."""
    return {
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
        "DJANGO_ALLOWED_HOSTS": "byte.example.com",
        "DJANGO_ADMIN_URL": "k7Qp2-Xn9LwZr4Tb/",
        "DATABASE_URL": "postgres://byte:unused@localhost:5432/byte",
        "REDIS_URL": "redis://localhost:6379/0",
        "BYTE_FIELD_ENCRYPTION_KEYS": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "BYTE_BLIND_INDEX_KEY": secrets.token_urlsafe(32),
        "TURNSTILE_SITE_KEY": "evidence-placeholder-site-key",
        "TURNSTILE_SECRET_KEY": "evidence-placeholder-secret-key",
        "BYTE_PAYMENT_GATEWAY": "wompi",
        "WOMPI_PUBLIC_KEY": "pub_test_evidence",
        "WOMPI_INTEGRITY_SECRET": "test_integrity_evidence",
        "WOMPI_EVENTS_SECRET": "test_events_evidence",
    }


HEADERS_SNIPPET = (
    "import os, django;"
    "os.environ['DJANGO_SETTINGS_MODULE']='config.settings.test';"
    "django.setup();"
    "from django.test import Client;"
    "r = Client().get('/');"
    "print('GET / ->', r.status_code);"
    "[print(f'{h}: {r[h]}') for h in ("
    "'Content-Security-Policy','X-Frame-Options','X-Content-Type-Options','Referrer-Policy',"
    "'Cross-Origin-Opener-Policy','Cross-Origin-Resource-Policy','Permissions-Policy','X-Request-ID')]"
)


def build_checks() -> list[Check]:
    checks = [
        Check(
            "01-pytest",
            "Tests y cobertura (pytest)",
            [
                PY,
                "-m",
                "pytest",
                "--cov",
                "--cov-report=term",
                "-p",
                "no:cacheprovider",
                "--color=yes",
            ],
        ),
        Check("02-ruff", "Linter (ruff)", [PY, "-m", "ruff", "check", "."]),
        Check("03-black", "Formato (black --check)", [PY, "-m", "black", "--check", "."]),
        Check("04-mypy", "Tipos (mypy)", [PY, "-m", "mypy", "."]),
        Check(
            "05-bandit",
            "SAST (bandit, severidad media o alta)",
            [PY, "-m", "bandit", "-c", "pyproject.toml", "-r", "apps", "config", "scripts", "-ll"],
        ),
        Check(
            "06-pip-audit",
            "Dependencias con vulnerabilidades conocidas (pip-audit)",
            [
                PY,
                "-m",
                "pip_audit",
                "--strict",
                "--disable-pip",
                "--require-hashes",
                "-r",
                "requirements/prod.txt",
            ],
        ),
        Check(
            "07-check-deploy",
            "Configuración de producción (manage.py check --deploy)",
            [PY, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
            env=prod_env(),
        ),
        Check("08-cabeceras", "Cabeceras de seguridad de GET /", [PY, "-c", HEADERS_SNIPPET]),
        Check(
            "12-matriz-permisos",
            "Matriz de permisos generada desde el código",
            [PY, "manage.py", "export_permissions_matrix", "--check"],
            env={"DJANGO_SETTINGS_MODULE": "config.settings.test"},
        ),
        Check(
            "13-cadena-auditoria",
            "Integridad de la cadena de auditoría (BD de desarrollo)",
            [PY, "manage.py", "verify_audit_chain"],
        ),
        Check(
            "09-vendor",
            "Integridad de librerías JS y binario de Tailwind",
            [PY, "scripts/vendor_assets.py", "--check"],
        ),
    ]
    semgrep = shutil.which("semgrep")
    if semgrep:
        checks.append(
            Check(
                "10-semgrep",
                "SAST (semgrep p/django + p/python)",
                [
                    semgrep,
                    "scan",
                    "--config",
                    "p/django",
                    "--config",
                    "p/python",
                    "--error",
                    "--metrics=off",
                    "--exclude",
                    "tests",
                ],
            )
        )
    elif SEMGREP_IMAGE and shutil.which("docker"):
        checks.append(
            Check(
                "10-semgrep",
                "SAST (semgrep p/django + p/python, en Docker)",
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{ROOT}:/src",
                    "-w",
                    "/src",
                    SEMGREP_IMAGE,
                    "semgrep",
                    "scan",
                    "--config",
                    "p/django",
                    "--config",
                    "p/python",
                    "--error",
                    "--metrics=off",
                    "--exclude",
                    "tests",
                ],
            )
        )
    if shutil.which("docker"):
        # Same pinned scanner and policy as CI: fail on fixable HIGH/CRITICAL.
        checks.append(
            Check(
                "11-trivy",
                f"Vulnerabilidades de la imagen {RUNTIME_IMAGE} (Trivy)",
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    "//var/run/docker.sock:/var/run/docker.sock",
                    TRIVY_IMAGE,
                    "image",
                    "--severity",
                    "HIGH,CRITICAL",
                    "--ignore-unfixed",
                    "--exit-code",
                    "1",
                    "--no-progress",
                    RUNTIME_IMAGE,
                ],
            )
        )
    return checks


def run(check: Check) -> tuple[int, str, float]:
    env = {
        **os.environ,
        "FORCE_COLOR": "1",
        "PY_COLORS": "1",
        "CLICOLOR_FORCE": "1",
        # Child Python processes write UTF-8 even on Windows consoles (cp1252).
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        **check.env,
    }
    start = time.perf_counter()
    result = subprocess.run(
        check.command,
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode, (result.stdout + result.stderr).rstrip(), time.perf_counter() - start


RESULT_RE = re.compile(r"\[(OK|FALLÓ[^\]]*?) en ([0-9.]+) s\]\s*$")


def save(out_dir: Path, check: Check, code: int, output: str, seconds: float) -> None:
    status = "OK" if code == 0 else f"FALLÓ (código {code})"
    shown = " ".join(Path(part).name if i == 0 else part for i, part in enumerate(check.command))
    (out_dir / f"{check.slug}.txt").write_text(
        f"$ {shown}\n\n{ANSI_RE.sub('', output)}\n\n[{status} en {seconds:.1f} s]\n",
        encoding="utf-8",
        newline="\n",
    )
    console = Console(record=True, width=118, file=io.StringIO(), force_terminal=True)
    console.print(Text(f"$ {shown}", style="bold cyan"))
    console.print(Text.from_ansi(output or "(sin salida)"))
    console.print(
        Panel(f"{status} · {seconds:.1f} s", style="green" if code == 0 else "red", expand=False)
    )
    console.save_svg(str(out_dir / f"{check.slug}.svg"), title=f"Byte · {check.title}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(
            encoding="utf-8", errors="replace"
        )  # Windows consoles default to cp1252
    parser = argparse.ArgumentParser(description="Evidencias de calidad y seguridad por fase")
    parser.add_argument("--fase", type=int, required=True)
    parser.add_argument("--solo", default="", help="slugs separados por coma (p. ej. pytest,ruff)")
    args = parser.parse_args()

    out_dir = ROOT / "docs" / "capturas" / f"fase-{args.fase:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    wanted = {name.strip() for name in args.solo.split(",") if name.strip()}
    checks = [c for c in build_checks() if not wanted or c.slug.split("-", 1)[1] in wanted]

    summary = Table(title=f"Byte · Evidencias de la Fase {args.fase}", show_lines=False)
    summary.add_column("Verificación")
    summary.add_column("Resultado", justify="center")
    summary.add_column("Tiempo", justify="right")
    failures = 0
    screen = Console()
    for check in checks:
        screen.print(f"[bold]→ {check.title}[/bold]")
        code, output, seconds = run(check)
        save(out_dir, check, code, output, seconds)
        failures += code != 0
    # The summary covers every check of the phase: with --solo, the others keep their last result.
    for check in build_checks():
        saved = out_dir / f"{check.slug}.txt"
        if not saved.exists():
            continue
        match = RESULT_RE.search(saved.read_text(encoding="utf-8"))
        if match is None:
            continue
        ok = match.group(1) == "OK"
        summary.add_row(
            check.title,
            "[green]OK[/green]" if ok else "[red]FALLÓ[/red]",
            f"{match.group(2)} s",
        )

    recorder = Console(record=True, width=100, file=io.StringIO(), force_terminal=True)
    recorder.print(summary)
    recorder.save_svg(str(out_dir / "00-resumen.svg"), title=f"Byte · Resumen Fase {args.fase}")
    screen.print(summary)
    screen.print(f"Evidencias en {out_dir.relative_to(ROOT)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
