"""Public interface of the construction module. Other modules import only this file.

Slice 3.7: the money module reads stage facts and execution access; notifications read what an
execution email may say. The projects module imports this file while it loads, so the execution
functions are imported when called, not at import time."""

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.catalog.interface import stage_master_names
from p2b.construction.models import StageInstance
from p2b.construction.service import StageView, Who, floors_for, instantiate_stages, stages_for
from p2b.core.errors import NotFound
from p2b.core.vocabulary import GateStatus, StageState

if TYPE_CHECKING:
    from p2b.construction.notices import ExecutionNotice
    from p2b.engagements.interface import EngagementFacts
    from p2b.identity.interface import Actor
    from p2b.projects.interface import ConnectionFacts


@dataclass(frozen=True)
class StageFacts:
    id: uuid.UUID
    project_id: uuid.UUID
    stage_number: int
    floor: int | None
    state: StageState
    is_payment_milestone: bool
    is_gate: bool = False
    gate_status: GateStatus | None = None
    name: str = ""
    gate: int | None = None  # 1 to 6: the order of the gate stages (SCH section 4)


def _facts(row: StageInstance, name: str = "", gate: int | None = None) -> StageFacts:
    return StageFacts(
        row.id, row.project_id, row.stage_number, row.floor, StageState(row.state),
        row.is_payment_milestone, row.is_gate,
        GateStatus(row.gate_status) if row.gate_status else None, name, gate,
    )  # fmt: skip


async def _gate_numbers(session: AsyncSession, project_id: uuid.UUID) -> dict[int, int]:
    """Stage number to gate number, from the project's own gate stages in build order."""
    numbers = sorted(
        set(
            await session.scalars(
                select(StageInstance.stage_number).where(
                    StageInstance.project_id == project_id, StageInstance.is_gate
                )
            )
        )
    )
    return {number: gate for gate, number in enumerate(numbers, 1)}


async def stage_facts(
    session: AsyncSession, stage_id: uuid.UUID, *, lock: bool = False
) -> StageFacts:
    """404 when the stage does not exist. `lock` holds the stage row for the transaction."""
    stage = await session.get(StageInstance, stage_id, with_for_update=lock)
    if stage is None:
        raise NotFound
    if lock:
        await session.refresh(stage)
    names = await stage_master_names(session, [stage.stage_master_id])
    gates = await _gate_numbers(session, stage.project_id) if stage.is_gate else {}
    return _facts(stage, names.get(stage.stage_master_id, ""), gates.get(stage.stage_number))


async def gate_stages(session: AsyncSession, project_id: uuid.UUID) -> list[StageFacts]:
    """The project's gate stage instances in display order, with their gate numbers."""
    rows = list(
        await session.scalars(
            select(StageInstance)
            .where(StageInstance.project_id == project_id, StageInstance.is_gate)
            .order_by(StageInstance.sequence)
        )
    )
    names = await stage_master_names(session, list({r.stage_master_id for r in rows}))
    gates = await _gate_numbers(session, project_id)
    return [_facts(r, names.get(r.stage_master_id, ""), gates.get(r.stage_number)) for r in rows]


async def gate_stages_to_inspect(session: AsyncSession, limit: int = 200) -> list[StageFacts]:
    """Gate stages whose completion is requested and that have no inspection yet (the
    operations assurance queue, F.2), oldest request first."""
    rows = list(
        await session.scalars(
            select(StageInstance)
            .where(
                StageInstance.is_gate,
                StageInstance.state == StageState.COMPLETION_REQUESTED.value,
                StageInstance.gate_status == GateStatus.NOT_INSPECTED.value,
            )
            .order_by(StageInstance.completion_requested_at, StageInstance.id)
            .limit(limit)
        )
    )
    out = []
    for row in rows:
        names = await stage_master_names(session, [row.stage_master_id])
        gates = await _gate_numbers(session, row.project_id)
        out.append(_facts(row, names.get(row.stage_master_id, ""), gates.get(row.stage_number)))
    return out


async def set_gate_status(
    session: AsyncSession, stage_id: uuid.UUID, status: GateStatus, who: Who, *,
    reason: str | None = None,
) -> None:  # fmt: skip
    """The assurance module's only write on a stage (P.A): the gate status, recorded in the
    execution history and the audit log. Never set by hand."""
    from p2b.construction import execution  # at call time (module docstring)

    stage = await session.get(StageInstance, stage_id, with_for_update=True)
    if stage is None or not stage.is_gate:
        raise NotFound
    if stage.gate_status == status.value:
        return
    old = stage.gate_status
    stage.gate_status = status.value
    stage.version += 1
    await session.flush()
    await execution.history(
        session, stage, subject="GATE", old=old, new=status.value, who=who, reason=reason
    )


async def milestone_stages(session: AsyncSession, project_id: uuid.UUID) -> list[StageFacts]:
    """The project's payment-milestone stages in display order."""
    rows = await session.scalars(
        select(StageInstance)
        .where(StageInstance.project_id == project_id, StageInstance.is_payment_milestone)
        .order_by(StageInstance.sequence)
    )
    return [_facts(r) for r in rows]


async def execution_summary(session: AsyncSession, project_id: uuid.UUID) -> list[dict[str, object]]:
    """Each stage instance's actual dates, state, gate status and update count (Build Record
    section Execution, I.1): no planned date, no percentage."""
    from p2b.construction import execution  # at call time (module docstring)

    rows = list(
        await session.scalars(
            select(StageInstance)
            .where(StageInstance.project_id == project_id)
            .order_by(StageInstance.sequence)
        )
    )
    names = await stage_master_names(session, list({r.stage_master_id for r in rows}))
    counts = await execution.update_counts(session, project_id)
    return [
        {
            "stage_number": r.stage_number, "name": names.get(r.stage_master_id, ""),
            "floor": r.floor, "state": r.state, "is_gate": r.is_gate,
            "gate_status": r.gate_status, "is_payment_milestone": r.is_payment_milestone,
            "actual_start": r.actual_start.isoformat() if r.actual_start else None,
            "actual_end": r.actual_end.isoformat() if r.actual_end else None,
            "updates": counts.get(r.id, (0, None))[0],
        }
        for r in rows
    ]  # fmt: skip


async def family_access(
    session: AsyncSession, actor: "Actor", project_id: uuid.UUID, *, write: bool
) -> "ConnectionFacts":
    from p2b.construction import execution  # at call time (module docstring)

    return await execution.family_access(session, actor, project_id, write=write)


async def own_contractor_engagement(
    session: AsyncSession, actor: "Actor", engagement_id: uuid.UUID
) -> "EngagementFacts":
    from p2b.construction import execution

    return await execution.own_contractor_engagement(session, actor, engagement_id)


async def contractor_of_record(
    session: AsyncSession, project_id: uuid.UUID
) -> "EngagementFacts | None":
    from p2b.construction import execution

    return await execution.contractor_of_record(session, project_id)


async def open_project(session: AsyncSession, project_id: uuid.UUID) -> "ConnectionFacts":
    from p2b.construction import execution

    return await execution.open_project(session, project_id)


async def stage_notice(
    session: AsyncSession, audience: str, notice: str, stage_id: uuid.UUID, *,
    engagement_id: uuid.UUID | None = None, ref: str,
) -> None:  # fmt: skip
    """An execution notice about a stage (the money module's "marked paid")."""
    from p2b.construction import execution

    stage = await session.get(StageInstance, stage_id)
    if stage is None:
        raise NotFound
    await execution.notify(session, audience, notice, stage, engagement_id=engagement_id, ref=ref)


async def execution_notice(
    session: AsyncSession, audience: str, aggregate_id: uuid.UUID, payload: dict[str, object]
) -> "ExecutionNotice | None":
    from p2b.construction import notices

    return await notices.execution_notice(session, audience, aggregate_id, payload)


__all__ = [
    "StageFacts",
    "StageView",
    "Who",
    "contractor_of_record",
    "execution_notice",
    "execution_summary",
    "family_access",
    "floors_for",
    "gate_stages",
    "gate_stages_to_inspect",
    "instantiate_stages",
    "milestone_stages",
    "open_project",
    "own_contractor_engagement",
    "set_gate_status",
    "stage_facts",
    "stage_notice",
    "stages_for",
]
