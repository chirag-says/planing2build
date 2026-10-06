"""Read models for execution (Slice 3.7A). One query per table, never per stage."""

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.catalog.interface import stage_master_names
from p2b.construction.execution import LOCAL_TIMEZONE, contractor_of_record, update_counts
from p2b.construction.models import StageInstance, StageUpdate
from p2b.construction.schemas import (
    ContractorOut,
    EvidenceOut,
    StageOut,
    UpdateOut,
)
from p2b.core.vocabulary import EngagementParty, GateStatus, StageState, StageUpdateKind
from p2b.documents.interface import file_facts
from p2b.engagements.interface import engagement_names

UPDATES_SHOWN = 200


async def instances(session: AsyncSession, project_id: uuid.UUID) -> list[StageInstance]:
    return list(
        await session.scalars(
            select(StageInstance)
            .where(StageInstance.project_id == project_id)
            .order_by(StageInstance.sequence)
        )
    )


def stage_out(
    stage: StageInstance, name: str, counts: dict[uuid.UUID, tuple[int, datetime | None]]
) -> StageOut:
    count, last = counts.get(stage.id, (0, None))
    return StageOut(
        id=stage.id, stage_number=stage.stage_number, name=name, floor=stage.floor,
        sequence=stage.sequence, state=StageState(stage.state), is_gate=stage.is_gate,
        gate_status=GateStatus(stage.gate_status) if stage.gate_status else None,
        is_payment_milestone=stage.is_payment_milestone, actual_start=stage.actual_start,
        actual_end=stage.actual_end, completion_requested_at=stage.completion_requested_at,
        version=stage.version, update_count=count, last_update_at=last,
    )  # fmt: skip


async def stages_out(
    session: AsyncSession, project_id: uuid.UUID, *, engagement_id: uuid.UUID | None = None
) -> list[StageOut]:
    rows = await instances(session, project_id)
    names = await stage_master_names(session, list({r.stage_master_id for r in rows}))
    counts = await update_counts(session, project_id, engagement_id=engagement_id)
    return [
        stage_out(r, names.get(r.stage_master_id, f"Stage {r.stage_number}"), counts) for r in rows
    ]


async def one_stage_out(
    session: AsyncSession, stage: StageInstance, *, engagement_id: uuid.UUID | None = None
) -> StageOut:
    names = await stage_master_names(session, [stage.stage_master_id])
    counts = await update_counts(session, stage.project_id, engagement_id=engagement_id)
    return stage_out(stage, names.get(stage.stage_master_id, f"Stage {stage.stage_number}"), counts)


async def contractor_out(session: AsyncSession, project_id: uuid.UUID) -> ContractorOut | None:
    current = await contractor_of_record(session, project_id)
    if current is None:
        return None
    names = await engagement_names(session, [current.id])
    return ContractorOut(
        engagement_id=current.id, party=EngagementParty(current.party), name=names.get(current.id)
    )


async def updates_out(session: AsyncSession, updates: list[StageUpdate]) -> list[UpdateOut]:
    """Newest first, at most UPDATES_SHOWN."""
    shown = sorted(updates, key=lambda u: (u.posted_at, u.id), reverse=True)[:UPDATES_SHOWN]
    facts = await file_facts(session, list({f for u in shown for f in u.file_ids}))
    names = await engagement_names(session, list({u.engagement_id for u in shown}))
    out: list[UpdateOut] = []
    for update in shown:
        photos = []
        for file_id in update.file_ids:
            fact = facts.get(file_id)
            if fact is None:
                continue
            claim = fact.capture_claim or {}
            captured = claim.get("captured_at")
            photos.append(
                EvidenceOut(
                    file_id=file_id,
                    file_name=fact.file_name,
                    captured_at=str(captured) if captured else None,
                )
            )
        out.append(
            UpdateOut(
                id=update.id,
                kind=StageUpdateKind(update.kind),
                note=update.note,
                materials=update.materials,
                open_problems=update.open_problems,
                photos=photos,
                corrects_update_id=update.corrects_update_id,
                entered_by_operations=update.posted_role != "PROFESSIONAL",
                contractor_name=names.get(update.engagement_id),
                posted_at=update.posted_at,
            )
        )
    return out


def waiting_exception(stage: StageInstance, today: date, days: int) -> bool:
    """EX-12: a completion request unanswered for `days` calendar days (Raipur dates)."""
    requested = stage.completion_requested_at
    if requested is None:
        return False
    return (today - requested.astimezone(ZoneInfo(LOCAL_TIMEZONE)).date()).days >= days
