"""Homeowner routes for concept floor plans (AD-12: the owner generates; members read). Every route
answers 404 while `houseplans_enabled` is off."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse

from p2b.core.config import Settings
from p2b.core.db import Database, DbSession
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.ratelimit import Limit, enforce
from p2b.core.vocabulary import (
    Audience,
    FeasibilityClass,
    InfeasibleReason,
    PlanFailureReason,
    PlanGenerationState,
    PlanOpKind,
    PlanOpReason,
    PlanValidity,
    RulesetStatus,
)
from p2b.houseplans.assistant import Call, interpret_requirement, propose_edit
from p2b.houseplans.engine import (
    ArchitecturalIntent,
    DesignInputs,
    HousePlan,
    RulesetContent,
    plan_geometry,
    score_plan,
)
from p2b.houseplans.engine.build import ROOM_NAMES
from p2b.houseplans.engine.insertion import insertion_slots
from p2b.houseplans.engine.ops import PLAN_OP, RevertToRevision, RevertToVersion
from p2b.houseplans.engine.validate import ValidationReport
from p2b.houseplans.models import HousePlanOp, HousePlanVersion
from p2b.houseplans.schemas import (
    AssistantCallOut,
    AssistantEditOut,
    AssistantEditRequest,
    AssistantRequirementOut,
    AssistantRequirementRequest,
    EditHousePlanOut,
    EditHousePlanRequest,
    EditingOut,
    GenerateHousePlanRequest,
    HousePlanDetailOut,
    HousePlanListOut,
    HousePlanRevisionListOut,
    HousePlanRevisionOut,
    HousePlanSummaryOut,
    HousePlanVersionListOut,
    HousePlanVersionOut,
    InfeasibilityOut,
    InfeasibleReasonOut,
    InsertionSlotOut,
    InvolvedConstraintOut,
    OpeningChangeOut,
    OpeningSizesOut,
    QualityOut,
    QualityTermOut,
    RequirementConflictOut,
    RoomChangeOut,
    RoomQualityOut,
    RoomTypeOut,
    SaveHousePlanVersionRequest,
)
from p2b.houseplans.service import (
    PlanView,
    apply_operations,
    document_of,
    get_plan,
    list_plans,
    list_revisions,
    list_versions,
    request_generation,
    save_version,
)
from p2b.identity.interface import Actor, require_actor

router = APIRouter(tags=["houseplans"])

HOMEOWNER = require_actor(Audience.IHB)
# Tier T2 writes, as for concept images; there is no generation quota in Checkpoint 1 (CP1-07).
REQUEST_LIMIT = Limit("houseplan_request_session", 20, 600)
# Edits are small and frequent (a nudge is one batch): about one a second on average.
EDIT_LIMIT = Limit("houseplan_edit_session", 600, 600)
# Saving a named version is a deliberate act (Checkpoint 3.1).
VERSION_LIMIT = Limit("houseplan_version_session", 30, 600)


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
        data = row.infeasibility
        infeasibility = InfeasibilityOut(
            reasons=[
                InfeasibleReasonOut(
                    code=InfeasibleReason(r["code"]),
                    params=r["params"],
                    message_key=r["message_key"],
                )
                for r in data["reasons"]
            ],
            classification=FeasibilityClass(data["classification"])
            if "classification" in data
            else None,
            message_key=data.get("message_key"),
            message=data.get("message"),
            explanation=data.get("explanation"),
            constraints=[InvolvedConstraintOut(**c) for c in data.get("constraints", [])],
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
        "quality": quality_of(document, view.ruleset.content) if document else None,
        "editing": editing_of(view) if document else None,
    }


def editing_of(view: PlanView) -> EditingOut:
    block = editing_block(
        view.ruleset.content, view.can_edit, view.row.head_revision_no, document_of(view)
    )
    return block.model_copy(update={"assistant": view.assistant})


def editing_block(
    content: RulesetContent, can_edit: bool, revision_no: int, document: HousePlan | None = None
) -> EditingOut:
    o = content.openings
    slots = insertion_slots(document, content) if document is not None and can_edit else []
    return EditingOut(
        can_edit=can_edit,
        revision_no=revision_no,
        grid_mm=content.grid_mm,
        room_types=[
            RoomTypeOut(
                type=t,
                name=ROOM_NAMES[t],
                needs_window=rule.needs_window,
                min_short_mm=rule.min_short_mm,
                min_area_mm2=rule.min_area_mm2,
            )
            for t, rule in content.rooms.items()
            if rule.enclosed
        ],
        openings=OpeningSizesOut(
            door_width_mm=o.door_width_mm,
            min_door_width_mm=o.min_door_width_mm,
            door_height_mm=o.door_height_mm,
            window_width_mm=o.window_width_mm,
            min_window_width_mm=o.min_window_width_mm,
            window_height_mm=o.window_height_mm,
            window_sill_mm=o.window_sill_mm,
            jamb_clearance_mm=o.jamb_clearance_mm,
        ),
        interior_wall_mm=content.walls.interior_mm,
        exterior_wall_mm=content.walls.exterior_mm,
        insertion_slots=[
            InsertionSlotOut(
                host_room=s.host_room,
                side=s.side,
                offset_mm=s.offset_mm,
                length_mm=s.length_mm,
                max_depth_mm=s.max_depth_mm,
                open_area=s.open_area,
                open_area_kind=s.open_area_kind,
                depth_allowance_mm=s.depth_allowance_mm,
                length_allowance_mm=s.length_allowance_mm,
            )
            for s in slots
        ],
    )


def quality_of(document: HousePlan, content: RulesetContent) -> QualityOut | None:
    """None for a ruleset without an objective (its weights would all be zero) or a plan the
    Scorer cannot read."""
    if content.objective is None:
        return None
    q = score_plan(document, content)
    if q is None:
        return None
    return QualityOut(
        total=q.total,
        circulation_share_milli=q.circulation_share_milli,
        aspect_violations=q.aspect_violations,
        terms=[
            QualityTermOut(
                kind=t.kind,
                weight=t.weight,
                score_milli=t.score_milli,
                outcome=t.outcome,
                subjects=list(t.subjects),
            )
            for t in q.terms
        ],
        rooms=[
            RoomQualityOut(
                room=r.key,
                room_type=r.room_type,
                clear_w_mm=r.clear_w_mm,
                clear_d_mm=r.clear_d_mm,
                aspect_x100=r.aspect_x100,
                over_aspect=r.over_aspect,
            )
            for r in q.rooms
        ],
    )


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


@router.post(
    "/projects/{project_id}/house-plans/{plan_id}/ops",
    response_model=EditHousePlanOut,
)
async def post_house_plan_ops(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    body: EditHousePlanRequest,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> EditHousePlanOut:
    """Edit the plan with one batch of typed operations (owner only, AD-12). The server applies
    the batch, validates the result and stores it as the next revision only when the validator
    reports no errors. No Idempotency-Key: `expected_revision` already makes a replay fail with
    409 REVISION_CONFLICT instead of applying twice. 403 for a member who is not the owner; 409
    STATE_CONFLICT or REVISION_CONFLICT; 422 PLAN_OPERATION_REJECTED or PLAN_EDIT_INVALID (with
    the validation report)."""
    database: Database = request.app.state.database
    await enforce(database, EDIT_LIMIT, str(actor.session_id))
    view, inverse = await apply_operations(
        db,
        request.app.state.settings,
        actor,
        project_id,
        plan_id,
        expected_revision=body.expected_revision,
        ops=body.ops,
    )
    return EditHousePlanOut(**detail_fields(view), inverse=list(inverse))


def version_out(version: HousePlanVersion, actor: Actor) -> HousePlanVersionOut:
    return HousePlanVersionOut(
        version_no=version.version_no,
        name=version.name,
        revision_no=version.revision_no,
        validity=PlanValidity(version.validity),
        created_at=version.created_at,
        created_by_you=version.created_by == actor.user_id,
    )


def revision_out(op: HousePlanOp, actor: Actor) -> HousePlanRevisionOut:
    ops = [PLAN_OP.validate_python(o) for o in op.ops]
    first = ops[0] if ops else None
    return HousePlanRevisionOut(
        revision_no=op.revision_no,
        reason=PlanOpReason(op.reason),
        ops=[PlanOpKind(o.op) for o in ops],
        restored_revision=first.revision if isinstance(first, RevertToRevision) else None,
        restored_version=first.version if isinstance(first, RevertToVersion) else None,
        created_at=op.created_at,
        by_you=op.actor_id == actor.user_id,
    )


@router.get(
    "/projects/{project_id}/house-plans/{plan_id}/versions",
    response_model=HousePlanVersionListOut,
)
async def get_house_plan_versions(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> HousePlanVersionListOut:
    """The plan's named versions, oldest first; version 1 is the generated plan (members read)."""
    versions = await list_versions(db, request.app.state.settings, actor, project_id, plan_id)
    return HousePlanVersionListOut(items=[version_out(v, actor) for v in versions])


@router.post(
    "/projects/{project_id}/house-plans/{plan_id}/versions",
    status_code=status.HTTP_201_CREATED,
    response_model=HousePlanVersionOut,
    responses={201: {"model": HousePlanVersionOut}},
)
async def post_house_plan_version(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    body: SaveHousePlanVersionRequest,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """Keep the plan as it is now as a named, immutable version (owner only). Restore it later
    with REVERT_TO_VERSION through the operations route. 403 for a member who is not the owner;
    409 STATE_CONFLICT (also at the version limit) or REVISION_CONFLICT."""
    database: Database = request.app.state.database
    await enforce(database, VERSION_LIMIT, str(actor.session_id))

    async def act() -> tuple[int, dict[str, object]]:
        version = await save_version(
            db,
            request.app.state.settings,
            actor,
            project_id,
            plan_id,
            name=body.name,
            expected_revision=body.expected_revision,
        )
        await db.refresh(version, ["created_at"])
        return 201, version_out(version, actor).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body={"plan_id": str(plan_id), **body.model_dump(mode="json")},
        action=act,
    )


@router.get(
    "/projects/{project_id}/house-plans/{plan_id}/revisions",
    response_model=HousePlanRevisionListOut,
)
async def get_house_plan_revisions(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> HousePlanRevisionListOut:
    """The plan's logged revisions, newest first, `limit` at a time below `before` (members
    read). Revision 0 is the generated plan and has no entry."""
    row, ops = await list_revisions(
        db, request.app.state.settings, actor, project_id, plan_id, before=before, limit=limit
    )
    items = [revision_out(op, actor) for op in ops]
    oldest = items[-1].revision_no if items else None
    return HousePlanRevisionListOut(
        head_revision_no=row.head_revision_no,
        items=items,
        next_before=oldest if len(items) == limit and oldest and oldest > 1 else None,
    )


# ---------- AI-assisted design interpretation (Checkpoint 4) ----------

ASSISTANT_LIMIT = Limit("houseplan_assistant_session", 30, 600)


def call_out(call: Call) -> AssistantCallOut:
    return AssistantCallOut(
        provider=call.provider,
        model=call.model,
        request_id=call.request_id,
        duration_ms=call.duration_ms,
        model_calls=call.attempts,
        input_tokens=call.input_tokens,
        output_tokens=call.output_tokens,
    )


@router.post(
    "/projects/{project_id}/house-plans/{plan_id}/assistant/edit",
    response_model=AssistantEditOut,
)
async def post_house_plan_assistant_edit(
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    body: AssistantEditRequest,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> AssistantEditOut:
    """Interpret one sentence into a proposed edit (owner only; off unless enabled). Nothing is
    stored: a PROPOSED answer's `ops` go through the operations route when the owner applies
    them, where the server applies and validates them again. 404 when off, 403 for a member,
    409 STATE_CONFLICT or REVISION_CONFLICT, 503 PROVIDER_UNAVAILABLE."""
    settings: Settings = request.app.state.settings
    database: Database = request.app.state.database
    await enforce(database, ASSISTANT_LIMIT, str(actor.session_id))
    outcome = await propose_edit(
        db,
        settings,
        request.app.state.text_provider,
        actor,
        project_id,
        plan_id,
        text=body.text,
        expected_revision=body.expected_revision,
    )
    view = await get_plan(db, settings, actor, project_id, plan_id)
    return AssistantEditOut(
        status=outcome.status,
        intent=outcome.intent,
        ops=list(outcome.ops),
        expected_revision=outcome.expected_revision,
        preview=plan_geometry(outcome.plan, view.ruleset.content) if outcome.plan else None,
        rooms=[RoomChangeOut(**vars(r)) for r in outcome.rooms],
        openings=[OpeningChangeOut(**vars(o)) for o in outcome.openings],
        detail=outcome.detail,
        call=call_out(outcome.call),
    )


@router.post(
    "/projects/{project_id}/house-plans/assistant/requirement",
    response_model=AssistantRequirementOut,
)
async def post_house_plan_assistant_requirement(
    project_id: uuid.UUID,
    body: AssistantRequirementRequest,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> AssistantRequirementOut:
    """Interpret the owner's description of the home into requirement facts and provisional
    design inputs, with the differences from the submitted requirement. Nothing is stored;
    generation uses `POST /projects/{id}/house-plans` with `design_inputs` and the existing
    deterministic solver. 404 when off, 403 for a member, 503 PROVIDER_UNAVAILABLE."""
    settings: Settings = request.app.state.settings
    database: Database = request.app.state.database
    await enforce(database, ASSISTANT_LIMIT, str(actor.session_id))
    outcome = await interpret_requirement(
        db, settings, request.app.state.text_provider, actor, project_id, text=body.text
    )
    bridge = outcome.bridge
    return AssistantRequirementOut(
        status=outcome.status,
        intent=outcome.intent.model_dump(mode="json") if outcome.intent else None,
        design_inputs=bridge.design_inputs if bridge else None,
        missing=list(bridge.missing) if bridge else [],
        assumed=list(bridge.assumed) if bridge else [],
        unsupported=list(bridge.unsupported) if bridge else [],
        preferences=list(bridge.preferences) if bridge else [],
        clarifications=list(outcome.intent.clarifications) if outcome.intent else [],
        conflicts=[RequirementConflictOut(**c) for c in outcome.conflicts],
        call=call_out(outcome.call),
    )
