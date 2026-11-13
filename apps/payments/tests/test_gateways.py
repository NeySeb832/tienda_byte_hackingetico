"""Gateway signatures (Wompi integrity + events) and webhook processing (idempotent, fail closed)."""

import hashlib
import json
from decimal import Decimal

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.audit.models import SecurityEvent
from apps.cart import services as cart_services
from apps.orders import services as orders
from apps.orders.models import Order
from apps.payments import services
from apps.payments.gateways import FakeGateway, InvalidSignatureError, WompiGateway
from apps.payments.models import Payment, WebhookEvent
from tests.factories import make_product, make_store, make_user

WOMPI = {
    "BYTE_PAYMENT_GATEWAY": "wompi",
    "WOMPI_PUBLIC_KEY": "pub_test_123",
    "WOMPI_INTEGRITY_SECRET": "test_integrity_abc",
    "WOMPI_EVENTS_SECRET": "test_events_xyz",
}


def wompi_event(
    reference: str,
    cents: int,
    status: str = "APPROVED",
    secret: str = "test_events_xyz",  # noqa: S107 - test value
) -> bytes:
    transaction = {
        "id": "1234-1610641025-49201",
        "status": status,
        "amount_in_cents": cents,
        "reference": reference,
    }
    timestamp = 1730000000
    checksum = hashlib.sha256(
        f"{transaction['id']}{status}{cents}{timestamp}{secret}".encode()
    ).hexdigest()
    return json.dumps(
        {
            "event": "transaction.updated",
            "data": {"transaction": transaction},
            "timestamp": timestamp,
            "signature": {
                "properties": [
                    "transaction.id",
                    "transaction.status",
                    "transaction.amount_in_cents",
                ],
                "checksum": checksum,
            },
        }
    ).encode()


@override_settings(**WOMPI)
def test_wompi_checkout_url_carries_the_integrity_signature():
    url = WompiGateway().checkout_url(
        reference="BYT-1", amount=Decimal("2750000"), email="a@b.co", redirect_url="https://x/"
    )
    expected = hashlib.sha256(b"BYT-1275000000COPtest_integrity_abc").hexdigest()
    assert f"signature%3Aintegrity={expected}" in url
    assert "amount-in-cents=275000000" in url
    assert "test_integrity_abc" not in url  # the secret never leaves the server


@override_settings(**WOMPI)
def test_wompi_event_signature():
    result = WompiGateway().parse_event(wompi_event("BYT-1", 100), {})
    assert (result.reference, result.status, result.amount_in_cents) == ("BYT-1", "approved", 100)
    with pytest.raises(InvalidSignatureError):
        WompiGateway().parse_event(wompi_event("BYT-1", 100, secret="otra"), {})
    tampered = json.loads(wompi_event("BYT-1", 100))
    tampered["data"]["transaction"]["amount_in_cents"] = 1
    with pytest.raises(InvalidSignatureError):
        WompiGateway().parse_event(json.dumps(tampered).encode(), {})
    with pytest.raises(InvalidSignatureError):
        WompiGateway().parse_event(b"no es json", {})


def test_fake_gateway_rejects_unsigned_events():
    body, signature = FakeGateway().sign({"event_id": "1"})
    with pytest.raises(InvalidSignatureError):
        FakeGateway().parse_event(body, {"x-fake-signature": "0" * 64})
    with pytest.raises(InvalidSignatureError):
        FakeGateway().parse_event(body, {"x-fake-signature": signature})  # signed but malformed


@pytest.fixture
def pending_payment(db):
    store = make_store(is_pickup_point=True)
    variant = make_product("Consola", store=store).variants.get()
    user = make_user()
    cart = cart_services.get_cart({}, user, create=True)
    assert cart is not None
    cart_services.add_item(cart, variant, 1)
    order = orders.place_order(
        user=user,
        cart=cart,
        fulfillment=Order.Fulfillment.PICKUP,
        pickup_store=store,
        accepted_terms=True,
    )
    payment, _ = services.start_payment(order, redirect_url="http://testserver/")
    return payment


@pytest.mark.django_db
@override_settings(**WOMPI)
def test_webhook_end_to_end_and_idempotent(client, pending_payment):
    body = wompi_event(pending_payment.reference, 10000000)
    url = reverse("payments:webhook")
    response = client.post(url, body, content_type="application/json")
    assert response.status_code == 200
    assert response.json()["detail"] == "aprobado"
    again = client.post(url, body, content_type="application/json")
    assert again.json()["detail"] == "evento duplicado"
    assert WebhookEvent.objects.count() == 1
    pending_payment.refresh_from_db()
    assert pending_payment.status == Payment.Status.APPROVED
    assert pending_payment.order.status == Order.Status.PAID


@pytest.mark.django_db
@override_settings(**WOMPI)
def test_webhook_with_bad_signature_is_rejected_and_logged(client, pending_payment):
    body = wompi_event(pending_payment.reference, 10000000, secret="adivinada")
    response = client.post(reverse("payments:webhook"), body, content_type="application/json")
    assert response.status_code == 400
    assert SecurityEvent.objects.filter(kind="webhook_invalid_signature").exists()
    pending_payment.refresh_from_db()
    assert pending_payment.status == Payment.Status.PENDING


@pytest.mark.django_db
@override_settings(**WOMPI)
def test_amount_mismatch_fails_closed(client, pending_payment):
    body = wompi_event(pending_payment.reference, 100)  # paid 1 peso for a 100.000 order
    response = client.post(reverse("payments:webhook"), body, content_type="application/json")
    assert response.json()["detail"] == "monto no coincide"
    pending_payment.refresh_from_db()
    assert pending_payment.status == Payment.Status.ERROR
    assert pending_payment.order.status == Order.Status.PENDING_PAYMENT
    assert SecurityEvent.objects.filter(kind="payment_amount_mismatch").exists()


@pytest.mark.django_db
@override_settings(**WOMPI)
def test_unknown_reference_and_oversized_body(client, db):
    response = client.post(
        reverse("payments:webhook"), wompi_event("NO-EXISTE", 1), content_type="application/json"
    )
    assert response.json()["detail"] == "referencia desconocida"
    huge = b"{" + b" " * (70 * 1024) + b"}"
    assert (
        client.post(reverse("payments:webhook"), huge, content_type="application/json").status_code
        == 413
    )
    assert client.get(reverse("payments:webhook")).status_code == 405


@pytest.mark.django_db
def test_sync_from_gateway_rejects_foreign_references(pending_payment, monkeypatch):
    from apps.payments import gateways

    def fake_fetch(self, transaction_id):
        return gateways.GatewayResult(
            "q", "query", "BYT-OTRO-PEDIDO", transaction_id, "approved", 1, {}
        )

    monkeypatch.setattr(gateways.FakeGateway, "fetch_transaction", fake_fetch)
    assert services.sync_from_gateway(pending_payment.order, "abc") == "referencia ajena"
    assert SecurityEvent.objects.filter(kind="payment_reference_mismatch").exists()
