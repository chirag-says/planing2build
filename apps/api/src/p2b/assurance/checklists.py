"""Versioned gate checklists (EX-08; SLICE3_7_READINESS F.4). Version 1 (migration 0017) holds
Gates 1 to 5 from the S04 "verified at" mapping. Operations prepare a DRAFT (copied from a
version, then its checkpoints replaced), ADMIN publishes it and the previous PUBLISHED version is
RETIRED. Checkpoints are configuration data, never text inside inspection logic; an inspection
keeps the version it was scheduled with."""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.assurance.common import conflict, db_now, history
from p2b.assurance.models import ChecklistVersion, Checkpoint
from p2b.construction.interface import Who
from p2b.core.errors import NotFound, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.vocabulary import ChecklistStatus


@dataclass(frozen=True)
class CheckpointIn:
    gate: int
    sequence: int
    code: str
    text: str
    expected_evidence: str | None
    is_critical: bool
    spec_line_code: str | None


async def version_row(
    session: AsyncSession, version_id: uuid.UUID, *, lock: bool = False
) -> ChecklistVersion:
    row = await session.get(ChecklistVersion, version_id, with_for_update=lock)
    if row is None:
        raise NotFound
    return row


async def published(session: AsyncSession) -> ChecklistVersion | None:
    return (
        await session.scalars(
            select(ChecklistVersion).where(
                ChecklistVersion.status == ChecklistStatus.PUBLISHED.value
            )
        )
    ).one_or_none()


async def checkpoints(
    session: AsyncSession, version_id: uuid.UUID, gate: int | None = None
) -> list[Checkpoint]:
    query = select(Checkpoint).where(Checkpoint.checklist_version_id == version_id)
    if gate is not None:
        query = query.where(Checkpoint.gate == gate)
    return list(await session.scalars(query.order_by(Checkpoint.gate, Checkpoint.sequence)))


async def draft(
    session: AsyncSession, who: Who, *, from_version_id: uuid.UUID | None, note: str
) -> ChecklistVersion:
    """A new DRAFT, a copy of `from_version_id`'s checkpoints when given."""
    number = (await session.scalar(select(func.max(ChecklistVersion.version)))) or 0
    row = ChecklistVersion(
        id=new_id(), version=number + 1, status=ChecklistStatus.DRAFT.value, note=note,
        prepared_by=who.user_id,
    )  # fmt: skip
    session.add(row)
    await session.flush()
    if from_version_id is not None:
        await version_row(session, from_version_id)
        for c in await checkpoints(session, from_version_id):
            session.add(
                Checkpoint(
                    id=new_id(), checklist_version_id=row.id, gate=c.gate, sequence=c.sequence,
                    code=c.code, text=c.text, expected_evidence=c.expected_evidence,
                    is_critical=c.is_critical, spec_line_code=c.spec_line_code,
                )
            )  # fmt: skip
        await session.flush()
    await history(
        session, subject="CHECKLIST", subject_id=row.id, project_id=None, old=None,
        new=ChecklistStatus.DRAFT.value, who=who,
        detail={"version": row.version, "from": str(from_version_id) if from_version_id else None},
    )  # fmt: skip
    return row


async def replace_checkpoints(
    session: AsyncSession, who: Who, version_id: uuid.UUID, items: list[CheckpointIn]
) -> None:
    row = await version_row(session, version_id, lock=True)
    if row.status != ChecklistStatus.DRAFT.value:
        raise conflict("NOT_DRAFT", "Only a draft checklist changes.")
    codes = [i.code for i in items]
    places = [(i.gate, i.sequence) for i in items]
    if len(set(codes)) != len(codes) or len(set(places)) != len(places):
        raise ValidationFailed(
            details={"fields": {"checkpoints": ["Codes, and sequences within a gate, are unique."]}}
        )
    await session.execute(delete(Checkpoint).where(Checkpoint.checklist_version_id == row.id))
    for i in items:
        session.add(
            Checkpoint(
                id=new_id(), checklist_version_id=row.id, gate=i.gate, sequence=i.sequence,
                code=i.code, text=i.text, expected_evidence=i.expected_evidence,
                is_critical=i.is_critical, spec_line_code=i.spec_line_code,
            )
        )  # fmt: skip
    await session.flush()
    await history(
        session, subject="CHECKLIST", subject_id=row.id, project_id=None,
        old=ChecklistStatus.DRAFT.value, new=ChecklistStatus.DRAFT.value, who=who,
        detail={"checkpoints": len(items)},
    )  # fmt: skip


async def publish(session: AsyncSession, who: Who, version_id: uuid.UUID) -> ChecklistVersion:
    row = await version_row(session, version_id, lock=True)
    if row.status != ChecklistStatus.DRAFT.value:
        raise conflict("NOT_DRAFT", "Only a draft checklist is published.")
    if not await checkpoints(session, row.id):
        raise conflict("EMPTY", "A checklist needs at least one checkpoint.")
    current = await published(session)
    if current is not None:
        current.status = ChecklistStatus.RETIRED.value
        await session.flush()
        await history(
            session, subject="CHECKLIST", subject_id=current.id, project_id=None,
            old=ChecklistStatus.PUBLISHED.value, new=ChecklistStatus.RETIRED.value, who=who,
        )  # fmt: skip
    row.status = ChecklistStatus.PUBLISHED.value
    row.published_by = who.user_id
    row.published_at = await db_now(session)
    await session.flush()
    await history(
        session, subject="CHECKLIST", subject_id=row.id, project_id=None,
        old=ChecklistStatus.DRAFT.value, new=ChecklistStatus.PUBLISHED.value, who=who,
    )  # fmt: skip
    return row


async def versions(session: AsyncSession) -> list[ChecklistVersion]:
    return list(
        await session.scalars(select(ChecklistVersion).order_by(ChecklistVersion.version.desc()))
    )
