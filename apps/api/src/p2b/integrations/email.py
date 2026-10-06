"""Email adapters behind `p2b.core.messaging.MessageProvider` (ADR-020; INTEGRATION section 3, 10).

- `ResendEmailProvider`: production. Idempotency-Key is our delivery id, so a retried job cannot
  send twice. Timeouts: connect 5 s, read 10 s.
- `SmtpEmailProvider`: development sink (Mailpit in the local stack). Refused in production by
  the settings guard.
- `MemoryEmailProvider`: tests.
"""

import asyncio
import smtplib
from email.message import EmailMessage as MimeMessage

import httpx

from p2b.core.config import Settings
from p2b.core.messaging import EmailMessage, MessageProvider, ProviderError, SendResult

RESEND_URL = "https://api.resend.com/emails"
RESEND_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class ResendEmailProvider:
    name = "resend"

    def __init__(
        self, api_key: str, sender: str, transport: httpx.AsyncBaseTransport | None = None
    ):
        self._api_key = api_key
        self._sender = sender
        self._transport = transport

    async def send_email(self, message: EmailMessage) -> SendResult:
        async with httpx.AsyncClient(timeout=RESEND_TIMEOUT, transport=self._transport) as client:
            try:
                response = await client.post(
                    RESEND_URL,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Idempotency-Key": message.idempotency_key,
                    },
                    json={
                        "from": self._sender,
                        "to": [message.to],
                        "subject": message.subject,
                        "text": message.text,
                    },
                )
            except httpx.TransportError as exc:
                raise ProviderError(
                    f"resend transport: {type(exc).__name__}", retryable=True
                ) from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise ProviderError(f"resend status {response.status_code}", retryable=True)
        if response.status_code >= 400:
            raise ProviderError(f"resend status {response.status_code}", retryable=False)
        message_id = response.json().get("id")
        return SendResult(self.name, str(message_id) if message_id else None)


class SmtpEmailProvider:
    name = "smtp"

    def __init__(self, host: str, port: int, sender: str):
        self._host, self._port, self._sender = host, port, sender

    def _send(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = self._sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime["Message-ID"] = f"<{message.idempotency_key}@plan2build.local>"
        mime.set_content(message.text)
        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            smtp.send_message(mime)

    async def send_email(self, message: EmailMessage) -> SendResult:
        try:
            await asyncio.to_thread(self._send, message)
        except (OSError, smtplib.SMTPException) as exc:
            raise ProviderError(f"smtp: {type(exc).__name__}", retryable=True) from exc
        return SendResult(self.name, None)


class MemoryEmailProvider:
    name = "memory"

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send_email(self, message: EmailMessage) -> SendResult:
        self.sent.append(message)
        return SendResult(self.name, f"memory-{len(self.sent)}")


def build_message_provider(settings: Settings) -> MessageProvider:
    if settings.email_provider == "resend":
        if settings.resend_api_key is None:
            raise ValueError("P2B_RESEND_API_KEY is required for the resend provider")
        return ResendEmailProvider(settings.resend_api_key.get_secret_value(), settings.email_from)
    if settings.email_provider == "smtp":
        return SmtpEmailProvider(settings.smtp_host, settings.smtp_port, settings.email_from)
    return MemoryEmailProvider()
