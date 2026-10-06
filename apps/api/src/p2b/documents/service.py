"""Uploads and downloads (DOMAIN_ARCHITECTURE 3.19; ADR-011; API section 15).

Path of a file: the API issues a presigned PUT for an `incoming/` key bound to the declared type
and size; the browser uploads to storage directly; `complete` checks the object exists with the
declared size and queues processing; the worker checks the type, scans, strips image metadata,
writes the clean object to its final key and only then marks it AVAILABLE. Downloads are
short-lived presigned URLs, each one logged.

Slice 1 has one purpose, requirement uploads, whose limits come from the locked question set
(the `uploads` question: types, size, count), so limits are data, not code.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.catalog.interface import question_set
from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.scanning import Scanner
from p2b.core.storage import PresignedUpload, Storage, incoming_key, object_key
from p2b.core.vocabulary import ActorType, FilePurpose, FileState, MembershipRole, ProjectStatus
from p2b.documents.inspection import inspect
from p2b.documents.models import DocumentAccessLog, FileObject
from p2b.identity.interface import Actor
from p2b.projects.interface import member_role

log = structlog.get_logger(__name__)
COUNTED_STATES = (
    FileState.PENDING_UPLOAD.value, FileState.UPLOADED.value, FileState.SCANNING.value,
    FileState.AVAILABLE.value,
)  # fmt: skip


@dataclass(frozen=True)
class UploadLimits:
    accept: tuple[str, ...]
    max_bytes: int
    max_files: int


class FileEvent(EventPayload):
    file_id: uuid.UUID
    project_id: uuid.UUID | None


async def requirement_upload_limits(session: AsyncSession, version: int) -> UploadLimits:
    definition = await question_set(session, version)
    uploads = definition.by_key()["uploads"]
    if uploads.max_bytes is None or uploads.max_files is None:
        raise RuntimeError("the uploads question must define max_bytes and max_files")
    return UploadLimits(tuple(uploads.accept), uploads.max_bytes, uploads.max_files)


# Files change with the requirement: while drafting and after a request for information (2.7).
EDITABLE_STATUSES = frozenset({ProjectStatus.DRAFT, ProjectStatus.NEEDS_INFO})


async def _owner_of_draft(session: AsyncSession, actor: Actor, project_id: uuid.UUID) -> None:
    membership = await member_role(session, user_id=actor.user_id, project_id=project_id)
    if membership is None or membership.role != MembershipRole.OWNER:
        raise NotFound
    if membership.project_status not in EDITABLE_STATUSES:
        raise StateConflict(details={"current_state": membership.project_status.value})


async def create_upload(
    session: AsyncSession,
    settings: Settings,
    storage: Storage,
    actor: Actor,
    *,
    project_id: uuid.UUID,
    question_set_version: int,
    original_name: str,
    content_type: str,
    size_bytes: int,
) -> tuple[FileObject, PresignedUpload]:
    await _owner_of_draft(session, actor, project_id)
    limits = await requirement_upload_limits(session, question_set_version)
    if content_type not in limits.accept:
        raise ValidationFailed(details={"fields": {"content_type": ["Use JPG, PNG or PDF."]}})
    if size_bytes > limits.max_bytes:
        raise ValidationFailed(details={"fields": {"size_bytes": ["The file is too large."]}})
    existing = await session.scalar(
        select(func.count())
        .select_from(FileObject)
        .where(
            FileObject.project_id == project_id,
            FileObject.purpose == FilePurpose.REQUIREMENT_UPLOAD.value,
            FileObject.state.in_(COUNTED_STATES),
        )
    )
    if (existing or 0) >= limits.max_files:
        raise ValidationFailed(details={"fields": {"files": ["You have reached the file limit."]}})

    file_id = new_id()
    now = (await session.execute(select(func.now()))).scalar_one()
    key = object_key(settings.env, FilePurpose.REQUIREMENT_UPLOAD.value, now, file_id)
    file = FileObject(
        id=file_id,
        bucket=settings.storage_bucket_private,
        object_key=key,
        purpose=FilePurpose.REQUIREMENT_UPLOAD.value,
        owner_user_id=actor.user_id,
        project_id=project_id,
        original_name=original_name.strip()[:200] or "file",
        declared_mime=content_type,
        size_bytes=size_bytes,
        state=FileState.PENDING_UPLOAD.value,
    )
    session.add(file)
    await session.flush()
    await record(
        session, action="file.upload_requested", entity_type="file", entity_id=file_id,
        project_id=project_id, actor_type=ActorType.USER, actor_user_id=actor.user_id,
        session_id=actor.session_id,
    )  # fmt: skip
    return file, storage.presign_put(incoming_key(key), content_type, size_bytes)


async def _own_file(session: AsyncSession, actor: Actor, file_id: uuid.UUID) -> FileObject:
    file = await session.get(FileObject, file_id, with_for_update=True)
    if file is None or file.owner_user_id != actor.user_id or file.project_id is None:
        raise NotFound
    return file


async def complete_upload(
    session: AsyncSession, storage: Storage, actor: Actor, file_id: uuid.UUID
) -> FileObject:
    file = await _own_file(session, actor, file_id)
    if file.state != FileState.PENDING_UPLOAD.value:
        raise StateConflict(details={"current_state": file.state})
    size = await storage.size_of(incoming_key(file.object_key))
    if size is None:
        raise StateConflict(
            message="The file has not arrived yet.", details={"current_state": file.state}
        )
    if size != file.size_bytes:
        file.state = FileState.FAILED.value
        file.rejection_reason = "SIZE_MISMATCH"
        return file
    file.state = FileState.UPLOADED.value
    file.version += 1
    await session.flush()
    await publish(
        session, event_type="documents.upload_completed", aggregate_type="file",
        aggregate_id=file.id, payload=FileEvent(file_id=file.id, project_id=file.project_id),
        dedupe_suffix="uploaded",
    )  # fmt: skip
    return file


async def process_file(
    database: Database, storage: Storage, scanner: Scanner, file_id: uuid.UUID
) -> FileState | None:
    """Worker step. Idempotent: a file already past processing is left alone. A scanner or
    storage failure raises, so the job retries; the file is never served meanwhile."""
    async with database.transaction() as session:
        file = await session.get(FileObject, file_id, with_for_update=True)
        if file is None or file.state not in (FileState.UPLOADED.value, FileState.SCANNING.value):
            return None
        file.state = FileState.SCANNING.value
        key, declared = file.object_key, file.declared_mime

    data = await storage.read(incoming_key(key))
    verdict = inspect(data, declared)
    scan = await scanner.scan(data) if verdict.ok else None

    async with database.transaction() as session:
        file = await session.get_one(FileObject, file_id, with_for_update=True)
        if file.state != FileState.SCANNING.value:
            return None
        file.sha256 = hashlib.sha256(data).hexdigest()
        file.detected_mime = verdict.detected_mime
        if not verdict.ok or (scan is not None and not scan.clean):
            file.state = FileState.QUARANTINED.value
            file.rejection_reason = verdict.reason or "MALWARE"
            event = "documents.file_quarantined"
            log.warning("file.quarantined", reason=file.rejection_reason)
        else:
            await storage.write(key, verdict.content, declared)
            file.state = FileState.AVAILABLE.value
            file.size_bytes = len(verdict.content)
            file.available_at = func.now()
            event = "documents.file_available"
        file.version += 1
        await session.flush()
        await publish(
            session, event_type=event, aggregate_type="file", aggregate_id=file.id,
            payload=FileEvent(file_id=file.id, project_id=file.project_id),
            dedupe_suffix=event.rsplit(".", 1)[-1],
        )  # fmt: skip
        state = FileState(file.state)
    if state == FileState.AVAILABLE:
        await storage.delete(incoming_key(key))  # the incoming copy is not the record
    return state


async def list_project_files(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID
) -> list[FileObject]:
    if await member_role(session, user_id=actor.user_id, project_id=project_id) is None:
        raise NotFound
    return list(
        await session.scalars(
            select(FileObject)
            .where(
                FileObject.project_id == project_id,
                FileObject.purpose == FilePurpose.REQUIREMENT_UPLOAD.value,  # AI concepts: designs
                FileObject.state != FileState.DELETED.value,
            )
            .order_by(FileObject.created_at)
        )
    )


async def download_url(
    session: AsyncSession, storage: Storage, actor: Actor, file_id: uuid.UUID, ip_hash: str
) -> str:
    file = await session.get(FileObject, file_id)
    if file is None or file.project_id is None:
        raise NotFound
    if await member_role(session, user_id=actor.user_id, project_id=file.project_id) is None:
        raise NotFound
    return _logged_link(session, storage, file, viewer_user_id=actor.user_id, ip_hash=ip_hash)


def _logged_link(
    session: AsyncSession,
    storage: Storage,
    file: FileObject,
    *,
    viewer_user_id: uuid.UUID,
    ip_hash: str,
) -> str:
    """A short-lived link to an available file, with the access logged (SECURITY 8)."""
    if file.state != FileState.AVAILABLE.value:
        raise StateConflict(details={"current_state": file.state})
    session.add(
        DocumentAccessLog(
            id=new_id(), file_id=file.id, viewer_user_id=viewer_user_id, ip_hash=ip_hash
        )
    )
    return storage.presign_get(file.object_key, file.original_name, file.declared_mime)


async def store_generated_file(
    session: AsyncSession,
    settings: Settings,
    storage: Storage,
    *,
    project_id: uuid.UUID | None,
    owner_user_id: uuid.UUID,
    purpose: FilePurpose,
    data: bytes,
    mime: str,
    file_name: str,
) -> uuid.UUID:
    """Store bytes the server produced itself (AI concepts; invoices and credit notes, which
    belong to the buyer and to no project): written under a generated key in the private bucket
    and recorded AVAILABLE. The caller produced the bytes, which is what the upload pipeline's
    checks exist for; nothing else is accepted."""
    if purpose not in (
        FilePurpose.AI_CONCEPT,
        FilePurpose.INVOICE,
        FilePurpose.BUILD_PLAN_DOCUMENT,
        FilePurpose.COMPARISON_DOCUMENT,
    ):
        raise ValueError("only server-generated purposes are stored this way")
    if (purpose == FilePurpose.INVOICE) != (project_id is None):
        raise ValueError("invoices belong to their buyer; concepts to a project")
    file_id = new_id()
    now = (await session.execute(select(func.now()))).scalar_one()
    key = object_key(settings.env, purpose.value, now, file_id)
    await storage.write(key, data, mime)
    session.add(
        FileObject(
            id=file_id,
            bucket=settings.storage_bucket_private,
            object_key=key,
            purpose=purpose.value,
            owner_user_id=owner_user_id,
            project_id=project_id,
            original_name=file_name,
            declared_mime=mime,
            detected_mime=mime,
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            state=FileState.AVAILABLE.value,
            available_at=now,
        )
    )
    await session.flush()
    return file_id


def concept_image_url(
    session: AsyncSession,
    storage: Storage,
    file: "FileRef",
    *,
    viewer_user_id: uuid.UUID,
    ip_hash: str,
) -> str:
    """A short-lived inline link to an AI concept image, logged like any download. The caller
    has checked that the viewer is a member of the image's project."""
    session.add(
        DocumentAccessLog(
            id=new_id(), file_id=file.file_id, viewer_user_id=viewer_user_id, ip_hash=ip_hash
        )
    )
    return storage.presign_get(file.object_key, file.file_name, file.mime, inline=True)


@dataclass(frozen=True)
class FileRef:
    file_id: uuid.UUID
    project_id: uuid.UUID
    object_key: str
    file_name: str
    mime: str


async def concept_files(
    session: AsyncSession, project_id: uuid.UUID, file_ids: list[uuid.UUID]
) -> dict[uuid.UUID, FileRef]:
    """The project's available AI concept files among `file_ids`."""
    if not file_ids:
        return {}
    rows = await session.scalars(
        select(FileObject).where(
            FileObject.id.in_(file_ids),
            FileObject.project_id == project_id,
            FileObject.purpose == FilePurpose.AI_CONCEPT.value,
            FileObject.state == FileState.AVAILABLE.value,
        )
    )
    return {
        row.id: FileRef(row.id, project_id, row.object_key, row.original_name, row.declared_mime)
        for row in rows
    }


@dataclass(frozen=True)
class FileSummary:
    file_id: uuid.UUID
    file_name: str
    content_type: str
    size_bytes: int
    state: FileState
    created_at: datetime


async def files_for_staff(session: AsyncSession, project_id: uuid.UUID) -> list[FileSummary]:
    """For staff routes only: the caller must already hold an operations role (API 18)."""
    files = await session.scalars(
        select(FileObject)
        .where(
            FileObject.project_id == project_id,
            FileObject.purpose == FilePurpose.REQUIREMENT_UPLOAD.value,
            FileObject.state != FileState.DELETED.value,
        )
        .order_by(FileObject.created_at)
    )
    return [
        FileSummary(
            file_id=file.id,
            file_name=file.original_name,
            content_type=file.declared_mime,
            size_bytes=file.size_bytes,
            state=FileState(file.state),
            created_at=file.created_at,
        )
        for file in files
    ]


# Professionals' own files (Slice 3.2): no project. Technical limits, not business rules.
MB = 1024 * 1024
PERSONAL_LIMITS: dict[FilePurpose, UploadLimits] = {
    FilePurpose.VERIFICATION_EVIDENCE: UploadLimits(
        accept=("image/jpeg", "image/png", "application/pdf"), max_bytes=10 * MB, max_files=30
    ),
    FilePurpose.PORTFOLIO: UploadLimits(
        accept=("image/jpeg", "image/png"), max_bytes=10 * MB, max_files=30
    ),
    # A quote the family holds, for Plan2Build's review (Slice 3.4 intake).
    FilePurpose.QUOTE_DOCUMENT: UploadLimits(
        accept=("image/jpeg", "image/png", "application/pdf"), max_bytes=10 * MB, max_files=20
    ),
}
# Project files for the Build Plan (Slice 3.5): drawings and evidence, uploaded by the family, a
# professional engaged on the project, or operations; the caller authorises the uploader.
PROJECT_LIMITS: dict[FilePurpose, UploadLimits] = {
    FilePurpose.DRAWING: UploadLimits(
        accept=("application/pdf", "image/jpeg", "image/png"), max_bytes=25 * MB, max_files=400
    ),
    FilePurpose.BUILD_PLAN_EVIDENCE: UploadLimits(
        accept=("application/pdf", "image/jpeg", "image/png"), max_bytes=10 * MB, max_files=200
    ),
    # A contractor's quote letter or method statement (Slice 3.6), or operations' evidence of a
    # quote they captured; the rfq module authorises the uploader.
    FilePurpose.QUOTE_ATTACHMENT: UploadLimits(
        accept=("application/pdf", "image/jpeg", "image/png"), max_bytes=10 * MB, max_files=200
    ),
}
STAFF_READABLE = frozenset(
    p.value
    for p in (
        FilePurpose.REQUIREMENT_UPLOAD,
        FilePurpose.VERIFICATION_EVIDENCE,
        FilePurpose.PORTFOLIO,
        FilePurpose.INVOICE,
        FilePurpose.QUOTE_DOCUMENT,
        FilePurpose.DRAWING,
        FilePurpose.BUILD_PLAN_EVIDENCE,
        FilePurpose.BUILD_PLAN_DOCUMENT,
        FilePurpose.QUOTE_ATTACHMENT,
        FilePurpose.COMPARISON_DOCUMENT,
    )
)


def _summary(file: FileObject) -> "FileSummary":
    return FileSummary(
        file_id=file.id,
        file_name=file.original_name,
        content_type=file.declared_mime,
        size_bytes=file.size_bytes,
        state=FileState(file.state),
        created_at=file.created_at,
    )


async def create_personal_upload(
    session: AsyncSession,
    settings: Settings,
    storage: Storage,
    actor: Actor,
    *,
    purpose: FilePurpose,
    original_name: str,
    content_type: str,
    size_bytes: int,
) -> tuple["FileSummary", PresignedUpload]:
    """A presigned upload for a file the actor owns with no project (verification evidence,
    portfolio). The same checks and scanning follow as for requirement uploads."""
    limits = PERSONAL_LIMITS.get(purpose)
    if limits is None:
        raise ValidationFailed(details={"fields": {"purpose": ["Not an upload purpose here."]}})
    if content_type not in limits.accept:
        raise ValidationFailed(
            details={"fields": {"content_type": ["This file type is not accepted."]}}
        )
    if size_bytes > limits.max_bytes:
        raise ValidationFailed(details={"fields": {"size_bytes": ["The file is too large."]}})
    existing = await session.scalar(
        select(func.count())
        .select_from(FileObject)
        .where(
            FileObject.owner_user_id == actor.user_id,
            FileObject.project_id.is_(None),
            FileObject.purpose == purpose.value,
            FileObject.state.in_(COUNTED_STATES),
        )
    )
    if (existing or 0) >= limits.max_files:
        raise ValidationFailed(details={"fields": {"files": ["You have reached the file limit."]}})
    file_id = new_id()
    now = (await session.execute(select(func.now()))).scalar_one()
    key = object_key(settings.env, purpose.value, now, file_id)
    file = FileObject(
        id=file_id,
        bucket=settings.storage_bucket_private,
        object_key=key,
        purpose=purpose.value,
        owner_user_id=actor.user_id,
        project_id=None,
        original_name=original_name.strip()[:200] or "file",
        declared_mime=content_type,
        size_bytes=size_bytes,
        state=FileState.PENDING_UPLOAD.value,
    )
    session.add(file)
    await session.flush()
    await session.refresh(file)
    await record(
        session, action="file.upload_requested", entity_type="file", entity_id=file_id,
        actor_type=ActorType.USER, actor_user_id=actor.user_id, session_id=actor.session_id,
        new_value={"purpose": purpose.value},
    )  # fmt: skip
    return _summary(file), storage.presign_put(incoming_key(key), content_type, size_bytes)


async def _own_personal_file(session: AsyncSession, actor: Actor, file_id: uuid.UUID) -> FileObject:
    file = await session.get(FileObject, file_id, with_for_update=True)
    if file is None or file.owner_user_id != actor.user_id or file.project_id is not None:
        raise NotFound
    return file


async def complete_personal_upload(
    session: AsyncSession, storage: Storage, actor: Actor, file_id: uuid.UUID
) -> "FileSummary":
    file = await _own_personal_file(session, actor, file_id)
    if file.state != FileState.PENDING_UPLOAD.value:
        raise StateConflict(details={"current_state": file.state})
    size = await storage.size_of(incoming_key(file.object_key))
    if size is None:
        raise StateConflict(
            message="The file has not arrived yet.", details={"current_state": file.state}
        )
    if size != file.size_bytes:
        file.state = FileState.FAILED.value
        file.rejection_reason = "SIZE_MISMATCH"
    else:
        file.state = FileState.UPLOADED.value
        file.version += 1
        await session.flush()
        await publish(
            session, event_type="documents.upload_completed", aggregate_type="file",
            aggregate_id=file.id, payload=FileEvent(file_id=file.id, project_id=None),
            dedupe_suffix="uploaded",
        )  # fmt: skip
    await session.flush()
    return _summary(file)


async def personal_files(
    session: AsyncSession, owner_user_id: uuid.UUID, file_ids: list[uuid.UUID]
) -> dict[uuid.UUID, "FileSummary"]:
    """The owner's own no-project files among `file_ids` (any state), for the caller to check."""
    if not file_ids:
        return {}
    rows = await session.scalars(
        select(FileObject).where(
            FileObject.id.in_(file_ids),
            FileObject.owner_user_id == owner_user_id,
            FileObject.project_id.is_(None),
        )
    )
    return {row.id: _summary(row) for row in rows}


async def file_purpose(session: AsyncSession, file_id: uuid.UUID) -> tuple[uuid.UUID, str] | None:
    """Owner and purpose of a file (for the caller's own authorisation checks)."""
    file = await session.get(FileObject, file_id)
    return (file.owner_user_id, file.purpose) if file else None


async def personal_file_url(
    session: AsyncSession, storage: Storage, actor: Actor, file_id: uuid.UUID, ip_hash: str
) -> str:
    """The owner's link to their own no-project file, logged."""
    file = await session.get(FileObject, file_id)
    if file is None or file.owner_user_id != actor.user_id or file.project_id is not None:
        raise NotFound
    return _logged_link(session, storage, file, viewer_user_id=actor.user_id, ip_hash=ip_hash)


async def public_image_urls(
    session: AsyncSession, storage: Storage, file_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Inline links for portfolio images the caller has established are approved for public
    view. Public content, so not logged per viewer."""
    if not file_ids:
        return {}
    rows = await session.scalars(
        select(FileObject).where(
            FileObject.id.in_(file_ids),
            FileObject.purpose == FilePurpose.PORTFOLIO.value,
            FileObject.state == FileState.AVAILABLE.value,
        )
    )
    return {
        row.id: storage.presign_get(
            row.object_key, row.original_name, row.declared_mime, inline=True
        )
        for row in rows
    }


async def staff_download_url(
    session: AsyncSession,
    storage: Storage,
    *,
    viewer_user_id: uuid.UUID,
    file_id: uuid.UUID,
    ip_hash: str,
) -> str:
    """For staff routes only: requirement uploads and professionals' evidence and portfolio;
    logged like any download. Never AI concepts."""
    file = await session.get(FileObject, file_id)
    if file is None or file.purpose not in STAFF_READABLE:
        raise NotFound
    return _logged_link(session, storage, file, viewer_user_id=viewer_user_id, ip_hash=ip_hash)


async def delete_file(session: AsyncSession, actor: Actor, file_id: uuid.UUID) -> None:
    """Soft delete while the requirement is a draft. The stored object is kept (ADR-011)."""
    file = await _own_file(session, actor, file_id)
    assert file.project_id is not None  # noqa: S101 (checked in _own_file)
    await _owner_of_draft(session, actor, file.project_id)
    if file.state == FileState.DELETED.value:
        return
    old = file.state
    file.state = FileState.DELETED.value
    file.deleted_at = func.now()
    file.version += 1
    await record(
        session, action="file.deleted", entity_type="file", entity_id=file.id,
        project_id=file.project_id, actor_type=ActorType.USER, actor_user_id=actor.user_id,
        session_id=actor.session_id, old_value={"state": old}, new_value={"state": file.state},
    )  # fmt: skip


async def requirement_files(
    session: AsyncSession, project_id: uuid.UUID, file_ids: list[uuid.UUID] | None = None
) -> dict[uuid.UUID, "FileSummary"]:
    """A project's available requirement uploads (optionally only `file_ids`), for the family to
    share with an engagement (Slice 3.4, N-08). The caller has checked the family's rights."""
    query = select(FileObject).where(
        FileObject.project_id == project_id,
        FileObject.purpose == FilePurpose.REQUIREMENT_UPLOAD.value,
        FileObject.state == FileState.AVAILABLE.value,
    )
    if file_ids is not None:
        query = query.where(FileObject.id.in_(file_ids))
    rows = await session.scalars(query.order_by(FileObject.created_at))
    return {row.id: _summary(row) for row in rows}


async def shared_file_url(
    session: AsyncSession,
    storage: Storage,
    *,
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    viewer_user_id: uuid.UUID,
    ip_hash: str,
) -> str:
    """A logged link to a requirement upload the family shared with the viewer's engagement. The
    caller has checked the share; this checks the file belongs to the project."""
    file = await session.get(FileObject, file_id)
    if (
        file is None
        or file.project_id != project_id
        or file.purpose != FilePurpose.REQUIREMENT_UPLOAD.value
    ):
        raise NotFound
    return _logged_link(session, storage, file, viewer_user_id=viewer_user_id, ip_hash=ip_hash)


# --- Build Plan project files (Slice 3.5) ----------------------------------------------------


@dataclass(frozen=True)
class FileFacts:
    file_id: uuid.UUID
    project_id: uuid.UUID | None
    owner_user_id: uuid.UUID
    purpose: FilePurpose
    state: FileState
    sha256: str | None
    file_name: str
    content_type: str
    size_bytes: int


async def create_project_file_upload(
    session: AsyncSession,
    settings: Settings,
    storage: Storage,
    *,
    uploader_user_id: uuid.UUID,
    project_id: uuid.UUID,
    purpose: FilePurpose,
    original_name: str,
    content_type: str,
    size_bytes: int,
) -> tuple["FileSummary", PresignedUpload]:
    """A presigned upload of a drawing or evidence file into a project. The caller has checked
    the uploader's right to add it; the same checks and scanning follow as for every upload."""
    limits = PROJECT_LIMITS.get(purpose)
    if limits is None:
        raise ValidationFailed(details={"fields": {"purpose": ["Not an upload purpose here."]}})
    if content_type not in limits.accept:
        raise ValidationFailed(details={"fields": {"content_type": ["Use PDF, JPG or PNG."]}})
    if size_bytes > limits.max_bytes:
        raise ValidationFailed(details={"fields": {"size_bytes": ["The file is too large."]}})
    existing = await session.scalar(
        select(func.count())
        .select_from(FileObject)
        .where(
            FileObject.project_id == project_id,
            FileObject.purpose == purpose.value,
            FileObject.state.in_(COUNTED_STATES),
        )
    )
    if (existing or 0) >= limits.max_files:
        raise ValidationFailed(
            details={"fields": {"files": ["The project's file limit is reached."]}}
        )
    file_id = new_id()
    now = (await session.execute(select(func.now()))).scalar_one()
    key = object_key(settings.env, purpose.value, now, file_id)
    file = FileObject(
        id=file_id,
        bucket=settings.storage_bucket_private,
        object_key=key,
        purpose=purpose.value,
        owner_user_id=uploader_user_id,
        project_id=project_id,
        original_name=original_name.strip()[:200] or "file",
        declared_mime=content_type,
        size_bytes=size_bytes,
        state=FileState.PENDING_UPLOAD.value,
    )
    session.add(file)
    await session.flush()
    await session.refresh(file)
    await record(
        session, action="file.upload_requested", entity_type="file", entity_id=file_id,
        project_id=project_id, actor_type=ActorType.USER, actor_user_id=uploader_user_id,
        new_value={"purpose": purpose.value},
    )  # fmt: skip
    return _summary(file), storage.presign_put(incoming_key(key), content_type, size_bytes)


async def complete_project_file_upload(
    session: AsyncSession, storage: Storage, *, uploader_user_id: uuid.UUID, file_id: uuid.UUID
) -> "FileSummary":
    file = await session.get(FileObject, file_id, with_for_update=True)
    if (
        file is None
        or file.owner_user_id != uploader_user_id
        or file.project_id is None
        or file.purpose not in {p.value for p in PROJECT_LIMITS}
    ):
        raise NotFound
    if file.state != FileState.PENDING_UPLOAD.value:
        raise StateConflict(details={"current_state": file.state})
    size = await storage.size_of(incoming_key(file.object_key))
    if size is None:
        raise StateConflict(
            message="The file has not arrived yet.", details={"current_state": file.state}
        )
    if size != file.size_bytes:
        file.state = FileState.FAILED.value
        file.rejection_reason = "SIZE_MISMATCH"
    else:
        file.state = FileState.UPLOADED.value
        await publish(
            session, event_type="documents.upload_completed", aggregate_type="file",
            aggregate_id=file.id, payload=FileEvent(file_id=file.id, project_id=file.project_id),
            dedupe_suffix="uploaded",
        )  # fmt: skip
    file.version += 1
    await session.flush()
    return _summary(file)


async def file_facts(
    session: AsyncSession, file_ids: list[uuid.UUID]
) -> dict[uuid.UUID, FileFacts]:
    if not file_ids:
        return {}
    rows = await session.scalars(select(FileObject).where(FileObject.id.in_(file_ids)))
    return {
        r.id: FileFacts(
            r.id, r.project_id, r.owner_user_id, FilePurpose(r.purpose), FileState(r.state),
            r.sha256, r.original_name, r.declared_mime, r.size_bytes,
        )
        for r in rows
    }  # fmt: skip


async def project_file_url(
    session: AsyncSession,
    storage: Storage,
    *,
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    purposes: frozenset[FilePurpose],
    viewer_user_id: uuid.UUID,
    ip_hash: str,
) -> str:
    """A logged link to a project file of one of `purposes`. The caller has checked the viewer's
    right to this file."""
    file = await session.get(FileObject, file_id)
    if file is None or file.project_id != project_id or FilePurpose(file.purpose) not in purposes:
        raise NotFound
    return _logged_link(session, storage, file, viewer_user_id=viewer_user_id, ip_hash=ip_hash)


async def store_staff_upload(
    session: AsyncSession,
    settings: Settings,
    storage: Storage,
    *,
    uploader_user_id: uuid.UUID,
    project_id: uuid.UUID,
    purpose: FilePurpose,
    original_name: str,
    content_type: str,
    data: bytes,
) -> "FileSummary":
    """A drawing or evidence file operations upload through the API (Slice 3.5): the admin host is
    not an allowed origin for direct storage uploads (R2 CORS, launch gate N-01), so the bytes come
    through the API and take the same path from there: incoming key, UPLOADED, then the worker's
    type check and scan before the file is AVAILABLE. The caller has checked the staff role."""
    limits = PROJECT_LIMITS.get(purpose)
    if limits is None:
        raise ValidationFailed(details={"fields": {"purpose": ["Not an upload purpose here."]}})
    if content_type not in limits.accept:
        raise ValidationFailed(details={"fields": {"content_type": ["Use PDF, JPG or PNG."]}})
    if not data or len(data) > limits.max_bytes:
        raise ValidationFailed(details={"fields": {"file": ["Empty or too large."]}})
    file_id = new_id()
    now = (await session.execute(select(func.now()))).scalar_one()
    key = object_key(settings.env, purpose.value, now, file_id)
    await storage.write(incoming_key(key), data, content_type)
    file = FileObject(
        id=file_id,
        bucket=settings.storage_bucket_private,
        object_key=key,
        purpose=purpose.value,
        owner_user_id=uploader_user_id,
        project_id=project_id,
        original_name=original_name.strip()[:200] or "file",
        declared_mime=content_type,
        size_bytes=len(data),
        state=FileState.UPLOADED.value,
    )
    session.add(file)
    await session.flush()
    await session.refresh(file)
    await record(
        session, action="file.uploaded_by_staff", entity_type="file", entity_id=file_id,
        project_id=project_id, actor_type=ActorType.USER, actor_user_id=uploader_user_id,
        new_value={"purpose": purpose.value},
    )  # fmt: skip
    await publish(
        session, event_type="documents.upload_completed", aggregate_type="file",
        aggregate_id=file.id, payload=FileEvent(file_id=file.id, project_id=project_id),
        dedupe_suffix="uploaded",
    )  # fmt: skip
    return _summary(file)
