"""End-to-end check of a real purchase through the browser (Playwright).

    uv run python scripts/e2e.py --base-url http://127.0.0.1:8001

Flow: home → search → product → add to cart as a guest → log in (cart is merged) →
checkout (store pickup) → sandbox payment approved → order paid → invoice PDF.
Uses the demo customer (``cliente@byte.test``) and ``BYTE_DEMO_PASSWORD`` from the environment
or ``.env``. Screenshots go to ``docs/capturas/fase-09/e2e-*.jpg``. Exit code 1 on any failure.
"""

import argparse
import os
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "capturas" / "fase-09"


def demo_password() -> str:
    value = os.environ.get("BYTE_DEMO_PASSWORD", "")
    env_file = ROOT / ".env"
    if not value and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("BYTE_DEMO_PASSWORD="):
                value = line.split("=", 1)[1].strip()
    if not value:
        raise SystemExit("Define BYTE_DEMO_PASSWORD.")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Compra de extremo a extremo")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    OUT.mkdir(parents=True, exist_ok=True)
    steps: list[str] = []
    errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1366, "height": 900}, locale="es-CO")
        page.on("pageerror", lambda error: errors.append(str(error)))

        def shot(name: str) -> None:
            page.screenshot(path=str(OUT / f"e2e-{name}.jpg"), type="jpeg", quality=80)
            steps.append(name)

        page.goto(f"{base}/")
        expect(page.locator("h1")).to_be_visible()
        shot("01-inicio")

        page.goto(f"{base}/buscar/?q=dualsense")
        page.get_by_role("link", name="Control inalámbrico DualSense").first.click()
        expect(page.locator("h1")).to_contain_text("DualSense")
        shot("02-ficha")

        page.get_by_role("button", name="Agregar al carrito").click()
        expect(page).to_have_url(f"{base}/carrito/")
        expect(page.locator(".cart-line")).to_have_count(1)
        shot("03-carrito-invitado")

        page.goto(f"{base}/cuenta/login/?next=/carrito/")
        page.get_by_label("Correo electrónico").fill("cliente@byte.test")
        page.get_by_label("Contraseña").fill(demo_password())
        page.get_by_role("button", name="Iniciar sesión").click()
        expect(page).to_have_url(f"{base}/carrito/")
        # The guest cart was merged into the customer's cart; keep only the DualSense.
        while page.locator(".cart-line").filter(has_not_text="DualSense").count():
            page.locator(".cart-line").filter(has_not_text="DualSense").first.get_by_role(
                "button", name="Quitar"
            ).click()
        expect(page.locator(".cart-line")).to_have_count(1)
        page.get_by_role("link", name="Continuar con el pago").click()
        expect(page).to_have_url(f"{base}/checkout/")
        expect(page.get_by_text("Control inalámbrico DualSense").first).to_be_visible()
        shot("04-checkout")

        page.get_by_label("Recoger en tienda").check()
        page.locator("#id_acepto").check()
        page.get_by_role("button", name="Ir a pagar").click()
        if "/pagos/" not in page.url:
            alerts = page.locator(".alert-error, .form-error").all_inner_texts()
            shot("error-checkout")
            raise SystemExit(f"El checkout no avanzó ({page.url}): {alerts}")
        expect(page.get_by_role("heading", name="Pagar")).to_be_visible()
        shot("05-pasarela")

        page.get_by_role("button", name="Simular pago aprobado").click()
        expect(page.get_by_role("heading", name="¡Pago aprobado!")).to_be_visible()
        shot("06-pago-aprobado")

        page.get_by_role("link", name="Ver el detalle del pedido").click()
        expect(page.get_by_text("Pagado").first).to_be_visible()
        shot("07-pedido")
        href = page.get_by_role("link", name="Descargar factura (PDF)").get_attribute("href") or ""
        response = page.request.get(base + href)
        if response.headers.get(
            "content-type"
        ) != "application/pdf" or not response.body().startswith(b"%PDF"):
            errors.append("La factura no es un PDF válido")
        browser.close()

    for step in steps:
        print(f"OK  {step}")
    for error in errors:
        print(f"ERROR {error}")
    print(f"{len(steps)} pasos, {len(errors)} errores")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
