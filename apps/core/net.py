"""Trusted client-IP resolution behind reverse proxies (pentest finding PT-01).

Every IP-based control (django-axes lockout, django-ratelimit, allauth's rate limits, the
audit log and the login CAPTCHA) must agree on *who* the client is. ``REMOTE_ADDR`` is the
last proxy, not the client: on Render it is a private address of Render's load balancer,
shared by many visitors, so per-IP controls never accumulate for a real attacker.

Resolution order, configured per environment:

1. ``BYTE_CLIENT_IP_HEADER`` (a ``request.META`` key such as ``HTTP_CF_CONNECTING_IP``):
   a single header written by an edge the client cannot bypass. Cloudflare overwrites
   ``CF-Connecting-IP``, and every ``*.onrender.com`` service is reached through it.
2. ``BYTE_TRUSTED_PROXY_COUNT`` (N > 0): the N-th address counted from the *right* of
   ``X-Forwarded-For``. Entries to the left of it are client-supplied and are never trusted.
3. ``REMOTE_ADDR``.

Only syntactically valid IP addresses are returned; anything else falls through to the next
source, so a malformed header cannot inject arbitrary keys into the counters.
"""

from __future__ import annotations

import ipaddress

from django.conf import settings
from django.http import HttpRequest


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.strip()
    if candidate.startswith("[") and "]" in candidate:  # "[::1]:443"
        candidate = candidate[1 : candidate.index("]")]
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _from_forwarded_for(request: HttpRequest, trusted_proxies: int) -> str | None:
    header = request.META.get("HTTP_X_FORWARDED_FOR", "")
    hops = [hop.strip() for hop in header.split(",") if hop.strip()]
    if trusted_proxies <= 0 or len(hops) < trusted_proxies:
        return None
    return _valid_ip(hops[-trusted_proxies])


def client_ip(request: HttpRequest | None) -> str | None:
    """Best trusted guess of the client's IP address, or ``None``."""
    if request is None:
        return None
    header = getattr(settings, "BYTE_CLIENT_IP_HEADER", "")
    if header:
        ip = _valid_ip(request.META.get(header))
        if ip:
            return ip
    trusted_proxies = int(getattr(settings, "BYTE_TRUSTED_PROXY_COUNT", 0))
    if trusted_proxies > 0:
        ip = _from_forwarded_for(request, trusted_proxies)
        if ip:
            return ip
    return _valid_ip(request.META.get("REMOTE_ADDR"))
