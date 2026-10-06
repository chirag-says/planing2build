"""The fake payment gateway for local development and tests (Slice 3.3). Never in staging or
production (Settings refuses it). It behaves like Razorpay where billing can tell the
difference: provider orders and payments live outside billing's tables (here in
`fake_gateway_records`, shared by the API and the worker), webhooks are signed with the
configured webhook secret, and the checkout callback with the key secret, so billing's
verification code runs unchanged. No money moves.

`simulate_payment` and `signed_webhook` stand in for the shopper and for Razorpay's servers.
"""

import json
import secrets
import time
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.config import Settings
from p2b.core.db import Base, Database
from p2b.core.payments import (
    GatewayError,
    GatewayEvent,
    GatewayOrder,
    GatewayPayment,
    GatewayRefund,
    PaymentStatus,
)
from p2b.integrations.razorpay import (
    checkout_message,
    event_from,
    hmac_hex,
    payment_from,
    refund_from,
    signature_matches,
)


class FakeGatewayRecord(Base):
    """Provider-side state of the fake gateway: orders, payments and refunds as Razorpay would
    hold them. Empty outside local development and tests."""

    __tablename__ = "fake_gateway_records"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    parent_id: Mapped[str | None] = mapped_column(String(40), index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(12))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


def _id(prefix: str) -> str:
    return f"{prefix}_fake{secrets.token_hex(7)}"


def _payment_entity(record: FakeGatewayRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "entity": "payment",
        "order_id": record.parent_id,
        "amount": record.amount_paise,
        "currency": record.currency,
        "status": record.status,
        "captured": record.status == "captured",
        "method": record.data.get("method", "upi"),
        "fee": 0,
        "tax": 0,
        "error_code": record.data.get("error_code"),
        "created_at": int(record.created_at.timestamp()),
    }


def _refund_entity(record: FakeGatewayRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "entity": "refund",
        "payment_id": record.parent_id,
        "amount": record.amount_paise,
        "status": record.status,
        "notes": record.data.get("notes") or [],
    }


class FakeGateway:
    name = "fake"
    configured = True

    def __init__(self, settings: Settings, database: Database):
        assert settings.payment_key_id  # noqa: S101 (Settings checks all three)
        assert settings.payment_key_secret  # noqa: S101
        assert settings.payment_webhook_secret  # noqa: S101
        self._key_id = settings.payment_key_id
        self._key_secret = settings.payment_key_secret.get_secret_value()
        self._webhook_secret = settings.payment_webhook_secret.get_secret_value()
        self._database = database

    @property
    def public_key_id(self) -> str:
        return self._key_id

    async def _records(self, *conditions: Any) -> list[FakeGatewayRecord]:
        async with self._database.transaction() as session:
            return list(
                await session.scalars(
                    select(FakeGatewayRecord)
                    .where(*conditions)
                    .order_by(FakeGatewayRecord.created_at)
                )
            )

    async def _add(self, record: FakeGatewayRecord) -> FakeGatewayRecord:
        async with self._database.transaction() as session:
            session.add(record)
            await session.flush()
            await session.refresh(record)
            return record

    async def create_order(
        self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]
    ) -> GatewayOrder:
        if amount_paise <= 0:
            raise GatewayError("amount must be positive", retryable=False)
        record = await self._add(
            FakeGatewayRecord(
                id=_id("order"),
                kind="ORDER",
                amount_paise=amount_paise,
                currency=currency,
                status="created",
                data={"receipt": receipt[:40], "notes": notes},
            )
        )
        return GatewayOrder(record.id, record.amount_paise, record.currency)

    async def order_payments(self, provider_order_id: str) -> list[GatewayPayment]:
        records = await self._records(
            FakeGatewayRecord.kind == "PAYMENT", FakeGatewayRecord.parent_id == provider_order_id
        )
        return [payment_from(_payment_entity(r)) for r in records]

    async def payments_between(self, start: datetime, end: datetime) -> list[GatewayPayment]:
        records = await self._records(
            FakeGatewayRecord.kind == "PAYMENT",
            FakeGatewayRecord.created_at >= start,
            FakeGatewayRecord.created_at <= end,
        )
        return [payment_from(_payment_entity(r)) for r in records]

    async def create_refund(
        self, *, payment_id: str, amount_paise: int, notes: dict[str, str]
    ) -> GatewayRefund:
        payments = await self._records(FakeGatewayRecord.id == payment_id)
        if not payments or payments[0].status not in ("captured", "refunded"):
            raise GatewayError("payment not captured", retryable=False)
        done = sum(r.amount_paise for r in await self.payment_refund_records(payment_id))
        if amount_paise <= 0 or done + amount_paise > payments[0].amount_paise:
            raise GatewayError("refund exceeds the captured amount", retryable=False)
        record = await self._add(
            FakeGatewayRecord(
                id=_id("rfnd"),
                kind="REFUND",
                parent_id=payment_id,
                amount_paise=amount_paise,
                currency=payments[0].currency,
                status="processed",
                data={"notes": notes},
            )
        )
        return refund_from(_refund_entity(record))

    async def payment_refund_records(self, payment_id: str) -> list[FakeGatewayRecord]:
        return await self._records(
            FakeGatewayRecord.kind == "REFUND", FakeGatewayRecord.parent_id == payment_id
        )

    async def payment_refunds(self, payment_id: str) -> list[GatewayRefund]:
        return [
            refund_from(_refund_entity(r)) for r in await self.payment_refund_records(payment_id)
        ]

    def verify_checkout_signature(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        return signature_matches(
            self._key_secret, checkout_message(order_id, payment_id), signature
        )

    def verify_webhook_signature(self, *, body: bytes, signature: str) -> bool:
        return signature_matches(self._webhook_secret, body, signature)

    def parse_event(self, body: bytes) -> GatewayEvent:
        return event_from(body)

    # --- the shopper and Razorpay's servers, for development and tests ------------------------

    async def simulate_payment(
        self,
        provider_order_id: str,
        *,
        status: PaymentStatus = "captured",
        amount_paise: int | None = None,
        currency: str | None = None,
    ) -> GatewayPayment:
        """A shopper paying the order in the checkout widget. `amount_paise` and `currency`
        override what the order says, to test mismatches."""
        orders = await self._records(FakeGatewayRecord.id == provider_order_id)
        if not orders:
            raise GatewayError("unknown order", retryable=False)
        order = orders[0]
        record = await self._add(
            FakeGatewayRecord(
                id=_id("pay"),
                kind="PAYMENT",
                parent_id=order.id,
                amount_paise=amount_paise if amount_paise is not None else order.amount_paise,
                currency=currency or order.currency,
                status=status,
                data={
                    "method": "upi",
                    "error_code": "BAD_REQUEST_ERROR" if status == "failed" else None,
                },
            )
        )
        return payment_from(_payment_entity(record))

    async def set_payment_status(self, payment_id: str, status: PaymentStatus) -> GatewayPayment:
        async with self._database.transaction() as session:
            record = await session.get_one(FakeGatewayRecord, payment_id, with_for_update=True)
            record.status = status
            await session.flush()
            return payment_from(_payment_entity(record))

    def checkout_signature(self, order_id: str, payment_id: str) -> str:
        return hmac_hex(self._key_secret, checkout_message(order_id, payment_id))

    def signed_webhook(
        self,
        event_type: str,
        *,
        payment: GatewayPayment | None = None,
        refund: GatewayRefund | None = None,
    ) -> tuple[bytes, str, str]:
        """A webhook as Razorpay sends it: body, `X-Razorpay-Signature`, `X-Razorpay-Event-Id`."""
        payload: dict[str, Any] = {}
        if payment is not None:
            payload["payment"] = {
                "entity": {
                    "id": payment.payment_id,
                    "entity": "payment",
                    "order_id": payment.order_id,
                    "amount": payment.amount_paise,
                    "currency": payment.currency,
                    "status": payment.status,
                    "captured": payment.captured,
                    "method": payment.method,
                    "fee": payment.fee_paise,
                    "tax": payment.tax_paise,
                    "error_code": payment.error_code,
                }
            }
        if refund is not None:
            payload["refund"] = {
                "entity": {
                    "id": refund.refund_id,
                    "entity": "refund",
                    "payment_id": refund.payment_id,
                    "amount": refund.amount_paise,
                    "status": refund.status,
                    "notes": refund.notes or [],
                }
            }
        body = json.dumps(
            {
                "entity": "event",
                "event": event_type,
                "contains": list(payload),
                "payload": payload,
                "created_at": int(time.time()),
            },
            separators=(",", ":"),
        ).encode()
        return body, hmac_hex(self._webhook_secret, body), _id("evt")
