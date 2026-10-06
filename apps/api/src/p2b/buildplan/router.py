"""Design intake and the Build Plan for the family (homeowner host) and professionals
(professionals host). Creating and transition POSTs take an `Idempotency-Key`. Drafts are never
shown to the family; downloads are signed-in and logged; there is no public share link (BP-16)."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from p2b.billing.interface import package_state
from p2b.buildplan import design, lifecycle, plans, signoffs
from p2b.buildplan.common import family, family_access, professional, project
from p2b.buildplan.models import (
    BuildPlanVersion,
    DesignRequest,
    DrawingFile,
    DrawingSet,
    SignoffStatement,
)
from p2b.buildplan.schemas import (
    BuildPlanAcceptIn,
    ChallengeOut,
    DesignRequestIn,
    DownloadOut,
    DrawingFileIn,
    DrawingFileOut,
    FamilyBuildPlanOut,
    FamilyDecisionIn,
    FileOut,
    ProDesignRequestOut,
    ProDesignRequestsOut,
    ProSignoffListOut,
    ProSignoffOut,
    ReasonIn,
    SignCodeIn,
    SignIn,
    SignoffLineOut,
    SnapshotOut,
    SnapshotSignoffOut,
    UploadIn,
    UploadTicketOut,
)
from p2b.buildplan.views import design_requests_out, file_out, snapshot, version_summary
from p2b.catalog.interface import active_spec_masters
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import Database, DbSession
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.ratelimit import Limit, enforce
from p2b.core.vocabulary import Audience, BuildPlanState, FilePurpose, MembershipRole, OtpPurpose
from p2b.documents.interface import (
    complete_project_file_upload,
    create_project_file_upload,
    file_facts,
    project_file_url,
)
from p2b.engagements.interface import active_engagements_of_profile
from p2b.identity.interface import (
    Actor,
    require_actor,
    start_confirmation,
    verify_confirmation,
)
from p2b.professionals.interface import profile_by_user
from p2b.projects.interface import member_role

router = APIRouter(tags=["buildplan"])

HOMEOWNER = require_actor(Audience.IHB)
PROFESSIONAL = require_actor(Audience.PRO)
UPLOAD_LIMIT = Limit("buildplan_uploads_session", 60, 60)
FAMILY_FILES = frozenset({FilePurpose.DRAWING, FilePurpose.BUILD_PLAN_DOCUMENT})


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


async def _family_view(db: DbSession, actor: Actor, project_id: uuid.UUID) -> FamilyBuildPlanOut:
    facts = await family_access(db, actor, project_id, write=False)
    membership = await member_role(db, user_id=actor.user_id, project_id=project_id)
    plan = await plans.plan_of(db, project_id)
    versions = [v for v in await plans.versions_of(db, project_id) if v.issued_at is not None]
    return FamilyBuildPlanOut(
        project_id=project_id,
        project_code=facts.code,
        availability=facts.availability,
        package_state=await package_state(db, project_id),
        can_act=membership is not None and membership.role == MembershipRole.OWNER,
        accepted_version_id=plan.accepted_version_id if plan else None,
        design_requests=await design_requests_out(db, project_id, family(actor), profile_id=None),
        versions=[version_summary(v) for v in versions],
    )


async def _issued_version(
    db: DbSession, project_id: uuid.UUID, version_id: uuid.UUID
) -> BuildPlanVersion:
    """Drafts and versions never issued are invisible to the family (404)."""
    version = await db.get(BuildPlanVersion, version_id)
    if version is None or version.project_id != project_id or version.issued_at is None:
        raise NotFound
    return version


async def _owned_set(db: DbSession, project_id: uuid.UUID, set_id: uuid.UUID) -> DrawingSet:
    drawing_set = await design.set_row(db, set_id, lock=True)
    if drawing_set.project_id != project_id:
        raise NotFound
    return drawing_set


async def _upload(
    db: DbSession,
    request: Request,
    actor: Actor,
    project_id: uuid.UUID,
    body: UploadIn,
    key: str,
) -> JSONResponse:
    database: Database = request.app.state.database
    await enforce(database, UPLOAD_LIMIT, str(actor.session_id))

    async def act() -> UploadTicketOut:
        summary, ticket = await create_project_file_upload(
            db, _settings(request), request.app.state.storage, uploader_user_id=actor.user_id,
            project_id=project_id, purpose=body.purpose, original_name=body.file_name,
            content_type=body.content_type, size_bytes=body.size_bytes,
        )  # fmt: skip
        return UploadTicketOut(
            file=file_out(summary), upload_url=ticket.url, headers=ticket.headers
        )

    return await _once(
        db, actor, key, {"project": str(project_id), **body.model_dump(mode="json")}, act, 201
    )


# --- the family ----------------------------------------------------------------------------


@router.get("/projects/{project_id}/build-plan", response_model=FamilyBuildPlanOut)
async def get_build_plan(
    project_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> FamilyBuildPlanOut:
    """Design requests and drawing sets, and the issued Build Plan versions (never drafts)."""
    return await _family_view(db, actor, project_id)


@router.get("/projects/{project_id}/build-plan/versions/{version_id}", response_model=SnapshotOut)
async def get_family_version(
    project_id: uuid.UUID, version_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> SnapshotOut:
    facts = await family_access(db, actor, project_id, write=False)
    version = await _issued_version(db, project_id, version_id)
    return SnapshotOut.model_validate(await snapshot(db, facts, version))


@router.post(
    "/projects/{project_id}/design-requests",
    response_model=FamilyBuildPlanOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": FamilyBuildPlanOut}},
)
async def post_design_request(
    project_id: uuid.UUID,
    body: DesignRequestIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """Ask for authoritative drawings from a professional or provide the family's own. Plan2Build
    generates no drawing; AI concepts may be named as illustrative references only."""

    async def act() -> FamilyBuildPlanOut:
        await family_access(db, actor, project_id, write=True)
        await design.open_request(
            db, family(actor), project_id, kind=body.kind, engagement_id=body.engagement_id,
            provider_name=body.provider_name, provider_qualification=body.provider_qualification,
            scope_note=body.scope_note, reference_design_ids=body.reference_design_ids,
        )  # fmt: skip
        return await _family_view(db, actor, project_id)

    return await _once(db, actor, key, body.model_dump(mode="json"), act, 201)


async def _family_request(
    db: DbSession, actor: Actor, project_id: uuid.UUID, request_id: uuid.UUID
) -> DesignRequest:
    await family_access(db, actor, project_id, write=True)
    request = await design.request_row(db, request_id)
    if request.project_id != project_id:
        raise NotFound
    if not await design.may_provide(db, request, family(actor), profile_id=None):
        raise NotFound
    return request


@router.post(
    "/projects/{project_id}/design-requests/{request_id}/sets",
    response_model=FamilyBuildPlanOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": FamilyBuildPlanOut}},
)
async def post_family_set(
    project_id: uuid.UUID,
    request_id: uuid.UUID,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    async def act() -> FamilyBuildPlanOut:
        request = await _family_request(db, actor, project_id, request_id)
        await design.new_set(db, family(actor), request)
        return await _family_view(db, actor, project_id)

    return await _once(db, actor, key, {"request": str(request_id)}, act, 201)


@router.post(
    "/projects/{project_id}/build-plan/uploads",
    response_model=UploadTicketOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": UploadTicketOut}},
)
async def post_family_upload(
    project_id: uuid.UUID,
    body: UploadIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """A drawing file the family adds to their own or their outside professional's set."""
    await family_access(db, actor, project_id, write=True)
    if body.purpose != FilePurpose.DRAWING:
        raise ValidationFailed(details={"fields": {"purpose": ["Drawings only."]}})
    return await _upload(db, request, actor, project_id, body, key)


@router.post("/projects/{project_id}/build-plan/uploads/{file_id}/complete", response_model=FileOut)
async def post_family_upload_complete(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> FileOut:
    await family_access(db, actor, project_id, write=True)
    return file_out(
        await complete_project_file_upload(
            db, request.app.state.storage, uploader_user_id=actor.user_id, file_id=file_id
        )
    )


@router.get("/projects/{project_id}/build-plan/files/{file_id}", response_model=FileOut)
async def get_family_file(
    project_id: uuid.UUID, file_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> FileOut:
    """A drawing upload's state while it is checked."""
    await family_access(db, actor, project_id, write=False)
    facts = (await file_facts(db, [file_id])).get(file_id)
    if facts is None or facts.project_id != project_id or facts.owner_user_id != actor.user_id:
        raise NotFound
    return FileOut(
        file_id=facts.file_id, file_name=facts.file_name, content_type=facts.content_type,
        size_bytes=facts.size_bytes, state=facts.state,
    )  # fmt: skip


@router.post(
    "/projects/{project_id}/drawing-sets/{set_id}/files", response_model=FamilyBuildPlanOut
)
async def post_family_set_file(
    project_id: uuid.UUID,
    set_id: uuid.UUID,
    body: DrawingFileIn,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> FamilyBuildPlanOut:
    drawing_set = await _owned_set(db, project_id, set_id)
    await _family_request(db, actor, project_id, drawing_set.request_id)
    await design.add_file(
        db, family(actor), drawing_set, file_id=body.file_id, drawing_class=body.drawing_class,
        floor=body.floor, title=body.title, sheet_no=body.sheet_no,
    )  # fmt: skip
    return await _family_view(db, actor, project_id)


@router.delete(
    "/projects/{project_id}/drawing-sets/{set_id}/files/{drawing_file_id}",
    response_model=FamilyBuildPlanOut,
)
async def delete_family_set_file(
    project_id: uuid.UUID,
    set_id: uuid.UUID,
    drawing_file_id: uuid.UUID,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> FamilyBuildPlanOut:
    drawing_set = await _owned_set(db, project_id, set_id)
    await _family_request(db, actor, project_id, drawing_set.request_id)
    await design.remove_file(db, drawing_set, drawing_file_id)
    return await _family_view(db, actor, project_id)


@router.post(
    "/projects/{project_id}/drawing-sets/{set_id}/submit", response_model=FamilyBuildPlanOut
)
async def post_family_submit(
    project_id: uuid.UUID,
    set_id: uuid.UUID,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """The family's own submission goes to the appointed checker."""

    async def act() -> FamilyBuildPlanOut:
        drawing_set = await _owned_set(db, project_id, set_id)
        await _family_request(db, actor, project_id, drawing_set.request_id)
        await design.submit_set(db, family(actor), drawing_set)
        return await _family_view(db, actor, project_id)

    return await _once(db, actor, key, {"set": str(set_id)}, act)


@router.post(
    "/projects/{project_id}/drawing-sets/{set_id}/decision", response_model=FamilyBuildPlanOut
)
async def post_family_decision(
    project_id: uuid.UUID,
    set_id: uuid.UUID,
    body: FamilyDecisionIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """Review a professional's submitted set: send it to the checker, or ask for changes."""

    async def act() -> FamilyBuildPlanOut:
        await family_access(db, actor, project_id, write=True)
        drawing_set = await _owned_set(db, project_id, set_id)
        await design.family_decide(
            db, family(actor), drawing_set, approve=body.approve, note=body.note
        )
        return await _family_view(db, actor, project_id)

    return await _once(db, actor, key, {"set": str(set_id), **body.model_dump(mode="json")}, act)


@router.post(
    "/projects/{project_id}/build-plan/versions/{version_id}/acceptance-code",
    response_model=ChallengeOut,
)
async def post_acceptance_code(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> ChallengeOut:
    """Send a one-time code to the owner's email to confirm accepting this exact version."""
    await family_access(db, actor, project_id, write=True)
    await lifecycle.check_acceptable(db, version_id, project_id)
    started = await start_confirmation(
        request.app.state.database, _settings(request), user_id=actor.user_id,
        audience=Audience.IHB, purpose=OtpPurpose.ACCEPT_BUILD_PLAN, subject_id=version_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return ChallengeOut(
        challenge_id=started.challenge_id, sent_to=started.sent_to, expires_at=started.expires_at
    )


@router.post(
    "/projects/{project_id}/build-plan/versions/{version_id}/accept", response_model=SnapshotOut
)
async def post_accept(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    body: BuildPlanAcceptIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    """Accept the latest issued version with the one-time code: it becomes the RFQ baseline and
    supersedes an earlier accepted version (BP-05)."""

    async def act() -> SnapshotOut:
        facts = await family_access(db, actor, project_id, write=True)
        version = await lifecycle.accept(
            db, request.app.state.database, _settings(request), request.app.state.storage,
            family(actor), facts, version_id, challenge_id=body.challenge_id, code=body.code,
            ip_hash=_ip_hash(request),
        )  # fmt: skip
        return SnapshotOut.model_validate(await snapshot(db, facts, version))

    return await _once(
        db, actor, key, {"version": str(version_id), "challenge": str(body.challenge_id)}, act
    )


@router.post(
    "/projects/{project_id}/build-plan/versions/{version_id}/request-changes",
    response_model=FamilyBuildPlanOut,
)
async def post_request_changes(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    body: ReasonIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    async def act() -> FamilyBuildPlanOut:
        await family_access(db, actor, project_id, write=True)
        await lifecycle.request_changes(db, family(actor), version_id, project_id, body.reason)
        return await _family_view(db, actor, project_id)

    return await _once(
        db, actor, key, {"version": str(version_id), **body.model_dump(mode="json")}, act
    )


@router.get("/projects/{project_id}/build-plan/files/{file_id}/url", response_model=DownloadOut)
async def get_family_file_url(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> DownloadOut:
    """A drawing of a set on this project, or the PDF of an issued version (logged)."""
    await family_access(db, actor, project_id, write=False)
    in_set = await db.scalar(
        select(DrawingFile.id).where(
            DrawingFile.project_id == project_id, DrawingFile.file_id == file_id
        )
    )
    issued_doc = await db.scalar(
        select(BuildPlanVersion.id).where(
            BuildPlanVersion.project_id == project_id,
            BuildPlanVersion.issued_at.is_not(None),
            (BuildPlanVersion.issued_document_id == file_id)
            | (BuildPlanVersion.accepted_document_id == file_id),
        )
    )
    if in_set is None and issued_doc is None:
        raise NotFound
    url = await project_file_url(
        db, request.app.state.storage, project_id=project_id, file_id=file_id,
        purposes=FAMILY_FILES, viewer_user_id=actor.user_id, ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)


# --- professionals: drawings -----------------------------------------------------------------


async def _me(db: DbSession, actor: Actor) -> uuid.UUID:
    profile_id = await profile_by_user(db, actor.user_id)
    if profile_id is None:
        raise NotFound
    return profile_id


async def _pro_request(
    db: DbSession, actor: Actor, request_id: uuid.UUID
) -> tuple[DesignRequest, uuid.UUID]:
    profile_id = await _me(db, actor)
    request = await design.request_row(db, request_id)
    if not await design.may_provide(db, request, professional(actor), profile_id=profile_id):
        raise NotFound
    return request, profile_id


async def _pro_requests(db: DbSession, actor: Actor) -> ProDesignRequestsOut:
    profile_id = await _me(db, actor)
    engagement_ids = [e.id for e in await active_engagements_of_profile(db, profile_id)]
    requests = list(
        await db.scalars(
            select(DesignRequest)
            .where(DesignRequest.engagement_id.in_(engagement_ids))
            .order_by(DesignRequest.opened_at)
        )
    ) if engagement_ids else []  # fmt: skip
    items = []
    for request in requests:
        facts = await project(db, request.project_id)
        out = await design_requests_out(
            db, request.project_id, professional(actor), profile_id=profile_id, only=request.id
        )
        items.append(
            ProDesignRequestOut(
                project_id=request.project_id, project_code=facts.code, request=out[0]
            )
        )
    return ProDesignRequestsOut(items=items)


@router.get("/pro/build-plan/design-requests", response_model=ProDesignRequestsOut)
async def get_pro_requests(
    db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> ProDesignRequestsOut:
    """Drawing requests addressed to your active engagements."""
    return await _pro_requests(db, actor)


@router.post(
    "/pro/build-plan/design-requests/{request_id}/sets",
    response_model=ProDesignRequestsOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": ProDesignRequestsOut}},
)
async def post_pro_set(
    request_id: uuid.UUID,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:
    async def act() -> ProDesignRequestsOut:
        request, _ = await _pro_request(db, actor, request_id)
        await design.new_set(db, professional(actor), request)
        return await _pro_requests(db, actor)

    return await _once(db, actor, key, {"request": str(request_id)}, act, 201)


@router.post(
    "/pro/build-plan/design-requests/{request_id}/uploads",
    response_model=UploadTicketOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": UploadTicketOut}},
)
async def post_pro_upload(
    request_id: uuid.UUID,
    body: UploadIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:
    design_request, _ = await _pro_request(db, actor, request_id)
    if body.purpose != FilePurpose.DRAWING:
        raise ValidationFailed(details={"fields": {"purpose": ["Drawings only."]}})
    return await _upload(db, request, actor, design_request.project_id, body, key)


@router.post("/pro/build-plan/uploads/{file_id}/complete", response_model=FileOut)
async def post_pro_upload_complete(
    file_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> FileOut:
    await _me(db, actor)
    return file_out(
        await complete_project_file_upload(
            db, request.app.state.storage, uploader_user_id=actor.user_id, file_id=file_id
        )
    )


@router.post("/pro/build-plan/drawing-sets/{set_id}/files", response_model=ProDesignRequestsOut)
async def post_pro_set_file(
    set_id: uuid.UUID, body: DrawingFileIn, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> ProDesignRequestsOut:
    drawing_set = await design.set_row(db, set_id, lock=True)
    await _pro_request(db, actor, drawing_set.request_id)
    await design.add_file(
        db, professional(actor), drawing_set, file_id=body.file_id,
        drawing_class=body.drawing_class, floor=body.floor, title=body.title,
        sheet_no=body.sheet_no,
    )  # fmt: skip
    return await _pro_requests(db, actor)


@router.post("/pro/build-plan/drawing-sets/{set_id}/submit", response_model=ProDesignRequestsOut)
async def post_pro_submit(
    set_id: uuid.UUID,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:
    """Submit for the family's review, then the appointed checker."""

    async def act() -> ProDesignRequestsOut:
        drawing_set = await design.set_row(db, set_id, lock=True)
        await _pro_request(db, actor, drawing_set.request_id)
        await design.submit_set(db, professional(actor), drawing_set)
        return await _pro_requests(db, actor)

    return await _once(db, actor, key, {"set": str(set_id)}, act)


# --- professionals: structural sign-off ------------------------------------------------------


async def _signoff_view(
    db: DbSession, profile_id: uuid.UUID, version: BuildPlanVersion
) -> ProSignoffOut:
    facts = await project(db, version.project_id)
    try:
        await signoffs.engineer_for(db, profile_id, version.project_id)
        verified = True
    except StateConflict:  # NOT_VERIFIED: shown on the screen, signing is refused
        verified = False
    masters = {m.code: m for m in await active_spec_masters(db)}
    signed = {s.line_code for s in await signoffs.signed(db, version.id)}
    try:
        statement = await signoffs.active_statement(db, SignoffStatement)
    except StateConflict:  # no active statement: signing is refused
        statement = None
    drawings: list[DrawingFileOut] = []
    if version.drawing_set_id:
        files = await design.set_files(db, version.drawing_set_id)
        f_facts = await file_facts(db, [f.file_id for f in files])
        drawings = [
            DrawingFileOut(
                id=f.id, file_id=f.file_id, drawing_class=f.drawing_class, floor=f.floor,
                title=f.title, sheet_no=f.sheet_no, sha256=f.sha256,
                file_name=f_facts[f.file_id].file_name, file_state=f_facts[f.file_id].state,
            )
            for f in files
        ]  # fmt: skip
    view = await snapshot(db, facts, version)
    return ProSignoffOut(
        version_id=version.id,
        project_code=facts.code,
        version_no=version.version_no,
        state=version.state,
        content_hash=version.content_hash,
        verified=verified,
        statement_version=statement.version if statement else None,
        statement_text=statement.text if statement else None,
        lines=[
            SignoffLineOut(
                code=v.line_code, item=masters[v.line_code].item if v.line_code in masters else "",
                criteria=v.criteria_text, applicability=v.applicability, value=v.value_text,
                basis=v.basis, not_applicable_reason=v.not_applicable_reason,
                signed=v.line_code in signed,
            )
            for v in (await signoffs.structural_values(db, version.id)).values()
        ],
        drawings=drawings,
        my_signoffs=[
            SnapshotSignoffOut.model_validate(s)
            for s in view["signoffs"]
            if s["signer_kind"] == "LISTED"
        ],
    )  # fmt: skip


async def _engaged_version(
    db: DbSession, actor: Actor, version_id: uuid.UUID
) -> tuple[BuildPlanVersion, uuid.UUID]:
    profile_id = await _me(db, actor)
    version = await db.get(BuildPlanVersion, version_id)
    if version is None:
        raise NotFound
    engaged = any(
        e.project_id == version.project_id and e.category_code == signoffs.CATEGORY
        for e in await active_engagements_of_profile(db, profile_id)
    )
    if not engaged:
        raise NotFound
    return version, profile_id


@router.get("/pro/build-plan/signoffs", response_model=ProSignoffListOut)
async def get_pro_signoffs(
    db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> ProSignoffListOut:
    """Build Plan versions in review on projects where you are the engaged structural engineer."""
    profile_id = await _me(db, actor)
    projects = {
        e.project_id
        for e in await active_engagements_of_profile(db, profile_id)
        if e.category_code == signoffs.CATEGORY
    }
    versions = list(
        await db.scalars(
            select(BuildPlanVersion).where(
                BuildPlanVersion.project_id.in_(projects),
                BuildPlanVersion.state == BuildPlanState.IN_REVIEW.value,
            )
        )
    ) if projects else []  # fmt: skip
    return ProSignoffListOut(items=[await _signoff_view(db, profile_id, v) for v in versions])


@router.get("/pro/build-plan/signoffs/{version_id}", response_model=ProSignoffOut)
async def get_pro_signoff(
    version_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> ProSignoffOut:
    version, profile_id = await _engaged_version(db, actor, version_id)
    return await _signoff_view(db, profile_id, version)


@router.post("/pro/build-plan/signoffs/{version_id}/code", response_model=ChallengeOut)
async def post_signoff_code(
    version_id: uuid.UUID,
    body: SignCodeIn,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> ChallengeOut:
    """Send a one-time code to confirm signing the chosen lines of this version."""
    version, profile_id = await _engaged_version(db, actor, version_id)
    if version.state != BuildPlanState.IN_REVIEW.value:
        raise NotFound
    await signoffs.engineer_for(db, profile_id, version.project_id)
    started = await start_confirmation(
        request.app.state.database, _settings(request), user_id=actor.user_id,
        audience=Audience.PRO, purpose=OtpPurpose.SIGN_STRUCTURAL, subject_id=version.id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return ChallengeOut(
        challenge_id=started.challenge_id, sent_to=started.sent_to, expires_at=started.expires_at
    )


@router.post("/pro/build-plan/signoffs/{version_id}/sign", response_model=ProSignoffOut)
async def post_sign(
    version_id: uuid.UUID,
    body: SignIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:
    """Sign the chosen structural lines of this exact version (one-time code confirmation; not a
    legally recognised electronic signature)."""

    async def act() -> ProSignoffOut:
        version, profile_id = await _engaged_version(db, actor, version_id)
        await signoffs.engineer_for(db, profile_id, version.project_id)
        await verify_confirmation(
            request.app.state.database, _settings(request), challenge_id=body.challenge_id,
            code=body.code, user_id=actor.user_id, purpose=OtpPurpose.SIGN_STRUCTURAL,
            subject_id=version.id, ip_hash=_ip_hash(request),
        )  # fmt: skip
        await signoffs.sign_with_code(
            db, professional(actor), version.id, profile_id=profile_id, codes=body.line_codes,
            challenge_id=body.challenge_id,
        )  # fmt: skip
        return await _signoff_view(db, profile_id, version)

    return await _once(
        db, actor, key, {"version": str(version_id), "challenge": str(body.challenge_id)}, act
    )


@router.post("/pro/build-plan/signoffs/{signoff_id}/revoke", response_model=ProSignoffListOut)
async def post_pro_revoke(
    signoff_id: uuid.UUID,
    body: ReasonIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:
    async def act() -> ProSignoffListOut:
        profile_id = await _me(db, actor)
        await signoffs.revoke(
            db, professional(actor), signoff_id, body.reason, profile_id=profile_id
        )
        return ProSignoffListOut(items=[])

    return await _once(
        db, actor, key, {"signoff": str(signoff_id), **body.model_dump(mode="json")}, act
    )


@router.get("/pro/build-plan/files/{file_id}/url", response_model=DownloadOut)
async def get_pro_file_url(
    file_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> DownloadOut:
    """A drawing of a set you provide, or of a version you are asked to sign (logged)."""
    profile_id = await _me(db, actor)
    row = (
        await db.scalars(select(DrawingFile).where(DrawingFile.file_id == file_id).limit(1))
    ).one_or_none()
    if row is None:
        raise NotFound
    drawing_set = await db.get_one(DrawingSet, row.set_id)
    request_row = await db.get_one(DesignRequest, drawing_set.request_id)
    allowed = await design.may_provide(db, request_row, professional(actor), profile_id=profile_id)
    if not allowed:
        allowed = any(
            e.project_id == row.project_id and e.category_code == signoffs.CATEGORY
            for e in await active_engagements_of_profile(db, profile_id)
        )
    if not allowed:
        raise NotFound
    url = await project_file_url(
        db, request.app.state.storage, project_id=row.project_id, file_id=file_id,
        purposes=frozenset({FilePurpose.DRAWING}), viewer_user_id=actor.user_id,
        ip_hash=_ip_hash(request),
    )  # fmt: skip
    return DownloadOut(url=url)
