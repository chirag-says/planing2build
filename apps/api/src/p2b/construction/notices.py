"""What an execution email may say (SLICE3_7_READINESS O). Ids in, plain values out: the project
code, the stage name and its floor. A contractor's email never names the homeowner; no email
carries an amount (EX-05)."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from p2b.catalog.interface import stage_master_names
from p2b.construction.models import StageInstance
from p2b.engagements.interface import engagement_facts
from p2b.professionals.interface import profile_names
from p2b.projects.interface import connection_facts

FLOOR_NAMES = {-1: "basement", 0: "ground floor", 1: "first floor", 2: "second floor",
               3: "third floor"}  # fmt: skip


@dataclass(frozen=True)
class ExecutionNotice:
    """`user_id` is None for an operations notice (the operations mailbox)."""

    user_id: uuid.UUID | None
    values: dict[str, str]


def stage_label(name: str, floor: int | None) -> str:
    return name if floor is None else f"{name} ({FLOOR_NAMES.get(floor, f'floor {floor}')})"


async def execution_notice(
    session: AsyncSession, audience: str, aggregate_id: uuid.UUID, payload: dict[str, object]
) -> ExecutionNotice | None:
    """`audience` is family, contractor or ops; the stage comes from the payload."""
    try:
        stage_id = uuid.UUID(str(payload.get("stage_instance_id")))
    except ValueError:
        return None
    stage = await session.get(StageInstance, stage_id)
    facts = await connection_facts(session, stage.project_id) if stage else None
    if stage is None or facts is None:
        return None
    name = (await stage_master_names(session, [stage.stage_master_id])).get(
        stage.stage_master_id, f"Stage {stage.stage_number}"
    )
    values = {"code": facts.code, "stage": stage_label(name, stage.floor)}
    if audience == "ops":
        return ExecutionNotice(None, values)
    if audience == "family":
        return ExecutionNotice(facts.owner_user_id, values)
    engagement = await engagement_facts(session, aggregate_id)
    if engagement is None or engagement.profile_id is None:
        return None  # an OUTSIDE contractor has no account (F-03)
    names = await profile_names(session, [engagement.profile_id])
    if engagement.profile_id not in names:
        return None
    return ExecutionNotice(names[engagement.profile_id][0], values)
