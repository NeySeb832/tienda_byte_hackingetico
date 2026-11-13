"""Payment gateways behind one interface (ADR-0007).

* ``WompiGateway``: Wompi sandbox. Web Checkout with integrity signature, transaction lookup
  and event verification (SHA-256 checksum over the listed properties + timestamp + secret).
* ``FakeGateway``: deterministic, no network. Used in development and tests; its "checkout"
  is an internal simulator page and its events are signed with HMAC-SHA256.

Card data never touches Byte: the customer pays on the gateway's page.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.urls import reverse
from django.utils.crypto import constant_time_compare

STATUS_MAP = {
    "APPROVED": "approved",
    "DECLINED": "declined",
    "VOIDED": "voided",
    "ERROR": "error",
    "PENDING": "pending",
}


class InvalidSignatureError(Exception):
    """The notification is not authentic (wrong checksum, missing fields or stale)."""


class GatewayError(Exception):
    """The gateway could not be reached or answered something unexpected."""


@dataclass(frozen=True, slots=True)
class GatewayResult:
    event_id: str
    event_type: str
    reference: str
    transaction_id: str
    status: str  # one of Payment.Status values
    amount_in_cents: int
    payload: dict[str, Any]


def to_cents(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value())


class PaymentGateway(Protocol):
    name: str

    def checkout_url(
        self, *, reference: str, amount: Decimal, email: str, redirect_url: str
    ) -> str: ...

    def fetch_transaction(self, transaction_id: str) -> GatewayResult: ...

    def parse_event(self, body: bytes, headers: dict[str, str]) -> GatewayResult: ...


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class WompiGateway:
    name = "wompi"

    def __init__(self) -> None:
        self.public_key = settings.WOMPI_PUBLIC_KEY
        self.integrity_secret = settings.WOMPI_INTEGRITY_SECRET
        self.events_secret = settings.WOMPI_EVENTS_SECRET
        self.api_url = settings.WOMPI_API_URL
        self.checkout_base = settings.WOMPI_CHECKOUT_URL

    def checkout_url(
        self, *, reference: str, amount: Decimal, email: str, redirect_url: str
    ) -> str:
        cents = to_cents(amount)
        signature = _sha256(f"{reference}{cents}COP{self.integrity_secret}")
        query = urlencode(
            {
                "public-key": self.public_key,
                "currency": "COP",
                "amount-in-cents": cents,
                "reference": reference,
                "signature:integrity": signature,
                "redirect-url": redirect_url,
                "customer-data:email": email,
            }
        )
        return f"{self.checkout_base}?{query}"

    def fetch_transaction(self, transaction_id: str) -> GatewayResult:
        if not transaction_id.replace("-", "").isalnum() or len(transaction_id) > 64:
            raise GatewayError("Identificador de transacción inválido.")
        try:
            response = httpx.get(
                f"{self.api_url}/transactions/{transaction_id}",
                headers={"Authorization": f"Bearer {self.public_key}"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()["data"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise GatewayError("No fue posible consultar la transacción.") from exc
        return GatewayResult(
            event_id=f"query:{data['id']}:{data['status']}",
            event_type="transaction.query",
            reference=str(data["reference"]),
            transaction_id=str(data["id"]),
            status=STATUS_MAP.get(str(data["status"]), "error"),
            amount_in_cents=int(data["amount_in_cents"]),
            payload={"id": data["id"], "status": data["status"]},
        )

    def parse_event(self, body: bytes, headers: dict[str, str]) -> GatewayResult:
        try:
            event = json.loads(body)
            signature = event["signature"]
            properties: list[str] = signature["properties"]
            data = event["data"]
            values = []
            for path in properties:
                node: Any = data
                for key in path.split("."):
                    node = node[key]
                values.append(str(node))
            timestamp = str(event["timestamp"])
            expected = _sha256("".join(values) + timestamp + self.events_secret)
            given = str(headers.get("x-event-checksum") or signature["checksum"])
            transaction = data["transaction"]
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidSignatureError("Evento mal formado.") from exc
        if not constant_time_compare(expected, given.lower()):
            raise InvalidSignatureError("Firma inválida.")
        return GatewayResult(
            event_id=f"{transaction['id']}:{transaction['status']}:{timestamp}",
            event_type=str(event.get("event", "")),
            reference=str(transaction["reference"]),
            transaction_id=str(transaction["id"]),
            status=STATUS_MAP.get(str(transaction["status"]), "error"),
            amount_in_cents=int(transaction["amount_in_cents"]),
            payload=event,
        )


class FakeGateway:
    """Deterministic gateway for development and tests (no network)."""

    name = "fake"

    @staticmethod
    def _secret() -> bytes:
        return hashlib.sha256(f"fake-gateway:{settings.SECRET_KEY}".encode()).digest()

    def sign(self, payload: dict[str, Any]) -> tuple[bytes, str]:
        body = json.dumps(payload, sort_keys=True).encode()
        return body, hmac.new(self._secret(), body, hashlib.sha256).hexdigest()

    def checkout_url(
        self, *, reference: str, amount: Decimal, email: str, redirect_url: str
    ) -> str:
        return reverse("payments:simulator", args=[reference])

    def fetch_transaction(self, transaction_id: str) -> GatewayResult:
        raise GatewayError("La pasarela de pruebas solo notifica por eventos.")

    def parse_event(self, body: bytes, headers: dict[str, str]) -> GatewayResult:
        expected = hmac.new(self._secret(), body, hashlib.sha256).hexdigest()
        if not constant_time_compare(expected, headers.get("x-fake-signature", "")):
            raise InvalidSignatureError("Firma inválida.")
        try:
            data = json.loads(body)
            return GatewayResult(
                event_id=str(data["event_id"]),
                event_type="transaction.updated",
                reference=str(data["reference"]),
                transaction_id=str(data["transaction_id"]),
                status=STATUS_MAP[str(data["status"])],
                amount_in_cents=int(data["amount_in_cents"]),
                payload=data,
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise InvalidSignatureError("Evento mal formado.") from exc


def get_gateway() -> PaymentGateway:
    if settings.BYTE_PAYMENT_GATEWAY == "wompi":
        return WompiGateway()
    return FakeGateway()
