"""Security-relevant configuration (OWASP A02/A04/A08)."""

import importlib
import os
import secrets
import subprocess
import sys

import pytest
from django.conf import settings
from django.contrib.auth.hashers import Argon2PasswordHasher

pytestmark = pytest.mark.security


def test_argon2_is_the_primary_password_hasher():
    base = importlib.import_module("config.settings.base")
    assert base.PASSWORD_HASHERS[0] == "django.contrib.auth.hashers.Argon2PasswordHasher"


def test_argon2_backend_is_installed():
    hasher = Argon2PasswordHasher()
    encoded = hasher.encode("una clave de prueba", hasher.salt())
    assert encoded.startswith("argon2$argon2id$")
    assert hasher.verify("una clave de prueba", encoded)


def test_celery_never_uses_pickle():
    assert settings.CELERY_ACCEPT_CONTENT == ["json"]
    assert settings.CELERY_TASK_SERIALIZER == "json"
    assert settings.CELERY_RESULT_SERIALIZER == "json"


def test_api_denies_by_default():
    assert settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == [
        "rest_framework.permissions.IsAuthenticated"
    ]
    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"]


def test_upload_limits_are_set():
    assert settings.DATA_UPLOAD_MAX_MEMORY_SIZE <= 5 * 1024 * 1024
    assert settings.FILE_UPLOAD_MAX_MEMORY_SIZE <= 5 * 1024 * 1024
    assert settings.DATA_UPLOAD_MAX_NUMBER_FILES <= 10


def test_production_settings_are_hardened():
    prod = importlib.import_module("config.settings.prod")
    assert prod.DEBUG is False
    assert prod.SECURE_SSL_REDIRECT is True
    assert prod.SECURE_HSTS_SECONDS >= 31_536_000
    assert prod.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert prod.SECURE_HSTS_PRELOAD is True
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SESSION_COOKIE_NAME.startswith("__Host-")
    assert prod.CSRF_COOKIE_NAME.startswith("__Host-")
    assert prod.CONTENT_SECURITY_POLICY["DIRECTIVES"]["upgrade-insecure-requests"] is True
    assert prod.STORAGES["staticfiles"]["BACKEND"].startswith("whitenoise.")
    media = prod.STORAGES["default"]["OPTIONS"]
    assert media["default_acl"] is None
    assert media["querystring_auth"] is True


def test_production_settings_do_not_leak_into_other_environments():
    importlib.import_module("config.settings.prod")
    assert "upgrade-insecure-requests" not in settings.CONTENT_SECURITY_POLICY["DIRECTIVES"]


def test_check_deploy_reports_no_warnings():
    """`manage.py check --deploy` must stay clean (OWASP A02)."""
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "config.settings.prod",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
        "DJANGO_ALLOWED_HOSTS": "byte.example.com",
        "DJANGO_ADMIN_URL": "k7Qp2-Xn9LwZr4Tb/",
        "DATABASE_URL": "postgres://byte:unused@localhost:5432/byte",
        "REDIS_URL": "redis://localhost:6379/0",
    }
    result = subprocess.run(
        [sys.executable, "manage.py", "check", "--deploy", "--fail-level", "WARNING"],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_static_files_are_readable_by_the_runtime_user():
    """Regression: strict upload permissions (0o640) once made staticfiles unreadable."""
    prod = importlib.import_module("config.settings.prod")
    options = prod.STORAGES["staticfiles"]["OPTIONS"]
    assert options["file_permissions_mode"] == 0o644
    assert options["directory_permissions_mode"] == 0o755
    assert settings.FILE_UPLOAD_PERMISSIONS == 0o640
