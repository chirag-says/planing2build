"""Read models for the family, the professional and operations. Disclosure (N-08) is decided
here, in one place: a professional's view shows the family's contact only for an ACCEPTED
request, and the plot pin and shared files only while that engagement is ACTIVE."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.billing.interface import package_state
from p2b.core.config import Settings
from p2b.core.vocabulary import (
    ConnectionState,
    DeclineReason,
    EngagementOrigin,
    EngagementParty,
    EngagementState,
    MembershipRole,
    NeedState,
    PackageAvailability,
    QuoteReviewState,
    WithdrawReason,
)
from p2b.documents.interface import FileSummary, personal_files, requirement_files
from p2b.engagements.models import (
    Connection,
    EngagementDocument,
    EngagementEvent,
    ProjectEngagement,
    ProjectServiceNeed,
    QuoteReviewRequest,
)
from p2b.engagements.schemas import (
    BriefOut,
    CategoryServiceOut,
    FamilyConnectionOut,
    FamilyContactOut,
    FamilyEngagementOut,
    FileOut,
    OpsConnectionOut,
    OpsEngagementOut,
    OpsEngagementsOut,
    OpsHistoryOut,
    OpsNeedOut,
    OpsQuoteReviewOut,
    PointOut,
    ProConnectionOut,
    ProEngagementOut,
    ProfessionalContactOut,
    QuoteReviewOut,
    ServicesOut,
)
from p2b.engagements.service import categories, needs
from p2b.identity.interface import Actor
from p2b.professionals.interface import profile_names
from p2b.projects.interface import ConnectionFacts, connection_facts, member_role

CN = ConnectionState


def file_out(summary: FileSummary) -> FileOut:
    return FileOut(
        file_id=summary.file_id,
        file_name=summary.file_name,
        content_type=summary.content_type,
        size_bytes=summary.size_bytes,
        state=summary.state,
    )


def _pro_contact(raw: dict[str, Any] | None) -> ProfessionalContactOut | None:
    return ProfessionalContactOut.model_validate(raw) if raw else None


async def _shared(
    session: AsyncSession, engagement_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    result: dict[uuid.UUID, list[uuid.UUID]] = {e: [] for e in engagement_ids}
    if not engagement_ids:
        return result
    rows = await session.execute(
        select(EngagementDocument.engagement_id, EngagementDocument.file_id)
        .where(
            EngagementDocument.engagement_id.in_(engagement_ids),
            EngagementDocument.unshared_at.is_(None),
        )
        .order_by(EngagementDocument.shared_at)
    )
    for engagement_id, file_id in rows.all():
        result[engagement_id].append(file_id)
    return result


# --- the family ----------------------------------------------------------------------------


async def services_out(
    session: AsyncSession, settings: Settings, actor: Actor, facts: ConnectionFacts
) -> ServicesOut:
    membership = await member_role(session, user_id=actor.user_id, project_id=facts.project_id)
    known = await categories(session)
    project_needs = await needs(session, facts)
    connections = list(
        await session.scalars(
            select(Connection)
            .where(Connection.project_id == facts.project_id)
            .order_by(Connection.sent_at.desc())
        )
    )
    engagements = list(
        await session.scalars(
            select(ProjectEngagement)
            .where(ProjectEngagement.project_id == facts.project_id)
            .order_by(ProjectEngagement.started_at.desc())
        )
    )
    profiles = {c.profile_id for c in connections} | {
        e.profile_id for e in engagements if e.profile_id
    }
    names = await profile_names(session, list(profiles))
    shared = await _shared(session, [e.id for e in engagements])
    by_id = {c.id: c for c in connections}

    def engagement_out(e: ProjectEngagement) -> FamilyEngagementOut:
        listed = e.party == EngagementParty.LISTED.value
        _, display, firm = names.get(e.profile_id, (None, None, None)) if e.profile_id else (
            None, e.outside_name, e.outside_firm
        )  # fmt: skip
        source = by_id.get(e.connection_id) if e.connection_id else None
        contact = source.professional_contact if source else e.professional_contact
        return FamilyEngagementOut(
            id=e.id,
            party=EngagementParty(e.party),
            state=EngagementState(e.state),
            started_at=e.started_at,
            ended_at=e.ended_at,
            profile_id=e.profile_id,
            name=display,
            firm=firm,
            contact=None if listed else e.outside_contact,
            professional_contact=_pro_contact(contact) if listed else None,
            shared_file_ids=shared.get(e.id, []),
        )

    def connection_out(c: Connection) -> FamilyConnectionOut:
        _, display, firm = names.get(c.profile_id, (None, None, None))
        return FamilyConnectionOut(
            id=c.id,
            profile_id=c.profile_id,
            professional_name=display,
            firm_name=firm,
            state=CN(c.state),
            sent_at=c.sent_at,
            respond_by=c.respond_by,
            responded_at=c.responded_at,
            withdraw_reason=WithdrawReason(c.withdraw_reason) if c.withdraw_reason else None,
            professional_contact=(
                _pro_contact(c.professional_contact) if c.state == CN.ACCEPTED.value else None
            ),
        )

    rows = []
    for code, name in known.names.items():
        need = project_needs[code]
        mine = [c for c in connections if c.category_code == code]
        theirs = [e for e in engagements if e.category_code == code]
        active = next((e for e in theirs if e.state == EngagementState.ACTIVE.value), None)
        rows.append(
            CategoryServiceOut(
                code=code,
                name=name,
                subtypes=known.subtypes[code],
                need=need.state,
                need_source=need.source,
                chosen_subtypes=need.subtypes,
                open_requests=sum(c.state == CN.SENT.value for c in mine),
                open_limit=settings.connection_open_limit,
                engagement=engagement_out(active) if active else None,
                connections=[connection_out(c) for c in mine],
                past_engagements=[engagement_out(e) for e in theirs if e is not active],
            )
        )
    reviews = list(
        await session.scalars(
            select(QuoteReviewRequest)
            .where(QuoteReviewRequest.project_id == facts.project_id)
            .order_by(QuoteReviewRequest.submitted_at.desc())
        )
    )
    review_files = await personal_files(
        session, actor.user_id, [f for r in reviews for f in r.file_ids]
    )
    files = await requirement_files(session, facts.project_id)
    return ServicesOut(
        project_id=facts.project_id,
        project_code=facts.code,
        availability=facts.availability,
        package_state=await package_state(session, facts.project_id),
        can_act=membership is not None
        and membership.role == MembershipRole.OWNER
        and facts.availability == PackageAvailability.ELIGIBLE,
        has_contractor=facts.has_contractor,
        response_hours=settings.connection_response_hours,
        categories=rows,
        requirement_files=[file_out(f) for f in files.values()],
        quote_reviews=[
            QuoteReviewOut(
                id=r.id,
                category=r.category_code,
                quoted_by=r.quoted_by,
                note=r.note,
                files=[file_out(review_files[f]) for f in r.file_ids if f in review_files],
                state=QuoteReviewState(r.state),
                submitted_at=r.submitted_at,
            )
            for r in reviews
        ],
    )


# --- the professional ----------------------------------------------------------------------


def _brief(c: Connection) -> BriefOut:
    b = c.brief
    return BriefOut(
        category=c.category_code,
        subtypes=list(b.get("subtypes") or []),
        locality=b.get("locality"),
        plot_area_sqft=b.get("plot_area_sqft"),
        built_up_area_sqft=b.get("built_up_area_sqft"),
        floors=b.get("floors"),
        basement=b.get("basement"),
        budget_band=b.get("budget_band"),
        start_window=b.get("start_window"),
        services=list(b.get("services") or []),
    )


async def pro_connection_out(
    session: AsyncSession, c: Connection, *, detail: bool
) -> ProConnectionOut:
    """`detail` adds the pin and the shared files (one connection, not the list)."""
    known = await categories(session)
    engagement = await session.get(ProjectEngagement, c.engagement_id) if c.engagement_id else None
    active = engagement is not None and engagement.state == EngagementState.ACTIVE.value
    accepted = c.state == CN.ACCEPTED.value
    location = files = None
    if detail and engagement is not None and active:
        facts = await connection_facts(session, c.project_id)
        location = (
            PointOut(lat=facts.point[0], lng=facts.point[1]) if facts and facts.point else None
        )
        ids = await _shared(session, [engagement.id])
        summaries = await requirement_files(session, c.project_id, ids[engagement.id])
        files = [file_out(s) for s in summaries.values()]
    return ProConnectionOut(
        id=c.id,
        category=c.category_code,
        category_name=known.names.get(c.category_code, c.category_code),
        state=CN(c.state),
        sent_at=c.sent_at,
        respond_by=c.respond_by,
        responded_at=c.responded_at,
        brief=_brief(c),
        decline_reason=DeclineReason(c.decline_reason) if c.decline_reason else None,
        decline_note=c.decline_note,
        withdraw_reason=WithdrawReason(c.withdraw_reason) if c.withdraw_reason else None,
        family_contact=FamilyContactOut.model_validate(c.family_contact) if accepted else None,
        location=location,
        engagement_id=engagement.id if engagement else None,
        engagement_state=EngagementState(engagement.state) if engagement else None,
        shared_files=files or [],
    )


async def pro_engagement_out(session: AsyncSession, e: ProjectEngagement) -> ProEngagementOut:
    """The family's contact comes from the accepted connection or, for an RFQ selection, from the
    engagement itself; the pin and shared files only while ACTIVE (N-08)."""
    known = await categories(session)
    facts = await connection_facts(session, e.project_id)
    assert facts is not None  # noqa: S101 (FK)
    source = await session.get(Connection, e.connection_id) if e.connection_id else None
    raw = source.family_contact if source else e.family_contact
    active = e.state == EngagementState.ACTIVE.value
    files: list[FileOut] = []
    if active:
        ids = await _shared(session, [e.id])
        summaries = await requirement_files(session, e.project_id, ids[e.id])
        files = [file_out(s) for s in summaries.values()]
    point = facts.point if active else None
    return ProEngagementOut(
        id=e.id,
        project_code=facts.code,
        category=e.category_code,
        category_name=known.names.get(e.category_code, e.category_code),
        origin=EngagementOrigin(e.origin),
        state=EngagementState(e.state),
        started_at=e.started_at,
        ended_at=e.ended_at,
        family_contact=FamilyContactOut.model_validate(raw) if raw else None,
        location=PointOut(lat=point[0], lng=point[1]) if point else None,
        shared_files=files,
    )


# --- operations ----------------------------------------------------------------------------


async def ops_out(session: AsyncSession, facts: ConnectionFacts) -> OpsEngagementsOut:
    project_id = facts.project_id
    project_needs = await needs(session, facts)
    stored = {
        n.category_code
        for n in await session.scalars(
            select(ProjectServiceNeed).where(ProjectServiceNeed.project_id == project_id)
        )
    }
    connections = list(
        await session.scalars(
            select(Connection)
            .where(Connection.project_id == project_id)
            .order_by(Connection.sent_at.desc())
        )
    )
    engagements = list(
        await session.scalars(
            select(ProjectEngagement)
            .where(ProjectEngagement.project_id == project_id)
            .order_by(ProjectEngagement.started_at.desc())
        )
    )
    names = await profile_names(
        session,
        list(
            {c.profile_id for c in connections}
            | {e.profile_id for e in engagements if e.profile_id}
        ),
    )
    shared = await _shared(session, [e.id for e in engagements])
    reviews = await session.scalars(
        select(QuoteReviewRequest)
        .where(QuoteReviewRequest.project_id == project_id)
        .order_by(QuoteReviewRequest.submitted_at.desc())
    )
    history = await session.scalars(
        select(EngagementEvent)
        .where(EngagementEvent.project_id == project_id)
        .order_by(EngagementEvent.at.desc(), EngagementEvent.id)
        .limit(200)
    )
    return OpsEngagementsOut(
        project_id=project_id,
        needs=[
            OpsNeedOut(
                category=n.category_code, state=n.state, source=n.source, subtypes=n.subtypes
            )
            for n in project_needs.values()
            if n.category_code in stored or n.state != NeedState.UNDECIDED
        ],
        connections=[
            OpsConnectionOut(
                id=c.id,
                category=c.category_code,
                profile_id=c.profile_id,
                professional_name=names.get(c.profile_id, (None, None, None))[1],
                state=CN(c.state),
                sent_at=c.sent_at,
                respond_by=c.respond_by,
                responded_at=c.responded_at,
                decline_reason=DeclineReason(c.decline_reason) if c.decline_reason else None,
                decline_note=c.decline_note,
                withdraw_reason=WithdrawReason(c.withdraw_reason) if c.withdraw_reason else None,
                withdrawn_by_role=c.withdrawn_by_role,
                withdraw_note=c.withdraw_note,
                family_contact=c.family_contact,
                professional_contact=c.professional_contact,
            )
            for c in connections
        ],
        engagements=[
            OpsEngagementOut(
                id=e.id,
                category=e.category_code,
                party=EngagementParty(e.party),
                state=EngagementState(e.state),
                profile_id=e.profile_id,
                name=names.get(e.profile_id, (None, None, None))[1]
                if e.profile_id
                else e.outside_name,
                firm=names.get(e.profile_id, (None, None, None))[2]
                if e.profile_id
                else e.outside_firm,
                contact=e.outside_contact,
                started_at=e.started_at,
                ended_at=e.ended_at,
                ended_by_role=e.ended_by_role,
                end_reason=e.end_reason,
                shared_file_ids=shared.get(e.id, []),
            )
            for e in engagements
        ],
        quote_reviews=[
            OpsQuoteReviewOut(
                id=r.id,
                category=r.category_code,
                quoted_by=r.quoted_by,
                note=r.note,
                file_ids=r.file_ids,
                state=QuoteReviewState(r.state),
                submitted_at=r.submitted_at,
            )
            for r in reviews
        ],
        history=[
            OpsHistoryOut(
                subject=h.subject,
                subject_id=h.subject_id,
                category=h.category_code,
                from_state=h.from_state,
                to_state=h.to_state,
                actor_role=h.actor_role,
                reason=h.reason,
                at=h.at,
            )
            for h in history
        ],
    )
