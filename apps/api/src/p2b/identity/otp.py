"""Email OTP sign-in, which is also registration (SECURITY 3.1; STATE_MODEL 2; API 2; ADR-010).

B-03 (Chirag, 2026-10-04): no user exists until its code is verified. `start_otp` therefore treats
known and unknown contacts identically (same work, same response, no account lookup), which is
also what makes enumeration impossible.

Limits (SECURITY 3.1): 6-digit code valid 10 minutes; 5 wrong codes lock the challenge; 10 wrong
codes for one contact within an hour lock the contact for the rest of that hour (counted from
`security_events`, a sliding window); 5 sends per contact per 10 minutes; 60 starts per IP per
hour; 20 verifications per IP per 10 minutes. A challenge is single use: VERIFIED, EXPIRED and
LOCKED are terminal, and a new start expires the contact's earlier open challenges.

Every step that must survive a rejected request (attempt counts, locks, security events) commits
in its own transaction before the error is raised.
"""

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from importlib import resources
from string import Template

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import count_security_events, record, record_security_event
from p2b.core.config import Settings
from p2b.core.crypto import decrypt, encrypt, keyed_hash
from p2b.core.db import Database
from p2b.core.errors import AppError, Forbidden, OtpInvalid, OtpLocked, RateLimited
from p2b.core.ids import new_id
from p2b.core.messaging import EmailMessage, MessageProvider, ProviderError
from p2b.core.outbox import EventPayload, publish
from p2b.core.ratelimit import Limit, enforce
from p2b.core.vocabulary import (
    ActorType,
    Audience,
    ContactKind,
    OtpPurpose,
    OtpState,
    SecuritySeverity,
    UserStatus,
)
from p2b.identity.models import OtpChallenge, User, UserContact
from p2b.identity.service import USER_ACCOUNT, IssuedSession, create_session


@dataclass(frozen=True)
class OtpPolicy:
    digits: int
    validity: timedelta
    max_attempts: int
    contact_failure_limit: int
    contact_failure_window: timedelta
    send_per_contact: Limit
    start_per_ip: Limit
    verify_per_ip: Limit


POLICY = OtpPolicy(
    digits=6,
    validity=timedelta(minutes=10),
    max_attempts=5,
    contact_failure_limit=10,
    contact_failure_window=timedelta(hours=1),
    send_per_contact=Limit("otp_send_contact", 5, 600),
    start_per_ip=Limit("otp_start_ip", 60, 3600),
    verify_per_ip=Limit("otp_verify_ip", 20, 600),
)

# argon2id with the library's interactive defaults; the pepper keeps a leaked table from being
# brute-forced offline (a 6-digit space is small).
_hasher = PasswordHasher()
_TIMING_HASH = _hasher.hash("timing-equaliser")

# Security event kinds written by this module (SECURITY section 11).
OTP_ISSUED = "OTP_ISSUED"
OTP_FAILED = "OTP_FAILED"  # a wrong code; these drive the contact lock
OTP_LOCKED = "OTP_LOCKED"
OTP_REJECTED = "OTP_REJECTED"  # used, replaced, expired or locked challenge, or locked contact
OTP_RATE_LIMITED = "OTP_RATE_LIMITED"
OTP_DELIVERY_FAILED = "OTP_DELIVERY_FAILED"
LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"
LOGIN_REFUSED = "LOGIN_REFUSED"


class OtpIssued(EventPayload):
    challenge_id: uuid.UUID
    purpose: OtpPurpose


class UserRegistered(EventPayload):
    user_id: uuid.UUID
    audience: Audience


@dataclass(frozen=True)
class StartedChallenge:
    challenge_id: uuid.UUID
    expires_at: datetime
    masked_contact: str


@dataclass(frozen=True)
class SignedIn:
    user: User
    is_new: bool
    session: IssuedSession


def normalize_email(value: str) -> str:
    return value.strip().lower()


def mask_email(normalized: str) -> str:
    local, _, domain = normalized.partition("@")
    return f"{local[:1]}***@{domain}"


def _contact_hash(settings: Settings, audience: Audience, normalized: str) -> str:
    key = settings.identifier_pepper.get_secret_value()
    return keyed_hash(key, f"{audience.value}:{ContactKind.EMAIL.value}:{normalized}")


def _peppered(settings: Settings, code: str) -> str:
    return f"{settings.otp_pepper.get_secret_value()}:{code}"


def _code_matches(settings: Settings, code_hash: str, code: str) -> bool:
    try:
        return _hasher.verify(code_hash, _peppered(settings, code))
    except (VerificationError, InvalidHashError):
        return False


async def _lock_contact_row(session: AsyncSession, contact_hash: str) -> None:
    """Serialise work on one contact inside the transaction (two starts, or two verifications of
    a new contact, cannot interleave)."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": contact_hash}
    )


async def _contact_locked(database: Database, contact_hash: str) -> bool:
    failures = await count_security_events(
        database, kind=OTP_FAILED, contact_hash=contact_hash, within=POLICY.contact_failure_window
    )
    return failures >= POLICY.contact_failure_limit


async def start_otp(
    database: Database, settings: Settings, *, email: str, audience: Audience, ip_hash: str
) -> StartedChallenge:
    normalized = normalize_email(email)
    contact_hash = _contact_hash(settings, audience, normalized)
    try:
        await enforce(database, POLICY.start_per_ip, ip_hash)
        await enforce(database, POLICY.send_per_contact, contact_hash)
    except RateLimited:
        await record_security_event(
            database, kind=OTP_RATE_LIMITED, severity=SecuritySeverity.WARNING, audience=audience,
            contact_hash=contact_hash, ip_hash=ip_hash, details={"step": "start"},
        )  # fmt: skip
        raise
    if await _contact_locked(database, contact_hash):
        await record_security_event(
            database, kind=OTP_REJECTED, severity=SecuritySeverity.WARNING, audience=audience,
            contact_hash=contact_hash, ip_hash=ip_hash, details={"reason": "contact_locked"},
        )  # fmt: skip
        raise OtpLocked

    code = f"{secrets.randbelow(10**POLICY.digits):0{POLICY.digits}d}"
    challenge_id = new_id()
    async with database.transaction() as session:
        await _lock_contact_row(session, contact_hash)
        await session.execute(
            update(OtpChallenge)
            .where(
                OtpChallenge.audience == audience.value,
                OtpChallenge.contact_kind == ContactKind.EMAIL.value,
                OtpChallenge.contact_normalized == normalized,
                OtpChallenge.purpose == OtpPurpose.LOGIN.value,
                OtpChallenge.state == OtpState.ISSUED.value,
            )
            .values(state=OtpState.EXPIRED.value, code_ciphertext=None)
        )
        now = (await session.execute(select(func.now()))).scalar_one()
        expires_at = now + POLICY.validity
        session.add(
            OtpChallenge(
                id=challenge_id,
                audience=audience.value,
                purpose=OtpPurpose.LOGIN.value,
                contact_kind=ContactKind.EMAIL.value,
                contact_normalized=normalized,
                code_hash=_hasher.hash(_peppered(settings, code)),
                code_ciphertext=encrypt(
                    settings.encryption_key.get_secret_value(), code, challenge_id.bytes
                ),
                state=OtpState.ISSUED.value,
                expires_at=expires_at,
                max_attempts=POLICY.max_attempts,
                ip_hash=ip_hash,
            )
        )
        await session.flush()
        await publish(
            session,
            event_type="otp.issued",
            aggregate_type="otp_challenge",
            aggregate_id=challenge_id,
            payload=OtpIssued(challenge_id=challenge_id, purpose=OtpPurpose.LOGIN),
            dedupe_suffix="issued",
        )
    await record_security_event(
        database, kind=OTP_ISSUED, severity=SecuritySeverity.INFO, audience=audience,
        contact_hash=contact_hash, ip_hash=ip_hash,
    )  # fmt: skip
    return StartedChallenge(challenge_id, expires_at, mask_email(normalized))


async def _sign_in(
    session: AsyncSession, settings: Settings, challenge: OtpChallenge, now: datetime
) -> SignedIn | None:
    """Find or create the user for a verified challenge. None: no account may sign in here."""
    audience = Audience(challenge.audience)
    contact = (
        await session.scalars(
            select(UserContact)
            .where(
                UserContact.audience == challenge.audience,
                UserContact.kind == challenge.contact_kind,
                UserContact.normalized == challenge.contact_normalized,
            )
            .with_for_update()
        )
    ).one_or_none()

    if contact is not None:
        user = await session.get_one(User, contact.user_id, with_for_update=True)
        if user.status == UserStatus.CLOSED.value:
            return None
        if contact.verified_at is None:
            contact.verified_at = now
        if user.status == UserStatus.PENDING_VERIFICATION.value:  # account created by operations
            await _advance(session, user, "verify_contact", "user.contact_verified")
        is_new = False
    else:
        if audience not in settings.self_registration_audiences:
            return None
        registered = USER_ACCOUNT.target(None, "register")
        user = User(id=new_id(), audience=audience.value, status=registered.value)
        session.add(user)
        await session.flush()
        await _audit_status(session, user, None, registered, "user.registered")
        session.add(
            UserContact(
                id=new_id(),
                user_id=user.id,
                audience=audience.value,
                kind=challenge.contact_kind,
                value=challenge.contact_normalized,
                normalized=challenge.contact_normalized,
                verified_at=now,
                is_primary=True,
            )
        )
        await _advance(session, user, "verify_contact", "user.contact_verified")
        await publish(
            session,
            event_type="user.registered",
            aggregate_type="user",
            aggregate_id=user.id,
            payload=UserRegistered(user_id=user.id, audience=audience),
            dedupe_suffix="registered",
        )
        is_new = True

    user.last_login_at = now
    issued = await create_session(session, user_id=user.id)
    return SignedIn(user=user, is_new=is_new, session=issued)


async def _advance(session: AsyncSession, user: User, trigger: str, action: str) -> None:
    """Move the account through USER_ACCOUNT (STATE_MODEL 2), audited in this transaction."""
    current = UserStatus(user.status)
    target = USER_ACCOUNT.target(current, trigger)
    user.status = target.value
    await session.flush()
    await _audit_status(session, user, current, target, action)


async def _audit_status(
    session: AsyncSession, user: User, old: UserStatus | None, new: UserStatus, action: str
) -> None:
    await record(
        session,
        action=action,
        entity_type="user",
        entity_id=user.id,
        actor_type=ActorType.USER,
        actor_user_id=user.id,
        old_value={"status": old.value} if old else None,
        new_value={"status": new.value},
    )


async def verify_otp(
    database: Database,
    settings: Settings,
    *,
    challenge_id: uuid.UUID,
    code: str,
    audience: Audience,
    ip_hash: str,
) -> SignedIn:
    try:
        await enforce(database, POLICY.verify_per_ip, ip_hash)
    except RateLimited:
        await record_security_event(
            database, kind=OTP_RATE_LIMITED, severity=SecuritySeverity.WARNING, audience=audience,
            ip_hash=ip_hash, details={"step": "verify"},
        )  # fmt: skip
        raise

    rejection: tuple[str, AppError] | None = None
    contact_hash: str | None = None
    signed_in: SignedIn | None = None
    wrong_code = False
    async with database.transaction() as session:
        challenge = await session.get(OtpChallenge, challenge_id, with_for_update=True)
        now = (await session.execute(select(func.now()))).scalar_one()
        if (
            challenge is None
            or challenge.audience != audience.value
            or challenge.purpose != OtpPurpose.LOGIN.value  # a confirmation code never signs in
        ):
            _code_matches(settings, _TIMING_HASH, code)  # same cost as a real check
            rejection = (OTP_REJECTED, OtpInvalid())
        else:
            contact_hash = _contact_hash(settings, audience, challenge.contact_normalized)
            if challenge.state == OtpState.LOCKED.value:
                rejection = (OTP_REJECTED, OtpLocked())
            elif challenge.state != OtpState.ISSUED.value:
                rejection = (OTP_REJECTED, OtpInvalid(details={"reason": "used_or_replaced"}))
            elif challenge.expires_at <= now:
                challenge.state = OtpState.EXPIRED.value
                challenge.code_ciphertext = None
                rejection = (OTP_REJECTED, OtpInvalid(details={"reason": "expired"}))
            elif await _contact_locked(database, contact_hash):
                rejection = (OTP_REJECTED, OtpLocked())
            elif not _code_matches(settings, challenge.code_hash, code):
                wrong_code = True
                challenge.attempts += 1
                if challenge.attempts >= challenge.max_attempts:
                    challenge.state = OtpState.LOCKED.value
                    challenge.locked_at = now
                    challenge.code_ciphertext = None
                    rejection = (OTP_LOCKED, OtpLocked())
                else:
                    left = challenge.max_attempts - challenge.attempts
                    rejection = (OTP_FAILED, OtpInvalid(details={"attempts_left": left}))
            else:
                await _lock_contact_row(session, contact_hash)
                challenge.state = OtpState.VERIFIED.value
                challenge.verified_at = now
                challenge.code_ciphertext = None
                signed_in = await _sign_in(session, settings, challenge, now)
                if signed_in is None:
                    rejection = (LOGIN_REFUSED, Forbidden("This account cannot sign in here."))
                else:
                    challenge.user_id = signed_in.user.id
    # Committed: attempts, locks, expiry and the new account and session are durable now.

    if wrong_code:
        await record_security_event(
            database, kind=OTP_FAILED, severity=SecuritySeverity.WARNING, audience=audience,
            contact_hash=contact_hash, ip_hash=ip_hash,
        )  # fmt: skip
    if rejection is not None:
        kind, error = rejection
        if kind != OTP_FAILED:
            await record_security_event(
                database, kind=kind, severity=SecuritySeverity.WARNING, audience=audience,
                contact_hash=contact_hash, ip_hash=ip_hash, details={"code": error.code},
            )  # fmt: skip
        raise error
    assert signed_in is not None  # noqa: S101 (no rejection means a session was created)
    await record_security_event(
        database, kind=LOGIN_SUCCEEDED, severity=SecuritySeverity.INFO, audience=audience,
        user_id=signed_in.user.id, contact_hash=contact_hash, ip_hash=ip_hash,
        details={"is_new": signed_in.is_new},
    )  # fmt: skip
    return signed_in


def render_otp_email(
    to: str, code: str, idempotency_key: str, purpose: OtpPurpose = OtpPurpose.LOGIN
) -> EmailMessage:
    """English template from a file beside this module (ADR-022: no user-facing literals in code;
    moves to `notification_templates` when the notifications module exists). Confirmation codes
    (Slice 3.5) use their own template."""
    name = "otp_login" if purpose == OtpPurpose.LOGIN else "otp_confirm"
    raw = resources.files("p2b.identity").joinpath(f"templates/{name}.en.txt").read_text("utf-8")
    subject, _, body = raw.partition("\n---\n")
    minutes = int(POLICY.validity.total_seconds() // 60)
    text_body = Template(body).substitute(code=code, minutes=minutes)
    return EmailMessage(
        to=to, subject=subject.strip(), text=text_body, idempotency_key=idempotency_key
    )


async def deliver_otp_code(
    database: Database,
    settings: Settings,
    provider: MessageProvider,
    challenge_id: uuid.UUID,
    *,
    final_attempt: bool,
) -> bool:
    """Send the code for one challenge. Idempotent: a challenge that is no longer open, already
    delivered or expired is skipped. The row lock is not held across the provider call."""
    async with database.transaction() as session:
        challenge = await session.get(OtpChallenge, challenge_id)
        now = (await session.execute(select(func.now()))).scalar_one()
        if (
            challenge is None
            or challenge.state != OtpState.ISSUED.value
            or challenge.code_ciphertext is None
            or challenge.delivered_at is not None
            or challenge.expires_at <= now
        ):
            return False
        code = decrypt(
            settings.encryption_key.get_secret_value(),
            challenge.code_ciphertext,
            challenge.id.bytes,
        )
        message = render_otp_email(
            challenge.contact_normalized, code, str(challenge.id), OtpPurpose(challenge.purpose)
        )
        audience = Audience(challenge.audience)

    try:
        await provider.send_email(message)
    except ProviderError as exc:
        if final_attempt or not exc.retryable:
            async with database.transaction() as session:
                await session.execute(
                    update(OtpChallenge)
                    .where(OtpChallenge.id == challenge_id)
                    .values(delivery_failed_at=func.now(), code_ciphertext=None)
                )
            await record_security_event(
                database, kind=OTP_DELIVERY_FAILED, severity=SecuritySeverity.WARNING,
                audience=audience, details={"provider": provider.name, "retryable": exc.retryable},
            )  # fmt: skip
            return False
        raise

    async with database.transaction() as session:
        await session.execute(
            update(OtpChallenge)
            .where(OtpChallenge.id == challenge_id)
            .values(delivered_at=func.now(), code_ciphertext=None)
        )
    return True
