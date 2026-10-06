"""Execution API contracts (Slice 3.7A). Requests refuse unknown fields. No model has a
percentage, a planned date, a delay, an amount or a contract value (EX-02, EX-04, EX-05). The
contractor's models carry only its own updates (SLICE3_7_READINESS N.1)."""

import uuid
from datetime import date, datetime
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from p2b.core.vocabulary import (
    EngagementParty,
    FileState,
    GateStatus,
    StageState,
    StageUpdateKind,
)


def _text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("This is required.")
    return value


def _optional(value: str | None) -> str | None:
    return (value.strip() or None) if value is not None else None


Text = Annotated[str, Field(min_length=1, max_length=2000), AfterValidator(_text)]
OptionalText = Annotated[str | None, Field(max_length=2000), AfterValidator(_optional)]
Reason = Annotated[str, Field(min_length=1, max_length=1000), AfterValidator(_text)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- requests ------------------------------------------------------------------------------


class UpdateIn(Strict):
    """The standard update (EX-02). A completion request is an update of that kind."""

    kind: StageUpdateKind
    note: Text
    materials: OptionalText = None
    open_problems: OptionalText = None
    file_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    corrects_update_id: uuid.UUID | None = None


class OpsUpdateIn(UpdateIn):
    """Operations enter an OUTSIDE contractor's update with how they received it."""

    reason: Reason


class DecisionIn(Strict):
    """`version` is the stage's version as read; a stale version is 409 STALE."""

    version: int = Field(ge=1)


class ReasonDecisionIn(DecisionIn):
    reason: Reason


class EvidenceUploadIn(Strict):
    """A photo of an update. Capture time and location are the device's claims, stored apart
    from the image (whose own metadata is stripped) and never authoritative (EX-22)."""

    file_name: Annotated[str, Field(min_length=1, max_length=200)]
    content_type: Annotated[str, Field(max_length=100)]
    size_bytes: int = Field(gt=0)
    captured_at: datetime | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def _both_or_neither(self) -> Self:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Give both latitude and longitude, or neither.")
        return self

    def claim(self) -> dict[str, object] | None:
        claim: dict[str, object] = {}
        if self.captured_at is not None:
            claim["captured_at"] = self.captured_at.isoformat()
        if self.latitude is not None:
            claim["latitude"] = self.latitude
            claim["longitude"] = self.longitude
        return claim or None


# --- responses ------------------------------------------------------------------------------


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


class EvidenceOut(BaseModel):
    file_id: uuid.UUID
    file_name: str
    captured_at: str | None = Field(description="The device's claim; not verified (EX-22)")


class UpdateOut(BaseModel):
    id: uuid.UUID
    kind: StageUpdateKind
    note: str
    materials: str | None
    open_problems: str | None
    photos: list[EvidenceOut]
    corrects_update_id: uuid.UUID | None
    entered_by_operations: bool
    contractor_name: str | None = Field(description="The contractor of record when posted")
    posted_at: datetime


class StageOut(BaseModel):
    """No planned date, percentage or delay: only what happened (EX-04)."""

    id: uuid.UUID
    stage_number: int
    name: str
    floor: int | None
    sequence: int = Field(description="Display order only, not build order (BP-07A)")
    state: StageState
    is_gate: bool
    gate_status: GateStatus | None
    is_payment_milestone: bool
    actual_start: date | None
    actual_end: date | None
    completion_requested_at: datetime | None
    version: int
    update_count: int
    last_update_at: datetime | None


class ContractorOut(BaseModel):
    engagement_id: uuid.UUID
    party: EngagementParty
    name: str | None


class FamilyExecutionOut(BaseModel):
    project_id: uuid.UUID
    is_owner: bool
    contractor: ContractorOut | None
    stages: list[StageOut]


class UpdatesOut(BaseModel):
    stage: StageOut
    updates: list[UpdateOut]


class DrawingOut(BaseModel):
    file_id: uuid.UUID
    title: str | None
    drawing_class: str | None
    floor: int | None
    sheet_no: str | None


class ProExecutionOut(BaseModel):
    engagement_id: uuid.UUID
    project_id: uuid.UUID
    project_code: str
    build_plan_version_no: int | None
    drawings: list[DrawingOut]
    stages: list[StageOut]


class OpsExecutionOut(BaseModel):
    project_id: uuid.UUID
    project_code: str
    contractor: ContractorOut | None
    stages: list[StageOut]


class OpsWaitingOut(BaseModel):
    """A completion request waiting for a decision; `exception` once it has waited longer than
    the configured number of days (EX-12). No reminder is sent."""

    project_id: uuid.UUID
    project_code: str
    stage: StageOut
    exception: bool


class OpsExecutionQueueOut(BaseModel):
    exception_days: int
    waiting: list[OpsWaitingOut]
