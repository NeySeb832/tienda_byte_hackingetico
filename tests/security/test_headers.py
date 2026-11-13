"""HTTP security headers and strict CSP (OWASP A02/A05)."""

import re

import pytest

pytestmark = pytest.mark.security

NONCE_RE = re.compile(r"'nonce-([A-Za-z0-9+/=_-]+)'")


def _directives(csp: str) -> dict[str, str]:
    result = {}
    for part in csp.split(";"):
        name, _, value = part.strip().partition(" ")
        if name:
            result[name] = value
    return result


def _nonce(response) -> str:
    match = NONCE_RE.search(response["Content-Security-Policy"])
    assert match, "CSP without nonce"
    return match.group(1)


def test_csp_is_strict(client):
    csp = client.get("/")["Content-Security-Policy"]
    directives = _directives(csp)
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp
    assert directives["default-src"] == "'self'"
    assert directives["object-src"] == "'none'"
    assert directives["frame-ancestors"] == "'none'"
    assert directives["base-uri"] == "'self'"
    assert directives["form-action"] == "'self'"
    assert NONCE_RE.search(directives["script-src"])


def test_every_script_tag_carries_the_request_nonce(client):
    response = client.get("/")
    nonce = _nonce(response)
    tags = re.findall(r"<script\b[^>]*>", response.content.decode())
    assert len(tags) >= 4
    for tag in tags:
        assert f'nonce="{nonce}"' in tag, tag


def test_nonce_is_unique_per_request(client):
    assert _nonce(client.get("/")) != _nonce(client.get("/"))


def test_templates_have_no_inline_handlers_or_styles(client):
    html = client.get("/").content.decode()
    assert not re.search(r"\son[a-z]+\s*=", html), "inline event handler found"
    assert " style=" not in html, "inline style attribute found"


def test_browser_hardening_headers(client):
    response = client.get("/")
    assert response["X-Frame-Options"] == "DENY"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response["Cross-Origin-Resource-Policy"] == "same-origin"
    assert "camera=()" in response["Permissions-Policy"]
    assert "geolocation=()" in response["Permissions-Policy"]


def test_error_pages_keep_security_headers(client):
    response = client.get("/ruta-que-no-existe/")
    assert response.status_code == 404
    assert "Content-Security-Policy" in response
    assert response["X-Frame-Options"] == "DENY"


def test_htmx_sends_csrf_token_in_header(client):
    html = client.get("/").content.decode()
    assert 'hx-headers=\'{"X-CSRFToken": "' in html
