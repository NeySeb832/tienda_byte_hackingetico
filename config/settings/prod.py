"""Production settings (Render). HTTPS only, secrets from the environment."""

import copy

from .base import *
from .base import ALLOWED_HOSTS, BYTE_SITE_URL, CSRF_TRUSTED_ORIGINS

DEBUG = False

# --- Render: the platform injects the public hostname ---
RENDER_HOST = env.str("RENDER_EXTERNAL_HOSTNAME", default="")
if RENDER_HOST:
    ALLOWED_HOSTS = [*ALLOWED_HOSTS, RENDER_HOST]
    CSRF_TRUSTED_ORIGINS = [*CSRF_TRUSTED_ORIGINS, f"https://{RENDER_HOST}"]
    if BYTE_SITE_URL.startswith("http://localhost"):
        BYTE_SITE_URL = f"https://{RENDER_HOST}"

# --- HTTPS / HSTS (A02, A04) ---
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REDIRECT_EXEMPT = [r"^healthz$"]  # platform health checks hit plain HTTP internally
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# --- Cookies: Secure + __Host- prefix (no Domain, Path=/) ---
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_NAME = "__Host-sessionid"
CSRF_COOKIE_NAME = "__Host-csrftoken"

# Work on copies: objects imported from base.py must never be mutated in place.
CONTENT_SECURITY_POLICY = copy.deepcopy(CONTENT_SECURITY_POLICY)
STORAGES = copy.deepcopy(STORAGES)
REST_FRAMEWORK = copy.deepcopy(REST_FRAMEWORK)

CONTENT_SECURITY_POLICY["DIRECTIVES"]["upgrade-insecure-requests"] = True
CONTENT_SECURITY_POLICY["DIRECTIVES"]["img-src"] += env.list("DJANGO_CSP_EXTRA_IMG_SRC", default=[])

# --- Static files (WhiteNoise, hashed + compressed) and private media (S3/R2) ---
STORAGES["staticfiles"] = {
    "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    # Static assets are public and must be readable by the unprivileged runtime user;
    # the strict FILE_UPLOAD_*_PERMISSIONS (0o640/0o750) only apply to user uploads.
    "OPTIONS": {"file_permissions_mode": 0o644, "directory_permissions_mode": 0o755},
}
if env.bool("DJANGO_USE_S3", default=True):
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": env.str("AWS_STORAGE_BUCKET_NAME", default=""),
            "endpoint_url": env.str("AWS_S3_ENDPOINT_URL", default=None),
            "region_name": env.str("AWS_S3_REGION_NAME", default="auto"),
            "access_key": env.str("AWS_ACCESS_KEY_ID", default=""),
            "secret_key": env.str("AWS_SECRET_ACCESS_KEY", default=""),
            "default_acl": None,  # private bucket
            "querystring_auth": True,  # signed URLs
            "querystring_expire": 300,
            "file_overwrite": False,
            "signature_version": "s3v4",
        },
    }

# --- Email (django-anymail; provider configured by environment) ---
EMAIL_BACKEND = env.str(
    "DJANGO_EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend"
)
ANYMAIL = env.json("DJANGO_ANYMAIL", default={})

# --- Optional error tracking with PII scrubbing (A09) ---
SENTRY_DSN = env.str("SENTRY_DSN", default="")
if SENTRY_DSN:  # pragma: no cover - requires an external service
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        send_default_pii=False,
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0),
        environment=env.str("SENTRY_ENVIRONMENT", default="production"),
    )
