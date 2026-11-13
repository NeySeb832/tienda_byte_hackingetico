"""Celery tasks of the audit app."""

from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from apps.audit.models import SecurityEvent


@shared_task(name="audit.send_security_alert")
def send_security_alert(event_id: int) -> int:
    """Email every active superadmin about a serious security event."""
    event = SecurityEvent.objects.filter(pk=event_id, alerted_at__isnull=True).first()
    if event is None:
        return 0
    recipients = list(
        get_user_model()
        .objects.filter(is_superuser=True, is_active=True)
        .values_list("email", flat=True)
    )
    if recipients:
        send_mail(
            subject=f"[Byte] Alerta de seguridad: {event.get_kind_display()}",
            message=(
                f"Evento: {event.get_kind_display()}\n"
                f"Severidad: {event.get_severity_display()}\n"
                f"Fecha: {timezone.localtime(event.created_at):%Y-%m-%d %H:%M:%S}\n"
                f"Referencia: {event.public_id}\n\n"
                "Revisa el detalle en Panel > Eventos de seguridad."
            ),
            from_email=None,
            recipient_list=recipients,
        )
    SecurityEvent.objects.filter(pk=event.pk).update(alerted_at=timezone.now())
    return len(recipients)
