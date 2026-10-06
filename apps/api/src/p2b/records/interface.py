"""Public interface of the records module (Slice 3.7C). Notifications read what a handover or
Build Record email may say: the project code only."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from p2b.engagements.interface import engagement_facts
from p2b.professionals.interface import profile_names
from p2b.projects.interface import connection_facts


@dataclass(frozen=True)
class RecordsNotice:
    """`user_id` is None for an operations notice (the operations mailbox)."""

    user_id: uuid.UUID | None
    values: dict[str, str]


async def records_notice(
    session: AsyncSession, audience: str, aggregate_id: uuid.UUID, payload: dict[str, object]
) -> RecordsNotice | None:
    facts = await connection_facts(session, uuid.UUID(str(payload["project_id"])))
    if facts is None:
        return None
    values = {"code": facts.code}
    if audience == "ops":
        return RecordsNotice(None, values)
    if audience == "family":
        return RecordsNotice(facts.owner_user_id, values)
    engagement = await engagement_facts(session, aggregate_id)
    if engagement is None or engagement.profile_id is None:
        return None
    names = await profile_names(session, [engagement.profile_id])
    if engagement.profile_id not in names:
        return None
    return RecordsNotice(names[engagement.profile_id][0], values)


__all__ = ["RecordsNotice", "records_notice"]
