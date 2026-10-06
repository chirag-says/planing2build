"""The project's specification ledger (STATE_MODEL 7; IHB_FLOW 8.9 J08; rulings 2.3 to 2.6).

Workspace creation instantiates every active master line once per project, in SPECIFIED, with
the issued criteria copied from the master version and the line linked to the first instance of
its consuming stage. Structural lines keep their engineer sign-off PENDING until a registered
structural engineer signs (ruling 2.4; the sign-off flow belongs to a later slice).

Lines are grouped A, B and C (S04's "packages"); the groups are never products or payments
(PD-09). Whether the family sees a line's criteria is decided by the projects module (open point
F-09, a setting).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.catalog.interface import active_spec_masters
from p2b.core.ids import new_id
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import ActorType, EngineerSignoff, SpecLineState
from p2b.specification.models import ProjectSpecLine, SpecLineEvent

L = SpecLineState
# STATE_MODEL 7. Slice 2 only instantiates; choosing, buying and verifying arrive later.
SPEC_LINE = TransitionTable[SpecLineState](
    "spec_line", [Transition(None, L.SPECIFIED, "instantiate")]
)


async def instantiate_lines(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    first_stage_instance: dict[int, uuid.UUID],
    actor_user_id: uuid.UUID,
    actor_role: str,
) -> int:
    """Create the project's lines once (UNIQUE project and code is the last guard). Each line
    gets a ledger event and an audit row. Returns the number of lines."""
    target = SPEC_LINE.target(None, "instantiate")
    masters = await active_spec_masters(session)
    ids = [new_id() for _ in masters]
    await session.execute(
        insert(ProjectSpecLine),
        [
            {
                "id": line_id,
                "project_id": project_id,
                "code": master.code,
                "master_version_id": master.version_id,
                "issued_criteria": master.performance_specification,
                "engineer_signoff": master.engineer_signoff.value,
                "state": target.value,
                "is_long_lead": master.is_long_lead,
                "consuming_stage_instance_id": first_stage_instance[min(master.consuming_stages)],
            }
            for line_id, master in zip(ids, masters, strict=True)
        ],
    )
    await session.execute(
        insert(SpecLineEvent),
        [
            {
                "id": new_id(),
                "line_id": line_id,
                "from_state": None,
                "to_state": target.value,
                "actor_user_id": actor_user_id,
                "actor_role": actor_role,
                "reason": "workspace created",
            }
            for line_id in ids
        ],
    )
    for line_id, master in zip(ids, masters, strict=True):
        await record(
            session,
            action="spec_line.created",
            entity_type="spec_line",
            entity_id=line_id,
            project_id=project_id,
            actor_type=ActorType.USER,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            new_value={"state": target.value, "code": master.code},
        )
    return len(ids)


@dataclass(frozen=True)
class LineView:
    code: str
    group: str
    item: str
    state: SpecLineState
    is_long_lead: bool
    is_structural: bool
    engineer_signoff: EngineerSignoff
    issued_criteria: str


async def lines_for(session: AsyncSession, project_id: uuid.UUID) -> list[LineView]:
    """Every line of the project in catalogue order, with its criteria. Callers decide what a
    given audience may see (open point F-09 decides the criteria for the family)."""
    masters = {master.code: master for master in await active_spec_masters(session)}
    lines = await session.scalars(
        select(ProjectSpecLine).where(ProjectSpecLine.project_id == project_id)
    )
    views = [
        LineView(
            code=line.code,
            group=masters[line.code].group,
            item=masters[line.code].item,
            state=SpecLineState(line.state),
            is_long_lead=line.is_long_lead,
            is_structural=masters[line.code].is_structural,
            engineer_signoff=EngineerSignoff(line.engineer_signoff),
            issued_criteria=line.issued_criteria,
        )
        for line in lines
    ]
    return sorted(views, key=lambda view: masters[view.code].sequence)


async def record_accepted_values(
    session: AsyncSession, project_id: uuid.UUID, values: dict[str, uuid.UUID]
) -> None:
    """Point each project line at its value in the accepted Build Plan version (Slice 3.5). The
    line's construction-time state is untouched."""
    lines = await session.scalars(
        select(ProjectSpecLine).where(ProjectSpecLine.project_id == project_id).with_for_update()
    )
    for line in lines:
        value_id = values.get(line.code)
        if value_id is not None and line.accepted_value_id != value_id:
            line.accepted_value_id = value_id
            line.version += 1
    await session.flush()
