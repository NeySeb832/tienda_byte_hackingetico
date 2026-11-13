"""Take screenshots of the running app for the phase log (ADR-0010).

Screens are captured on desktop and mobile, in dark and light mode. Browser console
messages (for example CSP violations) are recorded in ``consola-navegador.txt`` so
the evidence also proves the strict CSP does not break the page.

Requirements: the app running (``docker compose up`` or ``runserver``) and Chromium::

    uv run playwright install chromium
    uv run python scripts/capturas.py --fase 1 --base-url http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import ConsoleMessage, Error, Page, ViewportSize, sync_playwright

ROOT = Path(__file__).resolve().parent.parent


def _recorders(
    log: list[str], label: str
) -> tuple[Callable[[ConsoleMessage], None], Callable[[Error], None]]:
    """Callbacks that append browser console messages and page errors to ``log``."""

    def on_console(message: ConsoleMessage) -> None:
        log.append(f"[{label}] {message.type}: {message.text}")

    def on_error(error: Error) -> None:
        log.append(f"[{label}] pageerror: {error}")

    return on_console, on_error


# (name, path, take mobile + light variants too)
PAGES: dict[int, list[tuple[str, str, bool]]] = {
    1: [
        ("inicio", "/", True),
        ("error-404", "/pagina-que-no-existe/", True),
        ("healthz", "/healthz", False),
    ],
}
VIEWPORTS: dict[str, ViewportSize] = {
    "escritorio": {"width": 1440, "height": 900},
    "movil": {"width": 390, "height": 844},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Capturas de pantalla por fase")
    parser.add_argument("--fase", type=int, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--paginas", default="", help="nombres separados por coma (p. ej. inicio)")
    args = parser.parse_args()

    wanted = {name.strip() for name in args.paginas.split(",") if name.strip()}
    pages = [page for page in PAGES.get(args.fase, []) if not wanted or page[0] in wanted]
    if not pages:
        print(f"No hay pantallas definidas para la Fase {args.fase}")
        return 1
    out_dir = ROOT / "docs" / "capturas" / f"fase-{args.fase:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    console_log: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for name, path, variants in pages:
            for viewport_name, viewport in VIEWPORTS.items():
                for scheme in ("dark", "light"):
                    if not variants and (viewport_name != "escritorio" or scheme != "dark"):
                        continue
                    context = browser.new_context(
                        viewport=viewport,
                        color_scheme=scheme,
                        locale="es-CO",
                        device_scale_factor=2 if viewport_name == "movil" else 1,
                    )
                    page = context.new_page()
                    label = f"{name}-{viewport_name}-{'oscuro' if scheme == 'dark' else 'claro'}"
                    on_console, on_error = _recorders(console_log, label)
                    page.on("console", on_console)
                    page.on("pageerror", on_error)
                    page.goto(f"{args.base_url}{path}", wait_until="networkidle")
                    load_lazy_images(page)
                    # JPEG keeps full-page shots with gradients small enough for the repo.
                    page.screenshot(
                        path=str(out_dir / f"{label}.jpg"), full_page=True, type="jpeg", quality=85
                    )
                    print(f"+ {label}.jpg")
                    context.close()
        browser.close()

    report = out_dir / f"consola-navegador{'-' + '-'.join(sorted(wanted)) if wanted else ''}.txt"
    report.write_text(console_report(console_log), encoding="utf-8")
    print(f"Consola del navegador: {len(console_log)} mensajes -> {report.relative_to(ROOT)}")
    return 0


def load_lazy_images(page: Page) -> None:
    """Scroll through the page so ``loading="lazy"`` images load before the shot."""
    height = int(page.evaluate("document.documentElement.scrollHeight"))
    for _ in range(0, height, 600):
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(120)
    page.wait_for_load_state("networkidle")
    page.mouse.wheel(0, -height)
    page.wait_for_timeout(400)


def console_report(log: list[str]) -> str:
    """Summarise browser console output, highlighting CSP violations."""
    csp = [line for line in log if "Content Security Policy" in line]
    expected = [line for line in log if line.startswith("[error-404") and "404" in line]
    lines = [
        f"Violaciones de CSP: {len(csp)}",
        f"Mensajes totales: {len(log)} (esperados: {len(expected)}, el propio 404 de error-404)",
        "",
        *log,
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
