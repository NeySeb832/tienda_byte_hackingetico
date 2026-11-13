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
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

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


# (name, path, take mobile + light variants too[, demo user email])
PAGES: dict[int, list[tuple[str, ...] | tuple[str, str, bool] | tuple[str, str, bool, str]]] = {
    1: [
        ("inicio", "/", True),
        ("error-404", "/pagina-que-no-existe/", True),
        ("healthz", "/healthz", False),
    ],
    2: [
        ("login", "/cuenta/login/", True),
        ("registro", "/cuenta/signup/", False),
        ("politica-datos", "/legal/privacidad/", False),
        ("mi-cuenta", "/cuenta/", True, "cliente@byte.test"),
        ("direcciones", "/cuenta/direcciones/", False, "cliente@byte.test"),
        ("privacidad", "/cuenta/privacidad/", False, "cliente@byte.test"),
        ("sesiones", "/cuenta/sessions/", False, "cliente@byte.test"),
        ("panel-resumen", "/panel/", True, "superadmin@byte.test"),
        ("panel-personal", "/panel/personal/", False, "superadmin@byte.test"),
        ("panel-auditoria", "/panel/auditoria/", False, "superadmin@byte.test"),
        ("panel-seguridad", "/panel/seguridad/", False, "superadmin@byte.test"),
        ("panel-vendedor", "/panel/", False, "vendedor@byte.test"),
        ("403-vendedor-en-auditoria", "/panel/auditoria/", False, "vendedor@byte.test"),
    ],
    3: [
        ("inicio", "/", True),
        ("catalogo", "/catalogo/", True),
        ("categoria-playstation", "/categoria/playstation/", False),
        ("busqueda-con-error-de-tipeo", "/buscar/?q=plaistation", False),
        (
            "filtros-nintendo-usados",
            "/catalogo/?marca=nintendo&condicion=usado&orden=precio-asc",
            False,
        ),
        ("ficha-ps5-slim", "/producto/playstation-5-slim/", True),
        ("ficha-variante-agotada", "/producto/playstation-5-slim/?sku=PS5S-DIG-30ANIV-N", False),
        ("ficha-precio-por-modificadores", "/producto/xbox-series-s/?sku=XSS-1TB-N", False),
        ("ficha-juego", "/producto/astro-bot/", False),
        ("ficha-sin-foto", "/producto/playstation-5-pro/", False),
        (
            "comparador",
            "/comparar/",
            True,
            "comparar:playstation-5-slim,xbox-series-x,nintendo-switch-2",
        ),
    ],
}


def session_cookie(email: str) -> dict[str, str]:
    """Create a Django session for a demo user (development DB) and return the cookie."""
    import os

    import django

    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    django.setup()
    from django.conf import settings
    from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
    from django.contrib.sessions.backends.cached_db import SessionStore

    from apps.accounts.models import User

    session = SessionStore()
    if email.startswith("comparar:"):
        # Anonymous visitor with products already in the comparator.
        from apps.catalog.models import Product
        from apps.catalog.services import COMPARE_SESSION_KEY

        slugs = email.split(":", 1)[1].split(",")
        products = {p.slug: str(p.public_id) for p in Product.objects.filter(slug__in=slugs)}
        session[COMPARE_SESSION_KEY] = [products[slug] for slug in slugs if slug in products]
        session.save()
        return {"name": settings.SESSION_COOKIE_NAME, "value": session.session_key or ""}
    user = User.objects.get(email=email)
    session[SESSION_KEY] = str(user.pk)
    session[BACKEND_SESSION_KEY] = "allauth.account.auth_backends.AuthenticationBackend"
    session[HASH_SESSION_KEY] = user.get_session_auth_hash()
    session.save()
    return {"name": settings.SESSION_COOKIE_NAME, "value": session.session_key or ""}


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

    # Django's ORM must not run inside Playwright's event loop: create sessions first.
    cookies = {str(spec[3]): session_cookie(str(spec[3])) for spec in pages if len(spec) > 3}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for page_spec in pages:
            name, path, variants = page_spec[0], page_spec[1], bool(page_spec[2])
            as_user = page_spec[3] if len(page_spec) > 3 else None
            cookie = cookies.get(str(as_user)) if as_user else None
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
                    if cookie:
                        context.add_cookies(
                            [
                                {
                                    "name": cookie["name"],
                                    "value": cookie["value"],
                                    "url": args.base_url,
                                }
                            ]
                        )
                    page = context.new_page()
                    label = f"{name}-{viewport_name}-{'oscuro' if scheme == 'dark' else 'claro'}"
                    on_console, on_error = _recorders(console_log, label)
                    page.on("console", on_console)
                    page.on("pageerror", on_error)
                    page.goto(f"{args.base_url}{path}", wait_until="load")
                    settle(page)
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


def settle(page: Page) -> None:
    """Wait briefly for the network to go idle (third-party widgets may never be idle)."""
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PlaywrightTimeoutError:
        page.wait_for_timeout(500)


def load_lazy_images(page: Page) -> None:
    """Scroll through the page so ``loading="lazy"`` images load before the shot."""
    height = int(page.evaluate("document.documentElement.scrollHeight"))
    for _ in range(0, height, 600):
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(120)
    settle(page)
    page.mouse.wheel(0, -height)
    page.wait_for_timeout(400)


def console_report(log: list[str]) -> str:
    """Summarise browser console output, highlighting CSP violations."""
    csp = [line for line in log if "Content Security Policy" in line]
    expected = [
        line
        for line in log
        if ("404" in line and line.startswith("[error-404")) or ("403" in line and "[403-" in line)
    ]
    lines = [
        f"Violaciones de CSP: {len(csp)}",
        f"Mensajes totales: {len(log)} (esperados: {len(expected)}, el propio 404 de error-404)",
        "",
        *log,
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
