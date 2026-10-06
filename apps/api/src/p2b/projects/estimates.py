"""The indicative estimate stored against a project (Slice 3.0; PD-03, PD-04).

Computed from the project facts filled at submission, with the rate card in force for the city:
the DEMO card outside production, a published card in production (none until D-16, so production
records "no rate card" rather than a figure). Each submission stores one immutable row; a
resubmission after a request for information stores a new one. Projects submitted before this
existed get their row on first read.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.catalog.interface import EstimateInputs, active_stage_names, city_name, estimate_for_city
from p2b.core.ids import new_id
from p2b.core.vocabulary import EstimateStatus, EstimateUnavailableReason, FinishLevel
from p2b.projects.models import Project, ProjectEstimate


@dataclass(frozen=True)
class StageFigure:
    stage_number: int
    stage_name: str | None
    share_pct: Decimal
    amount: Decimal


@dataclass(frozen=True)
class EstimateView:
    status: EstimateStatus
    unavailable_reason: EstimateUnavailableReason | None
    created_at: datetime
    inputs: dict[str, Any]
    result: dict[str, Any] | None
    stages: list[StageFigure]


async def record_estimate(
    session: AsyncSession, project: Project, *, requirement_version: int, allow_demo: bool
) -> None:
    """Store the estimate for this submission. Idempotent: a second call for the same version
    leaves the first row as it is."""
    city = await city_name(session, project.city_code) or project.city_code
    inputs: dict[str, Any] = {
        "city": city,
        "built_up_area_sqft": project.built_up_area_sqft,
        "floors": project.floors,
        "finish_level": project.quality_tier,
    }
    row: dict[str, Any] = {
        "id": new_id(),
        "project_id": project.id,
        "requirement_version": requirement_version,
        "inputs": inputs,
        "status": EstimateStatus.UNAVAILABLE.value,
        "unavailable_reason": None,
        "rate_card_id": None,
        "result": None,
    }
    if project.built_up_area_sqft is None or project.floors is None or not project.quality_tier:
        row["unavailable_reason"] = EstimateUnavailableReason.BUILT_UP_AREA_NOT_GIVEN.value
    else:
        found = await estimate_for_city(
            session,
            city=city,
            inputs=EstimateInputs(
                project.built_up_area_sqft, project.floors, FinishLevel(project.quality_tier)
            ),
            allow_demo=allow_demo,
        )
        if found is None:
            row["unavailable_reason"] = EstimateUnavailableReason.NO_RATE_CARD.value
        else:
            card, estimate = found
            row["status"] = EstimateStatus.AVAILABLE.value
            row["rate_card_id"] = card.id
            row["result"] = {
                "total_low": str(estimate.total_low),
                "total_high": str(estimate.total_high),
                "total_mid": str(estimate.total_mid),
                "per_sqft_low": str(estimate.per_sqft_low),
                "per_sqft_high": str(estimate.per_sqft_high),
                "duration_months": estimate.duration_months,
                "stages": [
                    {
                        "stage_number": s.stage_number,
                        "share_pct": str(s.share_pct),
                        "amount": str(s.amount),
                    }
                    for s in estimate.stages
                ],
                # Rate cards are immutable, so their identity is kept with the figures.
                "rate_card": {
                    "city": card.city,
                    "version": card.version,
                    "is_demo": card.is_demo,
                    "label": card.label,
                },
            }
    await session.execute(
        insert(ProjectEstimate)
        .values(**row)
        .on_conflict_do_nothing(index_elements=["project_id", "requirement_version"])
    )


async def latest_estimate(
    session: AsyncSession, project: Project, *, current_version: int, allow_demo: bool
) -> EstimateView | None:
    """The estimate of the latest submission; None before the first submission."""
    if project.submitted_at is None:
        return None
    row = await _latest(session, project.id)
    if row is None:  # submitted before estimates were stored
        await record_estimate(
            session, project, requirement_version=current_version, allow_demo=allow_demo
        )
        row = await _latest(session, project.id)
    if row is None:
        raise RuntimeError(f"no estimate stored for project {project.id}")
    names = await active_stage_names(session) if row.result else {}
    return EstimateView(
        status=EstimateStatus(row.status),
        unavailable_reason=EstimateUnavailableReason(row.unavailable_reason)
        if row.unavailable_reason
        else None,
        created_at=row.created_at,
        inputs=row.inputs,
        result=row.result,
        stages=[
            StageFigure(
                stage_number=s["stage_number"],
                stage_name=names.get(s["stage_number"]),
                share_pct=Decimal(s["share_pct"]),
                amount=Decimal(s["amount"]),
            )
            for s in (row.result or {}).get("stages", [])
        ],
    )


async def _latest(session: AsyncSession, project_id: uuid.UUID) -> ProjectEstimate | None:
    return (
        await session.scalars(
            select(ProjectEstimate)
            .where(ProjectEstimate.project_id == project_id)
            .order_by(ProjectEstimate.requirement_version.desc())
            .limit(1)
        )
    ).one_or_none()
