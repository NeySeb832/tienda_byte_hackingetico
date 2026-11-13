"""Customer emails sent by Celery (JSON arguments only, ADR-0009)."""

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import F, Sum
from django.db.models.functions import Coalesce
from django.template.loader import render_to_string
from django.utils import timezone

from apps.orders.models import Order

SUBJECTS = {
    "paid": "Recibimos tu pago · pedido {number}",
}


def _send(subject: str, template: str, context: dict, to: str) -> None:
    context = {**context, "site_url": settings.BYTE_SITE_URL.rstrip("/")}
    message = EmailMultiAlternatives(
        subject=f"{settings.ACCOUNT_EMAIL_SUBJECT_PREFIX}{subject}",
        body=render_to_string(f"notifications/email/{template}.txt", context),
        to=[to],
    )
    message.attach_alternative(
        render_to_string(f"notifications/email/{template}.html", context), "text/html"
    )
    message.send()


@shared_task(
    name="notifications.send_order_email",
    autoretry_for=(OSError,),
    retry_backoff=True,
    max_retries=5,
)
def send_order_email(order_public_id: str, kind: str) -> bool:
    if kind not in SUBJECTS:
        return False
    order = (
        Order.objects.select_related("pickup_store", "invoice")
        .prefetch_related("lines")
        .filter(public_id=order_public_id)
        .first()
    )
    if order is None or not order.email:
        return False
    _send(
        SUBJECTS[kind].format(number=order.number), f"order_{kind}", {"order": order}, order.email
    )
    return True


@shared_task(
    name="notifications.send_ticket_email",
    autoretry_for=(OSError,),
    retry_backoff=True,
    max_retries=5,
)
def send_ticket_email(ticket_public_id: str) -> bool:
    from apps.services_desk.models import ServiceTicket

    ticket = (
        ServiceTicket.objects.select_related("store").filter(public_id=ticket_public_id).first()
    )
    if ticket is None:
        return False
    _send(
        f"Tu orden de servicio {ticket.code}: {ticket.get_status_display().lower()}",
        "ticket_update",
        {"ticket": ticket},
        ticket.customer_email,
    )
    return True


@shared_task(name="notifications.process_alerts")
def process_alerts(variant_id: int) -> int:
    """Notify pending alerts of a variant whose condition is now met. Each alert fires once."""
    from apps.catalog.models import ProductVariant
    from apps.notifications.models import ProductAlert

    variant = (
        ProductVariant.objects.select_related("product")
        .annotate(free=Coalesce(Sum(F("stock_items__quantity") - F("stock_items__reserved")), 0))
        .filter(pk=variant_id, is_active=True, product__is_active=True)
        .first()
    )
    if variant is None:
        return 0
    sent = 0
    pending = ProductAlert.objects.filter(variant=variant, notified_at=None).select_related("user")
    for alert in pending:
        if alert.kind == ProductAlert.Kind.BACK_IN_STOCK and variant.free <= 0:
            continue
        if alert.kind == ProductAlert.Kind.PRICE_DROP and variant.price >= alert.price_at_signup:
            continue
        # Mark first: a crash after sending never sends twice (at most once delivery).
        if not ProductAlert.objects.filter(pk=alert.pk, notified_at=None).update(
            notified_at=timezone.now()
        ):
            continue
        _send(
            f"{variant.product.name}: {'¡ya está disponible!' if alert.kind == 'stock' else '¡bajó de precio!'}",
            "product_alert",
            {"alert": alert, "variant": variant},
            alert.user.email,
        )
        sent += 1
    return sent
