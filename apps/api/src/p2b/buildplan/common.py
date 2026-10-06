"""Shared pieces of the buildplan module: who acted, history and audit, refusals with a reason,
the package gate (BP-09) and project access."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.billing.interface import package_active
from p2b.buildplan.models import BuildPlanEvent
from p2b.core.errors import Forbidden, NotFound, PackageRequired, StateConflict
from p2b.core.ids import new_id
from p2b.core.vocabulary import ActorType, MembershipRole, PackageAvailability
from p2b.identity.interface import Actor
from p2b.projects.interface import BuildPlanFacts, build_plan_facts, member_role

FAMILY_ROLES = (MembershipRole.OWNER, MembershipRole.HOUSEHOLD)


@dataclass(frozen=True)
class Who:
    user_id: uuid.UUID
    role: str  # FAMILY, PROFESSIONAL, OPS, ADMIN
    session_id: uuid.UUID | None = None


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


async def history(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
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
        BuildPlanEvent(
            id=new_id(), project_id=project_id, subject=subject, subject_id=subject_id,
            from_state=old, to_state=new, actor_user_id=who.user_id, actor_role=who.role,
            reason=reason,
        )
    )  # fmt: skip
    await session.flush()
    await record(
        session,
        action=f"{subject.lower()}.{new.lower()}",
        entity_type=subject.lower(),
        entity_id=subject_id,
        project_id=project_id,
        actor_type=ActorType.USER,
        actor_user_id=who.user_id,
        actor_role=who.role,
        session_id=who.session_id,
        reason=reason,
        old_value={"state": old} if old else None,
        new_value={"state": new, **(detail or {})},
    )


async def require_package(session: AsyncSession, project_id: uuid.UUID) -> None:
    """BP-09: package-gated work needs an active package; reading and withdrawal never do."""
    if not await package_active(session, project_id):
        raise PackageRequired


async def project(session: AsyncSession, project_id: uuid.UUID) -> BuildPlanFacts:
    facts = await build_plan_facts(session, project_id)
    if facts is None:
        raise NotFound
    return facts


async def family_access(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, *, write: bool
) -> BuildPlanFacts:
    """Owner and household read; only the owner acts. Not a member is 404."""
    membership = await member_role(session, user_id=actor.user_id, project_id=project_id)
    if membership is None or membership.role not in FAMILY_ROLES:
        raise NotFound
    if write and membership.role != MembershipRole.OWNER:
        raise Forbidden
    facts = await project(session, project_id)
    if write and facts.availability != PackageAvailability.ELIGIBLE:
        raise conflict(
            "NOT_ELIGIBLE",
            "This is available once the project has passed Plan2Build's initial review.",
        )
    return facts
