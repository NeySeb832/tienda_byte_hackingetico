"""Fetch, verify and optimise the product photos used by the storefront.

Photos come from Wikimedia Commons and must carry a free licence (public domain,
CC0, CC BY or CC BY-SA). The manifest ``assets/img/productos.json`` pins every
source file by its SHA-256; this script:

1. ``--bloquear``: queries the Commons API for URL, author and licence, downloads
   the original over HTTPS and records its SHA-256 (run once when adding a photo).
   Commons only publishes SHA-1, which is not collision resistant, so it is kept
   as informative metadata and never used for verification.
2. default: downloads each original, verifies the pinned SHA-256, rejects non-free
   licences, optionally removes a pure white studio background, trims, resizes
   and writes an EXIF-free WebP to ``static/img/productos/<slug>.webp``.
3. writes ``apps/cms/data/imagenes.json`` (dimensions + attribution) used by the
   templates and the "Créditos de imágenes" page.

Usage::

    uv run python scripts/product_images.py --bloquear
    uv run python scripts/product_images.py
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "assets" / "img" / "productos.json"
OUTPUT_DIR = ROOT / "static" / "img" / "productos"
CREDITS = ROOT / "apps" / "cms" / "data" / "imagenes.json"
API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "byte-storefront-assets/1.0 (educational project)"}
ALLOWED_LICENSES = {
    "Public domain",
    "CC0",
    "CC BY 2.0",
    "CC BY 3.0",
    "CC BY 4.0",
    "CC BY-SA 2.0",
    "CC BY-SA 3.0",
    "CC BY-SA 4.0",
}
WEBP_QUALITY = 82
THUMB_WIDTH = 1280  # standard Wikimedia thumbnail size
CACHE_DIR = ROOT / ".cache" / "product-images"  # downloads keyed by SHA-256 (git-ignored)


def cached_download(url: str, expected_sha256: str | None = None) -> bytes:
    """Download once; later runs read the verified copy from the local cache."""
    if expected_sha256:
        cached = CACHE_DIR / expected_sha256
        if cached.exists() and hashlib.sha256(cached.read_bytes()).hexdigest() == expected_sha256:
            return cached.read_bytes()
    data = fetch(url)
    time.sleep(2)  # be polite with Wikimedia between real downloads
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / hashlib.sha256(data).hexdigest()).write_bytes(data)
    return data


WHITE_TOLERANCE = 18
LIGHT_BACKGROUND_MIN = 200
NEUTRAL_SPREAD = 16


def _open_https(request: urllib.request.Request, timeout: float) -> Any:
    """Open a request whose URL was already checked to be https:// (S310/B310 mitigated)."""
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310  # nosec B310


def fetch(url: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError(f"Refusing non-HTTPS URL: {url}")
    for attempt in range(6):
        try:
            request = urllib.request.Request(url, headers=HEADERS)  # noqa: S310
            with _open_https(request, 90) as response:
                data: bytes = response.read()
                return data
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt == 5:
                raise
            # Polite back-off: honour Retry-After when Wikimedia sends it.
            retry_after = exc.headers.get("Retry-After", "")
            time.sleep(int(retry_after) if retry_after.isdigit() else 10 * (attempt + 1))
    raise RuntimeError("unreachable")


def lock(entries: list[dict[str, Any]], refresh: bool) -> None:
    pending = [e for e in entries if refresh or "sha256" not in e]
    if not pending:
        print("Todas las imágenes ya están fijadas.")
        return
    params = {
        "action": "query",
        "format": "json",
        "titles": "|".join(f"File:{e['commons_title']}" for e in pending),
        "prop": "imageinfo",
        "iiprop": "url|size|sha1|extmetadata",
        "iiurlwidth": str(THUMB_WIDTH),
        "iiextmetadatafilter": "LicenseShortName|LicenseUrl|Artist",
    }
    data = json.loads(fetch(f"{API}?{urllib.parse.urlencode(params)}"))
    normalized = {n["to"]: n["from"] for n in data["query"].get("normalized", [])}
    by_title: dict[str, dict[str, Any]] = {}
    for page in data["query"]["pages"].values():
        title = normalized.get(page["title"], page["title"]).removeprefix("File:")
        if "imageinfo" in page:
            by_title[title] = page["imageinfo"][0]
    for entry in pending:
        info = by_title.get(entry["commons_title"])
        if info is None:
            raise SystemExit(f"No existe en Commons: {entry['commons_title']}")
        meta = info.get("extmetadata", {})
        artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()
        # Wikimedia asks automated clients to use standard thumbnail sizes, not originals.
        use_thumb = info.get("width", 0) > THUMB_WIDTH and info.get("thumburl")
        entry.update(
            url=info["thumburl"] if use_thumb else info["url"],
            page=info["descriptionurl"],
            sha1=info["sha1"],
            license=meta.get("LicenseShortName", {}).get("value", ""),
            license_url=meta.get("LicenseUrl", {}).get("value", ""),
            author=re.sub(r"\s+", " ", artist),
        )
        entry["sha256"] = hashlib.sha256(cached_download(entry["url"])).hexdigest()
        print(f"fijada {entry['slug']}: {entry['license']} · {entry['author'][:50]}")
        time.sleep(2)
    MANIFEST.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def knockout_white(image: Image.Image) -> Image.Image:
    """Make a white/light-grey studio background transparent (flood fill from the corners)."""
    rgba = image.convert("RGBA")
    rgb = rgba.convert("RGB")
    marker = (255, 0, 255)
    width, height = rgb.size
    seeds = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    for seed in seeds:
        pixel = rgb.getpixel(seed)
        if not isinstance(pixel, tuple):
            continue
        # Studio backgrounds: white or a light, neutral grey.
        if min(pixel) >= LIGHT_BACKGROUND_MIN and max(pixel) - min(pixel) <= NEUTRAL_SPREAD:
            ImageDraw.floodfill(rgb, seed, marker, thresh=WHITE_TOLERANCE * 3)
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, marker)).convert("L")
    alpha = diff.point(lambda value: 255 if value > 0 else 0).filter(ImageFilter.GaussianBlur(1))
    rgba.putalpha(ImageChops.multiply(alpha, rgba.getchannel("A")))
    return rgba


def process(data: bytes, entry: dict[str, Any]) -> Image.Image:
    image: Image.Image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    image = knockout_white(image) if entry.get("knockout_white") else image.convert("RGBA")
    box = image.getchannel("A").getbbox()
    if box:
        image = image.crop(box)
    max_px = int(entry.get("max_px", 1000))
    image.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    return image


def build(entries: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    credits = []
    for entry in entries:
        if entry.get("license") not in ALLOWED_LICENSES:
            raise SystemExit(f"Licencia no permitida para {entry['slug']}: {entry.get('license')}")
        data = cached_download(entry["url"], entry["sha256"])
        if hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise SystemExit(f"SHA-256 no coincide para {entry['slug']}: el original cambió")
        image = process(data, entry)
        target = OUTPUT_DIR / f"{entry['slug']}.webp"
        image.save(target, "WEBP", quality=WEBP_QUALITY, method=6)  # no EXIF/metadata
        credits.append(
            {
                "slug": entry["slug"],
                "file": f"img/productos/{entry['slug']}.webp",
                "width": image.width,
                "height": image.height,
                "alt": entry["alt"],
                "title": entry["commons_title"],
                "author": entry["author"],
                "license": entry["license"],
                "license_url": entry.get("license_url", ""),
                "source": entry["page"],
            }
        )
        print(f"+ {target.relative_to(ROOT)} {image.width}x{image.height} ({entry['license']})")
    CREDITS.parent.mkdir(parents=True, exist_ok=True)
    CREDITS.write_text(
        json.dumps(credits, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"Créditos: {CREDITS.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Imágenes de producto con licencia libre")
    parser.add_argument("--bloquear", action="store_true", help="fijar SHA-256 y licencias")
    parser.add_argument("--refrescar", action="store_true", help="con --bloquear: rehacer todas")
    args = parser.parse_args()
    entries: list[dict[str, Any]] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if args.bloquear:
        lock(entries, args.refrescar)
        return 0
    build(entries)
    return 0


if __name__ == "__main__":
    sys.exit(main())
