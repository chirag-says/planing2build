"""Operations and ADMIN routes for design intake and the Build Plan (admin host; staff role and
MFA). Operations prepare rate cards, record drawing checks, draft and issue versions, and record
outside engineers' signed documents; ADMIN publishes rate cards, appoints checkers and activates
sign-off statements. Nobody edits an issued version."""

import hashlib
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from p2b.audit.interface import record
from p2b.billing.interface import package_state
from p2b.buildplan import design, lifecycle, plans, signoffs
from p2b.buildplan.common import Who, conflict, project
from p2b.buildplan.models import (
    AcceptanceStatement,
    BuildPlanEvent,
    SignoffStatement,
    StructuralSignoff,
)
from p2b.buildplan.schemas import (
    BoqIn,
    CheckerIn,
    CheckerOut,
    DesignRequestIn,
    DrawingCheckIn,
    DrawingFileIn,
    DrawingSetIdIn,
    EventOut,
    FileOut,
    OpsBuildPlanOut,
    OpsVersionOut,
    RateCardIn,
    RateCardOut,
    RateLineOut,
    RateLinesIn,
    ReasonIn,
    RfqManifestOut,
    ScheduleIn,
    ScopeIn,
    SignDocumentIn,
    SnapshotOut,
    StatementIn,
    StatementOut,
    ValuesIn,
)
from p2b.buildplan.views import (
    design_requests_out,
    file_out,
    manifest,
    snapshot,
    version_summary,
)
from p2b.catalog.interface import (
    RateLine,
    create_item_rate_card,
    item_rate_card,
    item_rate_cards,
    publish_item_rate_card,
    retire_item_rate_card,
    set_item_rate_lines,
)
from p2b.core.config import Settings
from p2b.core.db import DbSession
from p2b.core.errors import ValidationFailed
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.vocabulary import ActorType, Audience, BuildPlanState, FilePurpose, StaffRole
from p2b.documents.interface import store_staff_upload
from p2b.identity.interface import Actor, active_roles, require_actor

router = APIRouter(tags=["buildplan-operations"])

STAFF = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.OPS, StaffRole.ADMIN))
ADMIN = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.ADMIN,))


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def _who(db: DbSession, actor: Actor) -> Who:
    roles = await active_roles(db, actor.user_id)
    role = StaffRole.ADMIN.value if StaffRole.ADMIN in roles else StaffRole.OPS.value
    return Who(actor.user_id, role, actor.session_id)


async def _once(
    db: DbSession,
    actor: Actor,
    key: str,
    body: Any,
    act: Callable[[], Awaitable[BaseModel]],
    code: int = 200,
) -> JSONResponse:
    async def action() -> tuple[int, dict[str, object]]:
        return code, (await act()).model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key, request_body=body, action=action
    )


async def _project_view(db: DbSession, actor: Actor, project_id: uuid.UUID) -> OpsBuildPlanOut:
    facts = await project(db, project_id)
    plan = await plans.plan_of(db, project_id)
    events = await db.scalars(
        select(BuildPlanEvent)
        .where(BuildPlanEvent.project_id == project_id)
        .order_by(BuildPlanEvent.at.desc(), BuildPlanEvent.id)
        .limit(300)
    )
    return OpsBuildPlanOut(
        project_id=project_id,
        project_code=facts.code,
        package_state=await package_state(db, project_id),
        accepted_version_id=plan.accepted_version_id if plan else None,
        design_requests=await design_requests_out(
            db, project_id, await _who(db, actor), profile_id=None
        ),
        versions=[version_summary(v) for v in await plans.versions_of(db, project_id)],
        history=[
            EventOut(
                subject=e.subject, subject_id=e.subject_id, from_state=e.from_state,
                to_state=e.to_state, actor_role=e.actor_role, reason=e.reason, at=e.at,
            )
            for e in events
        ],
    )  # fmt: skip


async def _version_view(db: DbSession, version_id: uuid.UUID) -> OpsVersionOut:
    version = await plans.version_row(db, version_id)
    facts = await project(db, version.project_id)
    missing = (
        await plans.missing_for_submit(db, version)
        if version.state == BuildPlanState.DRAFT.value
        else []
    )
    return OpsVersionOut(
        snapshot=SnapshotOut.model_validate(await snapshot(db, facts, version)),
        missing=missing,
        last_edited_by=version.last_edited_by,
        issued_document_id=version.issued_document_id,
        accepted_document_id=version.accepted_document_id,
    )


# --- rate cards (BP-06) ----------------------------------------------------------------------


async def _card_out(db: DbSession, card_id: uuid.UUID) -> RateCardOut:
    card = await item_rate_card(db, card_id)
    return RateCardOut(
        id=card.id, geography=card.geography, version=card.version, status=card.status,
        is_demo=card.is_demo, effective_from=card.effective_from, effective_to=card.effective_to,
        source_reference=card.source_reference, note=card.note,
        lines=[RateLineOut(item_code=line.item_code, description=line.description,
                           unit=line.unit, rate=line.rate) for line in card.lines.values()],
    )  # fmt: skip


async def _audit_card(db: DbSession, who: Who, card_id: uuid.UUID, action: str) -> None:
    await record(
        db, action=f"item_rate_card.{action}", entity_type="item_rate_card", entity_id=card_id,
        actor_type=ActorType.USER, actor_user_id=who.user_id, actor_role=who.role,
        session_id=who.session_id,
    )  # fmt: skip


@router.get("/ops/item-rate-cards", response_model=list[RateCardOut])
async def get_rate_cards(db: DbSession, actor: Annotated[Actor, STAFF]) -> list[RateCardOut]:
    return [await _card_out(db, card.id) for card in await item_rate_cards(db)]


@router.post(
    "/ops/item-rate-cards",
    response_model=RateCardOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": RateCardOut}},
)
async def post_rate_card(
    body: RateCardIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    """Operations prepare a DRAFT card (BP-06). DEMO cards are refused in production."""

    async def act() -> RateCardOut:
        who = await _who(db, actor)
        if body.is_demo and _settings(request).env == "production":
            raise conflict("DEMO_CARD", "DEMO rate cards are not allowed in production.")
        card = await create_item_rate_card(
            db, geography=body.geography, effective_from=body.effective_from,
            effective_to=body.effective_to, source_reference=body.source_reference,
            note=body.note, is_demo=body.is_demo, prepared_by=actor.user_id,
        )  # fmt: skip
        await _audit_card(db, who, card.id, "drafted")
        return await _card_out(db, card.id)

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


@router.put("/ops/item-rate-cards/{card_id}/lines", response_model=RateCardOut)
async def put_rate_lines(
    card_id: uuid.UUID, body: RateLinesIn, db: DbSession, actor: Annotated[Actor, STAFF]
) -> RateCardOut:
    await set_item_rate_lines(
        db, card_id,
        [RateLine(line.item_code, line.description, line.unit, line.rate) for line in body.lines],
    )  # fmt: skip
    await _audit_card(db, await _who(db, actor), card_id, "lines_set")
    return await _card_out(db, card_id)


@router.post("/admin/item-rate-cards/{card_id}/publish", response_model=RateCardOut)
async def post_publish_card(
    card_id: uuid.UUID,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, ADMIN],
) -> JSONResponse:
    """An authorised ADMIN approves and publishes the card; it never changes afterwards."""

    async def act() -> RateCardOut:
        await publish_item_rate_card(
            db, card_id, publisher=actor.user_id,
            allow_demo=_settings(request).env != "production",
        )  # fmt: skip
        await _audit_card(db, await _who(db, actor), card_id, "published")
        return await _card_out(db, card_id)

    return await _once(db, actor, key, {"card": str(card_id)}, act)


@router.post("/admin/item-rate-cards/{card_id}/retire", response_model=RateCardOut)
async def post_retire_card(
    card_id: uuid.UUID, key: IdempotencyKeyHeader, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> JSONResponse:
    async def act() -> RateCardOut:
        await retire_item_rate_card(db, card_id)
        await _audit_card(db, await _who(db, actor), card_id, "retired")
        return await _card_out(db, card_id)

    return await _once(db, actor, key, {"card": str(card_id)}, act)


# --- checkers and statements (BP-01, BP-04) --------------------------------------------------


def _checker_out(row: Any) -> CheckerOut:
    return CheckerOut(
        id=row.id, name=row.name, qualification=row.qualification,
        registration_reference=row.registration_reference, user_id=row.user_id,
        appointed_at=row.appointed_at,
    )  # fmt: skip


@router.get("/ops/drawing-checkers", response_model=list[CheckerOut])
async def get_checkers(db: DbSession, actor: Annotated[Actor, STAFF]) -> list[CheckerOut]:
    return [_checker_out(row) for row in await design.active_checkers(db)]


@router.post(
    "/admin/drawing-checkers",
    response_model=CheckerOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": CheckerOut}},
)
async def post_checker(
    body: CheckerIn, key: IdempotencyKeyHeader, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> JSONResponse:
    """Appoint a qualified checker (not necessarily an employee)."""

    async def act() -> CheckerOut:
        row = await design.appoint_checker(
            db, await _who(db, actor), name=body.name, qualification=body.qualification,
            registration_reference=body.registration_reference, user_id=body.user_id,
        )  # fmt: skip
        return _checker_out(row)

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


@router.post("/admin/drawing-checkers/{appointment_id}/end", response_model=list[CheckerOut])
async def post_end_checker(
    appointment_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> list[CheckerOut]:
    await design.end_checker(db, await _who(db, actor), appointment_id)
    return [_checker_out(row) for row in await design.active_checkers(db)]


def _statement_out(row: Any) -> StatementOut:
    return StatementOut(
        id=row.id, version=row.version, text=row.text, status=row.status, note=row.note
    )


@router.get("/ops/signoff-statements", response_model=list[StatementOut])
async def get_statements(db: DbSession, actor: Annotated[Actor, STAFF]) -> list[StatementOut]:
    return [_statement_out(s) for s in await signoffs.statements(db, SignoffStatement)]


@router.post(
    "/admin/signoff-statements",
    response_model=StatementOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": StatementOut}},
)
async def post_statement(
    body: StatementIn, key: IdempotencyKeyHeader, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> JSONResponse:
    async def act() -> StatementOut:
        row = await signoffs.draft_statement(
            db, await _who(db, actor), body.text, body.note, SignoffStatement
        )
        return _statement_out(row)

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


@router.post("/admin/signoff-statements/{statement_id}/activate", response_model=list[StatementOut])
async def post_activate_statement(
    statement_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> list[StatementOut]:
    who = await _who(db, actor)
    await signoffs.activate_statement(db, who, statement_id, SignoffStatement)
    await record(
        db, action="signoff_statement.activated", entity_type="signoff_statement",
        entity_id=statement_id, actor_type=ActorType.USER, actor_user_id=who.user_id,
        actor_role=who.role, session_id=who.session_id,
    )  # fmt: skip
    return [_statement_out(s) for s in await signoffs.statements(db, SignoffStatement)]


@router.get("/ops/acceptance-statements", response_model=list[StatementOut])
async def get_acceptance_statements(
    db: DbSession, actor: Annotated[Actor, STAFF]
) -> list[StatementOut]:
    """The homeowner acceptance statement versions (BP-05)."""
    return [_statement_out(s) for s in await signoffs.statements(db, AcceptanceStatement)]


@router.post(
    "/admin/acceptance-statements",
    response_model=StatementOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": StatementOut}},
)
async def post_acceptance_statement(
    body: StatementIn, key: IdempotencyKeyHeader, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> JSONResponse:
    """A new DRAFT version; the text may use $version_no, $project_code and $content_hash."""

    async def act() -> StatementOut:
        row = await signoffs.draft_statement(
            db, await _who(db, actor), body.text, body.note, AcceptanceStatement
        )
        return _statement_out(row)

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


@router.post(
    "/admin/acceptance-statements/{statement_id}/activate", response_model=list[StatementOut]
)
async def post_activate_acceptance_statement(
    statement_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, ADMIN]
) -> list[StatementOut]:
    who = await _who(db, actor)
    await signoffs.activate_statement(db, who, statement_id, AcceptanceStatement)
    await record(
        db, action="acceptance_statement.activated", entity_type="acceptance_statement",
        entity_id=statement_id, actor_type=ActorType.USER, actor_user_id=who.user_id,
        actor_role=who.role, session_id=who.session_id,
    )  # fmt: skip
    return [_statement_out(s) for s in await signoffs.statements(db, AcceptanceStatement)]


# --- design intake on a project --------------------------------------------------------------


@router.get("/ops/projects/{project_id}/build-plan", response_model=OpsBuildPlanOut)
async def get_ops_build_plan(
    project_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, STAFF]
) -> OpsBuildPlanOut:
    """Design requests, drawing sets, every version (drafts included) and the history."""
    return await _project_view(db, actor, project_id)


@router.post(
    "/ops/projects/{project_id}/design-requests",
    response_model=OpsBuildPlanOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": OpsBuildPlanOut}},
)
async def post_ops_design_request(
    project_id: uuid.UUID,
    body: DesignRequestIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    async def act() -> OpsBuildPlanOut:
        await project(db, project_id)
        await design.open_request(
            db, await _who(db, actor), project_id, kind=body.kind,
            engagement_id=body.engagement_id, provider_name=body.provider_name,
            provider_qualification=body.provider_qualification, scope_note=body.scope_note,
            reference_design_ids=body.reference_design_ids,
        )  # fmt: skip
        return await _project_view(db, actor, project_id)

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


@router.post(
    "/ops/design-requests/{request_id}/sets",
    response_model=OpsBuildPlanOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": OpsBuildPlanOut}},
)
async def post_ops_set(
    request_id: uuid.UUID, key: IdempotencyKeyHeader, db: DbSession, actor: Annotated[Actor, STAFF]
) -> JSONResponse:
    async def act() -> OpsBuildPlanOut:
        request = await design.request_row(db, request_id)
        await design.new_set(db, await _who(db, actor), request)
        return await _project_view(db, actor, request.project_id)

    return await _once(db, actor, key, {"request": str(request_id)}, act, 201)


MAX_STAFF_UPLOAD = 25 * 1024 * 1024


@router.post(
    "/ops/projects/{project_id}/build-plan/files",
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": FileOut}},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                t: {"schema": {"type": "string", "format": "binary"}}
                for t in ("application/pdf", "image/jpeg", "image/png")
            },
        }
    },
)
async def post_ops_file(
    project_id: uuid.UUID,
    purpose: FilePurpose,
    file_name: Annotated[str, Query(min_length=1, max_length=200)],
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    """Upload a drawing or evidence file through the API (raw body; the admin host does not upload
    to storage directly). Scanned before use like every upload."""
    await project(db, project_id)
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip()
    declared = int(request.headers.get("content-length") or 0)
    if declared > MAX_STAFF_UPLOAD:
        raise ValidationFailed(details={"fields": {"file": ["The file is too large."]}})
    data = await request.body()

    async def act() -> FileOut:
        summary = await store_staff_upload(
            db, _settings(request), request.app.state.storage, uploader_user_id=actor.user_id,
            project_id=project_id, purpose=purpose, original_name=file_name,
            content_type=content_type, data=data,
        )  # fmt: skip
        return file_out(summary)

    body = {"project": str(project_id), "purpose": purpose.value, "name": file_name,
            "sha256": hashlib.sha256(data).hexdigest()}  # fmt: skip
    return await _once(db, actor, key, body, act, 201)


@router.post("/ops/drawing-sets/{set_id}/files", response_model=OpsBuildPlanOut)
async def post_ops_set_file(
    set_id: uuid.UUID, body: DrawingFileIn, db: DbSession, actor: Annotated[Actor, STAFF]
) -> OpsBuildPlanOut:
    drawing_set = await design.set_row(db, set_id, lock=True)
    await design.add_file(
        db, await _who(db, actor), drawing_set, file_id=body.file_id,
        drawing_class=body.drawing_class, floor=body.floor, title=body.title,
        sheet_no=body.sheet_no,
    )  # fmt: skip
    return await _project_view(db, actor, drawing_set.project_id)


@router.post("/ops/drawing-sets/{set_id}/submit", response_model=OpsBuildPlanOut)
async def post_ops_submit_set(
    set_id: uuid.UUID, key: IdempotencyKeyHeader, db: DbSession, actor: Annotated[Actor, STAFF]
) -> JSONResponse:
    async def act() -> OpsBuildPlanOut:
        drawing_set = await design.set_row(db, set_id, lock=True)
        await design.submit_set(db, await _who(db, actor), drawing_set)
        return await _project_view(db, actor, drawing_set.project_id)

    return await _once(db, actor, key, {"set": str(set_id)}, act)


@router.post("/ops/drawing-sets/{set_id}/check", response_model=OpsBuildPlanOut)
async def post_check(
    set_id: uuid.UUID,
    body: DrawingCheckIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    """Record the appointed checker's decision (BP-01). Structural drawings are reviewed by the
    signing engineer, whose sign-off covers their hashes."""

    async def act() -> OpsBuildPlanOut:
        drawing_set = await design.set_row(db, set_id, lock=True)
        await design.check_set(
            db, await _who(db, actor), drawing_set, appointment_id=body.appointment_id,
            approve=body.approve, note=body.note, evidence_file_id=body.evidence_file_id,
        )  # fmt: skip
        return await _project_view(db, actor, drawing_set.project_id)

    return await _once(db, actor, key, {"set": str(set_id), **body.model_dump(mode="json")}, act)


# --- Build Plan versions ---------------------------------------------------------------------


@router.post(
    "/ops/projects/{project_id}/build-plan/versions",
    response_model=OpsVersionOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": OpsVersionOut}},
)
async def post_version(
    project_id: uuid.UUID, key: IdempotencyKeyHeader, db: DbSession, actor: Annotated[Actor, STAFF]
) -> JSONResponse:
    """A new DRAFT, carried forward from the latest version or seeded empty."""

    async def act() -> OpsVersionOut:
        version = await plans.create_version(db, await _who(db, actor), project_id)
        return await _version_view(db, version.id)

    return await _once(db, actor, key, {"project": str(project_id)}, act, 201)


@router.get("/ops/build-plan-versions/{version_id}", response_model=OpsVersionOut)
async def get_version(
    version_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, STAFF]
) -> OpsVersionOut:
    return await _version_view(db, version_id)


@router.put("/ops/build-plan-versions/{version_id}/drawing-set", response_model=OpsVersionOut)
async def put_drawing_set(
    version_id: uuid.UUID, body: DrawingSetIdIn, db: DbSession, actor: Annotated[Actor, STAFF]
) -> OpsVersionOut:
    await plans.set_drawing_set(db, await _who(db, actor), version_id, body.set_id)
    return await _version_view(db, version_id)


@router.put("/ops/build-plan-versions/{version_id}/values", response_model=OpsVersionOut)
async def put_values(
    version_id: uuid.UUID, body: ValuesIn, db: DbSession, actor: Annotated[Actor, STAFF]
) -> OpsVersionOut:
    """Project values per S04 line (PD-14): a value and its basis, or not applicable with a
    reason. The S04 criteria are never edited here."""
    await plans.set_values(
        db, await _who(db, actor), version_id,
        [plans.ValueInput(v.code, v.applicability, v.value_text, v.basis, v.source_note,
                          v.not_applicable_reason, v.evidence_file_ids) for v in body.values],
    )  # fmt: skip
    return await _version_view(db, version_id)


@router.post(
    "/ops/build-plan-versions/{version_id}/values/{code}/refresh", response_model=OpsVersionOut
)
async def post_refresh(
    version_id: uuid.UUID, code: str, db: DbSession, actor: Annotated[Actor, STAFF]
) -> OpsVersionOut:
    await plans.refresh_criteria(db, await _who(db, actor), version_id, code)
    return await _version_view(db, version_id)


@router.put("/ops/build-plan-versions/{version_id}/boq", response_model=OpsVersionOut)
async def put_boq(
    version_id: uuid.UUID,
    body: BoqIn,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> OpsVersionOut:
    """Replace the BOQ: one published card; rates and amounts come from the server."""
    await plans.set_boq(
        db, _settings(request), await _who(db, actor), version_id, body.rate_card_id,
        [plans.BoqInput(b.item_code, b.quantity, b.quantity_basis, b.drawing_file_id,
                        b.basis_note, b.stage_number, b.floor, b.spec_line_codes, b.assumptions)
         for b in body.lines],
    )  # fmt: skip
    return await _version_view(db, version_id)


@router.put("/ops/build-plan-versions/{version_id}/schedule", response_model=OpsVersionOut)
async def put_schedule(
    version_id: uuid.UUID, body: ScheduleIn, db: DbSession, actor: Annotated[Actor, STAFF]
) -> OpsVersionOut:
    """Durations and explicitly entered predecessors. No dates (BP-07A deferred)."""
    await plans.set_schedule(
        db, await _who(db, actor), version_id,
        [plans.ScheduleInput(e.entry_key, e.duration_days, e.predecessors, e.note)
         for e in body.entries],
    )  # fmt: skip
    return await _version_view(db, version_id)


@router.put("/ops/build-plan-versions/{version_id}/scope", response_model=OpsVersionOut)
async def put_scope(
    version_id: uuid.UUID, body: ScopeIn, db: DbSession, actor: Annotated[Actor, STAFF]
) -> OpsVersionOut:
    await plans.set_scope(
        db, await _who(db, actor), version_id, inclusions=body.inclusions,
        exclusions=body.exclusions, assumptions=body.assumptions,
        explanation_note=body.explanation_note,
    )  # fmt: skip
    return await _version_view(db, version_id)


def _transition(
    name: str,
) -> Callable[..., Awaitable[JSONResponse]]:
    async def route(
        version_id: uuid.UUID,
        body: ReasonIn,
        key: IdempotencyKeyHeader,
        db: DbSession,
        actor: Annotated[Actor, STAFF],
    ) -> JSONResponse:
        async def act() -> OpsVersionOut:
            who = await _who(db, actor)
            if name == "return":
                await plans.return_to_draft(db, who, version_id, body.reason)
            else:
                await plans.withdraw(db, who, version_id, body.reason)
            return await _version_view(db, version_id)

        return await _once(db, actor, key, {"version": str(version_id), name: body.reason}, act)

    return route


router.add_api_route(
    "/ops/build-plan-versions/{version_id}/return", _transition("return"), methods=["POST"],
    response_model=OpsVersionOut, name="post_return_version",
    description="Back to DRAFT with a reason; every sign-off on the version becomes VOID.",
)  # fmt: skip
router.add_api_route(
    "/ops/build-plan-versions/{version_id}/withdraw", _transition("withdraw"), methods=["POST"],
    response_model=OpsVersionOut, name="post_withdraw_version",
    description="DRAFT, IN_REVIEW or an unaccepted ISSUED version; never ACCEPTED.",
)  # fmt: skip


@router.post("/ops/build-plan-versions/{version_id}/submit", response_model=OpsVersionOut)
async def post_submit(
    version_id: uuid.UUID, key: IdempotencyKeyHeader, db: DbSession, actor: Annotated[Actor, STAFF]
) -> JSONResponse:
    """Freeze the content for review and sign-off; 409 INCOMPLETE lists what is missing."""

    async def act() -> OpsVersionOut:
        await plans.submit(db, await _who(db, actor), version_id)
        return await _version_view(db, version_id)

    return await _once(db, actor, key, {"version": str(version_id)}, act)


@router.post("/ops/build-plan-versions/{version_id}/issue", response_model=OpsVersionOut)
async def post_issue(
    version_id: uuid.UUID,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    """Issue: never by the last editor; every structural line signed on this content; a
    published (never DEMO in production) rate card; the PDF stored with it."""

    async def act() -> OpsVersionOut:
        version = await plans.version_row(db, version_id)
        facts = await project(db, version.project_id)
        await lifecycle.issue(
            db, _settings(request), request.app.state.storage, await _who(db, actor), facts,
            version_id,
        )  # fmt: skip
        return await _version_view(db, version_id)

    return await _once(db, actor, key, {"version": str(version_id)}, act)


@router.post("/ops/build-plan-versions/{version_id}/signoffs", response_model=OpsVersionOut)
async def post_signed_document(
    version_id: uuid.UUID,
    body: SignDocumentIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    """Record an outside engineer's signed document for the chosen structural lines (BP-04)."""

    async def act() -> OpsVersionOut:
        await signoffs.sign_with_document(
            db, await _who(db, actor), version_id, codes=body.line_codes,
            engineer_name=body.engineer_name, engineer_firm=body.engineer_firm,
            registration_number=body.registration_number,
            registration_issuer=body.registration_issuer,
            credential_file_id=body.credential_file_id, evidence_file_id=body.evidence_file_id,
            attestation=body.attestation,
        )  # fmt: skip
        return await _version_view(db, version_id)

    return await _once(
        db, actor, key, {"version": str(version_id), **body.model_dump(mode="json")}, act
    )


@router.post("/ops/signoffs/{signoff_id}/revoke", response_model=OpsVersionOut)
async def post_ops_revoke(
    signoff_id: uuid.UUID,
    body: ReasonIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    async def act() -> OpsVersionOut:
        row = await db.get(StructuralSignoff, signoff_id)
        await signoffs.revoke(db, await _who(db, actor), signoff_id, body.reason, profile_id=None)
        assert row is not None  # noqa: S101 (revoke raised NotFound otherwise)
        return await _version_view(db, row.version_id)

    return await _once(
        db, actor, key, {"signoff": str(signoff_id), **body.model_dump(mode="json")}, act
    )


@router.get("/ops/projects/{project_id}/build-plan/rfq-manifest", response_model=RfqManifestOut)
async def get_rfq_manifest(
    project_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, STAFF]
) -> RfqManifestOut:
    """The contractor RFQ manifest of the accepted version (BP-08): scope, quantities and issued
    specifications; never Plan2Build's rates. 409 NO_ACCEPTED_VERSION before acceptance."""
    facts = await project(db, project_id)
    version = await lifecycle.accepted_version(db, project_id)
    if version is None:
        raise conflict("NO_ACCEPTED_VERSION", "No Build Plan version has been accepted.")
    return RfqManifestOut.model_validate(manifest(await snapshot(db, facts, version)))
