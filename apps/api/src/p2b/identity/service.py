"""Accounts and sessions (DOMAIN_ARCHITECTURE 3.2; STATE_MODEL section 2; ADR-010)."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.core.config import SESSION_POLICIES
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import ActorType, Audience, ContactKind, UserStatus
from p2b.identity.models import Session, User, UserContact

S = UserStatus
# STATE_MODEL section 2. The only writer of users.status.
USER_ACCOUNT = TransitionTable[UserStatus](
    "user_account",
    [
        Transition(None, S.PENDING_VERIFICATION, "register"),
        Transition(S.PENDING_VERIFICATION, S.ACTIVE, "verify_contact"),
        Transition(S.ACTIVE, S.SUSPENDED, "suspend"),
        Transition(S.SUSPENDED, S.ACTIVE, "reinstate"),
        Transition(S.SUSPENDED, S.CLOSED, "close_suspended"),
        Transition(S.ACTIVE, S.CLOSED, "close"),
    ],
)

# Refresh last_seen and slide the idle expiry at most this often, to avoid a write per request.
TOUCH_INTERVAL = timedelta(minutes=5)


@dataclass(frozen=True)
class Actor:
    """The authenticated caller, resolved from the session on every request."""

    user_id: uuid.UUID
    session_id: uuid.UUID
    audience: Audience
    status: UserStatus
    display_name: str | None
    locale: str
    mfa_verified_at: datetime | None


@dataclass(frozen=True)
class IssuedSession:
    token: str
    session_id: uuid.UUID
    max_age_seconds: int


class SessionRevoked(EventPayload):
    session_id: uuid.UUID
    user_id: uuid.UUID
    reason: str


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


async def create_session(session: AsyncSession, *, user_id: uuid.UUID) -> IssuedSession:
    """Create a session for a verified user. Called only after OTP verification (slice 1) or by
    tests; a session id is never accepted from the client (fixation, SECURITY section 5)."""
    user = await session.get_one(User, user_id)
    audience = Audience(user.audience)
    policy = SESSION_POLICIES[audience]
    token = secrets.token_urlsafe(32)  # 256 bits
    session_id = new_id()
    session.add(
        Session(
            id=session_id,
            token_hash=hash_token(token),
            user_id=user_id,
            audience=audience.value,
            expires_at=func.now() + policy.idle,
            absolute_expires_at=func.now() + policy.absolute,
        )
    )
    await session.flush()
    await record(
        session,
        action="session.created",
        entity_type="session",
        entity_id=session_id,
        actor_type=ActorType.USER,
        actor_user_id=user_id,
        session_id=session_id,
    )
    return IssuedSession(token, session_id, int(policy.absolute.total_seconds()))


async def resolve_session(session: AsyncSession, *, token: str, audience: Audience) -> Actor | None:
    """One indexed read. The session must be unrevoked, unexpired (idle and absolute, against
    database time) and belong to this host's audience."""
    row = (
        await session.execute(
            select(Session, User)
            .join(User, User.id == Session.user_id)
            .where(
                Session.token_hash == hash_token(token),
                Session.audience == audience.value,
                Session.revoked_at.is_(None),
                Session.expires_at > func.now(),
                Session.absolute_expires_at > func.now(),
            )
        )
    ).one_or_none()
    if row is None:
        return None
    stored, user = row
    policy = SESSION_POLICIES[audience]
    await session.execute(
        update(Session)
        .where(Session.id == stored.id, Session.last_seen_at < func.now() - TOUCH_INTERVAL)
        .values(
            last_seen_at=func.now(),
            expires_at=func.least(func.now() + policy.idle, Session.absolute_expires_at),
        )
    )
    return Actor(
        user_id=user.id,
        session_id=stored.id,
        audience=audience,
        status=UserStatus(user.status),
        display_name=user.display_name,
        locale=user.locale,
        mfa_verified_at=stored.mfa_verified_at,
    )


async def elevate_session(session: AsyncSession, *, actor: Actor) -> IssuedSession:
    """After a verified second factor: a new session id marked MFA-verified, the old one revoked
    (SECURITY 3.2 rotation on privilege change). The new session keeps the old absolute expiry,
    so re-verifying every 8 hours never stretches a session past its absolute lifetime."""
    old = await session.get_one(Session, actor.session_id, with_for_update=True)
    token = secrets.token_urlsafe(32)
    session_id = new_id()
    now = (await session.execute(select(func.now()))).scalar_one()
    policy = SESSION_POLICIES[actor.audience]
    session.add(
        Session(
            id=session_id,
            token_hash=hash_token(token),
            user_id=actor.user_id,
            audience=actor.audience.value,
            expires_at=min(now + policy.idle, old.absolute_expires_at),
            absolute_expires_at=old.absolute_expires_at,
            mfa_verified_at=now,
        )
    )
    old.revoked_at = now
    await session.flush()
    await record(
        session,
        action="session.mfa_verified",
        entity_type="session",
        entity_id=session_id,
        actor_type=ActorType.USER,
        actor_user_id=actor.user_id,
        session_id=session_id,
        old_value={"session_id": str(actor.session_id)},
    )
    max_age = int((old.absolute_expires_at - now).total_seconds())
    return IssuedSession(token, session_id, max(max_age, 0))


async def revoke_session(session: AsyncSession, *, actor: Actor, reason: str) -> None:
    result = await session.execute(
        update(Session)
        .where(Session.id == actor.session_id, Session.revoked_at.is_(None))
        .values(revoked_at=func.now())
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]  # already revoked: nothing to record
        return
    await record(
        session,
        action="session.revoked",
        entity_type="session",
        entity_id=actor.session_id,
        actor_type=ActorType.USER,
        actor_user_id=actor.user_id,
        session_id=actor.session_id,
        reason=reason,
    )
    await publish(
        session,
        event_type="session.revoked",
        aggregate_type="session",
        aggregate_id=actor.session_id,
        payload=SessionRevoked(session_id=actor.session_id, user_id=actor.user_id, reason=reason),
        dedupe_suffix="revoked",
    )


async def primary_email(session: AsyncSession, user_id: uuid.UUID) -> str | None:
    return (await primary_emails(session, [user_id])).get(user_id)


async def primary_emails(session: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Primary email per user, in one query (staff views; P2 data, staff routes only)."""
    if not user_ids:
        return {}
    rows = await session.execute(
        select(UserContact.user_id, UserContact.normalized).where(
            UserContact.user_id.in_(user_ids),
            UserContact.is_primary,
            UserContact.kind == ContactKind.EMAIL.value,
        )
    )
    return {user_id: email for user_id, email in rows.all()}
