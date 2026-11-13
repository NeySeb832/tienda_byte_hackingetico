"""Local development settings."""

import copy

from .base import *

DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])
INTERNAL_IPS = ["127.0.0.1"]
# Serve static files straight from STATICFILES_DIRS (no collectstatic needed locally).
WHITENOISE_USE_FINDERS = True

# The browsable API is handy locally; production serves JSON only.
REST_FRAMEWORK = copy.deepcopy(REST_FRAMEWORK)
REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = [
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
]

if env.bool("DJANGO_DEBUG_TOOLBAR", default=False):  # pragma: no cover - opt-in tooling
    INSTALLED_APPS = [*INSTALLED_APPS, "debug_toolbar"]
    MIDDLEWARE = list(MIDDLEWARE)
    MIDDLEWARE.insert(
        MIDDLEWARE.index("csp.middleware.CSPMiddleware") + 1,
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    )
