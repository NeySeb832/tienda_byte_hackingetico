"""Hash-chained, append-only audit trail and security events (OWASP A09)."""

import pytest
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django.urls import reverse

from apps.audit.models import AuditLog, SecurityEvent
from apps.audit.services import record_event, verify_chain

pytestmark = pytest.mark.django_db


def test_events_form_an_intact_chain(user):
    first = record_event("test.one", actor=user, target=user, changes={"password": "x"})
    second = record_event("test.two", actor=user)
    assert second.prev_hash == first.row_hash
    assert first.changes == {"password": "***"}
    assert first.actor_repr.endswith("@example.com")
    assert "*" in first.actor_repr
    assert verify_chain() is None
    call_command("verify_audit_chain", verbosity=0)


def test_tampering_is_detected(user):
    record_event("test.one", actor=user)
    second = record_event("test.two", actor=user)
    rows = list(AuditLog.objects.order_by("id"))
    rows[-1].action = "test.edited"
    assert verify_chain(rows) == second.pk


@pytest.mark.security
def test_orm_cannot_modify_audit_rows(user):
    entry = record_event("test.one", actor=user)
    with pytest.raises(PermissionError):
        entry.save()
    with pytest.raises(PermissionError):
        entry.delete()
    with pytest.raises(PermissionError):
        AuditLog.objects.filter(pk=entry.pk).update(action="x")
    with pytest.raises(PermissionError):
        AuditLog.objects.all().delete()


@pytest.mark.security
def test_database_trigger_blocks_raw_updates_and_deletes(user):
    entry = record_event("test.one", actor=user)
    for sql in (
        "UPDATE audit_auditlog SET action = 'x' WHERE id = %s",
        "DELETE FROM audit_auditlog WHERE id = %s",
    ):
        with pytest.raises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(sql, [entry.pk])
    assert AuditLog.objects.get(pk=entry.pk).action == "test.one"


@pytest.mark.security
@override_settings(BYTE_FORBIDDEN_BURST_THRESHOLD=3)
def test_burst_of_403_is_reported_once(client, customer):
    client.force_login(customer)
    for _ in range(5):
        assert client.get(reverse("panel:dashboard")).status_code == 403
    assert SecurityEvent.objects.filter(kind=SecurityEvent.Kind.FORBIDDEN_BURST).count() == 1
