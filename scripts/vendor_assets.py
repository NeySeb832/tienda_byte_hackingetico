"""Download and verify third-party front-end assets (ADR-0005 / ADR-0006).

* npm packages are verified against the sha512 ``integrity`` published by the npm
  registry (pinned below) and only the needed file is extracted from the tarball.
* The Tailwind CSS standalone CLI is verified against the official ``sha256sums.txt``
  of its GitHub release (pinned below).

Nothing is executed or trusted before its hash matches.

Usage::

    uv run python scripts/vendor_assets.py           # download what is missing
    uv run python scripts/vendor_assets.py --check   # verify files on disk (no network)
    uv run python scripts/vendor_assets.py --force   # re-download everything
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import platform
import stat
import sys
import tarfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VENDOR_SUMS = ROOT / "static" / "vendor" / "SHA256SUMS"
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
TIMEOUT_SECONDS = 60
HEADERS = {"User-Agent": "byte-vendor-assets/1.0"}


@dataclass(frozen=True)
class NpmAsset:
    package: str
    version: str
    tarball: str
    integrity: str  # "sha512-<base64>" as published by registry.npmjs.org
    member: str  # file inside the tarball
    dest: str  # path relative to the repository root


NPM_ASSETS = (
    NpmAsset(
        package="htmx.org",
        version="2.0.11",
        tarball="https://registry.npmjs.org/htmx.org/-/htmx.org-2.0.11.tgz",
        integrity="sha512-Thx/WtpeOQqSrqBCw/A1cwGJGg4UrVa3+sW0GmrM3p4gJgO89ecH4qtbnyzDDWFvBTqjnIMCgELTNt636dtamA==",
        member="package/dist/htmx.min.js",
        dest="static/vendor/htmx/htmx.min.js",
    ),
    NpmAsset(
        package="@alpinejs/csp",
        version="3.17.5",
        tarball="https://registry.npmjs.org/@alpinejs/csp/-/csp-3.17.5.tgz",
        integrity="sha512-7e5lYgzJJL2eZ7esnx+E7wtxws+VDs9em9ztttZ+AQAYEng2bABHFp2SUga0wt84RyfL7hc6B+S/RGglXsPf6w==",
        member="package/dist/cdn.min.js",
        dest="static/vendor/alpine/alpine-csp.min.js",
    ),
)

TAILWIND_VERSION = "4.3.5"
TAILWIND_SHA256 = {
    "tailwindcss-linux-arm64": "ffcd0d21dbd7c605dc12743ff0c0b47debc963c86b399674084c1c8f2c96ecad",
    "tailwindcss-linux-arm64-musl": "564dad3028c029b0c69042c66a7a79873ed7289b73fcb7b37973fbf79cb9a32f",
    "tailwindcss-linux-x64": "e47695cee3f0d90623a91f3939b08bdee610eb5ad99340adff9d4145b284d6cc",
    "tailwindcss-linux-x64-musl": "bb050edd13f15006d872a9bb1772b908618a8df6806d30bf095cba26a09e640b",
    "tailwindcss-macos-arm64": "f3f4f5d1727e2b693b8f1c9a1492b5dd87008c86ea286bee1589cb458e6235fc",
    "tailwindcss-macos-x64": "a63702686a3ed048b3135d84a73be49ea9d47f880c9b20e54b3ef60934ad8cdf",
    "tailwindcss-windows-x64.exe": "2803583268c53f4713e89943e211081fddb186c0a4a7d07b5c342c6ae853ec95",
}


class IntegrityError(RuntimeError):
    """A downloaded or local file does not match its pinned hash."""


def _open_https(request: urllib.request.Request, timeout: float) -> Any:
    """Open a request whose URL was already checked to be https:// (S310/B310 mitigated)."""
    return urllib.request.urlopen(request, timeout=timeout)  # noqa: S310  # nosec B310


def download(url: str) -> bytes:
    # Only https:// is accepted (checked here), which is what S310 warns about.
    if not url.startswith("https://"):
        raise ValueError(f"Refusing non-HTTPS URL: {url}")
    request = urllib.request.Request(url, headers=HEADERS)  # noqa: S310
    with _open_https(request, TIMEOUT_SECONDS) as response:
        data: bytes = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise IntegrityError(f"Download too large: {url}")
    return data


def verify_sri(data: bytes, integrity: str) -> None:
    algorithm, _, expected = integrity.partition("-")
    if algorithm != "sha512":
        raise IntegrityError(f"Unsupported integrity algorithm: {algorithm}")
    actual = base64.b64encode(hashlib.sha512(data).digest()).decode()
    if actual != expected:
        raise IntegrityError("npm tarball integrity mismatch")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tailwind_asset_name() -> str:
    machine = platform.machine().lower()
    arch = "arm64" if machine in {"arm64", "aarch64"} else "x64"
    if sys.platform == "win32":
        return "tailwindcss-windows-x64.exe"
    if sys.platform == "darwin":
        return f"tailwindcss-macos-{arch}"
    musl = any(Path("/lib").glob("ld-musl-*"))
    return f"tailwindcss-linux-{arch}{'-musl' if musl else ''}"


def tailwind_dest() -> Path:
    return ROOT / ".bin" / ("tailwindcss.exe" if sys.platform == "win32" else "tailwindcss")


def read_sums() -> dict[str, str]:
    if not VENDOR_SUMS.exists():
        return {}
    sums = {}
    for line in VENDOR_SUMS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, path = line.split(maxsplit=1)
            sums[path.strip()] = digest
    return sums


def write_sums(sums: dict[str, str]) -> None:
    VENDOR_SUMS.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{digest}  {path}" for path, digest in sorted(sums.items())]
    VENDOR_SUMS.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def fetch_npm(asset: NpmAsset, sums: dict[str, str], force: bool) -> None:
    dest = ROOT / asset.dest
    if dest.exists() and not force:
        print(f"= {asset.dest} ya existe")
        return
    data = download(asset.tarball)
    verify_sri(data, asset.integrity)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        member = tar.getmember(asset.member)  # exact name: no path traversal possible
        if not member.isfile():
            raise IntegrityError(f"{asset.member} is not a regular file")
        extracted = tar.extractfile(member)
        if extracted is None:
            raise IntegrityError(f"Cannot read {asset.member}")
        content = extracted.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    sums[asset.dest] = sha256(content)
    print(f"+ {asset.package}@{asset.version} -> {asset.dest} (sha512 OK)")


def fetch_tailwind(force: bool) -> None:
    name = tailwind_asset_name()
    expected = TAILWIND_SHA256[name]
    dest = tailwind_dest()
    if dest.exists() and not force and sha256(dest.read_bytes()) == expected:
        print(f"= {dest.relative_to(ROOT)} ya existe (sha256 OK)")
        return
    url = (
        "https://github.com/tailwindlabs/tailwindcss/releases/download/"
        f"v{TAILWIND_VERSION}/{name}"
    )
    data = download(url)
    if sha256(data) != expected:
        raise IntegrityError(f"Tailwind binary checksum mismatch for {name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
    print(f"+ Tailwind CSS {TAILWIND_VERSION} ({name}) -> {dest.relative_to(ROOT)} (sha256 OK)")


def check() -> int:
    errors = 0
    sums = read_sums()
    for asset in NPM_ASSETS:
        dest = ROOT / asset.dest
        if not dest.exists():
            print(f"! falta {asset.dest}")
            errors += 1
        elif sums.get(asset.dest) != sha256(dest.read_bytes()):
            print(f"! {asset.dest} no coincide con SHA256SUMS")
            errors += 1
        else:
            print(f"OK {asset.dest}")
    dest = tailwind_dest()
    if dest.exists():
        ok = sha256(dest.read_bytes()) == TAILWIND_SHA256[tailwind_asset_name()]
        print(f"{'OK' if ok else '!'} {dest.relative_to(ROOT)}")
        errors += 0 if ok else 1
    else:
        print(f"- {dest.relative_to(ROOT)} no descargado (opcional fuera de desarrollo)")
    return 1 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verificar archivos locales")
    parser.add_argument("--force", action="store_true", help="volver a descargar todo")
    parser.add_argument("--skip-tailwind", action="store_true", help="no descargar Tailwind")
    parser.add_argument(
        "--only-tailwind", action="store_true", help="solo el binario de Tailwind (Docker/CI)"
    )
    args = parser.parse_args()
    if args.check:
        return check()
    if args.only_tailwind:
        fetch_tailwind(args.force)
        return 0
    sums = read_sums()
    for asset in NPM_ASSETS:
        fetch_npm(asset, sums, args.force)
    write_sums(sums)
    if not args.skip_tailwind:
        fetch_tailwind(args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
