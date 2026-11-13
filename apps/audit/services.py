"""Business logic (write side) for the audit app.

``record_event`` appends a hash-chained audit row; ``record_security_event`` stores a
security event and, for serious ones, alerts the superadmins asynchronously.
"""

import hashlib
import json
import logging
from collections.abc import Iterable
from typing import Any

from django.db import connection, transaction
from django.db.models import Model
from django.http import HttpRequest

from apps.audit.models import AuditLog, SecurityEvent
from apps.core.logging import current_request_id, mask_sensitive

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64
CHAIN_LOCK_ID = 74_210_903  # pg_advisory_xact_lock key: one writer extends the chain at a time


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    return f"{local[:1]}***@{domain}"


def client_ip(request: HttpRequest | None) -> str | None:
    if request is None:
        return None
    from axes.helpers import get_client_ip_address

    return get_client_ip_address(request) or None


def _user_agent(request: HttpRequest | None) -> str:
    return (request.META.get("HTTP_USER_AGENT", "") if request else "")[:255]


def _payload(entry: AuditLog) -> str:
    data = {
        "created_at": entry.created_at.isoformat(),
        "actor_id": entry.actor_id,
        "actor_repr": entry.actor_repr,
        "action": entry.action,
        "target_type": entry.target_type,
        "target_id": entry.target_id,
        "target_repr": entry.target_repr,
        "changes": entry.changes,
        "ip": entry.ip,
        "user_agent": entry.user_agent,
        "request_id": entry.request_id,
        "prev_hash": entry.prev_hash,
    }
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def compute_hash(entry: AuditLog) -> str:
    return hashlib.sha256(_payload(entry).encode()).hexdigest()


def record_event(
    action: str,
    *,
    actor: Any = None,
    target: Model | None = None,
    changes: dict[str, Any] | None = None,
    request: HttpRequest | None = None,
) -> AuditLog:
    """Append an audit row. Sensitive values in ``changes`` are masked."""
    actor = actor if getattr(actor, "is_authenticated", False) else None
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [CHAIN_LOCK_ID])
        previous = AuditLog.objects.order_by("-id").values_list("row_hash", flat=True).first()
        entry = AuditLog(
            actor=actor,
            actor_repr=mask_email(actor.email) if actor else "sistema",
            action=action,
            target_type=target._meta.label if target is not None else "",
            target_id=str(getattr(target, "public_id", "") or getattr(target, "pk", "") or ""),
            target_repr=str(target)[:255] if target is not None else "",
            changes=mask_sensitive(changes or {}),
            ip=client_ip(request),
            user_agent=_user_agent(request),
            request_id=current_request_id(),
            prev_hash=previous or GENESIS_HASH,
        )
        entry.row_hash = compute_hash(entry)
        entry.save()
    return entry


def verify_chain(entries: Iterable[AuditLog] | None = None) -> int | None:
    """Return the id of the first tampered/broken row, or ``None`` if the chain is intact."""
    rows = entries if entries is not None else AuditLog.objects.order_by("id").iterator()
    previous = GENESIS_HASH
    for entry in rows:
        if entry.prev_hash != previous or compute_hash(entry) != entry.row_hash:
            return entry.pk
        previous = entry.row_hash
    return None


ALERT_KINDS = frozenset(
    {
        SecurityEvent.Kind.LOCKOUT,
        SecurityEvent.Kind.FORBIDDEN_BURST,
        SecurityEvent.Kind.ROLE_ESCALATION,
        SecurityEvent.Kind.MASS_EXPORT,
    }
)


def record_security_event(
    kind: str,
    severity: str,
    *,
    user: Any = None,
    request: HttpRequest | None = None,
    details: dict[str, Any] | None = None,
) -> SecurityEvent:
    user = user if getattr(user, "pk", None) else None
    event = SecurityEvent.objects.create(
        kind=kind,
        severity=severity,
        user=user,
        ip=client_ip(request),
        details=mask_sensitive(details or {}),
    )
    logger.warning(
        "Security event",
        extra={"event_kind": kind, "severity": severity, "event": str(event.public_id)},
    )
    if kind in ALERT_KINDS:
        from apps.audit.tasks import send_security_alert

        transaction.on_commit(lambda: send_security_alert.delay(event.pk))
    return event
