"""The package-eligibility checklist (F-05; SLICE3_3_READINESS L-02), as versioned data. Version
1 is seeded by migration 0011 with the five POC checks Chirag locked; ADMIN publishes later
versions. Accepting a project records each item's outcome against the ACTIVE version."""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.catalog.models import EligibilityChecklistVersion
from p2b.core.errors import StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.vocabulary import ConfigStatus

ITEM_ID = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


@dataclass(frozen=True)
class ChecklistItem:
    id: str
    label: str
    help: str


@dataclass(frozen=True)
class EligibilityChecklist:
    id: uuid.UUID
    version: int
    status: ConfigStatus
    items: list[ChecklistItem]
    note: str


def _view(row: EligibilityChecklistVersion) -> EligibilityChecklist:
    return EligibilityChecklist(
        row.id,
        row.version,
        ConfigStatus(row.status),
        [ChecklistItem(i["id"], i["label"], i.get("help", "")) for i in row.items],
        row.note,
    )


async def active_eligibility_checklist(session: AsyncSession) -> EligibilityChecklist | None:
    row = (
        await session.scalars(
            select(EligibilityChecklistVersion).where(
                EligibilityChecklistVersion.status == ConfigStatus.ACTIVE.value
            )
        )
    ).one_or_none()
    return _view(row) if row else None


async def eligibility_checklist(
    session: AsyncSession, version_id: uuid.UUID
) -> EligibilityChecklist:
    return _view(await session.get_one(EligibilityChecklistVersion, version_id))


async def eligibility_checklists(session: AsyncSession) -> list[EligibilityChecklist]:
    rows = await session.scalars(
        select(EligibilityChecklistVersion).order_by(EligibilityChecklistVersion.version.desc())
    )
    return [_view(r) for r in rows]


async def create_eligibility_checklist(
    session: AsyncSession, *, items: list[ChecklistItem], note: str, created_by: uuid.UUID
) -> EligibilityChecklist:
    ids = [i.id for i in items]
    if not items or len(set(ids)) != len(ids) or not all(ITEM_ID.match(i) for i in ids):
        raise ValidationFailed(details={"fields": {"items": ["Give each item a unique id."]}})
    if not all(i.label.strip() for i in items):
        raise ValidationFailed(details={"fields": {"items": ["Every item needs a label."]}})
    last = await session.scalar(select(func.max(EligibilityChecklistVersion.version)))
    row = EligibilityChecklistVersion(
        id=new_id(),
        version=int(last or 0) + 1,
        status=ConfigStatus.DRAFT.value,
        items=[{"id": i.id, "label": i.label.strip(), "help": i.help.strip()} for i in items],
        note=note.strip(),
        created_by=created_by,
    )
    session.add(row)
    await session.flush()
    return _view(row)


async def publish_eligibility_checklist(
    session: AsyncSession, version_id: uuid.UUID, *, published_by: uuid.UUID
) -> EligibilityChecklist:
    row = await session.get(EligibilityChecklistVersion, version_id, with_for_update=True)
    if row is None:
        raise ValidationFailed(details={"fields": {"version_id": ["Unknown version."]}})
    if row.status != ConfigStatus.DRAFT.value:
        raise StateConflict(details={"current_state": row.status})
    await session.execute(
        update(EligibilityChecklistVersion)
        .where(EligibilityChecklistVersion.status == ConfigStatus.ACTIVE.value)
        .values(status=ConfigStatus.RETIRED.value)
    )
    row.status = ConfigStatus.ACTIVE.value
    row.published_by = published_by
    row.published_at = (await session.execute(select(func.now()))).scalar_one()
    await session.flush()
    return _view(row)
