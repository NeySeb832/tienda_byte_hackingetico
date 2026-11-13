"""Custom system checks for the hidden admin URL."""

from django.test import override_settings

from apps.core.checks import check_admin_url_format, check_admin_url_unpredictable


@override_settings(ADMIN_URL="ruta con espacios/")
def test_invalid_admin_url_is_an_error():
    assert [m.id for m in check_admin_url_format(None)] == ["byte.E001"]


@override_settings(ADMIN_URL="admin/")
def test_predictable_admin_url_is_a_warning():
    assert [m.id for m in check_admin_url_unpredictable(None)] == ["byte.W001"]


@override_settings(ADMIN_URL="corta-123/")
def test_short_admin_url_is_a_warning():
    assert [m.id for m in check_admin_url_unpredictable(None)] == ["byte.W002"]


@override_settings(ADMIN_URL="k7Qp2-Xn9LwZr4Tb/")
def test_random_admin_url_passes():
    assert check_admin_url_format(None) == []
    assert check_admin_url_unpredictable(None) == []


@override_settings(ADMIN_URL="")
def test_disabled_admin_passes():
    assert check_admin_url_format(None) == []
    assert check_admin_url_unpredictable(None) == []
