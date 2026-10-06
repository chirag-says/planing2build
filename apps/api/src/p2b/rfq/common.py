"""Shared pieces of the rfq module: who acted, refusals with a reason, time, history and audit,
notices to the notifications module, and the state machines (SLICE3_6_READINESS section T)."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.billing.interface import package_active
from p2b.core.errors import Forbidden, NotFound, PackageRequired, StateConflict
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import (
    ActorType,
    ComparisonState,
    InvitationState,
    MembershipRole,
    PackageAvailability,
    QuoteCheckState,
    QuoteVersionState,
    RfqState,
)
from p2b.identity.interface import Actor
from p2b.projects.interface import ConnectionFacts, connection_facts, member_role
from p2b.rfq.models import RfqEvent

CATEGORY = "CONTRACTOR"  # 3.6 is contractor RFQs only (QD-26)
LOCAL_TIMEZONE = "Asia/Kolkata"  # quote validity dates are calendar dates in Raipur

R = RfqState
RFQ = TransitionTable[RfqState](
    "rfq",
    [
        Transition(None, R.DRAFT, "request"),
        Transition(R.DRAFT, R.ISSUED, "issue"),
        Transition(R.ISSUED, R.CLOSED, "select"),
        Transition(R.DRAFT, R.CANCELLED, "cancel"),
        Transition(R.ISSUED, R.CANCELLED, "cancel"),
    ],
)
I = InvitationState  # noqa: E741 (the readiness tables use these letters)
INVITATION = TransitionTable[InvitationState](
    "rfq_invitation",
    [
        Transition(None, I.PROPOSED, "propose"),
        Transition(None, I.SENT, "send"),  # introduced after issue
        Transition(I.PROPOSED, I.SENT, "send"),
        Transition(I.PROPOSED, I.ACCEPTED, "capture"),  # an OUTSIDE party at issue (QD-22)
        Transition(I.SENT, I.ACCEPTED, "accept"),
        Transition(I.SENT, I.DECLINED, "decline"),
        Transition(I.SENT, I.EXPIRED, "expire"),
        Transition(I.PROPOSED, I.WITHDRAWN, "withdraw"),
        Transition(I.SENT, I.WITHDRAWN, "withdraw"),
        Transition(I.ACCEPTED, I.WITHDRAWN, "withdraw"),
    ],
)
Q = QuoteVersionState
QUOTE = TransitionTable[QuoteVersionState](
    "quote_version",
    [
        Transition(None, Q.SUBMITTED, "submit"),
        Transition(Q.SUBMITTED, Q.SUPERSEDED, "supersede"),
        Transition(Q.SUBMITTED, Q.WITHDRAWN, "withdraw"),
        Transition(Q.SUBMITTED, Q.EXPIRED, "expire"),
        Transition(Q.SUBMITTED, Q.SELECTED, "select"),
        Transition(Q.SUBMITTED, Q.NOT_SELECTED, "not_select"),
    ],
)
C = QuoteCheckState
REVIEW = TransitionTable[QuoteCheckState](
    "quote_review",
    [
        Transition(None, C.PENDING, "open"),
        Transition(C.PENDING, C.NEEDS_CLARIFICATION, "ask"),
        Transition(C.NEEDS_CLARIFICATION, C.PENDING, "answered"),
        Transition(C.PENDING, C.REVIEWED, "review"),
        Transition(C.NEEDS_CLARIFICATION, C.REVIEWED, "review"),
        Transition(C.PENDING, C.CLOSED, "close"),
        Transition(C.NEEDS_CLARIFICATION, C.CLOSED, "close"),
    ],
)
COMPARISON = TransitionTable[ComparisonState](
    "comparison",
    [
        Transition(None, ComparisonState.PUBLISHED, "publish"),
        Transition(ComparisonState.PUBLISHED, ComparisonState.SUPERSEDED, "supersede"),
        Transition(ComparisonState.PUBLISHED, ComparisonState.DECIDED, "decide"),
    ],
)
OPEN_RFQ = (R.DRAFT.value, R.ISSUED.value)
LIVE_INVITATIONS = (I.PROPOSED.value, I.SENT.value, I.ACCEPTED.value)
OPEN_REVIEW = (C.PENDING.value, C.NEEDS_CLARIFICATION.value)


@dataclass(frozen=True)
class Who:
    user_id: uuid.UUID | None
    role: str  # FAMILY, PROFESSIONAL, OPS, ADMIN, SYSTEM
    session_id: uuid.UUID | None = None

    @property
    def actor_type(self) -> ActorType:
        return ActorType.USER if self.user_id else ActorType.JOB


SYSTEM = Who(None, "SYSTEM")


def family(actor: Actor) -> Who:
    return Who(actor.user_id, "FAMILY", actor.session_id)


def professional(actor: Actor) -> Who:
    return Who(actor.user_id, "PROFESSIONAL", actor.session_id)


def conflict(reason: str, message: str, **details: Any) -> StateConflict:
    return StateConflict(message=message, details={"reason": reason, **details})


async def db_now(session: AsyncSession) -> datetime:
    with session.sync_session.no_autoflush:
        now: datetime = (await session.execute(select(func.now()))).scalar_one()
    return now


async def today(session: AsyncSession) -> date:
    """The calendar date in Raipur, against which quote validity dates are read."""
    with session.sync_session.no_autoflush:
        value: date = (
            await session.execute(
                text("SELECT (now() AT TIME ZONE :tz)::date").bindparams(tz=LOCAL_TIMEZONE)
            )
        ).scalar_one()
    return value


async def history(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    rfq_id: uuid.UUID,
    subject: str,
    subject_id: uuid.UUID,
    old: str | None,
    new: str,
    who: Who,
    reason: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """One append-only history row and one audit row, in the caller's transaction."""
    session.add(
        RfqEvent(
            id=new_id(), project_id=project_id, rfq_id=rfq_id, subject=subject,
            subject_id=subject_id, from_state=old, to_state=new, actor_user_id=who.user_id,
            actor_role=who.role, reason=reason,
        )
    )  # fmt: skip
    await session.flush()
    await record(
        session,
        action=f"rfq_{subject.lower()}.{new.lower()}",
        entity_type=f"rfq_{subject.lower()}",
        entity_id=subject_id,
        project_id=project_id,
        actor_type=who.actor_type,
        actor_user_id=who.user_id,
        actor_role=who.role,
        session_id=who.session_id,
        reason=reason,
        old_value={"state": old} if old else None,
        new_value={"state": new, **(detail or {})},
    )


# --- notices: what the notifications module turns into email (section R) -------------------


class Notice(EventPayload):
    """Ids and a notice name only, never personal data."""

    notice: str
    rfq_id: uuid.UUID
    ref_id: uuid.UUID | None = None


async def notify(
    session: AsyncSession,
    audience: str,
    notice: str,
    *,
    aggregate_id: uuid.UUID,
    rfq_id: uuid.UUID,
    ref_id: uuid.UUID | None = None,
) -> None:
    """`rfq.family_notice` and `rfq.ops_notice` carry the RFQ id; `rfq.contractor_notice`
    carries the invitation id (one contractor per event)."""
    await publish(
        session,
        event_type=f"rfq.{audience}_notice",
        aggregate_type="rfq_invitation" if audience == "contractor" else "rfq",
        aggregate_id=aggregate_id,
        payload=Notice(notice=notice, rfq_id=rfq_id, ref_id=ref_id),
        dedupe_suffix=f"{notice}:{ref_id or aggregate_id}",
    )


# --- access ------------------------------------------------------------------------------


async def require_package(session: AsyncSession, project_id: uuid.UUID) -> None:
    """PD-19: RFQ work needs an active package; reading and withdrawal never do."""
    if not await package_active(session, project_id):
        raise PackageRequired


async def family_access(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, *, write: bool
) -> ConnectionFacts:
    """Owner and household read; only the owner acts. Not a member is 404."""
    membership = await member_role(session, user_id=actor.user_id, project_id=project_id)
    if membership is None or membership.role not in (
        MembershipRole.OWNER, MembershipRole.HOUSEHOLD,
    ):  # fmt: skip
        raise NotFound
    if write and membership.role != MembershipRole.OWNER:
        raise Forbidden
    facts = await connection_facts(session, project_id)
    if facts is None:
        raise NotFound
    if write and facts.availability != PackageAvailability.ELIGIBLE:
        raise conflict(
            "NOT_ELIGIBLE",
            "This is available once the project has passed Plan2Build's initial review.",
        )
    return facts


async def project(session: AsyncSession, project_id: uuid.UUID) -> ConnectionFacts:
    facts = await connection_facts(session, project_id)
    if facts is None:
        raise NotFound
    return facts


def is_live(state: str) -> bool:
    return state in LIVE_INVITATIONS


def submitted(state: str) -> bool:
    return state == QuoteVersionState.SUBMITTED.value
