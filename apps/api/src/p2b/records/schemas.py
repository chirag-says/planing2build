"""Handover and Build Record API contracts (Slice 3.7C). Requests refuse unknown fields. The
homeowner's handover model says plainly whether the owner acknowledged it or operations issued it
without acknowledgement (EX-15); no model carries a price or an amount."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from p2b.core.vocabulary import (
    BuildRecordBasis,
    BuildRecordState,
    FileState,
    HandoverDocumentKind,
    HandoverState,
)


def _text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("This is required.")
    return value


Text = Annotated[str, Field(min_length=1, max_length=1000), AfterValidator(_text)]
Short = Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_text)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentIn(Strict):
    kind: HandoverDocumentKind
    title: Short
    file_id: uuid.UUID


class WarrantyIn(Strict):
    """MVP P8: every warranty carries its term, expiry and installer."""

    item: Short
    term: Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_text)]
    expiry_date: date
    installer: Short
    spec_line_code: Annotated[str | None, Field(min_length=3, max_length=3)] = None
    document_id: uuid.UUID | None = None


class ReasonIn(Strict):
    reason: Text


class AcknowledgeIn(Strict):
    challenge_id: uuid.UUID
    code: Annotated[str, Field(min_length=4, max_length=10)]
    statement_id: uuid.UUID


class AssembleIn(Strict):
    reason: Annotated[str | None, Field(max_length=1000)] = Field(
        default=None, description="Required for a new version after an issued one"
    )


class UploadIn(Strict):
    file_name: Annotated[str, Field(min_length=1, max_length=200)]
    content_type: Annotated[str, Field(max_length=100)]
    size_bytes: int = Field(gt=0)


class FileOut(BaseModel):
    file_id: uuid.UUID
    file_name: str
    content_type: str
    size_bytes: int
    state: FileState


class UploadTicketOut(BaseModel):
    file: FileOut
    upload_url: str
    headers: dict[str, str]


class DownloadOut(BaseModel):
    url: str


class ChallengeOut(BaseModel):
    challenge_id: uuid.UUID
    sent_to: str
    expires_at: datetime
    statement_id: uuid.UUID
    statement_version: int
    statement_text: str


class DocumentOut(BaseModel):
    id: uuid.UUID
    kind: HandoverDocumentKind
    title: str
    file_id: uuid.UUID
    added_role: str
    added_at: datetime


class WarrantyOut(BaseModel):
    id: uuid.UUID
    item: str
    term: str
    expiry_date: date
    installer: str
    spec_line_code: str | None
    document_id: uuid.UUID | None


class HandoverOut(BaseModel):
    id: uuid.UUID
    state: HandoverState
    opened_at: datetime
    ready_at: datetime | None
    documents: list[DocumentOut]
    warranties: list[WarrantyOut]
    acknowledged_at: datetime | None = Field(description="Set only by the owner's code")
    statement_text: str | None
    issued_without_acknowledgement: bool
    issued_at: datetime | None
    issue_reason: str | None


class HandoverViewOut(BaseModel):
    project_id: uuid.UUID
    is_owner: bool
    handover: HandoverOut | None


class BuildRecordVersionOut(BaseModel):
    id: uuid.UUID
    version_no: int
    state: BuildRecordState
    basis: BuildRecordBasis
    correction_reason: str | None
    snapshot_sha256: str | None
    pdf_sha256: str | None
    json_sha256: str | None
    issued_at: datetime | None


class BuildRecordsOut(BaseModel):
    project_id: uuid.UUID
    versions: list[BuildRecordVersionOut]


class BuildRecordSnapshotOut(BuildRecordVersionOut):
    snapshot: dict[str, Any]
