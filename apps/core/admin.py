"""Django admin branding (admin is superadmin-only, on a hidden path)."""

from django.contrib import admin

admin.site.site_header = "Byte · Superadministración"
admin.site.site_title = "Byte"
admin.site.index_title = "Configuración del sistema"
