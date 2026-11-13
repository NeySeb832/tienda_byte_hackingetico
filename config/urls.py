"""Root URL configuration."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("apps.core.urls")),
    path("", include("apps.cms.urls")),
    path("", include("apps.catalog.urls")),
    path("cuenta/", include("apps.accounts.urls")),
    path("cuenta/", include("allauth.urls")),  # login, registro, MFA, sesiones...
    path("panel/", include("apps.panel.urls")),
    path("api/v1/", include("apps.api.v1.urls")),
]

# Django admin: superadmin only, on a hidden path configured by environment (empty = disabled).
if settings.ADMIN_URL:
    urlpatterns.append(path(settings.ADMIN_URL, admin.site.urls))

if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:  # pragma: no cover
    urlpatterns.append(path("__debug__/", include("debug_toolbar.urls")))

handler400 = "apps.core.views.bad_request"
handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"
