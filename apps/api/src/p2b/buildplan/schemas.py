"""Build Plan API contracts (Slice 3.5). Requests refuse unknown fields. Snapshots mirror
`views.snapshot`; the RFQ manifest has no rate, amount or rate card (BP-08)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from p2b.core.vocabulary import (
    BuildPlanState,
    DesignRequestKind,
    DrawingClass,
    DrawingSetState,
    FilePurpose,
    FileState,
    PackageAvailability,
    PackageState,
    QuantityBasis,
    RateCardStatus,
    ValueApplicability,
    ValueBasis,
)


def _text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("This is required.")
    return value


Text = Annotated[str, Field(min_length=1, max_length=2000), AfterValidator(_text)]
Short = Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_text)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- requests --------------------------------------------------------------------------------


class ReasonIn(Strict):
    reason: Text


class DesignRequestIn(Strict):
    kind: DesignRequestKind
    engagement_id: uuid.UUID | None = None
    provider_name: Annotated[str, Field(max_length=160)] | None = None
    provider_qualification: Annotated[str, Field(max_length=200)] | None = None
    scope_note: Text
    reference_design_ids: list[uuid.UUID] = Field(
        default_factory=list, max_length=10,
        description="AI concepts named as illustrative references only; never drawings",
    )  # fmt: skip


class UploadIn(Strict):
    purpose: FilePurpose = FilePurpose.DRAWING
    file_name: str = Field(min_length=1, max_length=200)
    content_type: str = Field(max_length=100)
    size_bytes: int = Field(gt=0)


class DrawingFileIn(Strict):
    file_id: uuid.UUID
    drawing_class: DrawingClass
    floor: int | None = Field(default=None, ge=-1, le=3)
    title: Short
    sheet_no: Annotated[str, Field(max_length=40)] | None = None


class FamilyDecisionIn(Strict):
    approve: bool
    note: Annotated[str, Field(max_length=2000)] | None = None


class DrawingCheckIn(Strict):
    appointment_id: uuid.UUID
    approve: bool
    note: Text
    evidence_file_id: uuid.UUID | None = Field(
        default=None, description="The checker's signed note, when the checker has no account"
    )


class DrawingSetIdIn(Strict):
    set_id: uuid.UUID


class ValueIn(Strict):
    code: str = Field(min_length=3, max_length=3)
    applicability: ValueApplicability = ValueApplicability.APPLICABLE
    value_text: Annotated[str, Field(max_length=4000)] | None = None
    basis: ValueBasis | None = None
    source_note: Annotated[str, Field(max_length=2000)] | None = None
    not_applicable_reason: Annotated[str, Field(max_length=2000)] | None = None
    evidence_file_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class ValuesIn(Strict):
    values: list[ValueIn] = Field(min_length=1, max_length=100)


class BoqLineIn(Strict):
    item_code: str = Field(min_length=1, max_length=40)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    quantity_basis: QuantityBasis
    drawing_file_id: uuid.UUID | None = Field(
        default=None, description="A drawing file id (from the set's files) for measured lines"
    )
    basis_note: Annotated[str, Field(max_length=1000)] | None = None
    stage_number: int | None = Field(default=None, ge=1, le=16)
    floor: int | None = Field(default=None, ge=-1, le=3)
    spec_line_codes: list[Annotated[str, Field(min_length=3, max_length=3)]] = Field(
        default_factory=list, max_length=20
    )
    assumptions: Annotated[str, Field(max_length=1000)] | None = None


class BoqIn(Strict):
    rate_card_id: uuid.UUID
    lines: list[BoqLineIn] = Field(min_length=1, max_length=3000)


class ScheduleEntryIn(Strict):
    entry_key: str = Field(min_length=3, max_length=8)
    duration_days: int | None = Field(default=None, ge=1, le=3650)
    predecessors: list[str] = Field(default_factory=list, max_length=40)
    note: Annotated[str, Field(max_length=500)] | None = None


class ScheduleIn(Strict):
    entries: list[ScheduleEntryIn] = Field(min_length=1, max_length=200)


class ScopeIn(Strict):
    inclusions: list[Annotated[str, Field(max_length=1000)]] = Field(max_length=100)
    exclusions: list[Annotated[str, Field(max_length=1000)]] = Field(max_length=100)
    assumptions: list[Annotated[str, Field(max_length=1000)]] = Field(max_length=100)
    explanation_note: Annotated[str, Field(max_length=4000)] | None = None


class SignDocumentIn(Strict):
    line_codes: list[str] = Field(min_length=1, max_length=20)
    engineer_name: Short
    engineer_firm: Annotated[str, Field(max_length=160)] | None = None
    registration_number: Short
    registration_issuer: Short
    credential_file_id: uuid.UUID
    evidence_file_id: uuid.UUID
    attestation: Text


class SignCodeIn(Strict):
    line_codes: list[str] = Field(min_length=1, max_length=20)


class SignIn(Strict):
    line_codes: list[str] = Field(min_length=1, max_length=20)
    challenge_id: uuid.UUID
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


class BuildPlanAcceptIn(Strict):
    challenge_id: uuid.UUID
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


class RateCardIn(Strict):
    geography: Short
    effective_from: date
    effective_to: date | None = None
    source_reference: Text
    note: Annotated[str, Field(max_length=2000)] | None = None
    is_demo: bool = Field(default=False, description="Development values; refused in production")


class RateLineIn(Strict):
    item_code: str = Field(min_length=1, max_length=40)
    description: Short
    unit: str = Field(min_length=1, max_length=20)
    rate: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class RateLinesIn(Strict):
    lines: list[RateLineIn] = Field(min_length=1, max_length=2000)


class CheckerIn(Strict):
    name: Short
    qualification: Short
    registration_reference: Annotated[str, Field(max_length=200)] | None = None
    user_id: uuid.UUID | None = None


class StatementIn(Strict):
    text: Text
    note: Text


# --- responses -------------------------------------------------------------------------------


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


class DrawingFileOut(BaseModel):
    id: uuid.UUID
    file_id: uuid.UUID
    drawing_class: DrawingClass
    floor: int | None
    title: str
    sheet_no: str | None
    sha256: str | None
    file_name: str
    file_state: FileState


class DrawingSetOut(BaseModel):
    id: uuid.UUID
    set_no: int
    state: DrawingSetState
    content_hash: str | None
    submitted_at: datetime | None
    family_note: str | None
    checker_name: str | None
    checked_at: datetime | None
    check_note: str | None
    files: list[DrawingFileOut]


class DesignRequestOut(BaseModel):
    id: uuid.UUID
    kind: DesignRequestKind
    engagement_id: uuid.UUID | None
    provider_name: str | None
    provider_qualification: str | None
    scope_note: str
    reference_design_ids: list[uuid.UUID]
    opened_at: datetime
    can_provide: bool
    sets: list[DrawingSetOut]


class VersionSummaryOut(BaseModel):
    id: uuid.UUID
    version_no: int
    state: BuildPlanState
    content_hash: str | None
    issued_at: datetime | None
    accepted_at: datetime | None
    closed_at: datetime | None
    close_reason: str | None
    issued_document_id: uuid.UUID | None
    accepted_document_id: uuid.UUID | None


class FamilyBuildPlanOut(BaseModel):
    project_id: uuid.UUID
    project_code: str
    availability: PackageAvailability
    package_state: PackageState
    can_act: bool
    accepted_version_id: uuid.UUID | None
    design_requests: list[DesignRequestOut]
    versions: list[VersionSummaryOut]


class SnapshotProjectOut(BaseModel):
    id: uuid.UUID
    code: str
    locality: str | None


class SnapshotVersionOut(BaseModel):
    id: uuid.UUID
    version_no: int
    state: BuildPlanState
    content_hash: str | None
    requirement_version: int
    submitted_at: str | None
    issued_at: str | None
    accepted_at: str | None
    closed_at: str | None
    close_reason: str | None


class SnapshotFileOut(BaseModel):
    id: uuid.UUID
    file_id: uuid.UUID
    drawing_class: DrawingClass
    floor: int | None
    title: str
    sheet_no: str | None
    sha256: str | None


class SnapshotCheckerOut(BaseModel):
    name: str
    qualification: str


class SnapshotSetOut(BaseModel):
    id: uuid.UUID
    set_no: int
    state: DrawingSetState
    content_hash: str | None
    request_kind: DesignRequestKind
    provider_name: str | None
    checker: SnapshotCheckerOut | None
    checked_at: str | None
    files: list[SnapshotFileOut]


class SnapshotValueOut(BaseModel):
    code: str
    group: str
    item: str
    criteria: str
    applicability: ValueApplicability
    value: str | None
    basis: ValueBasis | None
    not_applicable_reason: str | None
    source_note: str | None
    is_structural: bool


class SnapshotCardOut(BaseModel):
    id: uuid.UUID
    geography: str
    version: int
    is_demo: bool
    status: RateCardStatus


class SnapshotBoqOut(BaseModel):
    line_no: int
    item_code: str
    description: str
    unit: str
    quantity: str
    rate: str
    amount: str
    quantity_basis: QuantityBasis
    drawing_file_id: uuid.UUID | None
    basis_note: str | None
    stage_number: int | None
    floor: int | None
    spec_line_codes: list[str]
    assumptions: str | None


class SnapshotScheduleOut(BaseModel):
    entry_key: str
    stage_number: int
    stage_name: str
    floor: int | None
    duration_days: int | None
    predecessors: list[str]
    note: str | None
    planned_start: date | None = Field(description="Not calculated while BP-07A is deferred")
    planned_end: date | None = Field(description="Not calculated while BP-07A is deferred")


class SnapshotScopeOut(BaseModel):
    inclusions: list[str]
    exclusions: list[str]
    assumptions: list[str]
    explanation_note: str | None


class SnapshotSignoffOut(BaseModel):
    id: uuid.UUID
    line_code: str
    state: str
    mode: str
    signer_kind: str
    engineer_name: str
    engineer_firm: str | None
    registration_number: str | None
    registration_issuer: str | None
    category: str
    statement_version: int
    content_hash: str
    drawing_hashes: list[str]
    signed_at: str | None
    void_reason: str | None


class SnapshotHistoryOut(BaseModel):
    version_no: int
    state: BuildPlanState
    issued_at: str | None
    closed_at: str | None
    close_reason: str | None


class SnapshotAcceptanceOut(BaseModel):
    accepted_at: str | None
    content_hash: str
    issued_document_sha256: str
    statement: str
    statement_version: int


class SnapshotOut(BaseModel):
    project: SnapshotProjectOut
    version: SnapshotVersionOut
    drawing_set: SnapshotSetOut | None
    values: list[SnapshotValueOut]
    rate_card: SnapshotCardOut | None
    boq: list[SnapshotBoqOut]
    boq_total: str
    stage_totals: dict[str, str]
    schedule: list[SnapshotScheduleOut]
    dates_status: str
    scope: SnapshotScopeOut
    signoffs: list[SnapshotSignoffOut]
    statements: dict[str, str]
    unsigned_structural_lines: list[str]
    history: list[SnapshotHistoryOut]
    acceptance: SnapshotAcceptanceOut | None


class OpsVersionOut(BaseModel):
    snapshot: SnapshotOut
    missing: list[str] = Field(description="What submit still needs (DRAFT only)")
    last_edited_by: uuid.UUID
    issued_document_id: uuid.UUID | None
    accepted_document_id: uuid.UUID | None


class EventOut(BaseModel):
    subject: str
    subject_id: uuid.UUID
    from_state: str | None
    to_state: str
    actor_role: str
    reason: str | None
    at: datetime


class OpsBuildPlanOut(BaseModel):
    project_id: uuid.UUID
    project_code: str
    package_state: PackageState
    accepted_version_id: uuid.UUID | None
    design_requests: list[DesignRequestOut]
    versions: list[VersionSummaryOut]
    history: list[EventOut]


class RateLineOut(BaseModel):
    item_code: str
    description: str
    unit: str
    rate: Decimal


class RateCardOut(BaseModel):
    id: uuid.UUID
    geography: str
    version: int
    status: RateCardStatus
    is_demo: bool
    effective_from: date
    effective_to: date | None
    source_reference: str
    note: str | None
    lines: list[RateLineOut]


class CheckerOut(BaseModel):
    id: uuid.UUID
    name: str
    qualification: str
    registration_reference: str | None
    user_id: uuid.UUID | None
    appointed_at: datetime


class StatementOut(BaseModel):
    id: uuid.UUID
    version: int
    text: str
    status: str
    note: str


class ManifestDrawingOut(BaseModel):
    file_id: uuid.UUID
    drawing_class: DrawingClass
    floor: int | None
    title: str
    sheet_no: str | None
    sha256: str | None


class ManifestSpecOut(BaseModel):
    code: str
    item: str
    criteria: str
    applicability: ValueApplicability
    value: str | None
    not_applicable_reason: str | None


class ManifestQuantityOut(BaseModel):
    line_no: int
    item_code: str
    description: str
    unit: str
    quantity: str
    stage_number: int | None
    floor: int | None
    spec_line_codes: list[str]
    assumptions: str | None


class ManifestScheduleOut(BaseModel):
    entry_key: str
    stage_number: int
    stage_name: str
    floor: int | None
    duration_days: int | None
    predecessors: list[str]


class ManifestScopeOut(BaseModel):
    inclusions: list[str]
    exclusions: list[str]
    assumptions: list[str]


class QuoteFormatOut(BaseModel):
    version: int
    price_per_quantity_line: bool
    explicit_exclusions_per_line: bool
    contractor_schedule: bool


class RfqManifestOut(BaseModel):
    """BP-08: for contractor RFQs; never Plan2Build's rates or amounts."""

    model_config = ConfigDict(extra="forbid")

    build_plan_version_id: uuid.UUID
    version_no: int
    content_hash: str
    accepted_at: str | None
    project_code: str
    drawings: list[ManifestDrawingOut]
    drawing_set_hash: str | None
    specifications: list[ManifestSpecOut]
    quantities: list[ManifestQuantityOut]
    schedule: list[ManifestScheduleOut]
    dates_status: str
    scope: ManifestScopeOut
    quote_format: QuoteFormatOut


class SignoffLineOut(BaseModel):
    code: str
    item: str
    criteria: str
    applicability: ValueApplicability
    value: str | None
    basis: ValueBasis | None
    not_applicable_reason: str | None
    signed: bool


class ProSignoffOut(BaseModel):
    version_id: uuid.UUID
    project_code: str
    version_no: int
    state: BuildPlanState
    content_hash: str | None
    verified: bool = Field(description="A verified registration and an ACTIVE engagement here")
    statement_version: int | None
    statement_text: str | None
    lines: list[SignoffLineOut]
    drawings: list[DrawingFileOut]
    my_signoffs: list[SnapshotSignoffOut]


class ProSignoffListOut(BaseModel):
    items: list[ProSignoffOut]


class ProDesignRequestOut(BaseModel):
    project_id: uuid.UUID
    project_code: str
    request: DesignRequestOut


class ProDesignRequestsOut(BaseModel):
    items: list[ProDesignRequestOut]
