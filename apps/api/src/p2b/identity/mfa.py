"""TOTP second factor for operations and admin (SECURITY 3.3; DATA 4.2 `mfa_secrets`).

RFC 6238 through pyotp: 30-second steps, one step of drift either way, six digits. A code is
accepted once: the step it matched is stored and only later steps pass afterwards. The secret is
encrypted with the application key and bound to the user id. Ten recovery codes are shown once at
enrolment, stored as argon2id hashes and removed when used. Verification attempts are rate
limited per session and per account; every outcome is a security event.
"""

import base64
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Literal

import pyotp
import segno
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.core.config import Settings
from p2b.core.crypto import decrypt, encrypt
from p2b.core.errors import MfaAlreadyEnrolled, MfaInvalid, MfaNotEnrolled
from p2b.core.ratelimit import Limit
from p2b.core.vocabulary import ActorType
from p2b.identity.models import MfaSecret

ISSUER = "Plan2Build"
STEP_SECONDS = 30
DRIFT_STEPS = 1
RECOVERY_CODE_COUNT = 10

# SECURITY 3.3 and 9: limits on guessing. Every attempt counts, right or wrong.
VERIFY_PER_SESSION = Limit("mfa_verify_session", 5, 600)
VERIFY_PER_ACCOUNT = Limit("mfa_verify_account", 15, 3600)

_hasher = PasswordHasher()


def _bound_to(user_id: uuid.UUID) -> bytes:
    return f"mfa_secret:{user_id}".encode()


def _secret(settings: Settings, row: MfaSecret) -> str:
    key = settings.encryption_key.get_secret_value()
    return decrypt(key, row.secret_ciphertext, _bound_to(row.user_id))


def matching_step(secret: str, code: str, now: float) -> int | None:
    """The time step whose code equals `code`, within the allowed drift (constant-time compare)."""
    totp = pyotp.TOTP(secret)
    current = int(now) // STEP_SECONDS
    found = None
    for step in range(current - DRIFT_STEPS, current + DRIFT_STEPS + 1):
        if hmac.compare_digest(totp.at(step * STEP_SECONDS), code):
            found = step
    return found


def new_recovery_code() -> str:
    """Ten base32 characters (50 bits) in two groups, for example `k7m2q-x9p4r`."""
    raw = base64.b32encode(secrets.token_bytes(7)).decode().lower()[:10]
    return f"{raw[:5]}-{raw[5:]}"


def normalise_recovery_code(code: str) -> str:
    compact = "".join(code.split()).lower().replace("-", "")
    return f"{compact[:5]}-{compact[5:]}"


@dataclass(frozen=True)
class Enrolment:
    secret: str
    otpauth_uri: str
    qr_svg_data_uri: str


async def status(session: AsyncSession, user_id: uuid.UUID) -> tuple[bool, int]:
    """(enrolled, recovery codes left)."""
    row = await session.get(MfaSecret, user_id)
    if row is None or row.enabled_at is None:
        return False, 0
    return True, len(row.recovery_code_hashes)


async def start_enrolment(
    session: AsyncSession, settings: Settings, *, user_id: uuid.UUID, account_name: str
) -> Enrolment:
    """A new secret, pending until a code from it is confirmed. Starting again replaces a pending
    secret; an enabled one cannot be replaced here (reset is an admin action, later)."""
    row = await session.get(MfaSecret, user_id, with_for_update=True)
    if row is not None and row.enabled_at is not None:
        raise MfaAlreadyEnrolled
    secret = pyotp.random_base32()  # 160 bits
    ciphertext = encrypt(settings.encryption_key.get_secret_value(), secret, _bound_to(user_id))
    if row is None:
        session.add(MfaSecret(user_id=user_id, secret_ciphertext=ciphertext))
    else:
        row.secret_ciphertext = ciphertext
        row.last_used_step = None
        row.recovery_code_hashes = []
        row.version += 1
    await session.flush()
    await record(
        session,
        action="mfa.enrolment_started",
        entity_type="user",
        entity_id=user_id,
        actor_type=ActorType.USER,
        actor_user_id=user_id,
    )
    uri = pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=ISSUER)
    qr = segno.make(uri, error="m").svg_data_uri(scale=5, border=2)
    return Enrolment(secret=secret, otpauth_uri=uri, qr_svg_data_uri=qr)


async def confirm_enrolment(
    session: AsyncSession, settings: Settings, *, user_id: uuid.UUID, code: str
) -> list[str]:
    """Enable the pending secret with a valid code; returns the recovery codes, shown once."""
    row = await session.get(MfaSecret, user_id, with_for_update=True)
    if row is None:
        raise MfaNotEnrolled
    if row.enabled_at is not None:
        raise MfaAlreadyEnrolled
    step = matching_step(_secret(settings, row), code, time.time())
    if step is None:
        raise MfaInvalid
    codes = [new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    row.recovery_code_hashes = [_hasher.hash(code) for code in codes]
    row.last_used_step = step
    row.enabled_at = (await session.execute(select(func.now()))).scalar_one()
    row.version += 1
    await record(
        session,
        action="mfa.enrolled",
        entity_type="user",
        entity_id=user_id,
        actor_type=ActorType.USER,
        actor_user_id=user_id,
    )
    return codes


async def verify(
    session: AsyncSession, settings: Settings, *, user_id: uuid.UUID, code: str
) -> Literal["totp", "recovery"]:
    """Check a six-digit code or a recovery code; raises MfaInvalid when neither matches."""
    row = await session.get(MfaSecret, user_id, with_for_update=True)
    if row is None or row.enabled_at is None:
        raise MfaNotEnrolled
    candidate = code.strip()
    if candidate.isdigit() and len(candidate) == 6:
        step = matching_step(_secret(settings, row), candidate, time.time())
        if step is not None and (row.last_used_step is None or step > row.last_used_step):
            row.last_used_step = step
            row.version += 1
            return "totp"
        raise MfaInvalid
    normalised = normalise_recovery_code(candidate)
    for stored in row.recovery_code_hashes:
        try:
            _hasher.verify(stored, normalised)
        except (VerificationError, InvalidHashError):
            continue
        row.recovery_code_hashes = [h for h in row.recovery_code_hashes if h != stored]
        row.version += 1
        await record(
            session,
            action="mfa.recovery_code_used",
            entity_type="user",
            entity_id=user_id,
            actor_type=ActorType.USER,
            actor_user_id=user_id,
            new_value={"recovery_codes_left": len(row.recovery_code_hashes)},
        )
        return "recovery"
    raise MfaInvalid
