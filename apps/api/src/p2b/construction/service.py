"""Stage instances of a project's workspace (STATE_MODEL 6; IHB_FLOW 8.9 J08; rulings 2.2, 2.9).

Workspace creation instantiates the 16 stages of the active stage configuration. Stages that
repeat per floor (5, 6 and 9 in S04) get one instance per floor: ground, each floor above, and a
basement when the house has one (ruling 2.2). Every instance starts NOT_STARTED; gate stages start
NOT_INSPECTED; planned dates stay empty until an approved configuration exists (ruling 2.9).
"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.catalog.interface import StageMasterRow, active_stage_masters, stage_master_names
from p2b.construction.models import StageInstance
from p2b.core.ids import new_id
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import ActorType, GateStatus, StageState

S = StageState
# STATE_MODEL 6. Slice 2 only creates instances; the other transitions arrive with construction.
STAGE = TransitionTable[StageState](
    "stage_instance", [Transition(None, S.NOT_STARTED, "instantiate")]
)

BASEMENT = -1
GROUND = 0


def floors_for(floors_above_ground: int, has_basement: bool) -> list[int]:
    """Floor numbers that get their own instance of a repeating stage, bottom up. `floors` on the
    project counts ground and the floors above (G = 1, G+3 = 4)."""
    if not 1 <= floors_above_ground <= 4:
        raise ValueError("floors must be 1 (ground only) to 4 (ground + 3)")
    return ([BASEMENT] if has_basement else []) + list(range(GROUND, floors_above_ground))


@dataclass(frozen=True)
class PlannedInstance:
    master: StageMasterRow
    floor: int | None
    sequence: int


def plan(masters: list[StageMasterRow], floors: int, has_basement: bool) -> list[PlannedInstance]:
    """The instances a workspace needs, in build order. Pure, so the counts are unit-tested."""
    planned: list[PlannedInstance] = []
    for master in masters:
        levels: list[int | None] = (
            list(floors_for(floors, has_basement)) if master.repeats_per_floor else [None]
        )
        for level in levels:
            planned.append(PlannedInstance(master, level, len(planned) + 1))
    return planned


async def instantiate_stages(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    floors: int,
    has_basement: bool,
    actor_user_id: uuid.UUID,
) -> dict[int, uuid.UUID]:
    """Create the project's stage instances once. Returns the first instance of each stage number
    (the one specification lines are consumed at). The UNIQUE (project, stage, floor) constraint
    is the last guard against a second set."""
    target = STAGE.target(None, "instantiate")
    first: dict[int, uuid.UUID] = {}
    planned = plan(await active_stage_masters(session), floors, has_basement)
    ids = [new_id() for _ in planned]
    await session.execute(
        insert(StageInstance),
        [
            {
                "id": instance_id,
                "project_id": project_id,
                "stage_master_id": item.master.id,
                "stage_number": item.master.number,
                "floor": item.floor,
                "sequence": item.sequence,
                "state": target.value,
                "is_gate": item.master.is_audit_gate,
                "gate_status": GateStatus.NOT_INSPECTED.value
                if item.master.is_audit_gate
                else None,
                "is_payment_milestone": item.master.is_payment_milestone,
            }
            for instance_id, item in zip(ids, planned, strict=True)
        ],
    )
    for instance_id, item in zip(ids, planned, strict=True):
        first.setdefault(item.master.number, instance_id)
        await record(
            session,
            action="stage_instance.created",
            entity_type="stage_instance",
            entity_id=instance_id,
            project_id=project_id,
            actor_type=ActorType.USER,
            actor_user_id=actor_user_id,
            new_value={
                "state": target.value,
                "stage_number": item.master.number,
                "floor": item.floor,
            },
        )
    return first


@dataclass(frozen=True)
class StageView:
    id: uuid.UUID
    stage_number: int
    name: str
    floor: int | None
    sequence: int
    state: StageState
    is_gate: bool
    gate_status: GateStatus | None
    planned_start: date | None
    planned_end: date | None


async def stages_for(session: AsyncSession, project_id: uuid.UUID) -> list[StageView]:
    """The project's stages in build order, named from the exact configuration row each was
    created from, so a later configuration never renames an issued stage."""
    instances = list(
        await session.scalars(
            select(StageInstance)
            .where(StageInstance.project_id == project_id)
            .order_by(StageInstance.sequence)
        )
    )
    names = await stage_master_names(session, [i.stage_master_id for i in instances])
    return [
        StageView(
            id=i.id,
            stage_number=i.stage_number,
            name=names[i.stage_master_id],
            floor=i.floor,
            sequence=i.sequence,
            state=StageState(i.state),
            is_gate=i.is_gate,
            gate_status=GateStatus(i.gate_status) if i.gate_status else None,
            planned_start=i.planned_start,
            planned_end=i.planned_end,
        )
        for i in instances
    ]
