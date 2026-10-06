"""Assurance routes for the homeowner (homeowner host), the engaged contractor and the appointed
auditor (professionals host), Slice 3.7B. The homeowner and household read inspections, reports
and findings; the contractor reads them and submits rectification evidence; the auditor reaches
only the inspections of its active appointment and submits with a one-time code (EX-09). Every
other id is 404 (SECURITY 4.2). Reading and rectification need no package (EX-18)."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from p2b.assurance import appointments, inspections, ncs
from p2b.assurance.models import Inspection, InspectionReport
from p2b.assurance.schemas import (
    AssuranceOut,
    AuditorInspectionOut,
    AuditorInspectionsOut,
    ChallengeOut,
    DownloadOut,
    EvidenceUploadIn,
    FileOut,
    RectifyIn,
    ResultsIn,
    SubmitIn,
    UploadTicketOut,
)
from p2b.assurance.views import assurance_out, auditor_detail, auditor_summaries
from p2b.buildplan.interface import accepted_manifest
from p2b.construction.interface import Who, family_access, own_contractor_engagement
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import DbSession
from p2b.core.errors import NotFound
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.ratelimit import Limit, enforce
from p2b.core.vocabulary import Audience, FilePurpose, InspectionState, OtpPurpose
from p2b.documents.interface import (
    complete_project_file_upload,
    create_project_file_upload,
    project_file_url,
)
from p2b.identity.interface import Actor, require_actor, start_confirmation

router = APIRouter(tags=["assurance"])

HOMEOWNER = require_actor(Audience.IHB)
PROFESSIONAL = require_actor(Audience.PRO)
UPLOAD_LIMIT = Limit("inspection_evidence_session", 60, 60)  # T3
RESULTS_LIMIT = Limit("inspection_results_session", 120, 600)  # T2


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _ip_hash(request: Request) -> str:
    settings = _settings(request)
    peer = request.client.host if request.client else None
    return keyed_hash(
        settings.identifier_pepper.get_secret_value(), client_ip(request.headers, peer)
    )


async def _once(
    db: DbSession, actor: Actor, key: str, body: Any, act: Callable[[], Awaitable[BaseModel]],
    code: int = 200,
) -> JSONResponse:  # fmt: skip
    async def action() -> tuple[int, dict[str, object]]:
        return code, (await act()).model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key, request_body=body, action=action
    )


def _file_out(summary: Any) -> FileOut:
    return FileOut(
        file_id=summary.file_id, file_name=summary.file_name, content_type=summary.content_type,
        size_bytes=summary.size_bytes, state=summary.state,
    )  # fmt: skip


# --- the homeowner -------------------------------------------------------------------------


@router.get("/projects/{project_id}/assurance", response_model=AssuranceOut)
async def get_family_assurance(
    project_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> AssuranceOut:
    """Inspections (content once approved) and findings in plain language."""
    await family_access(db, actor, project_id, write=False)
    return await assurance_out(db, project_id)


@router.get(
    "/projects/{project_id}/inspections/{inspection_id}/reports/{version}/url",
    response_model=DownloadOut,
)
async def get_report(
    project_id: uuid.UUID, inspection_id: uuid.UUID, version: int, request: Request,
    db: DbSession, actor: Annotated[Actor, HOMEOWNER],
) -> DownloadOut:  # fmt: skip
    """An approved inspection's report, any version (logged)."""
    await family_access(db, actor, project_id, write=False)
    report = (
        await db.scalars(
            select(InspectionReport).where(
                InspectionReport.inspection_id == inspection_id,
                InspectionReport.project_id == project_id,
                InspectionReport.version == version,
            )
        )
    ).one_or_none()
    if report is None:
        raise NotFound
    url = await project_file_url(
        db, request.app.state.storage, project_id=project_id, file_id=report.file_id,
        purposes=frozenset({FilePurpose.INSPECTION_REPORT}), viewer_user_id=actor.user_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)


# --- the contractor ------------------------------------------------------------------------


@router.get("/pro/engagements/{engagement_id}/assurance", response_model=AssuranceOut)
async def get_contractor_assurance(
    engagement_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> AssuranceOut:
    """Inspections on the project's stages (content once approved) and the findings to correct."""
    engagement = await own_contractor_engagement(db, actor, engagement_id)
    return await assurance_out(db, engagement.project_id)


@router.post(
    "/pro/engagements/{engagement_id}/non-conformances/{nc_id}/rectification",
    response_model=AssuranceOut,
)
async def post_rectification(
    engagement_id: uuid.UUID, nc_id: uuid.UUID, body: RectifyIn, key: IdempotencyKeyHeader,
    db: DbSession, actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    """Evidence that a finding is corrected: a note and photos you uploaded (the evidence route
    of your execution page). Only an approved re-inspection closes it. 409 NOT_OPEN."""

    async def act() -> AssuranceOut:
        engagement = await own_contractor_engagement(db, actor, engagement_id)
        await ncs.rectify(
            db, Who(actor.user_id, "PROFESSIONAL", actor.session_id), nc_id,
            engagement.project_id, note=body.note, file_ids=body.file_ids,
        )  # fmt: skip
        return await assurance_out(db, engagement.project_id)

    return await _once(db, actor, key, {"nc": str(nc_id), **body.model_dump(mode="json")}, act)


# --- the auditor ---------------------------------------------------------------------------


def _auditor(actor: Actor) -> Who:
    return Who(actor.user_id, "AUDITOR", actor.session_id)


async def _assigned(db: DbSession, actor: Actor, inspection_id: uuid.UUID) -> Inspection:
    appointment = await appointments.of_actor(db, actor)
    row = await db.get(Inspection, inspection_id)
    if row is None or row.appointment_id != appointment.id:
        raise NotFound
    return row


@router.get("/pro/inspections", response_model=AuditorInspectionsOut)
async def get_auditor_inspections(
    db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> AuditorInspectionsOut:
    """The inspections assigned to your active auditor appointment, newest first."""
    appointment = await appointments.of_actor(db, actor)
    return AuditorInspectionsOut(
        auditor_code=appointment.auditor_code, items=await auditor_summaries(db, appointment.id)
    )


@router.get("/pro/inspections/{inspection_id}", response_model=AuditorInspectionOut)
async def get_auditor_inspection(
    inspection_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> AuditorInspectionOut:
    """The stage, the checklist with each line's criteria, the accepted drawings and your
    results. No supplier, brand, product, price or homeowner contact."""
    return await auditor_detail(db, await _assigned(db, actor, inspection_id))


@router.post("/pro/inspections/{inspection_id}/readiness", response_model=AuditorInspectionOut)
async def post_readiness(
    inspection_id: uuid.UUID, key: IdempotencyKeyHeader, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    """Confirm the stage is ready and start the inspection."""

    async def act() -> AuditorInspectionOut:
        row = await _assigned(db, actor, inspection_id)
        await inspections.start(db, _auditor(actor), row.id)
        return await auditor_detail(db, await inspections.inspection_row(db, row.id))

    return await _once(db, actor, key, {"inspection": str(inspection_id)}, act)


@router.put("/pro/inspections/{inspection_id}/results", response_model=AuditorInspectionOut)
async def put_results(
    inspection_id: uuid.UUID, body: ResultsIn, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> AuditorInspectionOut:  # fmt: skip
    """Record or replace checkpoint results while the inspection is open. A non-conformance on
    an inspection carries severity, description, corrective action and due date."""
    await enforce(request.app.state.database, RESULTS_LIMIT, str(actor.session_id))
    row = await _assigned(db, actor, inspection_id)
    row = await inspections.inspection_row(db, row.id, lock=True)
    await inspections.save_results(db, _auditor(actor), row, [r.model_dump() for r in body.results])
    return await auditor_detail(db, row)


@router.post(
    "/pro/inspections/{inspection_id}/evidence",
    response_model=UploadTicketOut,
    status_code=status.HTTP_201_CREATED,
)
async def post_inspection_evidence(
    inspection_id: uuid.UUID, body: EvidenceUploadIn, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> UploadTicketOut:  # fmt: skip
    """A presigned upload of an inspection photo or file, scanned and re-encoded; capture time
    and location are kept as the device's claims (EX-22)."""
    await enforce(request.app.state.database, UPLOAD_LIMIT, str(actor.session_id))
    row = await _assigned(db, actor, inspection_id)
    if row.state != InspectionState.IN_PROGRESS.value:
        raise NotFound
    summary, ticket = await create_project_file_upload(
        db, _settings(request), request.app.state.storage, uploader_user_id=actor.user_id,
        project_id=row.project_id, purpose=FilePurpose.INSPECTION_EVIDENCE,
        original_name=body.file_name, content_type=body.content_type,
        size_bytes=body.size_bytes, capture_claim=body.claim(),
    )  # fmt: skip
    return UploadTicketOut(file=_file_out(summary), upload_url=ticket.url, headers=ticket.headers)


@router.post("/pro/inspections/{inspection_id}/evidence/{file_id}/complete", response_model=FileOut)
async def post_inspection_evidence_complete(
    inspection_id: uuid.UUID, file_id: uuid.UUID, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> FileOut:  # fmt: skip
    await _assigned(db, actor, inspection_id)
    summary = await complete_project_file_upload(
        db, request.app.state.storage, uploader_user_id=actor.user_id, file_id=file_id
    )
    return _file_out(summary)


@router.get("/pro/inspections/{inspection_id}/files/{file_id}/url", response_model=DownloadOut)
async def get_auditor_file(
    inspection_id: uuid.UUID, file_id: uuid.UUID, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> DownloadOut:  # fmt: skip
    """A drawing of the accepted Build Plan, or evidence of this inspection (logged)."""
    row = await _assigned(db, actor, inspection_id)
    baseline = await accepted_manifest(db, row.project_id)
    drawings = {str(d["file_id"]) for d in (baseline.manifest.get("drawings", []) if baseline
                                            else [])}  # fmt: skip
    if str(file_id) in drawings:
        purpose = FilePurpose.DRAWING
    elif any(file_id in r.file_ids for r in await inspections.results_of(db, row.id)):
        purpose = FilePurpose.INSPECTION_EVIDENCE
    else:
        raise NotFound
    url = await project_file_url(
        db, request.app.state.storage, project_id=row.project_id, file_id=file_id,
        purposes=frozenset({purpose}), viewer_user_id=actor.user_id, ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)


@router.post("/pro/inspections/{inspection_id}/submission-code", response_model=ChallengeOut)
async def post_submission_code(
    inspection_id: uuid.UUID, request: Request, db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> ChallengeOut:  # fmt: skip
    """Send a one-time code to your email to confirm the submission (EX-09)."""
    row = await _assigned(db, actor, inspection_id)
    if row.state != InspectionState.IN_PROGRESS.value:
        raise NotFound
    started = await start_confirmation(
        request.app.state.database, _settings(request), user_id=actor.user_id,
        audience=Audience.PRO, purpose=OtpPurpose.SUBMIT_INSPECTION, subject_id=row.id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return ChallengeOut(
        challenge_id=started.challenge_id, sent_to=started.sent_to, expires_at=started.expires_at
    )


@router.post("/pro/inspections/{inspection_id}/submit", response_model=AuditorInspectionOut)
async def post_submit(
    inspection_id: uuid.UUID, body: SubmitIn, key: IdempotencyKeyHeader, request: Request,
    db: DbSession, actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:  # fmt: skip
    """Submit with the code: the inspection is frozen and hashed. 409 `details.reason`:
    INCOMPLETE (with the missing checkpoint codes), NOT_IN_PROGRESS."""

    async def act() -> AuditorInspectionOut:
        row = await _assigned(db, actor, inspection_id)
        await inspections.submit(
            db, request.app.state.database, _settings(request), _auditor(actor),
            inspection_id=row.id, summary=body.summary, challenge_id=body.challenge_id,
            code=body.code, ip_hash=_ip_hash(request),
        )  # fmt: skip
        return await auditor_detail(db, await inspections.inspection_row(db, row.id))

    return await _once(
        db, actor, key, {"inspection": str(inspection_id), "challenge": str(body.challenge_id)},
        act,
    )  # fmt: skip
