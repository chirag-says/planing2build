"""Assurance API contracts (Slice 3.7B). Requests refuse unknown fields. One response model per
audience (SECURITY 4.2): the auditor's models have no supplier, brand, product, price or
homeowner contact field (F.3); the homeowner and the contractor see an inspection's content only
once it is approved."""

import uuid
from datetime import date, datetime
from typing import Annotated, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from p2b.core.vocabulary import (
    AppointmentStatus,
    ChecklistStatus,
    CheckpointResult,
    FileState,
    InspectionKind,
    InspectionState,
    NcState,
    Severity,
)


def _text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("This is required.")
    return value


def _optional(value: str | None) -> str | None:
    return (value.strip() or None) if value is not None else None


Text = Annotated[str, Field(min_length=1, max_length=2000), AfterValidator(_text)]
Short = Annotated[str, Field(min_length=1, max_length=300), AfterValidator(_text)]
OptionalText = Annotated[str | None, Field(max_length=2000), AfterValidator(_optional)]
OptionalShort = Annotated[str | None, Field(max_length=200), AfterValidator(_optional)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- requests ------------------------------------------------------------------------------


class ScheduleIn(Strict):
    appointment_id: uuid.UUID
    visit_note: OptionalText = None
    amends_id: uuid.UUID | None = Field(
        default=None, description="A RETURNED inspection it replaces"
    )


class ReinspectionIn(Strict):
    nc_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    appointment_id: uuid.UUID
    visit_note: OptionalText = None


class ResultIn(Strict):
    checkpoint_id: uuid.UUID
    result: CheckpointResult
    note: OptionalText = None
    na_reason: OptionalText = None
    measurement: OptionalShort = None
    room_tag: Annotated[str | None, Field(max_length=80), AfterValidator(_optional)] = None
    file_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    severity: Severity | None = None
    description: OptionalText = None
    corrective_action: OptionalText = None
    due_date: date | None = None


class ResultsIn(Strict):
    results: list[ResultIn] = Field(min_length=1, max_length=200)


class SubmitIn(Strict):
    summary: OptionalText = None
    challenge_id: uuid.UUID
    code: Annotated[str, Field(min_length=4, max_length=10)]


class CaptureIn(Strict):
    """Operations enter the auditor's signed report (no account, F.3)."""

    results: list[ResultIn] = Field(min_length=1, max_length=200)
    summary: OptionalText = None
    evidence_file_id: uuid.UUID


class ReasonIn(Strict):
    reason: Text


class RectifyIn(Strict):
    note: Text
    file_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)


class OpsRectifyIn(RectifyIn):
    reason: Text


class DueDateIn(Strict):
    due_date: date
    reason: Text


class TestResultIn(Strict):
    test_kind: Short
    value: Text
    file_id: uuid.UUID | None = None


class AppointmentIn(Strict):
    name: Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_text)]
    qualification: Short
    registration_reference: Annotated[str | None, Field(max_length=120)] = None
    credential_file_id: uuid.UUID | None = None
    account_email: Annotated[str | None, Field(max_length=254)] = Field(
        default=None, description="Links a professionals-host account (optional, EX-09)"
    )


class ChecklistDraftIn(Strict):
    from_version_id: uuid.UUID | None = None
    note: Text


class CheckpointIn(Strict):
    gate: int = Field(ge=1, le=6)
    sequence: int = Field(ge=1, le=999)
    code: Annotated[str, Field(min_length=1, max_length=20), AfterValidator(_text)]
    text: Text
    expected_evidence: OptionalShort = None
    is_critical: bool = False
    spec_line_code: Annotated[str | None, Field(min_length=3, max_length=3)] = None


class CheckpointsIn(Strict):
    checkpoints: list[CheckpointIn] = Field(max_length=500)


class EvidenceUploadIn(Strict):
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


class ChallengeOut(BaseModel):
    challenge_id: uuid.UUID
    sent_to: str
    expires_at: datetime


class CheckpointOut(BaseModel):
    id: uuid.UUID
    gate: int
    sequence: int
    code: str
    text: str
    expected_evidence: str | None
    is_critical: bool
    spec_line_code: str | None


class AuditorCheckpointOut(CheckpointOut):
    criteria: str | None = Field(description="The issued performance specification of the line")
    accepted_value: str | None = Field(
        description="The accepted Build Plan value, only for lines with no brand category"
    )


class ResultOut(BaseModel):
    id: uuid.UUID
    checkpoint_id: uuid.UUID
    result: CheckpointResult
    note: str | None
    na_reason: str | None
    measurement: str | None
    room_tag: str | None
    file_ids: list[uuid.UUID]
    severity: Severity | None
    description: str | None
    corrective_action: str | None
    due_date: date | None


class DrawingOut(BaseModel):
    file_id: uuid.UUID
    title: str | None
    drawing_class: str | None
    sheet_no: str | None


class StageRef(BaseModel):
    stage_instance_id: uuid.UUID
    stage_number: int
    stage_name: str
    floor: int | None
    gate: int


class AuditorInspectionSummary(StageRef):
    id: uuid.UUID
    project_code: str
    kind: InspectionKind
    state: InspectionState
    scheduled_at: datetime


class AuditorInspectionsOut(BaseModel):
    auditor_code: str
    items: list[AuditorInspectionSummary]


class AuditorInspectionOut(AuditorInspectionSummary):
    locality: str | None
    visit_note: str | None
    checklist_version: int
    checkpoints: list[AuditorCheckpointOut]
    results: list[ResultOut]
    drawings: list[DrawingOut]
    summary: str | None
    return_reason: str | None
    version: int


class ReportOut(BaseModel):
    version: int
    correction_reason: str | None
    rendered_at: datetime


class InspectionOut(StageRef):
    """What the homeowner and the contractor see: content only once approved."""

    id: uuid.UUID
    kind: InspectionKind
    state: InspectionState
    scheduled_at: datetime
    approved_at: datetime | None
    auditor_code: str | None
    outcome: str | None
    reports: list[ReportOut]


class FindingOut(StageRef):
    id: uuid.UUID
    severity: Severity
    description: str
    corrective_action: str
    due_date: date
    state: NcState
    overdue: bool
    closed_at: datetime | None


class AssuranceOut(BaseModel):
    inspections: list[InspectionOut]
    findings: list[FindingOut]


class AppointmentOut(BaseModel):
    id: uuid.UUID
    auditor_code: str
    name: str
    qualification: str
    registration_reference: str | None
    has_account: bool
    status: AppointmentStatus
    end_reason: str | None


class ChecklistOut(BaseModel):
    id: uuid.UUID
    version: int
    status: ChecklistStatus
    note: str
    published_at: datetime | None
    checkpoints: list[CheckpointOut]


class OpsInspectionOut(InspectionOut):
    project_id: uuid.UUID
    project_code: str
    appointment_id: uuid.UUID
    auditor_name: str
    checklist_version: int
    visit_note: str | None
    summary: str | None
    staff_capture: bool
    content_sha256: str | None
    return_reason: str | None
    cancel_reason: str | None
    amends_id: uuid.UUID | None
    reinspects_id: uuid.UUID | None
    nc_ids: list[uuid.UUID]
    checkpoints: list[CheckpointOut]
    results: list[ResultOut]
    version: int


class OpsInspectionsOut(BaseModel):
    project_id: uuid.UUID
    project_code: str
    inspections: list[OpsInspectionOut]
    findings: list[FindingOut]


class QueueStageOut(StageRef):
    project_id: uuid.UUID
    project_code: str


class QueueInspectionOut(QueueStageOut):
    inspection_id: uuid.UUID
    state: InspectionState
    scheduled_at: datetime
    exception: bool


class QueueFindingOut(QueueStageOut):
    nc_id: uuid.UUID
    state: NcState
    due_date: date
    overdue: bool


class AssuranceQueueOut(BaseModel):
    """EX-12 and EX-23: exceptions for operations only; nothing is sent to anyone."""

    inspection_open_days: int
    to_schedule: list[QueueStageOut]
    open_inspections: list[QueueInspectionOut]
    to_approve: list[QueueInspectionOut]
    rectified: list[QueueFindingOut]
    overdue: list[QueueFindingOut]
