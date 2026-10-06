"""Email OTP sign-in and registration, end to end through the outbox, the job queue and the email
sink. Sources: SECURITY_ARCHITECTURE 3.1 and 3.2; STATE_MODEL 2; API_ARCHITECTURE 2; B-03."""

import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import timedelta

import pytest
from httpx import AsyncClient, Response
from procrastinate import App
from sqlalchemy import func, select, update

from p2b.audit.models import AuditEvent, SecurityEvent
from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.jobs import RESOURCES_KEY, JobResources, build_job_app
from p2b.core.messaging import EmailMessage, ProviderError, SendResult
from p2b.core.outbox import HandlerRegistry, OutboxEvent, relay_batch
from p2b.core.vocabulary import Audience, UserStatus
from p2b.identity import handlers as identity_handlers
from p2b.identity import jobs as identity_jobs
from p2b.identity.models import OtpChallenge, User, UserContact
from p2b.identity.otp import POLICY, deliver_otp_code
from p2b.integrations.ai_images import DemoImageProvider
from p2b.integrations.clamav import AcceptAllScanner
from p2b.integrations.email import MemoryEmailProvider
from p2b.integrations.razorpay import NoGateway
from p2b.integrations.storage import MemoryStorage
from tests.conftest import ClientFactory, csrf_headers

Deliver = Callable[[], Awaitable[None]]


@pytest.fixture
def mailbox() -> MemoryEmailProvider:
    return MemoryEmailProvider()


@pytest.fixture(scope="session")
def job_app() -> App:
    """One job app per process, as in the worker: a Procrastinate blueprint binds its tasks to the
    first app it is added to."""
    return build_job_app(
        get_settings(), [(identity_handlers.JOB_NAMESPACE, identity_jobs.blueprint)]
    )


@pytest.fixture
async def deliver(
    database: Database, mailbox: MemoryEmailProvider, job_app: App
) -> AsyncIterator[Deliver]:
    """Run what production runs after a commit: the relay defers the job, a worker sends it."""
    settings = get_settings()
    registry = HandlerRegistry()
    identity_handlers.register(registry, job_app)
    resources = JobResources(
        database,
        settings,
        mailbox,
        MemoryStorage(),
        AcceptAllScanner(),
        DemoImageProvider(),
        NoGateway(),
    )

    async def run() -> None:
        while await relay_batch(database, registry):
            pass
        await job_app.run_worker_async(
            queues=["priority"], wait=False, install_signal_handlers=False,
            additional_context={RESOURCES_KEY: resources},
        )  # fmt: skip

    async with job_app.open_async():
        yield run


def code_in(message: EmailMessage) -> str:
    match = re.search(r"\b(\d{6})\b", message.text)
    assert match, "no code in the email"
    return match.group(1)


async def start(client: AsyncClient, audience: Audience, email: str) -> Response:
    return await client.post(
        "/api/v1/auth/otp/start", json={"email": email}, headers=csrf_headers(audience)
    )


async def verify(client: AsyncClient, audience: Audience, challenge_id: str, code: str) -> Response:
    return await client.post(
        "/api/v1/auth/otp/verify",
        json={"challenge_id": challenge_id, "code": code},
        headers=csrf_headers(audience),
    )


async def issue(
    client: AsyncClient,
    audience: Audience,
    email: str,
    deliver: Deliver,
    mailbox: MemoryEmailProvider,
) -> tuple[str, str]:
    response = await start(client, audience, email)
    assert response.status_code == 200, response.text
    await deliver()
    return response.json()["challenge_id"], code_in(mailbox.sent[-1])


async def count(database: Database, model: type) -> int:
    async with database.transaction() as session:
        return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def security_kinds(database: Database) -> list[str]:
    async with database.transaction() as session:
        return list(await session.scalars(select(SecurityEvent.kind).order_by(SecurityEvent.at)))


def wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


async def test_sign_up_creates_the_account_only_after_the_code_is_verified(
    client_for: ClientFactory, database: Database, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    client = client_for(Audience.IHB)
    started = await start(client, Audience.IHB, "  Family@Example.IN ")
    assert started.status_code == 200
    assert started.json()["masked_contact"] == "f***@example.in"
    assert await count(database, User) == 0  # B-03: nothing exists before verification
    assert await count(database, UserContact) == 0

    await deliver()
    (email,) = mailbox.sent
    assert email.to == "family@example.in"
    assert email.subject == "Your Plan2Build sign-in code"
    assert "expires in 10 minutes" in email.text

    response = await verify(client, Audience.IHB, started.json()["challenge_id"], code_in(email))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_new"] is True
    assert body["mfa_required"] is False
    assert body["user"]["status"] == "ACTIVE"

    cookie = response.headers["set-cookie"]
    assert cookie.startswith("__Host-p2b_ihb_session=")
    for attribute in ("HttpOnly", "Secure", "SameSite=lax", "Path=/", "Max-Age=7776000"):
        assert attribute in cookie
    assert "Domain" not in cookie
    me = await client.get("/api/v1/me")
    assert me.status_code == 200
    assert me.json()["user_id"] == body["user"]["user_id"]

    async with database.transaction() as session:
        contact = (await session.scalars(select(UserContact))).one()
        actions = list(await session.scalars(select(AuditEvent.action).order_by(AuditEvent.at)))
        events = sorted(await session.scalars(select(OutboxEvent.event_type)))
        challenge = (await session.scalars(select(OtpChallenge))).one()
    assert contact.verified_at is not None
    assert contact.normalized == "family@example.in"
    assert actions == ["user.registered", "user.contact_verified", "session.created"]
    assert events == ["otp.issued", "user.registered"]
    assert challenge.state == "VERIFIED"
    assert challenge.code_ciphertext is None
    assert await security_kinds(database) == ["OTP_ISSUED", "LOGIN_SUCCEEDED"]


async def test_signing_in_again_reuses_the_account(
    client_for: ClientFactory, database: Database, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    for expected_new in (True, False):
        client = client_for(Audience.IHB)
        challenge_id, code = await issue(client, Audience.IHB, "a@example.in", deliver, mailbox)
        response = await verify(client, Audience.IHB, challenge_id, code)
        assert response.json()["is_new"] is expected_new
    assert await count(database, User) == 1


async def test_start_answers_known_and_unknown_contacts_the_same_way(
    client_for: ClientFactory, database: Database, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    client = client_for(Audience.IHB)
    challenge_id, code = await issue(client, Audience.IHB, "known@example.in", deliver, mailbox)
    await verify(client, Audience.IHB, challenge_id, code)

    known = await start(client_for(Audience.IHB), Audience.IHB, "known@example.in")
    unknown = await start(client_for(Audience.IHB), Audience.IHB, "unknown@example.in")
    assert known.status_code == unknown.status_code == 200
    assert (
        set(known.json()) == set(unknown.json()) == {"challenge_id", "expires_at", "masked_contact"}
    )
    assert await count(database, User) == 1


async def test_five_wrong_codes_lock_the_challenge(
    client_for: ClientFactory, database: Database, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    client = client_for(Audience.IHB)
    challenge_id, code = await issue(client, Audience.IHB, "a@example.in", deliver, mailbox)
    for left in (4, 3, 2, 1):
        response = await verify(client, Audience.IHB, challenge_id, wrong(code))
        assert response.status_code == 400
        assert response.json()["error"] == response.json()["error"] | {
            "code": "OTP_INVALID", "details": {"attempts_left": left}
        }  # fmt: skip
    locked = await verify(client, Audience.IHB, challenge_id, wrong(code))
    assert locked.status_code == 423
    assert locked.json()["error"]["code"] == "OTP_LOCKED"
    still_locked = await verify(client, Audience.IHB, challenge_id, code)
    assert still_locked.status_code == 423
    assert await count(database, User) == 0
    kinds = await security_kinds(database)
    assert kinds.count("OTP_FAILED") == 5
    assert "OTP_LOCKED" in kinds


async def test_a_code_cannot_be_used_twice(
    client_for: ClientFactory, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    client = client_for(Audience.IHB)
    challenge_id, code = await issue(client, Audience.IHB, "a@example.in", deliver, mailbox)
    assert (await verify(client, Audience.IHB, challenge_id, code)).status_code == 200
    replay = await verify(client_for(Audience.IHB), Audience.IHB, challenge_id, code)
    assert replay.status_code == 400
    assert replay.json()["error"]["details"] == {"reason": "used_or_replaced"}


async def test_a_new_code_replaces_the_previous_one(
    client_for: ClientFactory, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    client = client_for(Audience.IHB)
    first_id, first_code = await issue(client, Audience.IHB, "a@example.in", deliver, mailbox)
    second_id, second_code = await issue(client, Audience.IHB, "a@example.in", deliver, mailbox)
    old = await verify(client, Audience.IHB, first_id, first_code)
    assert old.status_code == 400
    assert old.json()["error"]["details"] == {"reason": "used_or_replaced"}
    assert (await verify(client, Audience.IHB, second_id, second_code)).status_code == 200


async def test_an_expired_code_is_refused(
    client_for: ClientFactory, database: Database, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    client = client_for(Audience.IHB)
    challenge_id, code = await issue(client, Audience.IHB, "a@example.in", deliver, mailbox)
    async with database.transaction() as session:
        await session.execute(
            update(OtpChallenge).values(expires_at=func.now() - timedelta(seconds=1))
        )
    response = await verify(client, Audience.IHB, challenge_id, code)
    assert response.status_code == 400
    assert response.json()["error"]["details"] == {"reason": "expired"}
    async with database.transaction() as session:
        assert (await session.scalars(select(OtpChallenge.state))).one() == "EXPIRED"


async def test_ten_wrong_codes_in_an_hour_lock_the_contact(
    client_for: ClientFactory, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    client = client_for(Audience.IHB)
    for _ in range(2):
        challenge_id, code = await issue(client, Audience.IHB, "a@example.in", deliver, mailbox)
        for _ in range(POLICY.max_attempts):
            await verify(client, Audience.IHB, challenge_id, wrong(code))
    blocked = await start(client, Audience.IHB, "a@example.in")
    assert blocked.status_code == 423
    assert blocked.json()["error"]["code"] == "OTP_LOCKED"
    other = await start(client, Audience.IHB, "someone-else@example.in")
    assert other.status_code == 200


async def test_sends_per_contact_are_limited(client_for: ClientFactory, database: Database) -> None:
    client = client_for(Audience.IHB)
    for _ in range(POLICY.send_per_contact.limit):
        assert (await start(client, Audience.IHB, "a@example.in")).status_code == 200
    limited = await start(client, Audience.IHB, "a@example.in")
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert 0 < int(limited.headers["retry-after"]) <= POLICY.send_per_contact.window_seconds
    assert "OTP_RATE_LIMITED" in await security_kinds(database)


async def test_verifications_per_ip_are_limited(client_for: ClientFactory) -> None:
    client = client_for(Audience.IHB)
    for _ in range(POLICY.verify_per_ip.limit):
        response = await verify(client, Audience.IHB, str(uuid.uuid4()), "123456")
        assert response.status_code == 400
    limited = await verify(client, Audience.IHB, str(uuid.uuid4()), "123456")
    assert limited.status_code == 429


async def test_a_code_from_another_host_is_refused(
    client_for: ClientFactory, database: Database, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    challenge_id, code = await issue(
        client_for(Audience.IHB), Audience.IHB, "a@example.in", deliver, mailbox
    )
    response = await verify(client_for(Audience.PRO), Audience.PRO, challenge_id, code)
    assert response.status_code == 400
    assert await count(database, User) == 0


async def test_professionals_may_register_themselves(
    client_for: ClientFactory, database: Database, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    """D-04: self-registration on the professionals host creates a professional account (it is
    not public: only an approved category is listed)."""
    client = client_for(Audience.PRO)
    challenge_id, code = await issue(client, Audience.PRO, "pro@example.in", deliver, mailbox)
    response = await verify(client, Audience.PRO, challenge_id, code)
    assert response.status_code == 200, response.text
    async with database.transaction() as session:
        audiences = list(await session.scalars(select(User.audience)))
    assert audiences == ["pro"]


@pytest.mark.parametrize("audience", [Audience.OPS])
async def test_the_operations_host_does_not_self_register(
    client_for: ClientFactory,
    database: Database,
    deliver: Deliver,
    mailbox: MemoryEmailProvider,
    audience: Audience,
) -> None:
    client = client_for(audience)
    challenge_id, code = await issue(client, audience, "a@example.in", deliver, mailbox)
    response = await verify(client, audience, challenge_id, code)
    assert response.status_code == 403
    assert "set-cookie" not in response.headers
    assert await count(database, User) == 0
    assert "LOGIN_REFUSED" in await security_kinds(database)


async def _existing_user(database: Database, status: UserStatus, *, verified: bool) -> uuid.UUID:
    user_id = new_id()
    async with database.transaction() as session:
        session.add(User(id=user_id, audience="ihb", status=status.value))
        await session.flush()
        session.add(
            UserContact(
                id=new_id(), user_id=user_id, audience="ihb", kind="EMAIL", value="a@example.in",
                normalized="a@example.in", verified_at=func.now() if verified else None,
            )
        )  # fmt: skip
    return user_id


async def test_a_closed_account_cannot_sign_in(
    client_for: ClientFactory, database: Database, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    await _existing_user(database, UserStatus.CLOSED, verified=True)
    client = client_for(Audience.IHB)
    challenge_id, code = await issue(client, Audience.IHB, "a@example.in", deliver, mailbox)
    assert (await verify(client, Audience.IHB, challenge_id, code)).status_code == 403


async def test_an_account_created_by_operations_is_activated_at_first_sign_in(
    client_for: ClientFactory, database: Database, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    user_id = await _existing_user(database, UserStatus.PENDING_VERIFICATION, verified=False)
    client = client_for(Audience.IHB)
    challenge_id, code = await issue(client, Audience.IHB, "a@example.in", deliver, mailbox)
    response = await verify(client, Audience.IHB, challenge_id, code)
    assert response.json()["is_new"] is False
    async with database.transaction() as session:
        user = await session.get_one(User, user_id)
        actions = list(await session.scalars(select(AuditEvent.action).order_by(AuditEvent.at)))
    assert user.status == "ACTIVE"
    assert actions == ["user.contact_verified", "session.created"]


async def test_otp_requests_need_the_csrf_headers(client_for: ClientFactory) -> None:
    client = client_for(Audience.IHB)
    response = await client.post("/api/v1/auth/otp/start", json={"email": "a@example.in"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_REJECTED"


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/v1/auth/otp/start", {"email": "not-an-email"}),
        ("/api/v1/auth/otp/verify", {"challenge_id": str(uuid.uuid4()), "code": "12345a"}),
        ("/api/v1/auth/otp/verify", {"challenge_id": "x", "code": "123456"}),
    ],
)
async def test_malformed_requests_are_rejected_at_the_boundary(
    client_for: ClientFactory, path: str, body: dict[str, str]
) -> None:
    response = await client_for(Audience.IHB).post(
        path, json=body, headers=csrf_headers(Audience.IHB)
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_the_code_is_stored_only_as_a_hash_once_delivered(
    client_for: ClientFactory, database: Database, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    started = await start(client_for(Audience.IHB), Audience.IHB, "a@example.in")
    async with database.transaction() as session:
        before = (await session.scalars(select(OtpChallenge))).one()
        outbox_payload = (await session.scalars(select(OutboxEvent.payload))).one()
    assert before.code_ciphertext is not None  # needed by the delivery job, encrypted
    await deliver()
    code = code_in(mailbox.sent[-1])
    async with database.transaction() as session:
        after = (await session.scalars(select(OtpChallenge))).one()
    assert after.code_ciphertext is None
    assert after.delivered_at is not None
    assert code not in after.code_hash
    assert after.code_hash.startswith("$argon2id$")
    assert code not in str(outbox_payload)
    assert started.json()["challenge_id"] == str(after.id)


async def test_delivery_runs_once_even_if_the_job_repeats(
    client_for: ClientFactory, database: Database, deliver: Deliver, mailbox: MemoryEmailProvider
) -> None:
    started = await start(client_for(Audience.IHB), Audience.IHB, "a@example.in")
    await deliver()
    challenge_id = uuid.UUID(started.json()["challenge_id"])
    sent_again = await deliver_otp_code(
        database, get_settings(), mailbox, challenge_id, final_attempt=False
    )
    assert sent_again is False
    assert len(mailbox.sent) == 1


class FailingProvider:
    name = "failing"

    def __init__(self, *, retryable: bool):
        self.retryable = retryable

    async def send_email(self, message: EmailMessage) -> SendResult:
        raise ProviderError("down", retryable=self.retryable)


async def test_a_retryable_failure_is_retried_until_the_last_attempt(
    client_for: ClientFactory, database: Database
) -> None:
    started = await start(client_for(Audience.IHB), Audience.IHB, "a@example.in")
    challenge_id = uuid.UUID(started.json()["challenge_id"])
    with pytest.raises(ProviderError):
        await deliver_otp_code(
            database, get_settings(), FailingProvider(retryable=True), challenge_id,
            final_attempt=False,
        )  # fmt: skip
    gave_up = await deliver_otp_code(
        database, get_settings(), FailingProvider(retryable=True), challenge_id, final_attempt=True
    )
    assert gave_up is False
    async with database.transaction() as session:
        challenge = await session.get_one(OtpChallenge, challenge_id)
    assert challenge.delivery_failed_at is not None
    assert challenge.code_ciphertext is None
    assert "OTP_DELIVERY_FAILED" in await security_kinds(database)


async def test_a_permanent_failure_is_not_retried(
    client_for: ClientFactory, database: Database
) -> None:
    started = await start(client_for(Audience.IHB), Audience.IHB, "a@example.in")
    challenge_id = uuid.UUID(started.json()["challenge_id"])
    result = await deliver_otp_code(
        database, get_settings(), FailingProvider(retryable=False), challenge_id,
        final_attempt=False,
    )  # fmt: skip
    assert result is False
    async with database.transaction() as session:
        assert (await session.get_one(OtpChallenge, challenge_id)).delivery_failed_at is not None
