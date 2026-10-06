"""Email adapters behind MessageProvider (INTEGRATION_ARCHITECTURE sections 3 and 10; ADR-020) and
the production configuration guards."""

import json
import os

import httpx
import pytest
from pydantic import ValidationError

from p2b.core.config import Settings
from p2b.core.messaging import EmailMessage, ProviderError
from p2b.integrations.email import (
    MemoryEmailProvider,
    ResendEmailProvider,
    SmtpEmailProvider,
    build_message_provider,
)

MESSAGE = EmailMessage(to="a@example.in", subject="Subject", text="Body", idempotency_key="k-1")


def _resend(handler: httpx.MockTransport) -> ResendEmailProvider:
    return ResendEmailProvider("re_test_key", "Plan2Build <no-reply@plan2build.in>", handler)


async def test_resend_sends_with_our_idempotency_key() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "email_123"})

    result = await _resend(httpx.MockTransport(handle)).send_email(MESSAGE)
    assert result.provider_message_id == "email_123"
    (request,) = seen
    assert request.url == "https://api.resend.com/emails"
    assert request.headers["authorization"] == "Bearer re_test_key"
    assert request.headers["idempotency-key"] == "k-1"
    assert json.loads(request.content) == {
        "from": "Plan2Build <no-reply@plan2build.in>",
        "to": ["a@example.in"],
        "subject": "Subject",
        "text": "Body",
    }


@pytest.mark.parametrize(
    ("status", "retryable"), [(429, True), (500, True), (503, True), (422, False), (401, False)]
)
async def test_resend_classifies_failures(status: int, retryable: bool) -> None:
    provider = _resend(httpx.MockTransport(lambda _: httpx.Response(status, json={})))
    with pytest.raises(ProviderError) as raised:
        await provider.send_email(MESSAGE)
    assert raised.value.retryable is retryable


async def test_resend_network_errors_are_retryable() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    with pytest.raises(ProviderError) as raised:
        await _resend(httpx.MockTransport(fail)).send_email(MESSAGE)
    assert raised.value.retryable is True


async def test_smtp_failure_is_retryable() -> None:
    provider = SmtpEmailProvider(
        "127.0.0.1", 9, "Plan2Build <no-reply@plan2build.in>"
    )  # discard port
    with pytest.raises(ProviderError) as raised:
        await provider.send_email(MESSAGE)
    assert raised.value.retryable is True


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "test",
        "database_url": os.environ["P2B_DATABASE_URL"],
        "host_ihb": "a",
        "host_pro": "b",
        "host_ops": "c",
        "otp_pepper": "p",
        "identifier_pepper": "q",
        "encryption_key": "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
    }
    values.update(overrides)
    return Settings.model_validate(values)


def test_the_provider_is_chosen_by_configuration() -> None:
    assert isinstance(
        build_message_provider(_settings(email_provider="memory")), MemoryEmailProvider
    )
    assert isinstance(build_message_provider(_settings(email_provider="smtp")), SmtpEmailProvider)
    resend = build_message_provider(_settings(email_provider="resend", resend_api_key="re_x"))
    assert isinstance(resend, ResendEmailProvider)


@pytest.mark.parametrize(
    "overrides",
    [
        {"email_provider": "smtp"},
        {"email_provider": "memory"},
        {"email_provider": "resend"},  # no API key
        {"email_provider": "resend", "resend_api_key": "re_x", "cookie_secure": False},
    ],
)
def test_production_refuses_unsafe_configuration(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _settings(env="production", **{**PRODUCTION_FILES, **overrides})


# The other production guards in force (files, scanning, no demo images), so each test checks one.
PRODUCTION_FILES = {
    "storage_provider": "s3",
    "scanner_provider": "clamav",
    "ai_image_provider": "none",
    "payment_provider": "none",
}


@pytest.mark.parametrize(
    "overrides", [{"storage_provider": "memory"}, {"scanner_provider": "accept_all"}]
)
def test_production_refuses_test_storage_or_scanning(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _settings(
            env="production", email_provider="resend", resend_api_key="re_x",
            **{**PRODUCTION_FILES, **overrides},
        )  # fmt: skip


def test_production_accepts_resend_with_secure_cookies() -> None:
    settings = _settings(
        env="production", email_provider="resend", resend_api_key="re_x", **PRODUCTION_FILES
    )
    assert settings.cookie_secure is True
