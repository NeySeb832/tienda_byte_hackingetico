"""Read-side queries for the audit app."""

from django.db.models import QuerySet

from apps.audit.models import AuditLog, SecurityEvent


def audit_entries() -> QuerySet[AuditLog]:
    return AuditLog.objects.select_related("actor").order_by("-id")


def security_events() -> QuerySet[SecurityEvent]:
    return SecurityEvent.objects.select_related("user").order_by("-created_at")
