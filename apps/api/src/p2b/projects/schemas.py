import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from p2b.core.vocabulary import (
    ComingSoonWork,
    EngineerSignoff,
    EnquiryKind,
    EstimateStatus,
    EstimateUnavailableReason,
    FinishLevel,
    GateStatus,
    PackageAvailability,
    PackageState,
    ProjectStatus,
    ProjectType,
    SpecLineState,
    StageState,
)


class ProjectCreateRequest(BaseModel):
    city: str = Field(min_length=1, max_length=80)
    project_type: ProjectType = ProjectType.NEW_HOME


class ProjectSummary(BaseModel):
    project_id: uuid.UUID
    code: str
    status: ProjectStatus
    city_code: str
    locality: str | None
    created_at: datetime
    submitted_at: datetime | None


class RequirementView(BaseModel):
    """The homeowner's own answers. Review flags are for operations and are not shown here."""

    question_set_version: int
    answers: dict[str, Any]
    version: int
    submitted_at: datetime | None


class ReviewMessageOut(BaseModel):
    """What Plan2Build told the family: the information asked for, or why the project was
    cancelled. Only while the project is in that status; never an internal note or flag."""

    status: ProjectStatus
    message: str
    at: datetime


class PackageOfferOut(BaseModel):
    """Whether the one Plan2Build package can be offered on this project (PD-21), and its state
    (L-05). ELIGIBLE means the project passed the initial service-eligibility review, nothing
    more. `purchasable` when eligible, no package is active and a complete offer is published;
    the price is the billing module's (GET /projects/{id}/package)."""

    availability: PackageAvailability
    state: PackageState
    purchasable: bool


class ProjectDetail(BaseModel):
    project: ProjectSummary
    requirement: RequirementView
    review_message: ReviewMessageOut | None = None
    package: PackageOfferOut


class RequirementSaveRequest(BaseModel):
    answers: dict[str, Any]
    version: int


class RequirementSubmitRequest(BaseModel):
    version: int


class EnquiryRequest(BaseModel):
    kind: EnquiryKind
    email: EmailStr = Field(max_length=320)
    work_type: ComingSoonWork | None = None


class EnquiryAccepted(BaseModel):
    received: bool = True


class LocalitySuggestion(BaseModel):
    locality: str | None


class WorkspaceStageOut(BaseModel):
    stage_number: int
    name: str
    floor: int | None = Field(
        description="-1 basement, 0 ground, 1 to 3 above; null if not per floor"
    )
    state: StageState
    is_gate: bool
    gate_status: GateStatus | None
    planned_start: date | None = Field(description="Null until an approved schedule exists")
    planned_end: date | None


class WorkspaceLineOut(BaseModel):
    code: str
    item: str
    state: SpecLineState
    is_long_lead: bool
    is_structural: bool
    engineer_signoff: EngineerSignoff = Field(
        description="PENDING on every structural line until an engineer signs it (ruling 2.4)"
    )
    performance_specification: str | None = Field(
        description="The line's criteria from the master; null unless `criteria_visible`"
    )


class WorkspaceGroupOut(BaseModel):
    """Specification group A, B or C: grouping and timing only, never a product (PD-09)."""

    code: str
    name: str
    issued: str
    lines: list[WorkspaceLineOut]


class WorkspaceOut(BaseModel):
    project: ProjectSummary
    stages: list[WorkspaceStageOut]
    groups: list[WorkspaceGroupOut]
    criteria_visible: bool = Field(
        description="True once the package is active, or earlier if the F-09 setting allows it"
    )


class EstimateInputsOut(BaseModel):
    city: str
    built_up_area_sqft: int | None
    floors: int | None
    finish_level: FinishLevel | None


class EstimateStageOut(BaseModel):
    stage_number: int
    stage_name: str | None
    share_pct: Decimal
    amount: Decimal


class EstimateRateCardOut(BaseModel):
    city: str
    version: int
    is_demo: bool
    label: str


class EstimateFiguresOut(BaseModel):
    total_low: Decimal
    total_high: Decimal
    total_mid: Decimal
    per_sqft_low: Decimal
    per_sqft_high: Decimal
    duration_months: int
    stages: list[EstimateStageOut]
    rate_card: EstimateRateCardOut


class ProjectEstimateOut(BaseModel):
    """The indicative construction estimate of the latest submission (PD-04): never a quote and
    never the package fee."""

    status: EstimateStatus
    unavailable_reason: EstimateUnavailableReason | None
    created_at: datetime
    inputs: EstimateInputsOut
    figures: EstimateFiguresOut | None
