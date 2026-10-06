"""Operations and ADMIN routes for assurance (admin host; staff role and MFA), Slice 3.7B.
Operations schedule, capture, approve, return and cancel inspections, act on findings (send a
rectification back, extend a due date, schedule a re-inspection, rectify for an OUTSIDE
contractor), correct a report as a new version, and add later test results. ADMIN appoints and
ends auditors and publishes checklists. Scheduling and approval need the package (EX-18)."""

import hashlib
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from p2b.assurance import appointments, checklists, inspections, ncs
from p2b.assurance.common import NOT_CLOSED, conflict, today
from p2b.assurance.models import (
    AuditorAppointment,
    Inspection,
    InspectionReport,
    NonConformance,
)
from p2b.assurance.schemas import (
    AppointmentIn,
    AppointmentOut,
    AssuranceQueueOut,
    CaptureIn,
    ChecklistDraftIn,
    ChecklistOut,
    CheckpointsIn,
    DownloadOut,
    DueDateIn,
    FileOut,
    OpsInspectionsOut,
    OpsRectifyIn,
    QueueFindingOut,
    QueueInspectionOut,
    QueueStageOut,
    ReasonIn,
    ReinspectionIn,
    ScheduleIn,
    TestResultIn,
)
from p2b.assurance.views import checkpoint_out, open_too_long, ops_project, ref, stage_map
from p2b.construction.interface import (
    StageFacts,
    Who,
    contractor_of_record,
    gate_stages_to_inspect,
    open_project,
)
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import DbSession
from p2b.core.errors import NotFound, ValidationFailed
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.vocabulary import (
    AppointmentStatus,
    Audience,
    ChecklistStatus,
    EngagementParty,
    FilePurpose,
    InspectionCancelReason,
    InspectionState,
    NcState,
    StaffRole,
)
from p2b.documents.interface import project_file_url, staff_download_url, store_staff_upload
from p2b.identity.interface import Actor, active_roles, require_actor
from p2b.projects.interface import connection_facts

router = APIRouter(tags=["assurance-operations"])

STAFF = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.OPS, StaffRole.ADMIN))
ADMIN = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.ADMIN,))
MAX_STAFF_UPLOAD = 10 * 1024 * 1024
QUEUE_SIZE = 200


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _ip_hash(request: Request) -> str:
    settings = _settings(request)
    peer = request.client.host if request.client else None
    return keyed_hash(
        settings.identifier_pepper.get_secret_value(), client_ip(request.headers, peer)
    )


async def _who(db: DbSession, actor: Actor) -> Who:
    roles = await active_roles(db, actor.user_id)
    role = StaffRole.ADMIN.value if StaffRole.ADMIN in roles else StaffRole.OPS.value
    return Who(actor.user_id, role, actor.session_id)


async def _once(
    db: DbSession, actor: Actor, key: str, body: Any, act: Callable[[], Awaitable[BaseModel]],
    code: int = 200,
) -> JSONResponse:  # fmt: skip
    async def action() -> tuple[int, dict[str, object]]:
        return code, (await act()).model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key, request_body=body, action=action
    )


async def _view(db: DbSession, project_id: uuid.UUID) -> OpsInspectionsOut:
    if await connection_facts(db, project_id) is None:
        raise NotFound
    code, items, findings = await ops_project(db, project_id)
    return OpsInspectionsOut(
        project_id=project_id, project_code=code, inspections=items, findings=findings
    )


async def _project_of(db: DbSession, inspection_id: uuid.UUID) -> uuid.UUID:
    row = await db.get(Inspection, inspection_id)
    if row is None:
        raise NotFound
    return row.project_id


# --- queue and project view ------------------------------------------------------------------


@router.get("/ops/assurance", response_model=AssuranceQueueOut)
async def get_queue(
    request: Request, db: DbSession, _: Annotated[Actor, STAFF]
) -> AssuranceQueueOut:
    """Gate stages to inspect, open inspections (an exception after the configured days, EX-12),
    submissions to approve, rectifications to re-inspect, and findings past due (EX-23)."""
    days = _settings(request).inspection_open_exception_days
    on = await today(db)
    stage_cache: dict[uuid.UUID, tuple[str, dict[uuid.UUID, StageFacts]]] = {}

    async def project(project_id: uuid.UUID) -> tuple[str, dict[uuid.UUID, StageFacts]]:
        if project_id not in stage_cache:
            facts = await connection_facts(db, project_id)
            stage_cache[project_id] = (facts.code if facts else "",
                                       await stage_map(db, project_id))  # fmt: skip
        return stage_cache[project_id]

    to_schedule = []
    for stage in await gate_stages_to_inspect(db, QUEUE_SIZE):
        code, _stages = await project(stage.project_id)
        to_schedule.append(QueueStageOut(**ref(stage), project_id=stage.project_id,
                                         project_code=code))  # fmt: skip
    open_rows = list(
        await db.scalars(
            select(Inspection)
            .where(
                Inspection.state.in_(
                    (
                        InspectionState.SCHEDULED.value,
                        InspectionState.IN_PROGRESS.value,
                        InspectionState.SUBMITTED.value,
                    )
                )
            )
            .order_by(Inspection.scheduled_at)
            .limit(QUEUE_SIZE)
        )
    )
    open_inspections: list[QueueInspectionOut] = []
    to_approve: list[QueueInspectionOut] = []
    for row in open_rows:
        code, stages = await project(row.project_id)
        item = QueueInspectionOut(
            **ref(stages[row.stage_instance_id]), project_id=row.project_id, project_code=code,
            inspection_id=row.id, state=InspectionState(row.state), scheduled_at=row.scheduled_at,
            exception=row.state != InspectionState.SUBMITTED.value
            and open_too_long(row, on, days),
        )  # fmt: skip
        (to_approve if row.state == InspectionState.SUBMITTED.value else open_inspections).append(
            item
        )
    rectified: list[QueueFindingOut] = []
    overdue: list[QueueFindingOut] = []
    for nc in await db.scalars(
        select(NonConformance)
        .where(NonConformance.state.in_(NOT_CLOSED))
        .order_by(NonConformance.due_date)
        .limit(QUEUE_SIZE * 2)
    ):
        code, stages = await project(nc.project_id)
        finding = QueueFindingOut(
            **ref(stages[nc.stage_instance_id]), project_id=nc.project_id, project_code=code,
            nc_id=nc.id, state=NcState(nc.state), due_date=nc.due_date, overdue=nc.due_date < on,
        )  # fmt: skip
        if nc.state == NcState.RECTIFICATION_SUBMITTED.value:
            rectified.append(finding)
        if finding.overdue:
            overdue.append(finding)
    return AssuranceQueueOut(
        inspection_open_days=days, to_schedule=to_schedule, open_inspections=open_inspections,
        to_approve=to_approve, rectified=rectified, overdue=overdue,
    )  # fmt: skip


@router.get("/ops/projects/{project_id}/assurance", response_model=OpsInspectionsOut)
async def get_project(
    project_id: uuid.UUID, db: DbSession, _: Annotated[Actor, STAFF]
) -> OpsInspectionsOut:
    return await _view(db, project_id)


# --- inspections ---------------------------------------------------------------------------------


@router.post(
    "/ops/stages/{stage_id}/inspections",
    response_model=OpsInspectionsOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": OpsInspectionsOut}},
)
async def post_schedule(
    stage_id: uuid.UUID, body: ScheduleIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Schedule the gate stage instance's inspection (EX-07). 409 `details.reason`: NOT_A_GATE,
    ALREADY_SCHEDULED, NO_CHECKLIST, APPOINTMENT_ENDED, NOT_RETURNED, PROJECT_CLOSED; or
    PACKAGE_REQUIRED."""

    async def act() -> OpsInspectionsOut:
        row = await inspections.schedule(
            db, await _who(db, actor), stage_id=stage_id, appointment_id=body.appointment_id,
            visit_note=body.visit_note, amends_id=body.amends_id,
        )  # fmt: skip
        return await _view(db, row.project_id)

    return await _once(db, actor, key, {"stage": str(stage_id), **body.model_dump(mode="json")},
                       act, 201)  # fmt: skip


@router.post(
    "/ops/reinspections",
    response_model=OpsInspectionsOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": OpsInspectionsOut}},
)
async def post_reinspection(
    body: ReinspectionIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Re-inspect rectified findings of one inspection. 409 NOT_RECTIFIED, MIXED_STAGES; or
    PACKAGE_REQUIRED."""

    async def act() -> OpsInspectionsOut:
        row = await inspections.schedule_reinspection(
            db, await _who(db, actor), nc_ids=body.nc_ids, appointment_id=body.appointment_id,
            visit_note=body.visit_note,
        )  # fmt: skip
        return await _view(db, row.project_id)

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


@router.post(
    "/ops/projects/{project_id}/inspection-evidence",
    response_model=FileOut,
    status_code=status.HTTP_201_CREATED,
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
async def post_inspection_evidence(
    project_id: uuid.UUID,
    file_name: Annotated[str, Query(min_length=1, max_length=200)],
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    """The auditor's signed report or photos received outside the portal (raw body). Scanned
    before use."""
    await open_project(db, project_id)
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip()
    if int(request.headers.get("content-length") or 0) > MAX_STAFF_UPLOAD:
        raise ValidationFailed(details={"fields": {"file": ["The file is too large."]}})
    data = await request.body()

    async def act() -> FileOut:
        summary = await store_staff_upload(
            db, _settings(request), request.app.state.storage, uploader_user_id=actor.user_id,
            project_id=project_id, purpose=FilePurpose.INSPECTION_EVIDENCE,
            original_name=file_name, content_type=content_type, data=data,
        )  # fmt: skip
        return FileOut(
            file_id=summary.file_id, file_name=summary.file_name,
            content_type=summary.content_type, size_bytes=summary.size_bytes,
            state=summary.state,
        )  # fmt: skip

    body = {"project": str(project_id), "name": file_name,
            "sha256": hashlib.sha256(data).hexdigest()}  # fmt: skip
    return await _once(db, actor, key, body, act, 201)


@router.post("/ops/inspections/{inspection_id}/capture", response_model=OpsInspectionsOut)
async def post_capture(
    inspection_id: uuid.UUID, body: CaptureIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Enter an inspection from the auditor's signed report (staff capture): results, summary
    and the report file; it is submitted and frozen at once."""

    async def act() -> OpsInspectionsOut:
        row = await inspections.capture(
            db, await _who(db, actor), inspection_id=inspection_id,
            items=[r.model_dump() for r in body.results], summary=body.summary,
            evidence_file_id=body.evidence_file_id,
        )  # fmt: skip
        return await _view(db, row.project_id)

    return await _once(db, actor, key, {"inspection": str(inspection_id),
                                        **body.model_dump(mode="json")}, act)  # fmt: skip


@router.post("/ops/inspections/{inspection_id}/approve", response_model=OpsInspectionsOut)
async def post_approve(
    inspection_id: uuid.UUID, key: IdempotencyKeyHeader, request: Request, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Approve: findings open, the report is rendered once, the gate follows. 409
    NOT_SUBMITTED, CONTENT_CHANGED; or PACKAGE_REQUIRED."""

    async def act() -> OpsInspectionsOut:
        row = await inspections.approve(
            db, _settings(request), request.app.state.storage, await _who(db, actor),
            inspection_id,
        )  # fmt: skip
        return await _view(db, row.project_id)

    return await _once(db, actor, key, {"inspection": str(inspection_id)}, act)


@router.post("/ops/inspections/{inspection_id}/return", response_model=OpsInspectionsOut)
async def post_return(
    inspection_id: uuid.UUID, body: ReasonIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    async def act() -> OpsInspectionsOut:
        row = await inspections.return_(db, await _who(db, actor), inspection_id, body.reason)
        return await _view(db, row.project_id)

    return await _once(db, actor, key, {"inspection": str(inspection_id), **body.model_dump()},
                       act)  # fmt: skip


@router.post("/ops/inspections/{inspection_id}/cancel", response_model=OpsInspectionsOut)
async def post_cancel(
    inspection_id: uuid.UUID, body: ReasonIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    async def act() -> OpsInspectionsOut:
        row = await inspections.cancel(
            db, await _who(db, actor), inspection_id, InspectionCancelReason.OPERATIONS,
            body.reason,
        )  # fmt: skip
        return await _view(db, row.project_id)

    return await _once(db, actor, key, {"inspection": str(inspection_id), **body.model_dump()},
                       act)  # fmt: skip


@router.post(
    "/ops/inspections/{inspection_id}/report-corrections", response_model=OpsInspectionsOut
)
async def post_report_correction(
    inspection_id: uuid.UUID, body: ReasonIn, key: IdempotencyKeyHeader, request: Request,
    db: DbSession, actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """A corrected report as a new version (EX-14); earlier versions stay readable."""

    async def act() -> OpsInspectionsOut:
        await inspections.correct_report(
            db, _settings(request), request.app.state.storage, await _who(db, actor),
            inspection_id, body.reason,
        )  # fmt: skip
        return await _view(db, await _project_of(db, inspection_id))

    return await _once(db, actor, key, {"inspection": str(inspection_id), **body.model_dump()},
                       act)  # fmt: skip


@router.get("/ops/inspections/{inspection_id}/reports/{version}/url", response_model=DownloadOut)
async def get_report(
    inspection_id: uuid.UUID, version: int, request: Request, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> DownloadOut:  # fmt: skip
    report = (
        await db.scalars(
            select(InspectionReport).where(
                InspectionReport.inspection_id == inspection_id,
                InspectionReport.version == version,
            )
        )
    ).one_or_none()
    if report is None:
        raise NotFound
    url = await project_file_url(
        db, request.app.state.storage, project_id=report.project_id, file_id=report.file_id,
        purposes=frozenset({FilePurpose.INSPECTION_REPORT}), viewer_user_id=actor.user_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)


@router.get("/ops/inspection-files/{file_id}/url", response_model=DownloadOut)
async def get_file(
    file_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, STAFF]
) -> DownloadOut:
    url = await staff_download_url(
        db, request.app.state.storage, viewer_user_id=actor.user_id, file_id=file_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)


@router.post(
    "/ops/results/{result_id}/test-results",
    response_model=OpsInspectionsOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": OpsInspectionsOut}},
)
async def post_test_result(
    result_id: uuid.UUID, body: TestResultIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """A later test result (a cube test at 7 or 28 days) on an approved inspection's checkpoint:
    a new record, never an edit."""

    async def act() -> OpsInspectionsOut:
        test = await inspections.add_test_result(
            db, await _who(db, actor), result_id, test_kind=body.test_kind, value=body.value,
            file_id=body.file_id,
        )  # fmt: skip
        return await _view(db, test.project_id)

    return await _once(db, actor, key, {"result": str(result_id), **body.model_dump(mode="json")},
                       act, 201)  # fmt: skip


# --- findings ----------------------------------------------------------------------------------


@router.post("/ops/non-conformances/{nc_id}/rectification", response_model=OpsInspectionsOut)
async def post_rectification(
    nc_id: uuid.UUID, body: OpsRectifyIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Rectification evidence an OUTSIDE contractor sent, with how it was received. 409
    LISTED_CONTRACTOR (it submits its own), NOT_OPEN."""

    async def act() -> OpsInspectionsOut:
        nc = await ncs.nc_row(db, nc_id)
        current = await contractor_of_record(db, nc.project_id)
        if current is not None and current.party == EngagementParty.LISTED.value:
            raise conflict("LISTED_CONTRACTOR", "A listed contractor submits its own evidence.")
        await ncs.rectify(
            db, await _who(db, actor), nc_id, nc.project_id, note=body.note,
            file_ids=body.file_ids, reason=body.reason,
        )  # fmt: skip
        return await _view(db, nc.project_id)

    return await _once(db, actor, key, {"nc": str(nc_id), **body.model_dump(mode="json")}, act)


@router.post("/ops/non-conformances/{nc_id}/reopen", response_model=OpsInspectionsOut)
async def post_reopen(
    nc_id: uuid.UUID, body: ReasonIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """Send a rectification back with a reason (not enough evidence)."""

    async def act() -> OpsInspectionsOut:
        nc = await ncs.reopen(db, await _who(db, actor), nc_id, body.reason)
        return await _view(db, nc.project_id)

    return await _once(db, actor, key, {"nc": str(nc_id), **body.model_dump()}, act)


@router.post("/ops/non-conformances/{nc_id}/due-date", response_model=OpsInspectionsOut)
async def post_due_date(
    nc_id: uuid.UUID, body: DueDateIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    async def act() -> OpsInspectionsOut:
        nc = await ncs.set_due_date(db, await _who(db, actor), nc_id, body.due_date, body.reason)
        return await _view(db, nc.project_id)

    return await _once(db, actor, key, {"nc": str(nc_id), **body.model_dump(mode="json")}, act)


# --- configuration -------------------------------------------------------------------------------


def _appointment_out(row: AuditorAppointment) -> AppointmentOut:
    return AppointmentOut(
        id=row.id, auditor_code=row.auditor_code, name=row.name, qualification=row.qualification,
        registration_reference=row.registration_reference, has_account=row.user_id is not None,
        status=AppointmentStatus(row.status), end_reason=row.end_reason,
    )  # fmt: skip


@router.get("/ops/auditor-appointments", response_model=list[AppointmentOut])
async def get_appointments(db: DbSession, _: Annotated[Actor, STAFF]) -> list[AppointmentOut]:
    return [_appointment_out(r) for r in await appointments.listing(db)]


@router.post(
    "/admin/auditor-appointments",
    response_model=AppointmentOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": AppointmentOut}},
)
async def post_appointment(
    body: AppointmentIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, ADMIN],
) -> JSONResponse:  # fmt: skip
    """Appoint an independent auditor (EX-09); a unique auditor ID is issued. With an account
    email the auditor signs in on the professionals site. 409 ACCOUNT_APPOINTED."""

    async def act() -> AppointmentOut:
        row = await appointments.appoint(
            db, await _who(db, actor), name=body.name, qualification=body.qualification,
            registration_reference=body.registration_reference,
            credential_file_id=body.credential_file_id, account_email=body.account_email,
        )  # fmt: skip
        return _appointment_out(row)

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


@router.post("/admin/auditor-appointments/{appointment_id}/end", response_model=AppointmentOut)
async def post_end_appointment(
    appointment_id: uuid.UUID, body: ReasonIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, ADMIN],
) -> JSONResponse:  # fmt: skip
    async def act() -> AppointmentOut:
        await appointments.end(db, await _who(db, actor), appointment_id, body.reason)
        return _appointment_out(await db.get_one(AuditorAppointment, appointment_id))

    return await _once(db, actor, key, {"appointment": str(appointment_id),
                                        **body.model_dump()}, act)  # fmt: skip


async def _checklist_out(db: DbSession, version_id: uuid.UUID) -> ChecklistOut:
    row = await checklists.version_row(db, version_id)
    return ChecklistOut(
        id=row.id, version=row.version, status=ChecklistStatus(row.status), note=row.note,
        published_at=row.published_at,
        checkpoints=[checkpoint_out(c) for c in await checklists.checkpoints(db, row.id)],
    )  # fmt: skip


@router.get("/ops/checklists", response_model=list[ChecklistOut])
async def get_checklists(db: DbSession, _: Annotated[Actor, STAFF]) -> list[ChecklistOut]:
    return [await _checklist_out(db, v.id) for v in await checklists.versions(db)]


@router.post(
    "/ops/checklists",
    response_model=ChecklistOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": ChecklistOut}},
)
async def post_checklist(
    body: ChecklistDraftIn, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:  # fmt: skip
    """A DRAFT checklist version, copied from an earlier one when named (EX-08: Gate 6 is
    drafted by the auditor and operations)."""

    async def act() -> ChecklistOut:
        row = await checklists.draft(
            db, await _who(db, actor), from_version_id=body.from_version_id, note=body.note
        )
        return await _checklist_out(db, row.id)

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


@router.put("/ops/checklists/{version_id}/checkpoints", response_model=ChecklistOut)
async def put_checkpoints(
    version_id: uuid.UUID, body: CheckpointsIn, db: DbSession, actor: Annotated[Actor, STAFF]
) -> ChecklistOut:
    """Replace a DRAFT's checkpoints. 409 NOT_DRAFT."""
    await checklists.replace_checkpoints(
        db, await _who(db, actor), version_id,
        [checklists.CheckpointIn(**c.model_dump()) for c in body.checkpoints],
    )  # fmt: skip
    return await _checklist_out(db, version_id)


@router.post("/admin/checklists/{version_id}/publish", response_model=ChecklistOut)
async def post_publish(
    version_id: uuid.UUID, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, ADMIN],
) -> JSONResponse:  # fmt: skip
    """Publish a DRAFT; the previous PUBLISHED version is RETIRED. Inspections keep the version
    they were scheduled with. 409 NOT_DRAFT, EMPTY."""

    async def act() -> ChecklistOut:
        await checklists.publish(db, await _who(db, actor), version_id)
        return await _checklist_out(db, version_id)

    return await _once(db, actor, key, {"version": str(version_id)}, act)
