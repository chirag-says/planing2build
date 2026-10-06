"""Service needs, connections and engagements (Slice 3.4; SLICE3_4_READINESS sections 0, 0.1).

Every rule is per project and per professional category (modularity): one ACTIVE engagement per
category (N-02), at most `connection_open_limit` open requests per category (N-05), a response
window of `connection_response_hours` (N-07). A connection needs the active package (PD-19); an
outside professional is recorded free. The professional sees a brief without identity until they
accept; then the family's contact, the plot pin and the files the family shares (N-08).

Lock order, so concurrent actions cannot deadlock: the category's need row, then connections,
then the engagement. The need row is the per-category lock for every write that counts or
creates connections or engagements."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.billing.interface import package_active, record_service_usage
from p2b.catalog.interface import categories_for_services, service_category_rows
from p2b.core.config import Settings
from p2b.core.errors import Forbidden, NotFound, PackageRequired, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import (
    ActorType,
    ConnectionState,
    DeclineReason,
    EngagementOrigin,
    EngagementParty,
    EngagementState,
    FilePurpose,
    FileState,
    MembershipRole,
    NeedSource,
    NeedState,
    PackageAvailability,
    PackageServiceKind,
    ProjectStatus,
    QuoteReviewState,
    WithdrawReason,
)
from p2b.documents.interface import file_purpose, personal_files, requirement_files
from p2b.engagements.models import (
    Connection,
    EngagementDocument,
    EngagementEvent,
    ProjectEngagement,
    ProjectServiceNeed,
    QuoteReviewRequest,
)
from p2b.identity.interface import Actor, primary_emails
from p2b.professionals.interface import (
    ConnectionCandidate,
    connection_candidate,
    profile_by_user,
)
from p2b.projects.interface import ConnectionFacts, connection_facts, member_role

CN = ConnectionState
CONNECTION = TransitionTable[ConnectionState](
    "connection",
    [
        Transition(None, CN.SENT, "send"),
        Transition(CN.SENT, CN.ACCEPTED, "accept"),
        Transition(CN.SENT, CN.DECLINED, "decline"),
        Transition(CN.SENT, CN.EXPIRED, "expire"),
        Transition(CN.SENT, CN.WITHDRAWN, "withdraw"),
    ],
)
EN = EngagementState
ENGAGEMENT = TransitionTable[EngagementState](
    "engagement",
    [
        Transition(None, EN.ACTIVE, "accept"),
        Transition(None, EN.ACTIVE, "record_outside"),
        Transition(None, EN.ACTIVE, "select"),  # an RFQ quote selected (3.6, ADR-024)
        Transition(EN.ACTIVE, EN.ENDED, "end"),
    ],
)

FAMILY_ROLES = (MembershipRole.OWNER, MembershipRole.HOUSEHOLD)
USAGE_SERVICE = PackageServiceKind.CONNECTION_ACCEPTED  # N-12


class ConnectionChanged(EventPayload):
    """`connection.sent|accepted|declined|expired|withdrawn`: ids and the state only."""

    connection_id: uuid.UUID
    project_id: uuid.UUID
    category_code: str
    state: ConnectionState
    reason: WithdrawReason | None = None


class QuoteReviewSubmitted(EventPayload):
    quote_review_id: uuid.UUID
    project_id: uuid.UUID
    category_code: str


@dataclass(frozen=True)
class FamilyContact:
    name: str
    phone: str
    site_address: str | None


@dataclass(frozen=True)
class OutsideProfessional:
    name: str
    firm: str | None
    contact: str | None


@dataclass(frozen=True)
class Who:
    """Who acted, for history and audit."""

    user_id: uuid.UUID | None
    role: str  # FAMILY, PROFESSIONAL, OPS, ADMIN, SYSTEM
    session_id: uuid.UUID | None = None

    @property
    def actor_type(self) -> ActorType:
        return ActorType.USER if self.user_id else ActorType.JOB


SYSTEM = Who(None, "SYSTEM")


def _conflict(reason: str, message: str, **details: Any) -> StateConflict:
    """409 with a machine-readable `reason` the screens translate."""
    return StateConflict(message=message, details={"reason": reason, **details})


async def _now(session: AsyncSession) -> datetime:
    with session.sync_session.no_autoflush:
        now: datetime = (await session.execute(select(func.now()))).scalar_one()
    return now


# --- categories and access -----------------------------------------------------------------


@dataclass(frozen=True)
class Categories:
    """Active top-level categories in display order, with their subtypes (N-01: a specialist
    trade is a subtype of SPECIALIST)."""

    names: dict[str, str]
    subtypes: dict[str, dict[str, str]]


async def categories(session: AsyncSession) -> Categories:
    rows = await service_category_rows(session)
    names = {r.code: r.name for r in rows if r.parent_code is None}
    subtypes: dict[str, dict[str, str]] = {code: {} for code in names}
    for r in rows:
        if r.parent_code in subtypes:
            subtypes[r.parent_code][r.code] = r.name
    return Categories(names, subtypes)


async def _category(session: AsyncSession, code: str) -> Categories:
    known = await categories(session)
    if code not in known.names:
        raise NotFound
    return known


async def family_access(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, *, write: bool
) -> ConnectionFacts:
    """Project membership: the owner and household read; only the owner acts. Not a member is
    404, so a project's existence is not disclosed."""
    membership = await member_role(session, user_id=actor.user_id, project_id=project_id)
    if membership is None or membership.role not in FAMILY_ROLES:
        raise NotFound
    if write and membership.role != MembershipRole.OWNER:
        raise Forbidden
    facts = await connection_facts(session, project_id)
    if facts is None:
        raise NotFound
    if write and facts.availability != PackageAvailability.ELIGIBLE:
        raise _conflict(
            "NOT_ELIGIBLE",
            "This is available once the project has passed Plan2Build's initial review.",
            availability=facts.availability.value,
        )
    return facts


async def own_profile_id(session: AsyncSession, actor: Actor) -> uuid.UUID:
    profile_id = await profile_by_user(session, actor.user_id)
    if profile_id is None:
        raise NotFound
    return profile_id


# --- history -------------------------------------------------------------------------------


async def _history(
    session: AsyncSession,
    *,
    subject: str,
    row: Connection | ProjectEngagement,
    old: str | None,
    who: Who,
    reason: str | None = None,
) -> None:
    session.add(
        EngagementEvent(
            id=new_id(),
            project_id=row.project_id,
            subject=subject,
            subject_id=row.id,
            category_code=row.category_code,
            from_state=old,
            to_state=row.state,
            actor_user_id=who.user_id,
            actor_role=who.role,
            reason=reason,
        )
    )
    await session.flush()
    await record(
        session,
        action=f"{subject.lower()}.{row.state.lower()}",
        entity_type=subject.lower(),
        entity_id=row.id,
        project_id=row.project_id,
        actor_type=who.actor_type,
        actor_user_id=who.user_id,
        actor_role=who.role,
        session_id=who.session_id,
        reason=reason,
        old_value={"state": old} if old else None,
        new_value={"state": row.state, "category": row.category_code},
    )
    if subject == "CONNECTION":
        assert isinstance(row, Connection)  # noqa: S101 (subject names the row type)
        await publish(
            session,
            event_type=f"connection.{row.state.lower()}",
            aggregate_type="connection",
            aggregate_id=row.id,
            payload=ConnectionChanged(
                connection_id=row.id,
                project_id=row.project_id,
                category_code=row.category_code,
                state=ConnectionState(row.state),
                reason=WithdrawReason(row.withdraw_reason) if row.withdraw_reason else None,
            ),
            dedupe_suffix=row.state,
        )


# --- needs ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Need:
    category_code: str
    state: NeedState
    source: NeedSource
    subtypes: list[str]


async def _derived(session: AsyncSession, facts: ConnectionFacts) -> set[str]:
    """Categories the requirement's services answer names (N-01, data in
    `service_value_categories`)."""
    return set(await categories_for_services(session, facts.question_set_version, facts.services))


async def needs(session: AsyncSession, facts: ConnectionFacts) -> dict[str, Need]:
    """One need per active category. Until the family sets it, a need is derived from the
    requirement and nothing is stored."""
    known = await categories(session)
    derived = await _derived(session, facts)
    stored = {
        row.category_code: row
        for row in await session.scalars(
            select(ProjectServiceNeed).where(ProjectServiceNeed.project_id == facts.project_id)
        )
    }
    result = {}
    for code in known.names:
        row = stored.get(code)
        if row is not None:
            result[code] = Need(code, NeedState(row.state), NeedSource(row.source), row.subtypes)
        else:
            state = NeedState.NEEDED if code in derived else NeedState.UNDECIDED
            result[code] = Need(code, state, NeedSource.REQUIREMENT, [])
    return result


async def _locked_need(
    session: AsyncSession, facts: ConnectionFacts, code: str
) -> ProjectServiceNeed:
    """The category's need row, created from the requirement if absent, locked."""
    derived = code in await _derived(session, facts)
    await session.execute(
        pg_insert(ProjectServiceNeed)
        .values(
            id=new_id(),
            project_id=facts.project_id,
            category_code=code,
            state=(NeedState.NEEDED if derived else NeedState.UNDECIDED).value,
            source=NeedSource.REQUIREMENT.value,
        )
        .on_conflict_do_nothing(index_elements=["project_id", "category_code"])
    )
    return (
        await session.scalars(
            select(ProjectServiceNeed)
            .where(
                ProjectServiceNeed.project_id == facts.project_id,
                ProjectServiceNeed.category_code == code,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).one()


async def _mark_needed(session: AsyncSession, need: ProjectServiceNeed, who: Who) -> None:
    if need.state == NeedState.NOT_NEEDED.value:
        raise _conflict("NOT_NEEDED", "You marked this service as not needed.")
    if need.state == NeedState.UNDECIDED.value:
        await _set_need_state(session, need, NeedState.NEEDED, need.subtypes, who)


async def _set_need_state(
    session: AsyncSession, need: ProjectServiceNeed, state: NeedState, subtypes: list[str], who: Who
) -> None:
    old = {"state": need.state, "subtypes": list(need.subtypes)}
    need.state = state.value
    need.subtypes = subtypes
    need.source = NeedSource.FAMILY.value
    need.updated_by = who.user_id
    need.updated_at = await _now(session)
    need.version += 1
    await session.flush()
    await record(
        session, action="service_need.set", entity_type="service_need", entity_id=need.id,
        project_id=need.project_id, actor_type=who.actor_type, actor_user_id=who.user_id,
        actor_role=who.role, session_id=who.session_id, old_value=old,
        new_value={"state": state.value, "subtypes": subtypes, "category": need.category_code},
    )  # fmt: skip


async def _active_engagement(
    session: AsyncSession, project_id: uuid.UUID, code: str
) -> ProjectEngagement | None:
    return (
        await session.scalars(
            select(ProjectEngagement).where(
                ProjectEngagement.project_id == project_id,
                ProjectEngagement.category_code == code,
                ProjectEngagement.state == EN.ACTIVE.value,
            )
        )
    ).one_or_none()


async def _open_connections(
    session: AsyncSession, project_id: uuid.UUID, code: str, *, lock: bool = False
) -> list[Connection]:
    query = select(Connection).where(
        Connection.project_id == project_id,
        Connection.category_code == code,
        Connection.state == CN.SENT.value,
    )
    return list(await session.scalars(query.with_for_update() if lock else query))


async def set_need(
    session: AsyncSession,
    actor: Actor,
    project_id: uuid.UUID,
    code: str,
    state: NeedState,
    subtypes: list[str],
) -> None:
    facts = await family_access(session, actor, project_id, write=True)
    known = await _category(session, code)
    unknown = set(subtypes) - set(known.subtypes[code])
    if unknown:
        raise ValidationFailed(details={"fields": {"subtypes": ["Choose from the listed types."]}})
    need = await _locked_need(session, facts, code)
    if state == NeedState.NOT_NEEDED and (
        await _active_engagement(session, project_id, code)
        or await _open_connections(session, project_id, code)
    ):
        raise _conflict(
            "IN_USE", "End the engagement or withdraw the open requests first.", category=code
        )
    who = Who(actor.user_id, "FAMILY", actor.session_id)
    await _set_need_state(session, need, state, sorted(set(subtypes)), who)


# --- connections: the family ---------------------------------------------------------------


SEND_BLOCKERS = {
    "NOT_OWNER": "Only the project owner can send requests.",
    "NOT_ELIGIBLE": "This is available once the project has passed Plan2Build's initial review.",
    "NOT_NEEDED": "You marked this service as not needed.",
    "ENGAGED": "This service already has an active professional.",
    "DUPLICATE": "You already have an open request with this professional.",
    "OPEN_LIMIT": "You have the most open requests allowed for this service.",
    "NO_LOCATION": "The project has no plot location.",
    "NOT_LISTED": "This professional is not listed for this service.",
    "SELF": "You cannot send a request to yourself.",
    "OUTSIDE_AREA": "This professional does not serve the project's area.",
}


async def send_blocker(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    facts: ConnectionFacts,
    code: str,
    need_state: NeedState,
    candidate: ConnectionCandidate | None,
) -> str | None:
    """Why a request to this professional for this category cannot be sent now (a key of
    SEND_BLOCKERS, or PACKAGE_REQUIRED), else None. The request screen and the send share it."""
    membership = await member_role(session, user_id=actor.user_id, project_id=facts.project_id)
    if membership is None or membership.role != MembershipRole.OWNER:
        return "NOT_OWNER"
    if facts.availability != PackageAvailability.ELIGIBLE:
        return "NOT_ELIGIBLE"
    if not await package_active(session, facts.project_id):
        return "PACKAGE_REQUIRED"
    if need_state == NeedState.NOT_NEEDED:
        return "NOT_NEEDED"
    if await _active_engagement(session, facts.project_id, code) is not None:
        return "ENGAGED"
    open_now = await _open_connections(session, facts.project_id, code)
    if candidate is not None and any(c.profile_id == candidate.profile_id for c in open_now):
        return "DUPLICATE"
    if len(open_now) >= settings.connection_open_limit:
        return "OPEN_LIMIT"
    if facts.point is None:
        return "NO_LOCATION"
    if candidate is None or not candidate.listed or candidate.hidden:
        return "NOT_LISTED"
    if candidate.user_id == actor.user_id:
        return "SELF"
    if not candidate.covers:
        return "OUTSIDE_AREA"
    return None


async def open_count(session: AsyncSession, project_id: uuid.UUID, code: str) -> int:
    return len(await _open_connections(session, project_id, code))


async def send_connection(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    project_id: uuid.UUID,
    code: str,
    profile_id: uuid.UUID,
    contact: FamilyContact,
) -> Connection:
    facts = await family_access(session, actor, project_id, write=True)
    await _category(session, code)
    need = await _locked_need(session, facts, code)
    candidate = await connection_candidate(session, profile_id, code, facts.point or (0.0, 0.0))
    blocker = await send_blocker(
        session, settings, actor, facts, code, NeedState(need.state), candidate
    )
    if blocker == "PACKAGE_REQUIRED":
        raise PackageRequired
    if blocker is not None:
        details = {"limit": settings.connection_open_limit} if blocker == "OPEN_LIMIT" else {}
        raise _conflict(blocker, SEND_BLOCKERS[blocker], **details)
    who = Who(actor.user_id, "FAMILY", actor.session_id)
    await _mark_needed(session, need, who)
    email = (await primary_emails(session, [actor.user_id])).get(actor.user_id)
    now = await _now(session)
    connection = Connection(
        id=new_id(),
        project_id=project_id,
        category_code=code,
        profile_id=profile_id,
        state=CONNECTION.target(None, "send").value,
        brief={**facts.brief, "category": code, "subtypes": list(need.subtypes)},
        family_contact={
            "name": contact.name,
            "phone": contact.phone,
            "email": email,
            "site_address": contact.site_address,
        },
        sent_by=actor.user_id,
        sent_at=now,
        respond_by=now + timedelta(hours=settings.connection_response_hours),
    )
    session.add(connection)
    await session.flush()
    await _history(session, subject="CONNECTION", row=connection, old=None, who=who)
    return connection


async def _withdraw(
    session: AsyncSession,
    connection: Connection,
    reason: WithdrawReason,
    who: Who,
    note: str | None = None,
) -> None:
    old = connection.state
    connection.state = CONNECTION.target(CN(old), "withdraw").value
    connection.withdraw_reason = reason.value
    connection.withdrawn_by_role = who.role
    connection.withdraw_note = note
    connection.responded_at = await _now(session)
    connection.version += 1
    await session.flush()
    await _history(
        session, subject="CONNECTION", row=connection, old=old, who=who, reason=reason.value
    )


async def _family_connection(
    session: AsyncSession, project_id: uuid.UUID, connection_id: uuid.UUID
) -> Connection:
    connection = await session.get(Connection, connection_id, with_for_update=True)
    if connection is None or connection.project_id != project_id:
        raise NotFound
    return connection


async def withdraw_by_family(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, connection_id: uuid.UUID
) -> Connection:
    """Allowed without a package: withdrawing stops coordination, it does not start any."""
    membership = await member_role(session, user_id=actor.user_id, project_id=project_id)
    if membership is None or membership.role not in FAMILY_ROLES:
        raise NotFound
    if membership.role != MembershipRole.OWNER:
        raise Forbidden
    connection = await _family_connection(session, project_id, connection_id)
    await _withdraw(
        session, connection, WithdrawReason.FAMILY, Who(actor.user_id, "FAMILY", actor.session_id)
    )
    return connection


# --- connections: the professional ---------------------------------------------------------


async def own_connection(
    session: AsyncSession, actor: Actor, connection_id: uuid.UUID, *, lock: bool = False
) -> Connection:
    profile_id = await own_profile_id(session, actor)
    connection = await session.get(Connection, connection_id, with_for_update=lock)
    if connection is None or connection.profile_id != profile_id:
        raise NotFound
    return connection


async def _respondable(session: AsyncSession, connection: Connection) -> None:
    if connection.state != CN.SENT.value:
        raise StateConflict(details={"current_state": connection.state})
    if connection.respond_by <= await _now(session):
        raise _conflict("EXPIRED", "The time to respond to this request has passed.")


async def accept(
    session: AsyncSession, actor: Actor, connection_id: uuid.UUID, phone: str | None
) -> Connection:
    first = await own_connection(session, actor, connection_id)
    facts = await connection_facts(session, first.project_id)
    assert facts is not None  # noqa: S101 (FK)
    await _locked_need(session, facts, first.category_code)
    connection = await own_connection(session, actor, connection_id, lock=True)
    await _respondable(session, connection)
    if facts.status == ProjectStatus.CANCELLED:
        raise _conflict("PROJECT_CLOSED", "This project is no longer active.")
    if not await package_active(session, connection.project_id):
        raise _conflict("PACKAGE_ENDED", "This request is no longer open.")
    if await _active_engagement(session, connection.project_id, connection.category_code):
        raise _conflict("ENGAGED", "The family has already engaged a professional for this.")
    # Coverage was checked when the request was sent; only the listing matters now.
    candidate = await connection_candidate(
        session, connection.profile_id, connection.category_code, facts.point or (0.0, 0.0)
    )
    if candidate is None or not candidate.listed:
        raise _conflict("NOT_LISTED", "You are not listed for this service now.")
    who = Who(actor.user_id, "PROFESSIONAL", actor.session_id)
    now = await _now(session)
    engagement = ProjectEngagement(
        id=new_id(),
        project_id=connection.project_id,
        category_code=connection.category_code,
        party=EngagementParty.LISTED.value,
        origin=EngagementOrigin.CONNECTION.value,
        profile_id=connection.profile_id,
        connection_id=connection.id,
        state=ENGAGEMENT.target(None, "accept").value,
        created_by=actor.user_id,
        started_at=now,
    )
    session.add(engagement)
    await session.flush()
    email = (await primary_emails(session, [actor.user_id])).get(actor.user_id)
    old = connection.state
    connection.state = CONNECTION.target(CN(old), "accept").value
    connection.responded_at = now
    connection.engagement_id = engagement.id
    connection.professional_contact = {
        "name": candidate.display_name,
        "firm": candidate.firm_name,
        "phone": phone,
        "email": email,
    }
    connection.version += 1
    await session.flush()
    await _history(session, subject="CONNECTION", row=connection, old=old, who=who)
    await _history(session, subject="ENGAGEMENT", row=engagement, old=None, who=who)
    for other in await _open_connections(
        session, connection.project_id, connection.category_code, lock=True
    ):
        await _withdraw(session, other, WithdrawReason.ANOTHER_ENGAGED, SYSTEM)
    await record_service_usage(session, connection.project_id, USAGE_SERVICE, connection.id)
    return connection


async def decline(
    session: AsyncSession,
    actor: Actor,
    connection_id: uuid.UUID,
    reason: DeclineReason,
    note: str | None,
) -> Connection:
    note = (note or "").strip() or None
    if reason == DeclineReason.OTHER and note is None:
        raise ValidationFailed(details={"fields": {"note": ["Explain the reason."]}})
    connection = await own_connection(session, actor, connection_id, lock=True)
    await _respondable(session, connection)
    old = connection.state
    connection.state = CONNECTION.target(CN(old), "decline").value
    connection.decline_reason = reason.value
    connection.decline_note = note
    connection.responded_at = await _now(session)
    connection.version += 1
    await session.flush()
    who = Who(actor.user_id, "PROFESSIONAL", actor.session_id)
    await _history(
        session, subject="CONNECTION", row=connection, old=old, who=who, reason=reason.value
    )
    return connection


# --- system transitions --------------------------------------------------------------------


async def expire_due(session: AsyncSession, *, limit: int = 500) -> int:
    """N-07: SENT past `respond_by` becomes EXPIRED. No auto-accept, no reminder."""
    rows = list(
        await session.scalars(
            select(Connection)
            .where(Connection.state == CN.SENT.value, Connection.respond_by <= func.now())
            .order_by(Connection.respond_by)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for connection in rows:
        old = connection.state
        connection.state = CONNECTION.target(CN(old), "expire").value
        connection.responded_at = await _now(session)
        connection.version += 1
        await session.flush()
        await _history(session, subject="CONNECTION", row=connection, old=old, who=SYSTEM)
    return len(rows)


async def withdraw_open(
    session: AsyncSession,
    reason: WithdrawReason,
    *,
    project_id: uuid.UUID | None = None,
    profile_id: uuid.UUID | None = None,
    category_code: str | None = None,
) -> int:
    """System withdrawal of open requests: the package refunded or cancelled (N-10), the
    project cancelled, the professional no longer listed. Engagements are untouched: the
    direct relationship is the family's and the professional's."""
    query = select(Connection).where(Connection.state == CN.SENT.value)
    if project_id is not None:
        query = query.where(Connection.project_id == project_id)
    if profile_id is not None:
        query = query.where(Connection.profile_id == profile_id)
    if category_code is not None:
        query = query.where(Connection.category_code == category_code)
    rows = list(await session.scalars(query.order_by(Connection.sent_at).with_for_update()))
    for connection in rows:
        await _withdraw(session, connection, reason, SYSTEM)
    return len(rows)


async def withdraw_by_staff(
    session: AsyncSession, who: Who, connection_id: uuid.UUID, note: str
) -> Connection:
    connection = await session.get(Connection, connection_id, with_for_update=True)
    if connection is None:
        raise NotFound
    await _withdraw(session, connection, WithdrawReason.OPERATIONS, who, note)
    return connection


# --- engagements ---------------------------------------------------------------------------


async def record_outside(
    session: AsyncSession,
    actor: Actor,
    project_id: uuid.UUID,
    code: str,
    outside: OutsideProfessional,
) -> ProjectEngagement:
    """The family's own professional (no package needed, N-10). Open requests in the category
    are withdrawn: the category now has its one active engagement (N-02)."""
    facts = await family_access(session, actor, project_id, write=True)
    await _category(session, code)
    need = await _locked_need(session, facts, code)
    if await _active_engagement(session, project_id, code) is not None:
        raise _conflict("ENGAGED", "This service already has an active professional.")
    who = Who(actor.user_id, "FAMILY", actor.session_id)
    if need.state != NeedState.NEEDED.value:
        await _set_need_state(session, need, NeedState.NEEDED, need.subtypes, who)
    engagement = ProjectEngagement(
        id=new_id(),
        project_id=project_id,
        category_code=code,
        party=EngagementParty.OUTSIDE.value,
        origin=EngagementOrigin.OUTSIDE.value,
        outside_name=outside.name,
        outside_firm=outside.firm,
        outside_contact=outside.contact,
        state=ENGAGEMENT.target(None, "record_outside").value,
        created_by=actor.user_id,
        started_at=await _now(session),
    )
    session.add(engagement)
    await session.flush()
    await _history(session, subject="ENGAGEMENT", row=engagement, old=None, who=who)
    for other in await _open_connections(session, project_id, code, lock=True):
        await _withdraw(session, other, WithdrawReason.ANOTHER_ENGAGED, SYSTEM)
    return engagement


async def end_engagement(
    session: AsyncSession, engagement: ProjectEngagement, who: Who, reason: str
) -> None:
    """Ends Plan2Build's record of the engagement; shared files stop being visible. Whatever
    the family and the professional agreed between themselves is theirs."""
    old = engagement.state
    engagement.state = ENGAGEMENT.target(EN(old), "end").value
    now = await _now(session)
    engagement.ended_at = now
    engagement.ended_by_role = who.role
    engagement.end_reason = reason
    engagement.version += 1
    for shared in await session.scalars(
        select(EngagementDocument).where(
            EngagementDocument.engagement_id == engagement.id,
            EngagementDocument.unshared_at.is_(None),
        )
    ):
        shared.unshared_at = now
    await session.flush()
    await _history(session, subject="ENGAGEMENT", row=engagement, old=old, who=who, reason=reason)


async def locked_engagement(session: AsyncSession, engagement_id: uuid.UUID) -> ProjectEngagement:
    engagement = await session.get(ProjectEngagement, engagement_id, with_for_update=True)
    if engagement is None:
        raise NotFound
    return engagement


async def end_by_family(
    session: AsyncSession,
    actor: Actor,
    project_id: uuid.UUID,
    engagement_id: uuid.UUID,
    reason: str,
) -> None:
    await family_access(session, actor, project_id, write=True)
    engagement = await locked_engagement(session, engagement_id)
    if engagement.project_id != project_id:
        raise NotFound
    await end_engagement(
        session, engagement, Who(actor.user_id, "FAMILY", actor.session_id), reason
    )


async def end_by_professional(
    session: AsyncSession, actor: Actor, connection_id: uuid.UUID, reason: str
) -> None:
    connection = await own_connection(session, actor, connection_id)
    if connection.engagement_id is None:
        raise StateConflict(details={"current_state": connection.state})
    engagement = await locked_engagement(session, connection.engagement_id)
    await end_engagement(
        session, engagement, Who(actor.user_id, "PROFESSIONAL", actor.session_id), reason
    )


# --- documents shared with an engagement ---------------------------------------------------


async def _family_active_listed(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, engagement_id: uuid.UUID
) -> ProjectEngagement:
    await family_access(session, actor, project_id, write=True)
    engagement = await locked_engagement(session, engagement_id)
    if engagement.project_id != project_id:
        raise NotFound
    if engagement.state != EN.ACTIVE.value or engagement.party != EngagementParty.LISTED.value:
        raise StateConflict(details={"current_state": engagement.state})
    return engagement


async def share_files(
    session: AsyncSession,
    actor: Actor,
    project_id: uuid.UUID,
    engagement_id: uuid.UUID,
    file_ids: list[uuid.UUID],
) -> None:
    """N-08: nothing is shared by default; the family chooses requirement files for one
    engagement."""
    engagement = await _family_active_listed(session, actor, project_id, engagement_id)
    wanted = list(dict.fromkeys(file_ids))
    available = await requirement_files(session, project_id, wanted)
    if len(available) != len(wanted):
        raise ValidationFailed(details={"fields": {"file_ids": ["Choose your project's files."]}})
    for file_id in wanted:
        inserted = await session.execute(
            pg_insert(EngagementDocument)
            .values(
                id=new_id(), engagement_id=engagement.id, file_id=file_id, shared_by=actor.user_id
            )
            .on_conflict_do_nothing(
                index_elements=["engagement_id", "file_id"],
                index_where=EngagementDocument.unshared_at.is_(None),
            )
            .returning(EngagementDocument.id)
        )
        if inserted.scalar_one_or_none() is not None:
            await record(
                session, action="engagement.file_shared", entity_type="engagement",
                entity_id=engagement.id, project_id=project_id, actor_type=ActorType.USER,
                actor_user_id=actor.user_id, actor_role="FAMILY", session_id=actor.session_id,
                new_value={"file_id": str(file_id)},
            )  # fmt: skip


async def unshare_file(
    session: AsyncSession,
    actor: Actor,
    project_id: uuid.UUID,
    engagement_id: uuid.UUID,
    file_id: uuid.UUID,
) -> None:
    engagement = await _family_active_listed(session, actor, project_id, engagement_id)
    shared = (
        await session.scalars(
            select(EngagementDocument).where(
                EngagementDocument.engagement_id == engagement.id,
                EngagementDocument.file_id == file_id,
                EngagementDocument.unshared_at.is_(None),
            )
        )
    ).one_or_none()
    if shared is None:
        raise NotFound
    shared.unshared_at = await _now(session)
    await session.flush()
    await record(
        session, action="engagement.file_unshared", entity_type="engagement",
        entity_id=engagement.id, project_id=project_id, actor_type=ActorType.USER,
        actor_user_id=actor.user_id, actor_role="FAMILY", session_id=actor.session_id,
        old_value={"file_id": str(file_id)},
    )  # fmt: skip


async def shared_file_ids(session: AsyncSession, engagement_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        await session.scalars(
            select(EngagementDocument.file_id)
            .where(
                EngagementDocument.engagement_id == engagement_id,
                EngagementDocument.unshared_at.is_(None),
            )
            .order_by(EngagementDocument.shared_at)
        )
    )


async def professional_may_read(
    session: AsyncSession, actor: Actor, connection_id: uuid.UUID, file_id: uuid.UUID
) -> Connection:
    """The file is shared with this professional's ACTIVE engagement."""
    connection = await own_connection(session, actor, connection_id)
    if connection.engagement_id is None:
        raise NotFound
    engagement = await session.get(ProjectEngagement, connection.engagement_id)
    if engagement is None or engagement.state != EN.ACTIVE.value:
        raise NotFound
    if file_id not in await shared_file_ids(session, engagement.id):
        raise NotFound
    return connection


# --- quote-holder review intake ------------------------------------------------------------

QUOTE_FILES_MAX = 5


async def submit_quote_review(
    session: AsyncSession,
    actor: Actor,
    project_id: uuid.UUID,
    code: str,
    quoted_by: str,
    note: str | None,
    file_ids: list[uuid.UUID],
) -> QuoteReviewRequest:
    """Intake only (3.4): the family's quote reaches operations. Reviewing, normalising and
    comparing quotes are the later quote workflow."""
    await family_access(session, actor, project_id, write=True)
    await _category(session, code)
    if not await package_active(session, project_id):
        raise PackageRequired
    wanted = list(dict.fromkeys(file_ids))
    if not 1 <= len(wanted) <= QUOTE_FILES_MAX:
        raise ValidationFailed(details={"fields": {"file_ids": ["Attach 1 to 5 files."]}})
    owned = await personal_files(session, actor.user_id, wanted)
    for file_id in wanted:
        summary = owned.get(file_id)
        purpose = await file_purpose(session, file_id)
        if (
            summary is None
            or summary.state != FileState.AVAILABLE
            or purpose is None
            or purpose[1] != FilePurpose.QUOTE_DOCUMENT.value
        ):
            raise ValidationFailed(
                details={"fields": {"file_ids": ["Upload the quote and wait for the check."]}}
            )
    request = QuoteReviewRequest(
        id=new_id(),
        project_id=project_id,
        category_code=code,
        quoted_by=quoted_by,
        note=note,
        file_ids=wanted,
        state=QuoteReviewState.SUBMITTED.value,
        submitted_by=actor.user_id,
    )
    session.add(request)
    await session.flush()
    await record(
        session, action="quote_review.submitted", entity_type="quote_review",
        entity_id=request.id, project_id=project_id, actor_type=ActorType.USER,
        actor_user_id=actor.user_id, actor_role="FAMILY", session_id=actor.session_id,
        new_value={"category": code, "files": len(wanted)},
    )  # fmt: skip
    await publish(
        session,
        event_type="quote_review.submitted",
        aggregate_type="quote_review",
        aggregate_id=request.id,
        payload=QuoteReviewSubmitted(
            quote_review_id=request.id, project_id=project_id, category_code=code
        ),
        dedupe_suffix="submitted",
    )
    return request


# --- RFQ selection (Slice 3.6, ADR-024; QD-01, QD-12, QD-13) -------------------------------


async def lock_category(session: AsyncSession, project_id: uuid.UUID, code: str) -> NeedState:
    """Take the category's per-project lock (the need row, created from the requirement if
    absent) before reading or creating its engagement, as every engagements write does."""
    facts = await connection_facts(session, project_id)
    if facts is None:
        raise NotFound
    return NeedState((await _locked_need(session, facts, code)).state)


async def engage_for_selection(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    code: str,
    profile_id: uuid.UUID | None,
    outside_engagement_id: uuid.UUID | None,
    selection_id: uuid.UUID,
    family_contact: dict[str, Any],
    professional_contact: dict[str, Any] | None,
    by_user_id: uuid.UUID,
) -> tuple[uuid.UUID, bool]:
    """The homeowner selected a quote: the category's one engagement (N-02). An ACTIVE
    engagement with the same party is reused (QD-13); one with anyone else refuses the selection
    (ENGAGED). Otherwise a LISTED engagement starts now with origin RFQ_SELECTION, the contacts
    are exchanged as on an accepted connection (N-08), and the family's open requests in the
    category are withdrawn. Returns the engagement id and whether it was created."""
    facts = await connection_facts(session, project_id)
    if facts is None:
        raise NotFound
    need = await _locked_need(session, facts, code)
    who = Who(by_user_id, "FAMILY")
    active = await _active_engagement(session, project_id, code)
    if active is not None:
        same = (profile_id is not None and active.profile_id == profile_id) or (
            outside_engagement_id is not None and active.id == outside_engagement_id
        )
        if not same:
            raise _conflict("ENGAGED", "This service already has an active professional.")
        await _history(
            session, subject="ENGAGEMENT", row=active, old=active.state, who=who,
            reason="RFQ quote selected",
        )  # fmt: skip
        return active.id, False
    if profile_id is None:
        raise _conflict("ENGAGEMENT_ENDED", "The outside professional is no longer engaged.")
    await _mark_needed(session, need, who)
    engagement = ProjectEngagement(
        id=new_id(),
        project_id=project_id,
        category_code=code,
        party=EngagementParty.LISTED.value,
        origin=EngagementOrigin.RFQ_SELECTION.value,
        profile_id=profile_id,
        selection_id=selection_id,
        family_contact=family_contact,
        professional_contact=professional_contact,
        state=ENGAGEMENT.target(None, "select").value,
        created_by=by_user_id,
        started_at=await _now(session),
    )
    session.add(engagement)
    await session.flush()
    await _history(session, subject="ENGAGEMENT", row=engagement, old=None, who=who)
    for other in await _open_connections(session, project_id, code, lock=True):
        await _withdraw(session, other, WithdrawReason.ANOTHER_ENGAGED, SYSTEM)
    return engagement.id, True


async def own_engagement(
    session: AsyncSession, actor: Actor, engagement_id: uuid.UUID, *, lock: bool = False
) -> ProjectEngagement:
    """A listed engagement of the signed-in professional, whatever its origin."""
    profile_id = await own_profile_id(session, actor)
    engagement = await session.get(ProjectEngagement, engagement_id, with_for_update=lock)
    if engagement is None or engagement.profile_id != profile_id:
        raise NotFound
    return engagement


async def professional_may_read_shared(
    session: AsyncSession, actor: Actor, engagement_id: uuid.UUID, file_id: uuid.UUID
) -> ProjectEngagement:
    engagement = await own_engagement(session, actor, engagement_id)
    if engagement.state != EN.ACTIVE.value or file_id not in await shared_file_ids(
        session, engagement.id
    ):
        raise NotFound
    return engagement


async def end_own_engagement(
    session: AsyncSession, actor: Actor, engagement_id: uuid.UUID, reason: str
) -> None:
    engagement = await own_engagement(session, actor, engagement_id, lock=True)
    await end_engagement(
        session, engagement, Who(actor.user_id, "PROFESSIONAL", actor.session_id), reason
    )
