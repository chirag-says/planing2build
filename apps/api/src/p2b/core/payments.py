"""Payment gateway interface (Slice 3.3; INTEGRATION_ARCHITECTURE section 4; ADR-020).

The billing module depends on `PaymentGateway`, never on a vendor SDK. Amounts cross this
interface as integer paise. Two adapters exist: Razorpay (staging in test mode, production live)
and a fake for local development and tests (`P2B_PAYMENT_PROVIDER`). Only the server talks to
the gateway's API; the browser receives the public key id and the provider order id, nothing
else.

What the gateway reports is authoritative only when it comes from a verified webhook or from an
authenticated server-to-provider fetch. The browser's checkout callback is a hint.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol

PaymentStatus = Literal["created", "authorized", "captured", "refunded", "failed"]
RefundStatus = Literal["pending", "processed", "failed"]


@dataclass(frozen=True)
class GatewayOrder:
    provider_order_id: str
    amount_paise: int
    currency: str


@dataclass(frozen=True)
class GatewayPayment:
    """A payment as the provider reports it; `captured` is true once money was taken."""

    payment_id: str
    order_id: str | None
    amount_paise: int
    currency: str
    status: PaymentStatus
    captured: bool
    method: str | None = None
    fee_paise: int | None = None
    tax_paise: int | None = None
    error_code: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True)
class GatewayRefund:
    refund_id: str
    payment_id: str
    amount_paise: int
    status: RefundStatus
    notes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GatewayEvent:
    """A verified webhook, reduced to the fields billing uses (DATA: minimal payload)."""

    event_type: str
    payment: GatewayPayment | None
    refund: GatewayRefund | None


class GatewayError(Exception):
    """A provider call failed. `retryable` says whether trying again can succeed."""

    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


class PaymentGateway(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def configured(self) -> bool: ...

    @property
    def public_key_id(self) -> str: ...

    async def create_order(
        self, *, amount_paise: int, currency: str, receipt: str, notes: dict[str, str]
    ) -> GatewayOrder: ...

    async def order_payments(self, provider_order_id: str) -> list[GatewayPayment]: ...

    async def payments_between(self, start: datetime, end: datetime) -> list[GatewayPayment]: ...

    async def create_refund(
        self, *, payment_id: str, amount_paise: int, notes: dict[str, str]
    ) -> GatewayRefund: ...

    async def payment_refunds(self, payment_id: str) -> list[GatewayRefund]: ...

    def verify_checkout_signature(self, *, order_id: str, payment_id: str, signature: str) -> bool:
        """The checkout callback's signature: proves the ids came from the provider's widget,
        never that the payment was captured."""
        ...

    def verify_webhook_signature(self, *, body: bytes, signature: str) -> bool: ...

    def parse_event(self, body: bytes) -> GatewayEvent:
        """Only after `verify_webhook_signature` accepted the same bytes."""
        ...
