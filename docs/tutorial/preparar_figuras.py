"""Prepara las figuras del tutorial a partir de las evidencias de docs/capturas/.

Recorta las capturas de página completa a la parte superior (lo que se ve en pantalla),
las reduce a un ancho apto para impresión y convierte a PNG los resúmenes de terminal en SVG.

Uso:  uv run python docs/tutorial/preparar_figuras.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
CAPTURAS = ROOT / "docs" / "capturas"
OUT = Path(__file__).resolve().parent / "figuras"

# nombre de salida -> (captura de origen, alto máximo en px de la captura original o None)
JPG = {
    "f01-inicio": ("fase-01/inicio-escritorio-oscuro.jpg", 1150),
    "f01-inicio-movil": ("fase-01/inicio-movil-claro.jpg", 1500),
    "f02-login": ("fase-02/login-escritorio-oscuro.jpg", 900),
    "f02-403": ("fase-02/403-vendedor-en-auditoria-escritorio-oscuro.jpg", 900),
    "f03-busqueda": ("fase-03/busqueda-con-error-de-tipeo-escritorio-oscuro.jpg", 1050),
    "f03-ficha": ("fase-03/ficha-ps5-slim-escritorio-oscuro.jpg", 1100),
    "f04-checkout": ("fase-04/checkout-escritorio-oscuro.jpg", 1150),
    "f04-pasarela": ("fase-04/pasarela-de-pruebas-escritorio-oscuro.jpg", 900),
    "f05-ajustes": ("fase-05/panel-ajustes-bodega-no-aprueba-escritorio-oscuro.jpg", 950),
    "f05-pos": ("fase-05/panel-pos-escritorio-claro.jpg", 900),
    "f06-retomas": ("fase-06/cuenta-retomas-escritorio-oscuro.jpg", 1050),
    "f06-servicio": ("fase-06/panel-servicio-tecnico-escritorio-oscuro.jpg", 950),
    "f07-bi": ("fase-07/panel-inteligencia-de-negocio-escritorio-oscuro.jpg", 1350),
    "f09-e2e-pago": ("fase-09/e2e-06-pago-aprobado.jpg", None),
    "f09-e2e-pedido": ("fase-09/e2e-07-pedido.jpg", None),
}
SVG = {
    "f01-resumen": "fase-01/00-resumen.svg",
    "f02-semgrep": "fase-02/10-semgrep.svg",
    "f08-resumen": "fase-08/00-resumen.svg",
}
LIVE = {"f09-render-en-vivo": "https://byte-web-v9h4.onrender.com/"}
MAX_W = 1400


def crop_jpg(name: str, src: str, max_h: int | None) -> None:
    with Image.open(CAPTURAS / src) as original:
        im: Image.Image = original.convert("RGB")
        if max_h and im.height > max_h:
            im = im.crop((0, 0, im.width, max_h))
        if im.width > MAX_W:
            size = (MAX_W, round(im.height * MAX_W / im.width))
            im = im.resize(size, Image.Resampling.LANCZOS)
        im.save(OUT / f"{name}.jpg", quality=85, optimize=True, progressive=True)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for name, (src, max_h) in JPG.items():
        crop_jpg(name, src, max_h)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(device_scale_factor=2)
        for name, src in SVG.items():
            svg = (CAPTURAS / src).resolve()
            page.goto(svg.as_uri())
            page.locator("svg").first.screenshot(path=str(OUT / f"{name}.png"))
            trim_white(OUT / f"{name}.png")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        for name, url in LIVE.items():
            page.goto(url, wait_until="load")
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT / f"{name}.png"))
            crop_jpg_from_png(name)
        browser.close()
    print("figuras:", sorted(p.name for p in OUT.iterdir()))  # noqa: T201 - CLI script


def trim_white(png: Path, pad: int = 12) -> None:
    """Quita el margen blanco alrededor de la ventana de terminal del SVG."""
    with Image.open(png) as im:
        rgb = im.convert("RGB")
        mask = rgb.point(lambda v: 255 if v < 245 else 0).convert("L")
        box = mask.getbbox()
        if box:
            left, top, right, bottom = box
            rgb = rgb.crop(
                (
                    max(left - pad, 0),
                    max(top - pad, 0),
                    min(right + pad, rgb.width),
                    min(bottom + pad, rgb.height),
                )
            )
        rgb.save(png)


def crop_jpg_from_png(name: str) -> None:
    png = OUT / f"{name}.png"
    with Image.open(png) as im:
        im.convert("RGB").save(OUT / f"{name}.jpg", quality=85, optimize=True)
    png.unlink()


if __name__ == "__main__":
    main()
