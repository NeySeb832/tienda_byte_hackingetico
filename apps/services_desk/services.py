"""Repair tickets: intake, diagnosis and quote, customer approval, repair and delivery."""

import secrets
from datetime import timedelta
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.core.money import to_money
from apps.services_desk.models import ServiceTicket, TechnicalService, TicketEvent

S = ServiceTicket.Status
WARRANTY_DAYS = 90
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I to avoid confusion when dictated

STAFF_TRANSITIONS: dict[str, set[str]] = {
    S.RECEIVED: {S.DIAGNOSING, S.CANCELLED},
    S.DIAGNOSING: {S.QUOTED, S.CANCELLED},
    S.QUOTED: {S.CANCELLED},  # the customer approves or rejects the quote
    S.REPAIRING: {S.READY},
    S.READY: {S.DELIVERED},
    S.DELIVERED: set(),
    S.CANCELLED: set(),
}


def new_code() -> str:
    return "ST-" + "".join(secrets.choice(ALPHABET) for _ in range(8))


def _event(ticket: ServiceTicket, note: str, actor: Any) -> None:
    TicketEvent.objects.create(
        ticket=ticket,
        status=ticket.status,
        note=note[:255],
        actor=actor if getattr(actor, "pk", None) else None,
    )


@transaction.atomic
def open_ticket(
    *,
    store: Any,
    actor: Any,
    customer_name: str,
    customer_email: str,
    device: str,
    issue: str,
    serial_number: str = "",
    service: TechnicalService | None = None,
    customer: Any = None,
) -> ServiceTicket:
    if not device.strip() or not issue.strip():
        raise ValidationError("Indica el equipo y la falla.")
    ticket = ServiceTicket.objects.create(
        code=new_code(),
        store=store,
        customer=customer,
        customer_name=customer_name.strip()[:120],
        customer_email=customer_email.strip().lower(),
        device=device.strip()[:120],
        serial_number=serial_number.strip()[:60],
        issue=issue.strip()[:1000],
        service=service,
        quote=service.price if service else None,
    )
    _event(ticket, "Equipo recibido en tienda", actor)
    record_event(
        "services.ticket_opened", actor=actor, target=ticket, changes={"code": ticket.code}
    )
    return ticket


@transaction.atomic
def advance(
    ticket: ServiceTicket,
    to_status: str,
    *,
    actor: Any,
    note: str = "",
    diagnosis: str = "",
    quote: Any = None,
) -> ServiceTicket:
    locked = ServiceTicket.objects.select_for_update().get(pk=ticket.pk)
    if to_status not in STAFF_TRANSITIONS.get(locked.status, set()):
        raise ValidationError("Cambio de estado no permitido.")
    if to_status == S.QUOTED:
        if quote is None:
            raise ValidationError("Indica la cotización.")
        value = to_money(quote)
        if value < 0:
            raise ValidationError("La cotización no puede ser negativa.")
        locked.quote = value
        locked.diagnosis = diagnosis.strip()[:1000]
    if to_status == S.DIAGNOSING:
        locked.technician = actor
    if to_status == S.DELIVERED:
        locked.warranty_until = timezone.localdate() + timedelta(days=WARRANTY_DAYS)
    locked.status = to_status
    locked.save()
    _event(locked, note, actor)
    record_event("services.ticket_status", actor=actor, target=locked, changes={"to": to_status})
    if to_status in (S.QUOTED, S.READY):
        from apps.notifications.tasks import send_ticket_email

        transaction.on_commit(lambda: send_ticket_email.delay(str(locked.public_id)))
    return locked


@transaction.atomic
def answer_quote(ticket: ServiceTicket, *, approve: bool, actor: Any = None) -> ServiceTicket:
    """The customer approves (repair starts) or rejects (equipment is returned) the quote."""
    locked = ServiceTicket.objects.select_for_update().get(pk=ticket.pk)
    if locked.status != S.QUOTED:
        raise ValidationError("La orden no tiene una cotización pendiente.")
    locked.status = S.REPAIRING if approve else S.CANCELLED
    locked.save(update_fields=["status", "updated_at"])
    _event(
        locked,
        (
            "Cotización aprobada por el cliente"
            if approve
            else "Cotización rechazada: se devuelve el equipo"
        ),
        actor,
    )
    record_event(
        "services.quote_answered", actor=actor, target=locked, changes={"approved": approve}
    )
    return locked


def ticket_by_code(code: str, email: str) -> ServiceTicket | None:
    """Public tracking needs both the code and the email (the code alone is not enough)."""
    return (
        ServiceTicket.objects.filter(
            code=code.strip().upper()[:12], customer_email=email.strip().lower()[:254]
        )
        .select_related("store", "service")
        .first()
    )
