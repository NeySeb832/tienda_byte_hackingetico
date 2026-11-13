"""Customer emails sent by Celery (JSON arguments only, ADR-0009)."""

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from apps.orders.models import Order

SUBJECTS = {
    "paid": "Recibimos tu pago · pedido {number}",
}


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
    if order is None:
        return False
    context = {"order": order, "site_url": settings.BYTE_SITE_URL.rstrip("/")}
    message = EmailMultiAlternatives(
        subject=f"{settings.ACCOUNT_EMAIL_SUBJECT_PREFIX}{SUBJECTS[kind].format(number=order.number)}",
        body=render_to_string(f"notifications/email/order_{kind}.txt", context),
        to=[order.email],
    )
    message.attach_alternative(
        render_to_string(f"notifications/email/order_{kind}.html", context), "text/html"
    )
    message.send()
    return True
