"""Public interface of the money module (Slice 3.7). The records module reads the current
payment marks for the Build Record (I.1): yes or no with times, never an amount. Billing never
imports this module (import-linter)."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from p2b.construction.interface import milestone_stages
from p2b.money.service import milestones


async def marks_summary(session: AsyncSession, project_id: uuid.UUID) -> list[dict[str, Any]]:
    stages = await milestone_stages(session, project_id)
    by_id = {s.id: s for s in stages}
    out: list[dict[str, Any]] = []
    for m in await milestones(session, project_id, [(s.id, s.state) for s in stages]):
        stage = by_id[m.stage_instance_id]
        out.append({
            "stage_number": stage.stage_number, "floor": stage.floor, "due": m.due,
            "paid": {"value": m.paid.value.value, "marked_at": m.paid.marked_at.isoformat()}
            if m.paid else None,
            "received": {"value": m.received.value.value,
                         "marked_at": m.received.marked_at.isoformat(),
                         "by_operations": m.received.by_operations}
            if m.received else None,
        })  # fmt: skip
    return out


__all__ = ["marks_summary"]
