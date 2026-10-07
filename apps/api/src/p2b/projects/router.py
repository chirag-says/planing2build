import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.billing.interface import offer_published, package_active, package_state
from p2b.core.authz import public_route
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import Database, DbSession
from p2b.core.errors import StateConflict
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.ratelimit import Limit, enforce
from p2b.core.vocabulary import (
    Audience,
    OfferingKind,
    PackageAvailability,
    PackageState,
    ProjectStatus,
)
from p2b.identity.interface import Actor, require_actor
from p2b.projects.estimates import latest_estimate
from p2b.projects.models import Project, ProjectRequirement
from p2b.projects.review import ReviewMessage, get_workspace, review_message
from p2b.projects.schemas import (
    EnquiryAccepted,
    EnquiryRequest,
    EstimateFiguresOut,
    EstimateInputsOut,
    EstimateRateCardOut,
    EstimateStageOut,
    LocalitySuggestion,
    PackageOfferOut,
    ProjectCreateRequest,
    ProjectDetail,
    ProjectEstimateOut,
    ProjectSummary,
    RequirementSaveRequest,
    RequirementSubmitRequest,
    RequirementView,
    ReviewMessageOut,
    WorkspaceGroupOut,
    WorkspaceLineOut,
    WorkspaceOut,
    WorkspaceStageOut,
)
from p2b.projects.service import (
    create_enquiry,
    create_project,
    delete_project,
    get_project,
    list_projects,
    package_availability,
    save_requirement,
    submit_requirement,
    suggest_locality,
)

router = APIRouter(tags=["projects"])

HOMEOWNER = require_actor(Audience.IHB)

# API_ARCHITECTURE section 1, tier T1 for contact capture.
ENQUIRY_PER_CONTACT = Limit("enquiry_contact", 5, 600)
ENQUIRY_PER_IP = Limit("enquiry_ip", 20, 600)
# Nominatim's public instance allows about one request per second for the whole application.
LOCALITY_PER_SESSION = Limit("locality_session", 30, 600)
LOCALITY_GLOBAL = Limit("locality_global", 1, 1)


def _summary(project: Project) -> ProjectSummary:
    return ProjectSummary(
        project_id=project.id,
        code=project.code,
        status=ProjectStatus(project.status),
        city_code=project.city_code,
        locality=project.locality,
        created_at=project.created_at,
        submitted_at=project.submitted_at,
    )


async def _detail(
    db: AsyncSession,
    settings: Settings,
    project: Project,
    requirement: ProjectRequirement,
    message: ReviewMessage | None = None,
) -> ProjectDetail:
    availability = package_availability(project)
    state = await package_state(db, project.id)
    purchasable = (
        availability == PackageAvailability.ELIGIBLE
        and state != PackageState.ACTIVE
        and await offer_published(db, settings, OfferingKind.PACKAGE)
    )
    return ProjectDetail(
        project=_summary(project),
        requirement=RequirementView(
            question_set_version=requirement.question_set_version,
            answers=requirement.answers,
            version=requirement.version,
            submitted_at=requirement.submitted_at,
        ),
        review_message=ReviewMessageOut(
            status=message.status, message=message.message, at=message.at
        )
        if message
        else None,
        package=PackageOfferOut(
            availability=availability,
            state=state,
            purchasable=purchasable,
        ),
    )


def _allow_demo_rates(request: Request) -> bool:
    """DEMO rate cards never reach production (Chirag, 2026-10-04)."""
    settings: Settings = request.app.state.settings
    return settings.env != "production"


def _ip_hash(request: Request) -> str:
    settings: Settings = request.app.state.settings
    peer = request.client.host if request.client else None
    return keyed_hash(
        settings.identifier_pepper.get_secret_value(), client_ip(request.headers, peer)
    )


@router.post(
    "/projects",
    status_code=status.HTTP_201_CREATED,
    response_model=ProjectDetail,
    responses={201: {"model": ProjectDetail}},
)
async def post_project(
    body: ProjectCreateRequest,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    async def act() -> tuple[int, dict[str, object]]:
        project = await create_project(
            db, actor, city_name=body.city, project_type=body.project_type
        )
        _, requirement = await get_project(db, actor, project.id)
        await db.refresh(project)
        return 201, (
            await _detail(db, request.app.state.settings, project, requirement)
        ).model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key,
        request_body=body.model_dump(mode="json"), action=act,
    )  # fmt: skip


@router.get("/projects", response_model=list[ProjectSummary])
async def get_projects(db: DbSession, actor: Annotated[Actor, HOMEOWNER]) -> list[ProjectSummary]:
    return [_summary(p) for p in await list_projects(db, actor)]


@router.get("/projects/{project_id}", response_model=ProjectDetail)
async def get_project_detail(
    project_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> ProjectDetail:
    project, requirement = await get_project(db, actor, project_id)
    return await _detail(
        db, request.app.state.settings, project, requirement, await review_message(db, project)
    )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_route(
    project_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> Response:
    """A draft the family no longer wants. Anything submitted is cancelled by operations."""
    await delete_project(db, actor, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/projects/{project_id}/estimate", response_model=ProjectEstimateOut)
async def get_project_estimate(
    project_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> ProjectEstimateOut:
    """The indicative estimate stored with the latest submission. 409 before the first
    submission."""
    project, requirement = await get_project(db, actor, project_id)
    view = await latest_estimate(
        db, project, current_version=requirement.version, allow_demo=_allow_demo_rates(request)
    )
    if view is None:
        raise StateConflict(details={"current_state": project.status})
    result = view.result
    return ProjectEstimateOut(
        status=view.status,
        unavailable_reason=view.unavailable_reason,
        created_at=view.created_at,
        inputs=EstimateInputsOut.model_validate(view.inputs),
        figures=EstimateFiguresOut(
            total_low=result["total_low"],
            total_high=result["total_high"],
            total_mid=result["total_mid"],
            per_sqft_low=result["per_sqft_low"],
            per_sqft_high=result["per_sqft_high"],
            duration_months=result["duration_months"],
            stages=[
                EstimateStageOut(
                    stage_number=s.stage_number,
                    stage_name=s.stage_name,
                    share_pct=s.share_pct,
                    amount=s.amount,
                )
                for s in view.stages
            ],
            rate_card=EstimateRateCardOut.model_validate(result["rate_card"]),
        )
        if result
        else None,
    )


@router.get("/projects/{project_id}/workspace", response_model=WorkspaceOut)
async def get_project_workspace(
    project_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> WorkspaceOut:
    """The stages and specification lines, from the initial review on (ACCEPTED): every stage
    instance with its status and schedule, and the lines by group (A, B, C). A line's criteria
    are included only when `criteria_visible` (open point F-09)."""
    settings: Settings = request.app.state.settings
    workspace = await get_workspace(
        db,
        actor,
        project_id,
        criteria_before_package=settings.spec_criteria_before_package,
        package_active=await package_active(db, project_id),
    )
    by_group: dict[str, list[WorkspaceLineOut]] = {g.code: [] for g in workspace.groups}
    for line in workspace.lines:
        by_group[line.group].append(
            WorkspaceLineOut(
                code=line.code,
                item=line.item,
                state=line.state,
                is_long_lead=line.is_long_lead,
                is_structural=line.is_structural,
                engineer_signoff=line.engineer_signoff,
                performance_specification=line.issued_criteria
                if workspace.criteria_visible
                else None,
            )
        )
    return WorkspaceOut(
        project=_summary(workspace.project),
        stages=[
            WorkspaceStageOut(
                stage_number=stage.stage_number,
                name=stage.name,
                floor=stage.floor,
                state=stage.state,
                is_gate=stage.is_gate,
                gate_status=stage.gate_status,
                planned_start=stage.planned_start,
                planned_end=stage.planned_end,
            )
            for stage in workspace.stages
        ],
        groups=[
            WorkspaceGroupOut(
                code=group.code, name=group.name, issued=group.issued, lines=by_group[group.code]
            )
            for group in workspace.groups
        ],
        criteria_visible=workspace.criteria_visible,
    )


@router.put("/projects/{project_id}/requirement", response_model=RequirementView)
async def put_requirement(
    project_id: uuid.UUID,
    body: RequirementSaveRequest,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> RequirementView:
    requirement = await save_requirement(
        db, actor, project_id, answers=body.answers, version=body.version
    )
    return RequirementView(
        question_set_version=requirement.question_set_version,
        answers=requirement.answers,
        version=requirement.version,
        submitted_at=requirement.submitted_at,
    )


@router.post(
    "/projects/{project_id}/requirement/submit",
    response_model=ProjectDetail,
    responses={200: {"model": ProjectDetail}},
)
async def post_submit(
    project_id: uuid.UUID,
    body: RequirementSubmitRequest,
    request: Request,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    allow_demo = _allow_demo_rates(request)

    async def act() -> tuple[int, dict[str, object]]:
        project, requirement = await submit_requirement(
            db, actor, project_id, version=body.version, allow_demo_rates=allow_demo
        )
        await db.refresh(project)
        return 200, (
            await _detail(db, request.app.state.settings, project, requirement)
        ).model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key,
        request_body={"project_id": str(project_id), **body.model_dump(mode="json")}, action=act,
    )  # fmt: skip


@router.get("/geo/locality", response_model=LocalitySuggestion)
async def get_locality(
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
) -> LocalitySuggestion:
    database: Database = request.app.state.database
    await enforce(database, LOCALITY_PER_SESSION, str(actor.session_id))
    await enforce(database, LOCALITY_GLOBAL, "all")
    locality = await suggest_locality(db, request.app.state.geocoder, lat=lat, lng=lng)
    return LocalitySuggestion(locality=locality)


@router.post(
    "/public/enquiries",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=EnquiryAccepted,
    dependencies=[public_route],
)
async def post_enquiry(body: EnquiryRequest, request: Request, db: DbSession) -> EnquiryAccepted:
    settings: Settings = request.app.state.settings
    database: Database = request.app.state.database
    ip_hash = _ip_hash(request)
    contact = keyed_hash(settings.identifier_pepper.get_secret_value(), str(body.email).lower())
    await enforce(database, ENQUIRY_PER_IP, ip_hash)
    await enforce(database, ENQUIRY_PER_CONTACT, contact)
    await create_enquiry(
        db, kind=body.kind, email=str(body.email), work_type=body.work_type, ip_hash=ip_hash
    )
    return EnquiryAccepted()
