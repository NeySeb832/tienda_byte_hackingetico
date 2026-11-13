"""Settings shared by every environment.

Anything secret or environment-specific comes from environment variables
(documented in .env.example). Never hard-code secrets here.
"""

import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import environ
from celery.schedules import crontab
from csp.constants import NONCE, NONE, SELF
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
_ENV_FILE = BASE_DIR / ".env"
if _ENV_FILE.is_file():
    environ.Env.read_env(_ENV_FILE)

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env.str("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS: list[str] = env.list("DJANGO_ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS: list[str] = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# Hidden, non-predictable Django admin path (superadmin only). Empty disables it.
ADMIN_URL = env.str("DJANGO_ADMIN_URL", default="")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django.contrib.humanize",  # used by allauth templates (sessions)
]
THIRD_PARTY_APPS = [
    "rest_framework",
    "drf_spectacular",
    "django_celery_beat",
    "django_htmx",
    "django_tailwind_cli",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.usersessions",
    "axes",
]
LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.audit",
    "apps.catalog",
    "apps.pricing",
    "apps.inventory",
    "apps.purchasing",
    "apps.cart",
    "apps.orders",
    "apps.payments",
    "apps.shipping",
    "apps.promotions",
    "apps.tradein",
    "apps.services_desk",
    "apps.reviews",
    "apps.pos",
    "apps.notifications",
    "apps.cms",
    "apps.analytics",
    "apps.panel",
    "apps.api",
]
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "apps.core.middleware.RequestIDMiddleware",
    "apps.audit.middleware.ForbiddenBurstMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "allauth.usersessions.middleware.UserSessionsMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.accounts.middleware.StaffSecurityMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    # Must be last (django-axes): turns lockouts into the lockout response.
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
                "apps.panel.context_processors.panel",
                "apps.catalog.context_processors.catalog",
                "apps.cart.context_processors.cart",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Data stores
# ---------------------------------------------------------------------------
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DJANGO_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DATABASES["default"].setdefault("OPTIONS", {})["connect_timeout"] = 5
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = env.str("REDIS_URL")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "byte",
        "TIMEOUT": 300,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 2,
            "SOCKET_TIMEOUT": 2,
        },
    }
}

# ---------------------------------------------------------------------------
# Sessions, CSRF and authentication
# ---------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_AGE = env.int("DJANGO_SESSION_COOKIE_AGE", default=60 * 60 * 24 * 14)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True  # HTMX sends the token from the template (X-CSRFToken header)
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "apps.core.views.csrf_failure"

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",  # brute-force protection first (A07)
    "allauth.account.auth_backends.AuthenticationBackend",
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",  # A04: Argon2id first
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {
        "NAME": "apps.accounts.validators.StaffMinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "apps.accounts.validators.PwnedPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation (prepared for gettext; UI language is Spanish - Colombia)
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "es-co"
LANGUAGES = [("es-co", _("Español (Colombia)"))]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files and uploads
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES: dict[str, dict[str, Any]] = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Request and upload limits (A05 / DoS hardening).
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000
DATA_UPLOAD_MAX_NUMBER_FILES = 10
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750

# ---------------------------------------------------------------------------
# Security headers (all environments; prod.py adds HTTPS-only settings)
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
BYTE_PERMISSIONS_POLICY = (
    "accelerometer=(), autoplay=(), camera=(), display-capture=(), geolocation=(), "
    "gyroscope=(), magnetometer=(), microphone=(), midi=(), payment=(self), usb=(), "
    "browsing-topics=()"
)

# Strict nonce-based CSP (ADR-0002/0006): no 'unsafe-inline', no 'unsafe-eval'.
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [SELF],
        "script-src": [SELF, NONCE, "https://challenges.cloudflare.com"],
        "style-src": [SELF],
        "img-src": [SELF, "data:"],
        "font-src": [SELF],
        "connect-src": [SELF],
        "manifest-src": [SELF],
        "worker-src": [SELF],
        "frame-src": ["https://challenges.cloudflare.com"],  # Turnstile CAPTCHA
        "object-src": [NONE],
        "base-uri": [SELF],
        "form-action": [SELF],
        "frame-ancestors": [NONE],
    },
}

# ---------------------------------------------------------------------------
# Django REST Framework / OpenAPI
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Deny by default: every endpoint must opt in to wider access explicitly.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 24,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "60/min", "user": "240/min"},
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Byte API",
    "DESCRIPTION": "API REST de Byte (v1).",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # The schema is internal documentation: staff only.
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
}

# ---------------------------------------------------------------------------
# Celery (ADR-0009): JSON only, never pickle
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env.str("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_IGNORE_RESULT = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 10 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 9 * 60
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    # Scheduled price changes (apps.pricing): applied within 5 minutes of their start.
    "analytics-nightly-pipeline": {
        "task": "analytics.run_pipeline",
        "schedule": crontab(hour=3, minute=0),
    },
    "orders-expire-unpaid": {
        "task": "orders.expire_unpaid_orders",
        "schedule": 300.0,
    },
    "pricing-apply-scheduled": {
        "task": "pricing.apply_scheduled_price_changes",
        "schedule": 300.0,
    },
}
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env.str(
    "DJANGO_EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
DEFAULT_FROM_EMAIL = env.str("DJANGO_DEFAULT_FROM_EMAIL", default="Byte <no-reply@byte.localhost>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_TIMEOUT = 10

# ---------------------------------------------------------------------------
# Logging: structured JSON with correlation id; sensitive values masked (A09)
# ---------------------------------------------------------------------------
LOG_LEVEL = env.str("DJANGO_LOG_LEVEL", default="INFO")
LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "apps.core.logging.RequestIDFilter"},
        "sensitive": {"()": "apps.core.logging.SensitiveDataFilter"},
    },
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
            "rename_fields": {"asctime": "timestamp", "levelname": "level", "name": "logger"},
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_id", "sensitive"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        # Replaces Django's default handlers (no mail_admins with stack traces / PII).
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "django.security": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "celery": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Authentication: django-allauth (+ MFA, sessions), django-axes (ADR-0012)
# ---------------------------------------------------------------------------
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "accounts:dashboard"
ACCOUNT_LOGOUT_REDIRECT_URL = "core:home"
ACCOUNT_ADAPTER = "apps.accounts.adapters.AccountAdapter"
ACCOUNT_FORMS = {
    "login": "apps.accounts.forms.LoginForm",
    "signup": "apps.accounts.forms.SignupForm",
    "reset_password": "apps.accounts.forms.ResetPasswordForm",
}
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_PREVENT_ENUMERATION = True  # same answer whether or not an account exists
ACCOUNT_EMAIL_SUBJECT_PREFIX = "[Byte] "
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = "Byte"
USERSESSIONS_TRACK_ACTIVITY = True

AXES_ENABLED = env.bool("AXES_ENABLED", default=True)
AXES_VERBOSE = False  # our own JSON logs and security events cover it
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]  # user + IP combination
AXES_USERNAME_FORM_FIELD = "login"
AXES_USERNAME_CALLABLE = "apps.accounts.security.axes_username"
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "account/lockout.html"
AXES_HTTP_RESPONSE_CODE = 429
# Client IP behind proxies (pentest PT-01): one resolver for axes, django-ratelimit, allauth
# and the audit log. REMOTE_ADDR is the last proxy (a private address on Render), so per-IP
# controls need a trusted source. Render sits behind Cloudflare: HTTP_CF_CONNECTING_IP.
BYTE_CLIENT_IP_HEADER = env.str("BYTE_CLIENT_IP_HEADER", default="")
BYTE_TRUSTED_PROXY_COUNT = env.int("BYTE_TRUSTED_PROXY_COUNT", default=0)
AXES_CLIENT_IP_CALLABLE = "apps.core.net.client_ip"
RATELIMIT_IP_META_KEY = "apps.core.net.client_ip"
# Progressive lockout (failures, minutes). Converted to axes.conf.LockoutTier in
# AccountsConfig.ready(): axes.conf cannot be imported from settings.
BYTE_LOCKOUT_TIERS = ((5, 5), (10, 30), (20, 24 * 60))

# Cloudflare Turnstile. The defaults are Cloudflare's public *test* keys (always pass);
# production must set real keys (deploy check byte.W003).
BYTE_CAPTCHA_ENABLED = env.bool("BYTE_CAPTCHA_ENABLED", default=True)
TURNSTILE_SITE_KEY = env.str("TURNSTILE_SITE_KEY", default="1x00000000000000000000AA")
TURNSTILE_SECRET_KEY = env.str(
    "TURNSTILE_SECRET_KEY", default="1x0000000000000000000000000000000AA"
)
BYTE_LOGIN_CAPTCHA_AFTER_FAILURES = env.int("BYTE_LOGIN_CAPTCHA_AFTER_FAILURES", default=3)
# Breached-password check (Have I Been Pwned, k-anonymity).
BYTE_HIBP_ENABLED = env.bool("BYTE_HIBP_ENABLED", default=True)

# Staff hardening.
BYTE_STAFF_IDLE_TIMEOUT_MINUTES = env.int("BYTE_STAFF_IDLE_TIMEOUT_MINUTES", default=15)
BYTE_FORBIDDEN_BURST_THRESHOLD = 10
BYTE_FORBIDDEN_BURST_WINDOW_SECONDS = 300

# Field-level encryption (A04): comma-separated Fernet keys, newest first (rotation).
BYTE_FIELD_ENCRYPTION_KEYS: list[str] = env.list("BYTE_FIELD_ENCRYPTION_KEYS", default=[])
BYTE_BLIND_INDEX_KEY = env.str("BYTE_BLIND_INDEX_KEY", default="")
# Password of the demo users (seed_demo_users). Development/demo only.
BYTE_DEMO_PASSWORD = env.str("BYTE_DEMO_PASSWORD", default="")

# ---------------------------------------------------------------------------
# Tailwind CSS (ADR-0006): standalone CLI, pinned and checksum-verified.
# The binary is downloaded by scripts/vendor_assets.py; automatic (unverified)
# downloads by django-tailwind-cli are disabled.
# ---------------------------------------------------------------------------
TAILWIND_CLI_VERSION = "4.3.5"
TAILWIND_CLI_SRC_CSS = "assets/css/input.css"
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"
TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
TAILWIND_CLI_PATH = env.str(
    "TAILWIND_CLI_PATH",
    default=str(
        BASE_DIR / ".bin" / ("tailwindcss.exe" if sys.platform == "win32" else "tailwindcss")
    ),
)

# ---------------------------------------------------------------------------
# Business parameters (ADR-0004). Configurable per environment.
# ---------------------------------------------------------------------------
BYTE_SITE_NAME = "Byte"
BYTE_CURRENCY = "COP"
BYTE_VAT_RATE = Decimal("0.19")
BYTE_HIGH_DISCOUNT_APPROVAL_PCT = env.int("BYTE_HIGH_DISCOUNT_APPROVAL_PCT", default=15)
BYTE_STOCK_RESERVATION_TTL_MINUTES = env.int("BYTE_STOCK_RESERVATION_TTL_MINUTES", default=15)
BYTE_FREE_SHIPPING_FROM = env.int("BYTE_FREE_SHIPPING_FROM", default=300_000)

# ---------------------------------------------------------------------------
# Checkout and payments (Phase 4, ADR-0007/0014)
# ---------------------------------------------------------------------------
BYTE_SITE_URL = env.str("BYTE_SITE_URL", default="http://localhost:8000")
# "fake" (built-in simulator, no network) or "wompi" (sandbox). Deploy checks: byte.W004/E004.
BYTE_PAYMENT_GATEWAY = env.str("BYTE_PAYMENT_GATEWAY", default="fake")
WOMPI_PUBLIC_KEY = env.str("WOMPI_PUBLIC_KEY", default="")
WOMPI_INTEGRITY_SECRET = env.str("WOMPI_INTEGRITY_SECRET", default="")
WOMPI_EVENTS_SECRET = env.str("WOMPI_EVENTS_SECRET", default="")
WOMPI_API_URL = env.str("WOMPI_API_URL", default="https://sandbox.wompi.co/v1")
WOMPI_CHECKOUT_URL = env.str("WOMPI_CHECKOUT_URL", default="https://checkout.wompi.co/p/")

# ---------------------------------------------------------------------------
# BI / data lake (Phase 7, ADR-0017)
# ---------------------------------------------------------------------------
BYTE_DATA_LAKE_DIR = env.path("BYTE_DATA_LAKE_DIR", default=str(BASE_DIR / "data" / "lake"))
