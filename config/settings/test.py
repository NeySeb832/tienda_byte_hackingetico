"""Settings for the automated test suite (pytest)."""

import copy
import os
from pathlib import Path

import environ

# Real values from .env win; the defaults below only make the suite runnable in CI.
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"
if _ENV_FILE.is_file():
    environ.Env.read_env(_ENV_FILE)
os.environ.setdefault(
    "DJANGO_SECRET_KEY", "test-only-insecure-key-never-used-in-production-0123456789"
)
os.environ.setdefault("DATABASE_URL", "postgres://byte:byte@localhost:5432/byte")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("BYTE_FIELD_ENCRYPTION_KEYS", "Ynl0ZS10ZXN0LW9ubHktZmVybmV0LWtleS0wMDAwMDE=")
os.environ.setdefault("BYTE_BLIND_INDEX_KEY", "test-only-blind-index-key")

from .base import *  # noqa: E402

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]
ADMIN_URL = "test-admin/"

# Speed only: production keeps Argon2 first (verified in tests/security/test_settings.py).
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
CELERY_TASK_ALWAYS_EAGER = True
BYTE_CAPTCHA_ENABLED = False  # enabled explicitly in captcha tests
BYTE_HIBP_ENABLED = False  # network check mocked in validator tests
CELERY_TASK_EAGER_PROPAGATES = True
LOGGING = copy.deepcopy(LOGGING)
LOGGING["root"]["level"] = "WARNING"
LOGGING["loggers"]["django"]["level"] = "WARNING"
