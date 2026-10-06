"""Razorpay adapter (ADR-020; INTEGRATION_ARCHITECTURE section 4) and the gateway factory.

Orders API with Basic auth (key id and secret, server side only); hosted Checkout in the browser;
webhooks signed with HMAC-SHA256 of the raw body and the per-environment webhook secret; the
checkout callback signed with HMAC-SHA256 of "order_id|payment_id" and the key secret. Payment
capture is automatic per the account's dashboard setting (launch gate N-03).
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Any

import httpx

from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.payments import (
    GatewayError,
    GatewayEvent,
    GatewayOrder,
    GatewayPayment,
    GatewayRefund,
    PaymentGateway,
)

PAGE = 100


def hmac_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def signature_matches(secret: str, message: bytes, signature: str) -> bool:
    return hmac.compare_digest(hmac_hex(secret, message), signature or "")


def checkout_message(order_id: str, payment_id: str) -> bytes:
    return f"{order_id}|{payment_id}".encode()


def _notes(raw: Any) -> dict[str, str]:
    # Razorpay sends empty notes as a list.
    return {str(k): str(v) for k, v in raw.items()} if isinstance(raw, dict) else {}


def _time(raw: Any) -> datetime | None:
    return datetime.fromtimestamp(int(raw), tz=UTC) if raw else None


def payment_from(entity: dict[str, Any]) -> GatewayPayment:
    status = str(entity.get("status", "created"))
    return GatewayPayment(
        payment_id=str(entity["id"]),
        order_id=entity.get("order_id"),
        amount_paise=int(entity["amount"]),
        currency=str(entity.get("currency", "INR")),
        status=status
        if status in ("created", "authorized", "captured", "refunded", "failed")
        else "created",  # type: ignore[arg-type]
        captured=bool(entity.get("captured")) or status in ("captured", "refunded"),
        method=entity.get("method"),
        fee_paise=int(entity["fee"]) if entity.get("fee") is not None else None,
        tax_paise=int(entity["tax"]) if entity.get("tax") is not None else None,
        error_code=entity.get("error_code"),
        created_at=_time(entity.get("created_at")),
    )


def refund_from(entity: dict[str, Any]) -> GatewayRefund:
    status = str(entity.get("status", "pending"))
    return GatewayRefund(
        refund_id=str(entity["id"]),
        payment_id=str(entity["payment_id"]),
        amount_paise=int(entity["amount"]),
        status=status if status in ("pending", "processed", "failed") else "pending",  # type: ignore[arg-type]
        notes=_notes(entity.get("notes")),
    )


def event_from(body: bytes) -> GatewayEvent:
    data = json.loads(body)
    payload = data.get("payload") or {}
    payment = payload.get("payment", {}).get("entity") if isinstance(payload, dict) else None
    refund = payload.get("refund", {}).get("entity") if isinstance(payload, dict) else None
    return GatewayEvent(
        event_type=str(data.get("event", "")),
        payment=payment_from(payment) if payment else None,
        refund=refund_from(refund) if refund else None,
    )


class RazorpayGateway:
    name = "razorpay"
    configured = True

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        assert settings.payment_key_id  # noqa: S101 (Settings checks all three)
        assert settings.payment_key_secret  # noqa: S101
        assert settings.payment_webhook_secret  # noqa: S101
        self._key_id = settings.payment_key_id
        self._key_secret = settings.payment_key_secret.get_secret_value()
        self._webhook_secret = settings.payment_webhook_secret.get_secret_value()
        self._url = settings.razorpay_api_url.rstrip("/")
        self._timeout = settings.payment_timeout_seconds
        self._transport = transport  # tests only: a mock transport in place of the network

    @property
    def public_key_id(self) -> str:
        return self._key_id

    async def _call(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                auth=(self._key_id, self._key_secret),
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.request(method, f"{self._url}{path}", **kwargs)
        except httpx.HTTPError as exc:
            raise GatewayError(
                f"razorpay unreachable: {type(exc).__name__}", retryable=True
            ) from exc
        if response.status_code >= 400:
            retryable = response.status_code >= 500 or response.status_code == 429
            raise GatewayError(f"razorpay {response.status_code}", retryable=retryable)
        result: dict[str, Any] = response.json()
        return result

    async def create_order(
        self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]
    ) -> GatewayOrder:
        data = await self._call(
            "POST",
            "/orders",
            json={
                "amount": amount_paise,
                "currency": currency,
                "receipt": receipt[:40],
                "notes": notes,
            },
        )
        return GatewayOrder(str(data["id"]), int(data["amount"]), str(data["currency"]))

    async def order_payments(self, provider_order_id: str) -> list[GatewayPayment]:
        data = await self._call("GET", f"/orders/{provider_order_id}/payments")
        return [payment_from(item) for item in data.get("items", [])]

    async def payments_between(self, start: datetime, end: datetime) -> list[GatewayPayment]:
        found: list[GatewayPayment] = []
        skip = 0
        while True:
            data = await self._call(
                "GET",
                "/payments",
                params={
                    "from": int(start.timestamp()),
                    "to": int(end.timestamp()),
                    "count": PAGE,
                    "skip": skip,
                },
            )
            items = data.get("items", [])
            found.extend(payment_from(item) for item in items)
            if len(items) < PAGE:
                return found
            skip += PAGE

    async def create_refund(
        self, *, payment_id: str, amount_paise: int, notes: dict[str, str]
    ) -> GatewayRefund:
        data = await self._call(
            "POST", f"/payments/{payment_id}/refund", json={"amount": amount_paise, "notes": notes}
        )
        return refund_from(data)

    async def payment_refunds(self, payment_id: str) -> list[GatewayRefund]:
        data = await self._call("GET", f"/payments/{payment_id}/refunds")
        return [refund_from(item) for item in data.get("items", [])]

    def verify_checkout_signature(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        return signature_matches(
            self._key_secret, checkout_message(order_id, payment_id), signature
        )

    def verify_webhook_signature(self, *, body: bytes, signature: str) -> bool:
        return signature_matches(self._webhook_secret, body, signature)

    def parse_event(self, body: bytes) -> GatewayEvent:
        return event_from(body)


class NoGateway:
    """Buying is off (`P2B_PAYMENT_PROVIDER=none`)."""

    name = "none"
    configured = False
    public_key_id = ""

    async def create_order(self, **_: Any) -> GatewayOrder:
        raise GatewayError("no payment provider is configured", retryable=False)

    async def order_payments(self, provider_order_id: str) -> list[GatewayPayment]:
        return []

    async def payments_between(self, start: datetime, end: datetime) -> list[GatewayPayment]:
        return []

    async def create_refund(self, **_: Any) -> GatewayRefund:
        raise GatewayError("no payment provider is configured", retryable=False)

    async def payment_refunds(self, payment_id: str) -> list[GatewayRefund]:
        return []

    def verify_checkout_signature(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        return False

    def verify_webhook_signature(self, *, body: bytes, signature: str) -> bool:
        return False

    def parse_event(self, body: bytes) -> GatewayEvent:
        raise GatewayError("no payment provider is configured", retryable=False)


def build_payment_gateway(settings: Settings, database: Database) -> PaymentGateway:
    if settings.payment_provider == "razorpay":
        return RazorpayGateway(settings)
    if settings.payment_provider == "fake":
        from p2b.integrations.fake_gateway import FakeGateway

        return FakeGateway(settings, database)
    return NoGateway()
