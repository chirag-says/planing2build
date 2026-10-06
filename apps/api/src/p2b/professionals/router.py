import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import JSONResponse

from p2b.catalog.interface import service_category_rows
from p2b.core.authz import public_route
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import Database, DbSession
from p2b.core.errors import NotFound
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.ratelimit import Limit, enforce
from p2b.core.vocabulary import Audience
from p2b.documents.interface import (
    complete_personal_upload,
    create_personal_upload,
    personal_file_url,
)
from p2b.identity.interface import Actor, require_actor
from p2b.professionals.schemas import (
    AddCategoryIn,
    CategoryOut,
    DirectoryPageOut,
    DocumentIn,
    DownloadOut,
    FileOut,
    OwnDashboardOut,
    PortfolioIn,
    ProfileUpdateIn,
    PublicProfileOut,
    ReferenceIn,
    SubtypesIn,
    UploadIn,
    UploadTicketOut,
)
from p2b.professionals.service import (
    DirectoryFilters,
    ProfileUpdate,
    add_category,
    add_document,
    add_portfolio_item,
    add_reference,
    cover_images,
    directory,
    own_profile,
    public_profile,
    remove_evidence,
    set_hidden,
    set_subtypes,
    submit_category,
    update_profile,
)
from p2b.professionals.views import (
    directory_out,
    own_dashboard,
    public_profile_out,
)
from p2b.projects.interface import project_point

router = APIRouter(tags=["professionals"])

PROFESSIONAL = require_actor(Audience.PRO)
HOMEOWNER = require_actor(Audience.IHB)
# T0 for the public directory (API section 1); T3 for uploads.
DIRECTORY_LIMIT = Limit("directory_ip", 120, 60)
UPLOAD_LIMIT = Limit("pro_uploads_session", 60, 60)


def _ip_hash(request: Request) -> str:
    settings: Settings = request.app.state.settings
    peer = request.client.host if request.client else None
    return keyed_hash(
        settings.identifier_pepper.get_secret_value(), client_ip(request.headers, peer)
    )


async def _dashboard(db: DbSession, actor: Actor) -> OwnDashboardOut:
    return await own_dashboard(db, await own_profile(db, actor))


# --- the professional's own side (professionals host) --------------------------------------


@router.get("/pro/profile", response_model=OwnDashboardOut)
async def get_own(db: DbSession, actor: Annotated[Actor, PROFESSIONAL]) -> OwnDashboardOut:
    """Your profile, categories with their listing state and requirements, and your evidence."""
    return await _dashboard(db, actor)


@router.patch("/pro/profile", response_model=OwnDashboardOut)
async def patch_profile(
    body: ProfileUpdateIn, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> OwnDashboardOut:
    sent = body.model_fields_set
    change = ProfileUpdate(
        display_name=body.display_name,
        firm_name=body.firm_name,
        bio=body.bio,
        years_experience=body.years_experience,
        team_size=body.team_size,
        base_locality=body.base_locality,
        base_point=(body.base_point.lat, body.base_point.lng) if body.base_point else None,
        service_radius_km=body.service_radius_km,
        fields_set=frozenset(sent),
    )
    await update_profile(db, actor, change)
    return await _dashboard(db, actor)


@router.post(
    "/pro/categories",
    response_model=OwnDashboardOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": OwnDashboardOut}},
)
async def post_category(
    body: AddCategoryIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:
    async def act() -> tuple[int, dict[str, object]]:
        await add_category(db, actor, body.category, body.subtypes)
        return 201, (await _dashboard(db, actor)).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body=body.model_dump(mode="json"),
        action=act,
    )


@router.put("/pro/categories/{code}/subtypes", response_model=OwnDashboardOut)
async def put_subtypes(
    code: str, body: SubtypesIn, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> OwnDashboardOut:
    await set_subtypes(db, actor, code, body.subtypes)
    return await _dashboard(db, actor)


@router.post(
    "/pro/categories/{code}/submit",
    response_model=OwnDashboardOut,
    responses={200: {"model": OwnDashboardOut}},
)
async def post_submit(
    code: str, key: IdempotencyKeyHeader, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> JSONResponse:
    """Submit a category for review (also resubmission, reapplying after the waiting time, and
    re-verification when due). 422 lists what is still needed."""

    async def act() -> tuple[int, dict[str, object]]:
        await submit_category(db, actor, code)
        return 200, (await _dashboard(db, actor)).model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key, request_body={"code": code}, action=act
    )


@router.post("/pro/categories/{code}/hide", response_model=OwnDashboardOut)
async def post_hide(
    code: str, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> OwnDashboardOut:
    """Hide a listed category from the public directory (D-11). Reversible."""
    await set_hidden(db, actor, code, hidden=True)
    return await _dashboard(db, actor)


@router.post("/pro/categories/{code}/show", response_model=OwnDashboardOut)
async def post_show(
    code: str, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> OwnDashboardOut:
    """Show a hidden listed category again; 409 when re-verification is due."""
    await set_hidden(db, actor, code, hidden=False)
    return await _dashboard(db, actor)


@router.post(
    "/pro/uploads",
    response_model=UploadTicketOut,
    status_code=status.HTTP_201_CREATED,
    responses={201: {"model": UploadTicketOut}},
)
async def post_pro_upload(
    body: UploadIn,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, PROFESSIONAL],
) -> JSONResponse:
    database: Database = request.app.state.database
    await enforce(database, UPLOAD_LIMIT, str(actor.session_id))

    async def act() -> tuple[int, dict[str, object]]:
        summary, ticket = await create_personal_upload(
            db,
            request.app.state.settings,
            request.app.state.storage,
            actor,
            purpose=body.purpose,
            original_name=body.file_name,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
        )
        out = UploadTicketOut(
            file=FileOut(
                file_id=summary.file_id,
                file_name=summary.file_name,
                content_type=summary.content_type,
                size_bytes=summary.size_bytes,
                state=summary.state,
            ),
            upload_url=ticket.url,
            headers=ticket.headers,
        )
        return 201, out.model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body=body.model_dump(mode="json"),
        action=act,
    )


@router.post("/pro/uploads/{file_id}/complete", response_model=FileOut)
async def post_pro_upload_complete(
    file_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> FileOut:
    summary = await complete_personal_upload(db, request.app.state.storage, actor, file_id)
    return FileOut(
        file_id=summary.file_id,
        file_name=summary.file_name,
        content_type=summary.content_type,
        size_bytes=summary.size_bytes,
        state=summary.state,
    )


@router.get("/pro/files/{file_id}/url", response_model=DownloadOut)
async def get_pro_file_url(
    file_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> DownloadOut:
    url = await personal_file_url(db, request.app.state.storage, actor, file_id, _ip_hash(request))
    return DownloadOut(url=url)


@router.post("/pro/documents", response_model=OwnDashboardOut)
async def post_document(
    body: DocumentIn, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> OwnDashboardOut:
    await add_document(
        db,
        actor,
        kind=body.kind,
        file_id=body.file_id,
        category_code=body.category_code,
        details={"issuer": body.issuer, "number": body.number, "gstin": body.gstin},
    )
    return await _dashboard(db, actor)


@router.post("/pro/references", response_model=OwnDashboardOut)
async def post_reference(
    body: ReferenceIn, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> OwnDashboardOut:
    await add_reference(
        db,
        actor,
        category_code=body.category_code,
        name=body.name,
        phone=body.phone,
        note=body.project_note,
    )
    return await _dashboard(db, actor)


@router.post("/pro/portfolio", response_model=OwnDashboardOut)
async def post_portfolio(
    body: PortfolioIn, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> OwnDashboardOut:
    await add_portfolio_item(db, actor, file_id=body.file_id, caption=body.caption)
    return await _dashboard(db, actor)


@router.delete("/pro/documents/{item_id}", response_model=OwnDashboardOut)
async def delete_document(
    item_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> OwnDashboardOut:
    await remove_evidence(db, actor, "document", item_id)
    return await _dashboard(db, actor)


@router.delete("/pro/references/{item_id}", response_model=OwnDashboardOut)
async def delete_reference(
    item_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> OwnDashboardOut:
    await remove_evidence(db, actor, "reference", item_id)
    return await _dashboard(db, actor)


@router.delete("/pro/portfolio/{item_id}", response_model=OwnDashboardOut)
async def delete_portfolio(
    item_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, PROFESSIONAL]
) -> OwnDashboardOut:
    await remove_evidence(db, actor, "portfolio", item_id)
    return await _dashboard(db, actor)


# --- public directory (homeowner host, no sign-in; D-09) -------------------------------------


async def _limited(request: Request) -> None:
    await enforce(request.app.state.database, DIRECTORY_LIMIT, _ip_hash(request))


@router.get(
    "/public/professional-categories", response_model=list[CategoryOut], dependencies=[public_route]
)
async def get_public_categories(db: DbSession) -> list[CategoryOut]:
    return [
        CategoryOut(code=r.code, name=r.name, parent_code=r.parent_code)
        for r in await service_category_rows(db)
    ]


async def _page(
    request: Request, db: DbSession, filters: DirectoryFilters, cursor: str | None
) -> DirectoryPageOut:
    page = await directory(db, filters, cursor)
    covers = await cover_images(db, [p.id for p in page.profiles])
    return await directory_out(db, request.app.state.storage, page, covers)


@router.get("/public/professionals", response_model=DirectoryPageOut, dependencies=[public_route])
async def get_directory(
    request: Request,
    db: DbSession,
    category: Annotated[str | None, Query(max_length=40)] = None,
    subtype: Annotated[str | None, Query(max_length=40)] = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    locality: Annotated[str | None, Query(max_length=80)] = None,
    cursor: Annotated[str | None, Query(max_length=300)] = None,
) -> DirectoryPageOut:
    """Approved, listed professionals only, in a neutral daily shuffle (D-08). Never ranked,
    sponsored or ordered by price."""
    await _limited(request)
    filters = DirectoryFilters(category=category, subtype=subtype, q=q, locality=locality)
    return await _page(request, db, filters, cursor)


@router.get(
    "/public/professionals/{profile_id}",
    response_model=PublicProfileOut,
    dependencies=[public_route],
)
async def get_public_profile(
    profile_id: uuid.UUID, request: Request, db: DbSession
) -> PublicProfileOut:
    """The public profile (D-01); 404 unless at least one category is listed and shown."""
    await _limited(request)
    return await public_profile_out(
        db, request.app.state.storage, await public_profile(db, profile_id)
    )


@router.get("/projects/{project_id}/professionals", response_model=DirectoryPageOut)
async def get_directory_for_project(
    project_id: uuid.UUID,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
    category: Annotated[str | None, Query(max_length=40)] = None,
    subtype: Annotated[str | None, Query(max_length=40)] = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    cursor: Annotated[str | None, Query(max_length=300)] = None,
) -> DirectoryPageOut:
    """Project-aware filter for a signed-in family: only professionals whose service area
    covers the project's plot. It narrows the list; the order stays the neutral shuffle."""
    point = await project_point(db, user_id=actor.user_id, project_id=project_id)
    if point is None:
        raise NotFound
    filters = DirectoryFilters(category=category, subtype=subtype, q=q, near=point)
    return await _page(request, db, filters, cursor)
