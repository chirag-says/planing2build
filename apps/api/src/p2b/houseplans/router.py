"""Homeowner routes for concept floor plans (AD-12: the owner generates; members read). Every route
answers 404 while `houseplans_enabled` is off."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from p2b.core.config import Settings
from p2b.core.db import Database, DbSession
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.ratelimit import Limit, enforce
from p2b.core.vocabulary import (
    Audience,
    InfeasibleReason,
    PlanFailureReason,
    PlanGenerationState,
    PlanValidity,
    RulesetStatus,
)
from p2b.houseplans.engine import ArchitecturalIntent, DesignInputs, plan_geometry
from p2b.houseplans.engine.validate import ValidationReport
from p2b.houseplans.schemas import (
    GenerateHousePlanRequest,
    HousePlanDetailOut,
    HousePlanListOut,
    HousePlanSummaryOut,
    InfeasibilityOut,
    InfeasibleReasonOut,
)
from p2b.houseplans.service import PlanView, document_of, get_plan, list_plans, request_generation
from p2b.identity.interface import Actor, require_actor

router = APIRouter(tags=["houseplans"])

HOMEOWNER = require_actor(Audience.IHB)
# Tier T2 writes, as for concept images; there is no generation quota in Checkpoint 1 (CP1-07).
REQUEST_LIMIT = Limit("houseplan_request_session", 20, 600)


def summary(view: PlanView) -> HousePlanSummaryOut:
    row = view.row
    return HousePlanSummaryOut(
        plan_id=str(row.id),
        sequence=row.sequence,
        state=PlanGenerationState(row.state),
        validity=PlanValidity(row.head_validity) if row.head_validity else None,
        failure_reason=PlanFailureReason(row.failure_reason) if row.failure_reason else None,
        ruleset_version=row.ruleset_version,
        ruleset_status=RulesetStatus(view.ruleset.status),
        ruleset_is_synthetic=view.ruleset.is_synthetic,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


def detail_fields(view: PlanView) -> dict[str, object]:
    row = view.row
    document = document_of(view)
    infeasibility = None
    if row.infeasibility:
        infeasibility = InfeasibilityOut(
            reasons=[
                InfeasibleReasonOut(
                    code=InfeasibleReason(r["code"]),
                    params=r["params"],
                    message_key=r["message_key"],
                )
                for r in row.infeasibility["reasons"]
            ]
        )
    return {
        **summary(view).model_dump(),
        "intent": ArchitecturalIntent.model_validate(row.intent),
        "design_inputs": DesignInputs.model_validate(row.design_inputs)
        if row.design_inputs
        else None,
        "document": document,
        "geometry": plan_geometry(document, view.ruleset.content) if document else None,
        "validation": ValidationReport.model_validate(row.head_report) if row.head_report else None,
        "infeasibility": infeasibility,
    }


@router.get("/projects/{project_id}/house-plans", response_model=HousePlanListOut)
async def get_house_plans(
    project_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> HousePlanListOut:
    views = await list_plans(db, request.app.state.settings, actor, project_id)
    return HousePlanListOut(items=[summary(v) for v in views])


@router.post(
    "/projects/{project_id}/house-plans",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=HousePlanSummaryOut,
    responses={202: {"model": HousePlanSummaryOut}},
)
async def post_house_plan(
    project_id: uuid.UUID,
    body: GenerateHousePlanRequest,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """Generate a concept floor plan. 202 with the QUEUED plan; the job lays it out and validates
    it. 409 GENERATION_IN_PROGRESS, RULESET_NOT_PUBLISHED or STATE_CONFLICT; 422
    DESIGN_INPUT_REQUIRED (with the missing keys), PLAN_UNSUPPORTED or VALIDATION_ERROR."""
    settings: Settings = request.app.state.settings
    database: Database = request.app.state.database
    await enforce(database, REQUEST_LIMIT, str(actor.session_id))

    async def act() -> tuple[int, dict[str, object]]:
        row = await request_generation(
            db, settings, actor, project_id, design_inputs=body.design_inputs
        )
        from p2b.houseplans.rulesets import load_ruleset_by_id

        view = PlanView(row, await load_ruleset_by_id(db, row.ruleset_id))
        return 202, summary(view).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body={"project_id": str(project_id), **body.model_dump(mode="json")},
        action=act,
    )


@router.get("/projects/{project_id}/house-plans/{plan_id}", response_model=HousePlanDetailOut)
async def get_house_plan(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> HousePlanDetailOut:
    view = await get_plan(db, request.app.state.settings, actor, project_id, plan_id)
    return HousePlanDetailOut(**detail_fields(view))
