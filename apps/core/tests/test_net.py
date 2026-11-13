"""Client-IP resolution behind proxies (pentest finding PT-01)."""

import pytest
from axes.helpers import get_client_ip_address
from django.test import RequestFactory
from django_ratelimit.core import _get_ip

from apps.accounts.adapters import AccountAdapter
from apps.audit.services import client_ip as audit_client_ip
from apps.core.net import client_ip

RENDER_PROXY = "10.21.157.68"  # private address of Render's load balancer
REAL_CLIENT = "203.0.113.7"
CLOUDFLARE_EDGE = "104.22.17.40"


def _request(**meta):
    meta.setdefault("REMOTE_ADDR", RENDER_PROXY)
    return RequestFactory().get("/", **meta)


def test_without_configuration_falls_back_to_remote_addr(settings):
    settings.BYTE_CLIENT_IP_HEADER = ""
    settings.BYTE_TRUSTED_PROXY_COUNT = 0
    assert client_ip(_request(HTTP_X_FORWARDED_FOR=REAL_CLIENT)) == RENDER_PROXY


def test_trusted_edge_header_wins(settings):
    settings.BYTE_CLIENT_IP_HEADER = "HTTP_CF_CONNECTING_IP"
    request = _request(
        HTTP_CF_CONNECTING_IP=REAL_CLIENT,
        HTTP_X_FORWARDED_FOR=f"6.6.6.6, {REAL_CLIENT}, {CLOUDFLARE_EDGE}",
    )
    assert client_ip(request) == REAL_CLIENT


@pytest.mark.parametrize("bad", ["", "not-an-ip", "1.2.3.4; DROP", "999.1.1.1"])
def test_invalid_edge_header_is_ignored(settings, bad):
    settings.BYTE_CLIENT_IP_HEADER = "HTTP_CF_CONNECTING_IP"
    settings.BYTE_TRUSTED_PROXY_COUNT = 0
    assert client_ip(_request(HTTP_CF_CONNECTING_IP=bad)) == RENDER_PROXY


def test_forwarded_for_counts_trusted_hops_from_the_right(settings):
    """Render appends the Cloudflare edge; whatever the client sent stays on the left."""
    settings.BYTE_CLIENT_IP_HEADER = ""
    settings.BYTE_TRUSTED_PROXY_COUNT = 2
    spoofed = f"6.6.6.6, 7.7.7.7, {REAL_CLIENT}, {CLOUDFLARE_EDGE}"
    assert client_ip(_request(HTTP_X_FORWARDED_FOR=spoofed)) == REAL_CLIENT


def test_short_forwarded_for_chain_is_not_trusted(settings):
    settings.BYTE_CLIENT_IP_HEADER = ""
    settings.BYTE_TRUSTED_PROXY_COUNT = 2
    assert client_ip(_request(HTTP_X_FORWARDED_FOR=REAL_CLIENT)) == RENDER_PROXY


def test_ipv6_and_bracketed_addresses(settings):
    settings.BYTE_CLIENT_IP_HEADER = "HTTP_CF_CONNECTING_IP"
    assert client_ip(_request(HTTP_CF_CONNECTING_IP="[2001:db8::1]:443")) == "2001:db8::1"


def test_none_request():
    assert client_ip(None) is None


def test_every_ip_based_control_uses_the_same_resolver(settings):
    """axes, django-ratelimit, allauth and the audit log must agree on the client."""
    settings.BYTE_CLIENT_IP_HEADER = "HTTP_CF_CONNECTING_IP"
    request = _request(HTTP_CF_CONNECTING_IP=REAL_CLIENT)
    assert get_client_ip_address(request) == REAL_CLIENT
    assert _get_ip(request) == REAL_CLIENT
    assert AccountAdapter(request).get_client_ip(request) == REAL_CLIENT
    assert audit_client_ip(request) == REAL_CLIENT
