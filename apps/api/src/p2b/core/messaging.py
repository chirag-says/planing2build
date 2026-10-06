"""Outbound message interface (INTEGRATION_ARCHITECTURE section 1: one adapter per provider, the
interface owned by the application). Modules depend on `MessageProvider`, never on an SDK; the
provider is chosen by configuration (`P2B_EMAIL_PROVIDER`), so switching Mailpit to Resend, or
adding SMS later, changes no business logic."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    # Our delivery id. Providers that support it use it to make retries send once.
    idempotency_key: str


@dataclass(frozen=True)
class SendResult:
    provider: str
    provider_message_id: str | None


class ProviderError(Exception):
    """A provider call failed. `retryable` tells the job whether another attempt can succeed."""

    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


class MessageProvider(Protocol):
    name: str

    async def send_email(self, message: EmailMessage) -> SendResult: ...
