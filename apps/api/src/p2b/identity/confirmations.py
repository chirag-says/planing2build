"""One-time-code confirmations of a signed-in user's action on one object (SECURITY 3.1; Slice
3.5 BP-04 and BP-05): accepting a Build Plan version, signing structural lines. The code goes to
the account's primary email, is bound to the user, the purpose and the subject id, is valid 10
minutes and locks after 5 wrong attempts. It is a confirmation step: it is not presented as a
legally recognised electronic signature.

Verification commits in its own transaction (attempts and locks survive a rejected request); the
caller records the challenge id with the action, so one verified code serves one action."""

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, update

from p2b.audit.interface import record_security_event
from p2b.core.config import Settings
from p2b.core.crypto import encrypt
from p2b.core.db import Database
from p2b.core.errors import OtpInvalid, OtpLocked, StateConflict
from p2b.core.ids import new_id
from p2b.core.outbox import publish
from p2b.core.ratelimit import Limit, enforce
from p2b.core.vocabulary import Audience, ContactKind, OtpPurpose, OtpState, SecuritySeverity
from p2b.identity.models import OtpChallenge, UserContact
from p2b.identity.otp import (
    _TIMING_HASH,
    POLICY,
    OtpIssued,
    _code_matches,
    _hasher,
    _peppered,
    mask_email,
)

START_PER_USER = Limit("confirm_start_user", 5, 600)
VERIFY_PER_USER = Limit("confirm_verify_user", 20, 600)
CONFIRMED = "OTP_CONFIRMATION_VERIFIED"
REJECTED = "OTP_CONFIRMATION_REJECTED"


@dataclass(frozen=True)
class ConfirmationStarted:
    challenge_id: uuid.UUID
    expires_at: datetime
    sent_to: str


async def start_confirmation(
    database: Database,
    settings: Settings,
    *,
    user_id: uuid.UUID,
    audience: Audience,
    purpose: OtpPurpose,
    subject_id: uuid.UUID,
    ip_hash: str,
) -> ConfirmationStarted:
    if purpose == OtpPurpose.LOGIN:
        raise ValueError("sign-in codes are started by start_otp")
    await enforce(database, START_PER_USER, str(user_id))
    code = f"{secrets.randbelow(10**POLICY.digits):0{POLICY.digits}d}"
    challenge_id = new_id()
    async with database.transaction() as session:
        email = await session.scalar(
            select(UserContact.normalized).where(
                UserContact.user_id == user_id,
                UserContact.is_primary,
                UserContact.kind == ContactKind.EMAIL.value,
            )
        )
        if email is None:
            raise StateConflict(
                message="Your account has no email address for a confirmation code.",
                details={"reason": "NO_EMAIL"},
            )
        await session.execute(
            update(OtpChallenge)
            .where(
                OtpChallenge.user_id == user_id,
                OtpChallenge.purpose == purpose.value,
                OtpChallenge.subject_id == subject_id,
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
                purpose=purpose.value,
                contact_kind=ContactKind.EMAIL.value,
                contact_normalized=email,
                code_hash=_hasher.hash(_peppered(settings, code)),
                code_ciphertext=encrypt(
                    settings.encryption_key.get_secret_value(), code, challenge_id.bytes
                ),
                state=OtpState.ISSUED.value,
                expires_at=expires_at,
                max_attempts=POLICY.max_attempts,
                ip_hash=ip_hash,
                user_id=user_id,
                subject_id=subject_id,
            )
        )
        await session.flush()
        await publish(
            session,
            event_type="otp.issued",
            aggregate_type="otp_challenge",
            aggregate_id=challenge_id,
            payload=OtpIssued(challenge_id=challenge_id, purpose=purpose),
            dedupe_suffix="issued",
        )
    return ConfirmationStarted(challenge_id, expires_at, mask_email(email))


async def verify_confirmation(
    database: Database,
    settings: Settings,
    *,
    challenge_id: uuid.UUID,
    code: str,
    user_id: uuid.UUID,
    purpose: OtpPurpose,
    subject_id: uuid.UUID,
    ip_hash: str,
) -> None:
    """Marks the challenge VERIFIED, or raises OtpInvalid or OtpLocked after committing the
    attempt. A challenge for another user, purpose or subject is invalid."""
    await enforce(database, VERIFY_PER_USER, str(user_id))
    error: OtpInvalid | OtpLocked | None = None
    async with database.transaction() as session:
        challenge = await session.get(OtpChallenge, challenge_id, with_for_update=True)
        now = (await session.execute(select(func.now()))).scalar_one()
        if (
            challenge is None
            or challenge.user_id != user_id
            or challenge.purpose != purpose.value
            or challenge.subject_id != subject_id
        ):
            _code_matches(settings, _TIMING_HASH, code)  # same cost as a real check
            error = OtpInvalid()
        elif challenge.state == OtpState.LOCKED.value:
            error = OtpLocked()
        elif challenge.state != OtpState.ISSUED.value:
            error = OtpInvalid(details={"reason": "used_or_replaced"})
        elif challenge.expires_at <= now:
            challenge.state = OtpState.EXPIRED.value
            challenge.code_ciphertext = None
            error = OtpInvalid(details={"reason": "expired"})
        elif not _code_matches(settings, challenge.code_hash, code):
            challenge.attempts += 1
            if challenge.attempts >= challenge.max_attempts:
                challenge.state = OtpState.LOCKED.value
                challenge.locked_at = now
                challenge.code_ciphertext = None
                error = OtpLocked()
            else:
                left = challenge.max_attempts - challenge.attempts
                error = OtpInvalid(details={"attempts_left": left})
        else:
            challenge.state = OtpState.VERIFIED.value
            challenge.verified_at = now
            challenge.code_ciphertext = None
    await record_security_event(
        database,
        kind=REJECTED if error else CONFIRMED,
        severity=SecuritySeverity.WARNING if error else SecuritySeverity.INFO,
        user_id=user_id,
        ip_hash=ip_hash,
        details={"purpose": purpose.value, **({"code": error.code} if error else {})},
    )
    if error is not None:
        raise error
