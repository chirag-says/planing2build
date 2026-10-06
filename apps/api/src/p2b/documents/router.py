import uuid
from typing import Annotated

from fastapi import APIRouter, Request, Response, status
from fastapi.responses import JSONResponse

from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import Database, DbSession
from p2b.core.http import client_ip
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.ratelimit import Limit, enforce
from p2b.core.storage import DOWNLOAD_URL_TTL_SECONDS
from p2b.core.vocabulary import Audience, FileState
from p2b.documents.models import FileObject
from p2b.documents.schemas import DownloadLink, FileView, UploadRequest, UploadTicket
from p2b.documents.service import (
    complete_upload,
    create_upload,
    delete_file,
    download_url,
    list_project_files,
)
from p2b.identity.interface import Actor, require_actor
from p2b.projects.interface import question_set_version_of

router = APIRouter(tags=["documents"])

HOMEOWNER = require_actor(Audience.IHB)
# Tier T3 (uploads and heavy writes): 60 per minute per session.
UPLOAD_LIMIT = Limit("uploads_session", 60, 60)


def _view(file: FileObject) -> FileView:
    return FileView(
        file_id=file.id,
        file_name=file.original_name,
        content_type=file.declared_mime,
        size_bytes=file.size_bytes,
        state=FileState(file.state),
        created_at=file.created_at,
    )


@router.post(
    "/uploads", status_code=status.HTTP_201_CREATED, response_model=UploadTicket,
    responses={201: {"model": UploadTicket}},
)  # fmt: skip
async def post_upload(
    body: UploadRequest,
    key: IdempotencyKeyHeader,
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, HOMEOWNER],
) -> JSONResponse:
    database: Database = request.app.state.database
    await enforce(database, UPLOAD_LIMIT, str(actor.session_id))

    async def act() -> tuple[int, dict[str, object]]:
        version = await question_set_version_of(db, body.project_id)
        file, ticket = await create_upload(
            db, request.app.state.settings, request.app.state.storage, actor,
            project_id=body.project_id, question_set_version=version,
            original_name=body.file_name, content_type=body.content_type,
            size_bytes=body.size_bytes,
        )  # fmt: skip
        await db.refresh(file)
        out = UploadTicket(file=_view(file), upload_url=ticket.url, headers=ticket.headers)
        return 201, out.model_dump(mode="json")

    return await run_once(
        db, session_id=actor.session_id, key=key,
        request_body=body.model_dump(mode="json"), action=act,
    )  # fmt: skip


@router.post("/uploads/{file_id}/complete", response_model=FileView)
async def post_upload_complete(
    file_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> FileView:
    file = await complete_upload(db, request.app.state.storage, actor, file_id)
    return _view(file)


@router.get("/projects/{project_id}/files", response_model=list[FileView])
async def get_project_files(
    project_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> list[FileView]:
    return [_view(f) for f in await list_project_files(db, actor, project_id)]


@router.get("/files/{file_id}/url", response_model=DownloadLink)
async def get_file_url(
    file_id: uuid.UUID, request: Request, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> DownloadLink:
    settings: Settings = request.app.state.settings
    peer = request.client.host if request.client else None
    ip_hash = keyed_hash(
        settings.identifier_pepper.get_secret_value(), client_ip(request.headers, peer)
    )
    url = await download_url(db, request.app.state.storage, actor, file_id, ip_hash)
    return DownloadLink(url=url, expires_in_seconds=DOWNLOAD_URL_TTL_SECONDS)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file_route(
    file_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, HOMEOWNER]
) -> Response:
    await delete_file(db, actor, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
