"""Public interface of the engagements module. Notifications read what an email may say about a
connection; buildplan reads engagements (3.5); rfq takes the category lock, reads the ACTIVE
engagement and creates or reuses it for a selection (3.6, ADR-024)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.engagements.models import Connection, ProjectEngagement, QuoteReviewRequest
from p2b.engagements.service import (
    categories,
    engage_for_selection,
    lock_category,
)
from p2b.professionals.interface import profile_names
from p2b.projects.interface import connection_facts


@dataclass(frozen=True)
class ConnectionNotice:
    """Facts an email about a connection may carry (N-11). Nothing private: no family identity
    for the professional, no decline reason for the family."""

    family_user_id: uuid.UUID
    professional_user_id: uuid.UUID
    project_code: str
    category_name: str
    locality: str
    professional_name: str
    respond_hours: int


async def connection_notice(
    session: AsyncSession, connection_id: uuid.UUID
) -> ConnectionNotice | None:
    connection = await session.get(Connection, connection_id)
    if connection is None:
        return None
    facts = await connection_facts(session, connection.project_id)
    names = await profile_names(session, [connection.profile_id])
    if facts is None or connection.profile_id not in names:
        return None
    user_id, display_name, firm_name = names[connection.profile_id]
    window = connection.respond_by - connection.sent_at
    return ConnectionNotice(
        family_user_id=facts.owner_user_id,
        professional_user_id=user_id,
        project_code=facts.code,
        category_name=(await categories(session)).names.get(
            connection.category_code, connection.category_code
        ),
        locality=str(connection.brief.get("locality") or "your area"),
        professional_name=display_name or firm_name or "The professional",
        respond_hours=round(window.total_seconds() / 3600),
    )


@dataclass(frozen=True)
class QuoteReviewNotice:
    project_code: str
    category_name: str


async def quote_review_notice(
    session: AsyncSession, quote_review_id: uuid.UUID
) -> QuoteReviewNotice | None:
    request = await session.get(QuoteReviewRequest, quote_review_id)
    if request is None:
        return None
    facts = await connection_facts(session, request.project_id)
    if facts is None:
        return None
    name = (await categories(session)).names.get(request.category_code, request.category_code)
    return QuoteReviewNotice(project_code=facts.code, category_name=name)


__all__ = [
    "ConnectionNotice",
    "EngagementFacts",
    "QuoteReviewNotice",
    "active_engagement",
    "active_engagements_of_profile",
    "connection_notice",
    "engage_for_selection",
    "engagement_facts",
    "contractor_history",
    "engagement_names",
    "lock_category",
    "quote_review_notice",
]


@dataclass(frozen=True)
class EngagementFacts:
    """An engagement as the buildplan module sees it (Slice 3.5)."""

    id: uuid.UUID
    project_id: uuid.UUID
    category_code: str
    party: str  # LISTED or OUTSIDE
    active: bool
    profile_id: uuid.UUID | None
    outside_name: str | None
    outside_firm: str | None


def _facts(row: ProjectEngagement) -> EngagementFacts:
    return EngagementFacts(
        row.id, row.project_id, row.category_code, row.party, row.state == "ACTIVE",
        row.profile_id, row.outside_name, row.outside_firm,
    )  # fmt: skip


async def engagement_facts(
    session: AsyncSession, engagement_id: uuid.UUID
) -> EngagementFacts | None:
    row = await session.get(ProjectEngagement, engagement_id)
    return _facts(row) if row else None


async def active_engagements_of_profile(
    session: AsyncSession, profile_id: uuid.UUID
) -> list[EngagementFacts]:
    rows = await session.scalars(
        select(ProjectEngagement).where(
            ProjectEngagement.profile_id == profile_id, ProjectEngagement.state == "ACTIVE"
        )
    )
    return [_facts(row) for row in rows]


async def active_engagement(
    session: AsyncSession, project_id: uuid.UUID, category_code: str
) -> EngagementFacts | None:
    row = (
        await session.scalars(
            select(ProjectEngagement).where(
                ProjectEngagement.project_id == project_id,
                ProjectEngagement.category_code == category_code,
                ProjectEngagement.state == "ACTIVE",
            )
        )
    ).one_or_none()
    return _facts(row) if row else None


async def engagement_names(
    session: AsyncSession, engagement_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str | None]:
    """The name to show for each engagement's party, whatever its state now (Slice 3.7: an
    update stays with the contractor who posted it, EX-19)."""
    if not engagement_ids:
        return {}
    rows = list(
        await session.scalars(
            select(ProjectEngagement).where(ProjectEngagement.id.in_(engagement_ids))
        )
    )
    names = await profile_names(session, [r.profile_id for r in rows if r.profile_id])
    out: dict[uuid.UUID, str | None] = {}
    for row in rows:
        if row.profile_id is not None and row.profile_id in names:
            _, display_name, firm_name = names[row.profile_id]
            out[row.id] = display_name or firm_name
        else:
            out[row.id] = row.outside_firm or row.outside_name
    return out


async def contractor_history(
    session: AsyncSession, project_id: uuid.UUID, category_code: str = "CONTRACTOR"
) -> list[dict[str, object]]:
    """Every engagement of the category, oldest first, as the Build Record names them (I.1): an
    OUTSIDE party is labelled as chosen by the family."""
    rows = list(
        await session.scalars(
            select(ProjectEngagement)
            .where(
                ProjectEngagement.project_id == project_id,
                ProjectEngagement.category_code == category_code,
            )
            .order_by(ProjectEngagement.started_at, ProjectEngagement.id)
        )
    )
    names = await engagement_names(session, [r.id for r in rows])
    return [
        {
            "name": names.get(r.id), "party": r.party, "origin": r.origin, "state": r.state,
            "chosen_by_family": r.party == "OUTSIDE",
            "started_at": r.started_at.isoformat(),
            "ended_at": r.ended_at.isoformat() if r.ended_at else None,
        }
        for r in rows
    ]  # fmt: skip
