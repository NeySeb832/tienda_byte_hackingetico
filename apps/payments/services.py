"""Payments: start a payment, process gateway notifications (idempotent), fail closed.

A gateway result is applied only if the reference exists, the payment is not final yet and
the amount matches the order total exactly; otherwise it is rejected and logged as a
security event. Approval consumes the reserved stock, issues the invoice and emails the
customer (after commit).
"""

import secrets
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import record_event, record_security_event
from apps.cart.models import Cart
from apps.inventory import services as inventory
from apps.orders import services as orders
from apps.orders.models import Order
from apps.payments.gateways import GatewayResult, InvalidSignatureError, get_gateway, to_cents
from apps.payments.models import Payment, WebhookEvent

P = Payment.Status


def start_payment(order: Order, *, redirect_url: str) -> tuple[Payment, str]:
    """Create the payment and return the gateway URL the customer is sent to."""
    if not order.is_open_for_payment:
        raise ValueError("El pedido ya no admite pagos.")
    gateway = get_gateway()
    payment = Payment.objects.create(
        order=order,
        reference=f"{order.number}-{secrets.token_hex(4).upper()}",
        gateway=gateway.name,
        amount=order.total,
    )
    url = gateway.checkout_url(
        reference=payment.reference,
        amount=payment.amount,
        email=order.email,
        redirect_url=redirect_url,
    )
    record_event(
        "payments.started", actor=order.user, target=payment, changes={"amount": str(order.total)}
    )
    return payment, url


def _notify(order: Order, kind: str) -> None:
    from apps.notifications.tasks import send_order_email

    transaction.on_commit(lambda: send_order_email.delay(str(order.public_id), kind))


@transaction.atomic
def apply_result(result: GatewayResult) -> str:
    """Apply a verified gateway result. Returns a short description of what happened."""
    payment = (
        Payment.objects.select_for_update()
        .select_related("order")
        .filter(reference=result.reference)
        .first()
    )
    if payment is None:
        record_security_event(
            "payment_unknown_reference", "medium", details={"reference": result.reference[:64]}
        )
        return "referencia desconocida"
    if payment.status in Payment.FINAL:
        return "ya procesado"
    if result.status == P.PENDING:
        return "pendiente"
    order = payment.order
    payment.gateway_txn_id = result.transaction_id[:64]
    if result.status == P.APPROVED and result.amount_in_cents != to_cents(payment.amount):
        payment.status = P.ERROR
        payment.status_message = "El monto notificado no coincide con el pedido"
        payment.save(update_fields=["status", "status_message", "gateway_txn_id", "updated_at"])
        record_security_event(
            "payment_amount_mismatch",
            "high",
            user=order.user,
            details={
                "order": order.number,
                "expected": to_cents(payment.amount),
                "got": result.amount_in_cents,
            },
        )
        return "monto no coincide"
    if result.status == P.APPROVED:
        if order.status != Order.Status.PENDING_PAYMENT:
            # Paid after expiry: keep the money traceable for a manual refund (fail closed).
            payment.status = P.APPROVED
            payment.status_message = "Aprobado con el pedido vencido: requiere reembolso"
            payment.approved_at = timezone.now()
            payment.save(
                update_fields=[
                    "status",
                    "status_message",
                    "approved_at",
                    "gateway_txn_id",
                    "updated_at",
                ]
            )
            record_security_event(
                "payment_after_expiry", "medium", user=order.user, details={"order": order.number}
            )
            return "aprobado tarde"
        payment.status = P.APPROVED
        payment.approved_at = timezone.now()
        payment.save(update_fields=["status", "approved_at", "gateway_txn_id", "updated_at"])
        inventory.consume_reservations(order)
        orders.transition(order, Order.Status.PAID, note=f"Pago {payment.reference} aprobado")
        orders.issue_invoice(order)
        Cart.objects.filter(user=order.user, status=Cart.Status.OPEN).update(
            status=Cart.Status.CONVERTED
        )
        _notify(order, "paid")
        record_event("payments.approved", actor=order.user, target=payment)
        return "aprobado"
    payment.status = result.status
    payment.status_message = (
        "Rechazado por la entidad" if result.status == P.DECLINED else "No se completó"
    )
    payment.save(update_fields=["status", "status_message", "gateway_txn_id", "updated_at"])
    if order.status == Order.Status.PENDING_PAYMENT:
        inventory.release_reservations(order)
        orders.transition(
            order, Order.Status.PAYMENT_FAILED, note=f"Pago {payment.reference}: {result.status}"
        )
    record_event(
        "payments.failed", actor=order.user, target=payment, changes={"status": result.status}
    )
    return "rechazado"


def process_notification(body: bytes, headers: dict[str, str]) -> tuple[int, str]:
    """Webhook entry point. Returns (HTTP status, message)."""
    gateway = get_gateway()
    try:
        result = gateway.parse_event(body, headers)
    except InvalidSignatureError:
        record_security_event(
            "webhook_invalid_signature",
            "high",
            details={"gateway": gateway.name, "size": len(body)},
        )
        return 400, "firma inválida"
    try:
        with transaction.atomic():
            event = WebhookEvent.objects.create(
                gateway=gateway.name,
                event_id=result.event_id[:128],
                event_type=result.event_type[:60],
                signature_valid=True,
                payload=result.payload,
            )
    except IntegrityError:
        return 200, "evento duplicado"
    outcome = apply_result(result)
    WebhookEvent.objects.filter(pk=event.pk).update(processed_at=timezone.now(), result=outcome)
    return 200, outcome


def sync_from_gateway(order: Order, transaction_id: str) -> str:
    """Return page: ask the gateway (server to server) instead of trusting the query string."""
    gateway = get_gateway()
    result = gateway.fetch_transaction(transaction_id)
    if not result.reference.startswith(order.number):
        record_security_event(
            "payment_reference_mismatch", "high", user=order.user, details={"order": order.number}
        )
        return "referencia ajena"
    return apply_result(result)


def simulate(payment: Payment, *, approve: bool) -> str:
    """FakeGateway only: emit the signed event the simulator page represents."""
    from apps.payments.gateways import FakeGateway

    gateway = FakeGateway()
    body, signature = gateway.sign(
        {
            "event_id": f"fake:{payment.reference}:{'APPROVED' if approve else 'DECLINED'}",
            "reference": payment.reference,
            "transaction_id": f"FAKE-{secrets.token_hex(6).upper()}",
            "status": "APPROVED" if approve else "DECLINED",
            "amount_in_cents": to_cents(Decimal(payment.amount)),
        }
    )
    return process_notification(body, {"x-fake-signature": signature})[1]
