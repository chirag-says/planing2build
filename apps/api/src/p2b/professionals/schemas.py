import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from p2b.core.vocabulary import (
    CheckKind,
    CheckOutcome,
    FilePurpose,
    FileState,
    ListingState,
    PortfolioReviewState,
    ProfessionalDocumentKind,
    RequirementLevel,
)


class CategoryOut(BaseModel):
    code: str
    name: str
    parent_code: str | None


class PointIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class ProfileUpdateIn(BaseModel):
    """Only the fields sent are changed."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=120)
    firm_name: str | None = Field(default=None, max_length=160)
    bio: str | None = Field(default=None, max_length=2000)
    years_experience: int | None = Field(default=None, ge=0, le=80)
    team_size: int | None = Field(default=None, ge=1, le=10000)
    base_locality: str | None = Field(default=None, max_length=120)
    base_point: PointIn | None = None
    service_radius_km: int | None = Field(default=None, ge=1, le=300)


class OwnProfileOut(BaseModel):
    profile_id: uuid.UUID
    display_name: str | None
    firm_name: str | None
    bio: str | None
    years_experience: int | None
    team_size: int | None
    base_locality: str | None
    base_point: PointIn | None
    service_radius_km: int | None
    missing: list[str] = Field(description="Profile fields still needed before submitting")
    names_locked: bool


class RequirementOut(BaseModel):
    id: str
    label: str
    accepts: list[CheckKind]
    level: RequirementLevel
    count: int
    provided: int = Field(description="What the professional has supplied toward it")


class OwnCategoryOut(BaseModel):
    code: str
    name: str
    subtypes: list[str]
    listing_state: ListingState
    hidden: bool
    public: bool
    message: str | None = Field(description="What Plan2Build told you with its last decision")
    submitted_at: datetime | None
    listed_at: datetime | None
    review_due_at: datetime | None
    reapply_after: datetime | None
    requirements: list[RequirementOut]
    missing_requirements: list[str]


class FileOut(BaseModel):
    file_id: uuid.UUID
    file_name: str
    content_type: str
    size_bytes: int
    state: FileState


class DocumentOut(BaseModel):
    document_id: uuid.UUID
    kind: ProfessionalDocumentKind
    category_code: str | None
    details: dict[str, str]
    file: FileOut | None


class ReferenceOut(BaseModel):
    reference_id: uuid.UUID
    category_code: str
    name: str
    phone: str
    project_note: str


class PortfolioOut(BaseModel):
    item_id: uuid.UUID
    caption: str
    review_state: PortfolioReviewState
    file: FileOut | None


class OwnDashboardOut(BaseModel):
    profile: OwnProfileOut
    categories: list[OwnCategoryOut]
    documents: list[DocumentOut]
    references: list[ReferenceOut]
    portfolio: list[PortfolioOut]
    available_categories: list[CategoryOut]


class AddCategoryIn(BaseModel):
    category: str = Field(max_length=40)
    subtypes: list[str] = Field(default_factory=list, max_length=20)


class SubtypesIn(BaseModel):
    subtypes: list[str] = Field(default_factory=list, max_length=20)


class UploadIn(BaseModel):
    purpose: Literal[FilePurpose.VERIFICATION_EVIDENCE, FilePurpose.PORTFOLIO]
    file_name: str = Field(min_length=1, max_length=200)
    content_type: str = Field(max_length=100)
    size_bytes: int = Field(gt=0)


class UploadTicketOut(BaseModel):
    file: FileOut
    upload_url: str
    headers: dict[str, str]


class DocumentIn(BaseModel):
    kind: ProfessionalDocumentKind
    file_id: uuid.UUID
    category_code: str | None = Field(default=None, max_length=40)
    issuer: str = Field(default="", max_length=120, description="Issuing body (registration)")
    number: str = Field(default="", max_length=60, description="Registration or licence number")
    gstin: str = Field(default="", max_length=20, description="GSTIN (business), where registered")


class ReferenceIn(BaseModel):
    category_code: str = Field(max_length=40)
    name: str = Field(max_length=120)
    phone: str = Field(max_length=20)
    project_note: str = Field(max_length=300)


class PortfolioIn(BaseModel):
    file_id: uuid.UUID
    caption: str = Field(max_length=200)


class DownloadOut(BaseModel):
    url: str


# --- public ---


class PublicCategoryOut(BaseModel):
    code: str
    name: str
    subtypes: list[str]
    verified: list[CheckKind] = Field(description="Checks Plan2Build passed when approving")
    registrations: list[dict[str, str]] = Field(description="Issuer and number, when verified")


class PortfolioImageOut(BaseModel):
    caption: str
    image_url: str | None


class DirectoryCardOut(BaseModel):
    profile_id: uuid.UUID
    display_name: str | None
    firm_name: str | None
    base_locality: str | None
    service_radius_km: int | None
    years_experience: int | None
    team_size: int | None
    categories: list[PublicCategoryOut]
    cover_image_url: str | None


class DirectoryPageOut(BaseModel):
    items: list[DirectoryCardOut]
    next_cursor: str | None
    order: Literal["daily_shuffle"] = Field(
        default="daily_shuffle",
        description="Neutral order that changes daily (D-08); never a ranking or recommendation",
    )


class PublicProfileOut(DirectoryCardOut):
    bio: str | None
    portfolio: list[PortfolioImageOut]


# --- operations ---


class CreateProfessionalIn(BaseModel):
    email: str = Field(max_length=320)
    display_name: str = Field(default="", max_length=120)


class CreatedProfessionalOut(BaseModel):
    user_id: uuid.UUID
    profile_id: uuid.UUID
    created: bool


class CheckIn(BaseModel):
    kind: CheckKind
    subject: str = Field(min_length=1, max_length=80)
    outcome: CheckOutcome
    detail: dict[str, str] = Field(default_factory=dict, max_length=10)
    note: str | None = Field(default=None, max_length=2000)


class DecisionIn(BaseModel):
    message: str | None = Field(default=None, max_length=2000)
    note: str | None = Field(default=None, max_length=2000)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class CheckOut(BaseModel):
    kind: CheckKind
    subject: str
    outcome: CheckOutcome
    detail: dict[str, str]
    internal_note: str | None
    recorded_by_email: str | None
    recorded_at: datetime


class HistoryOut(BaseModel):
    event: str
    from_state: ListingState | None
    to_state: ListingState
    actor_email: str | None
    actor_role: str
    reason: str | None
    at: datetime


class ReviewItemOut(BaseModel):
    item_id: uuid.UUID
    state: str
    claimed_by_me: bool
    claimed_by_email: str | None


class ReviewDetailOut(BaseModel):
    category_id: uuid.UUID
    category_code: str
    category_name: str
    subtypes: list[str]
    listing_state: ListingState
    hidden: bool
    review_due_at: datetime | None
    profile: OwnProfileOut
    email: str | None
    requirements: list[RequirementOut]
    unmet: list[str]
    case_open: bool
    case_decision: str | None
    checks: list[CheckOut]
    documents: list[DocumentOut]
    references: list[ReferenceOut]
    portfolio: list[PortfolioOut]
    history: list[HistoryOut]
    queue_item: ReviewItemOut | None


class ReviewQueueEntryOut(BaseModel):
    item_id: uuid.UUID | None = Field(description="The open review item, when there is one")
    category_id: uuid.UUID
    display_name: str | None
    firm_name: str | None
    category_code: str
    listing_state: ListingState
    submitted_at: datetime | None
    claimed_by_me: bool
    claimed: bool


class ReviewQueueOut(BaseModel):
    entries: list[ReviewQueueEntryOut]
    next_cursor: str | None
