"""Review decisions by operations and the family's workspace (STATE_MODEL 5; rulings 2.1, 2.6,
2.7). The caller of the decision functions holds the OPS role with MFA; the operations module
checks the claim and resolves its queue item in the same transaction.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.catalog.interface import GroupRow, active_eligibility_checklist, spec_groups
from p2b.construction.interface import StageView, instantiate_stages, stages_for
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.outbox import publish
from p2b.core.vocabulary import ActorType, EligibilityOutcome, ProjectStatus
from p2b.identity.interface import Actor
from p2b.projects.models import EligibilityAssessment, Project, ProjectStatusHistory
from p2b.projects.service import (
    PROJECT,
    WITH_WORKSPACE,
    ReviewDecided,
    _member_project,
    _record_status,
)
from p2b.specification.interface import LineView, instantiate_lines, lines_for

P = ProjectStatus
STAFF_ROLE = "OPS"


async def _locked_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id, with_for_update=True)
    if project is None:
        raise NotFound
    return project


def _required_text(value: str, field: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValidationFailed(details={"fields": {field: ["This is required."]}})
    return stripped


async def _publish_decision(
    session: AsyncSession, project: Project, event_type: str, message: str | None, suffix: str
) -> None:
    await publish(
        session,
        event_type=event_type,
        aggregate_type="project",
        aggregate_id=project.id,
        payload=ReviewDecided(
            project_id=project.id, owner_user_id=project.owner_user_id, message=message
        ),
        dedupe_suffix=suffix,
    )


@dataclass(frozen=True)
class EligibilityCheck:
    """Operations' outcome for one checklist item (F-05)."""

    item_id: str
    outcome: EligibilityOutcome
    note: str = ""


async def _assess(
    session: AsyncSession, actor: Actor, project: Project, checks: list[EligibilityCheck]
) -> None:
    """Every item of the ACTIVE checklist, once, PASSED (L-02). The assessment is stored with the
    acceptance; a failing or missing item is 422 with which ones."""
    checklist = await active_eligibility_checklist(session)
    if checklist is None:
        raise StateConflict(details={"eligibility": "no active checklist"})
    expected = [item.id for item in checklist.items]
    given = [c.item_id for c in checks]
    unknown = sorted(set(given) - set(expected))
    duplicated = sorted({i for i in given if given.count(i) > 1})
    missing = [i for i in expected if i not in given]
    failed = [c.item_id for c in checks if c.outcome != EligibilityOutcome.PASSED]
    if unknown or duplicated or missing or failed:
        raise ValidationFailed(
            message="Every eligibility check must pass before the project is accepted.",
            details={"eligibility": {"missing": missing, "failed": failed, "unknown": unknown,
                                     "duplicated": duplicated}},
        )  # fmt: skip
    results = [
        {"item_id": c.item_id, "outcome": c.outcome.value, "note": c.note.strip()[:1000]}
        for c in sorted(checks, key=lambda c: expected.index(c.item_id))
    ]
    assessment = EligibilityAssessment(
        id=new_id(), project_id=project.id, checklist_version_id=checklist.id, results=results,
        assessed_by=actor.user_id,
    )  # fmt: skip
    session.add(assessment)
    await session.flush()
    await record(
        session, action="project.eligibility_assessed", entity_type="eligibility_assessment",
        entity_id=assessment.id, project_id=project.id, actor_type=ActorType.USER,
        actor_user_id=actor.user_id, actor_role=STAFF_ROLE, session_id=actor.session_id,
        new_value={"checklist_version": checklist.version, "results": results},
    )  # fmt: skip


async def accept_project(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, checks: list[EligibilityCheck]
) -> Project:
    """SUBMITTED -> ACCEPTED: Plan2Build has completed its initial service-eligibility review and
    may offer the package (L-02). Needs the eligibility checklist, every item passed, stored with
    the decision. Creates the workspace in the same transaction: the stage instances (per floor,
    and a basement, for repeating stages) and the 67 specification lines, once. A repeat on an
    ACCEPTED project changes nothing: the row lock serialises concurrent requests and the UNIQUE
    constraints are the last guard. CANCELLED cannot be accepted (ruling 2.1)."""
    project = await _locked_project(session, project_id)
    current = ProjectStatus(project.status)
    if current == P.ACCEPTED:
        return project
    target = PROJECT.target(current, "accept")
    if project.floors is None or project.has_basement is None:
        raise StateConflict(details={"current_state": project.status, "missing": "floors"})
    await _assess(session, actor, project, checks)
    first = await instantiate_stages(
        session,
        project_id=project.id,
        floors=project.floors,
        has_basement=project.has_basement,
        actor_user_id=actor.user_id,
    )
    await instantiate_lines(
        session,
        project_id=project.id,
        first_stage_instance=first,
        actor_user_id=actor.user_id,
        actor_role=STAFF_ROLE,
    )
    project.status = target.value
    project.version += 1
    await session.flush()
    await _record_status(session, project, current, actor, role=STAFF_ROLE)
    await _publish_decision(session, project, "project.accepted", None, "accepted")
    return project


@dataclass(frozen=True)
class AssessmentView:
    checklist_version_id: uuid.UUID
    results: list[dict[str, str]]
    assessed_by: uuid.UUID
    assessed_at: datetime


async def eligibility_assessment(
    session: AsyncSession, project_id: uuid.UUID
) -> AssessmentView | None:
    """None for projects not yet accepted, or accepted before checklist version 1 (O-11)."""
    row = (
        await session.scalars(
            select(EligibilityAssessment).where(EligibilityAssessment.project_id == project_id)
        )
    ).one_or_none()
    if row is None:
        return None
    return AssessmentView(row.checklist_version_id, row.results, row.assessed_by, row.assessed_at)


async def request_information(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, *, message: str
) -> Project:
    """SUBMITTED -> NEEDS_INFO with a message the family sees; the requirement reopens (2.7)."""
    text = _required_text(message, "message")
    project = await _locked_project(session, project_id)
    current = ProjectStatus(project.status)
    target = PROJECT.target(current, "ask")
    project.status = target.value
    project.version += 1
    await session.flush()
    await _record_status(session, project, current, actor, role=STAFF_ROLE, reason=text)
    await _publish_decision(
        session, project, "project.needs_info", text, f"needs_info:{project.version}"
    )
    return project


async def cancel_project(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, *, reason: str
) -> Project:
    """SUBMITTED or NEEDS_INFO -> CANCELLED with a reason the family sees (2.1). Cancelling a
    cancelled project changes nothing."""
    text = _required_text(reason, "reason")
    project = await _locked_project(session, project_id)
    current = ProjectStatus(project.status)
    if current == P.CANCELLED:
        return project
    target = PROJECT.target(current, "cancel")
    project.status = target.value
    project.version += 1
    await session.flush()
    await _record_status(session, project, current, actor, role=STAFF_ROLE, reason=text)
    await _publish_decision(session, project, "project.cancelled", text, "cancelled")
    return project


@dataclass(frozen=True)
class ReviewMessage:
    """What operations told the family: a request for information or a cancellation reason."""

    status: ProjectStatus
    message: str
    at: datetime


async def review_message(session: AsyncSession, project: Project) -> ReviewMessage | None:
    """The message behind the current status, only while the project is in NEEDS_INFO or
    CANCELLED. Review flags and anything internal never pass through here."""
    if project.status not in (P.NEEDS_INFO.value, P.CANCELLED.value):
        return None
    row = (
        await session.execute(
            select(ProjectStatusHistory.reason, ProjectStatusHistory.at)
            .where(
                ProjectStatusHistory.project_id == project.id,
                ProjectStatusHistory.to_status == project.status,
            )
            .order_by(ProjectStatusHistory.at.desc())
            .limit(1)
        )
    ).first()
    if row is None or row[0] is None:
        return None
    return ReviewMessage(ProjectStatus(project.status), row[0], row[1])


@dataclass(frozen=True)
class HistoryEntry:
    from_status: ProjectStatus | None
    to_status: ProjectStatus
    actor_user_id: uuid.UUID | None
    reason: str | None
    at: datetime


async def status_history(session: AsyncSession, project_id: uuid.UUID) -> list[HistoryEntry]:
    """For staff routes only: every transition with who made it and why."""
    rows = await session.scalars(
        select(ProjectStatusHistory)
        .where(ProjectStatusHistory.project_id == project_id)
        .order_by(ProjectStatusHistory.at, ProjectStatusHistory.id)
    )
    return [
        HistoryEntry(
            from_status=ProjectStatus(row.from_status) if row.from_status else None,
            to_status=ProjectStatus(row.to_status),
            actor_user_id=row.actor_user_id,
            reason=row.reason,
            at=row.at,
        )
        for row in rows
    ]


@dataclass(frozen=True)
class Workspace:
    project: Project
    stages: list[StageView]
    groups: list[GroupRow]
    lines: list[LineView]
    criteria_visible: bool


async def get_workspace(
    session: AsyncSession,
    actor: Actor,
    project_id: uuid.UUID,
    *,
    criteria_before_package: bool,
    package_active: bool,
) -> Workspace:
    """The stages and specification lines, created when the project passed the initial review
    (ACCEPTED). Members only; 409 before then. A line's criteria are shown once the package is
    active, or before that when the F-09 setting allows it (open point; ruling 2.6 by default)."""
    project, _ = await _member_project(session, actor, project_id)
    if project.status not in WITH_WORKSPACE:
        raise StateConflict(details={"current_state": project.status})
    return Workspace(
        project=project,
        stages=await stages_for(session, project.id),
        groups=await spec_groups(session),
        lines=await lines_for(session, project.id),
        criteria_visible=criteria_before_package or package_active,
    )
