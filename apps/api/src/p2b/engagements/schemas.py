"""Engagements API contracts (Slice 3.4). Requests refuse unknown fields. A professional's view
of a request carries no family identity until they accept (N-08); a family's view of a decline
carries no reason (N-06)."""

import re
import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from p2b.core.vocabulary import (
    ConnectionState,
    DeclineReason,
    EngagementOrigin,
    EngagementParty,
    EngagementState,
    FileState,
    NeedSource,
    NeedState,
    PackageAvailability,
    PackageState,
    QuoteReviewState,
    WithdrawReason,
)

PHONE_CHARS = re.compile(r"^\+?[0-9 ()-]+$")


def _phone(value: str) -> str:
    value = value.strip()
    digits = sum(ch.isdigit() for ch in value)
    if not PHONE_CHARS.match(value) or not 10 <= digits <= 15:
        raise ValueError("Enter a phone number with 10 to 15 digits.")
    return value


def _text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("This is required.")
    return value


Phone = Annotated[str, Field(max_length=24), AfterValidator(_phone)]
Name = Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_text)]
Reason = Annotated[str, Field(min_length=1, max_length=1000), AfterValidator(_text)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- requests ------------------------------------------------------------------------------


class NeedIn(Strict):
    state: NeedState
    subtypes: list[Annotated[str, Field(max_length=40)]] = Field(
        default_factory=list, max_length=10
    )


class ConnectionIn(Strict):
    category: str = Field(max_length=40)
    profile_id: uuid.UUID
    contact_name: Name
    contact_phone: Phone
    site_address: Annotated[str, Field(max_length=300)] | None = Field(
        default=None, description="Shown to the professional only after they accept"
    )


class OutsideIn(Strict):
    category: str = Field(max_length=40)
    name: Name
    firm: Annotated[str, Field(max_length=160)] | None = None
    contact: Annotated[str, Field(max_length=200)] | None = None


class ReasonIn(Strict):
    reason: Reason


class ShareIn(Strict):
    file_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)


class AcceptIn(Strict):
    phone: Phone | None = Field(default=None, description="Shown to the family with your email")


class DeclineIn(Strict):
    reason: DeclineReason
    note: Annotated[str, Field(max_length=1000)] | None = Field(
        default=None, description="Required for OTHER; never shown to the family"
    )


class QuoteReviewIn(Strict):
    category: str = Field(max_length=40)
    quoted_by: Name
    note: Annotated[str, Field(max_length=1000)] | None = None
    file_ids: list[uuid.UUID] = Field(min_length=1, max_length=5)


class UploadIn(Strict):
    file_name: str = Field(min_length=1, max_length=200)
    content_type: str = Field(max_length=100)
    size_bytes: int = Field(gt=0)


# --- shared pieces -------------------------------------------------------------------------


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


class BriefOut(BaseModel):
    """What a professional sees before accepting: no name, phone, email, address, pin or file."""

    category: str
    subtypes: list[str]
    locality: str | None
    plot_area_sqft: str | None
    built_up_area_sqft: int | None
    floors: int | None
    basement: bool | None
    budget_band: str | None
    start_window: str | None
    services: list[str]


class ProfessionalContactOut(BaseModel):
    name: str | None
    firm: str | None
    phone: str | None
    email: str | None


class FamilyContactOut(BaseModel):
    name: str
    phone: str
    email: str | None
    site_address: str | None


class PointOut(BaseModel):
    lat: float
    lng: float


class ProEngagementOut(BaseModel):
    """A professional's engagement, whatever its origin (ADR-024): the family's contact, and the
    plot pin and shared files while it is ACTIVE (N-08)."""

    id: uuid.UUID
    project_code: str
    category: str
    category_name: str
    origin: EngagementOrigin
    state: EngagementState
    started_at: datetime
    ended_at: datetime | None
    family_contact: FamilyContactOut | None
    location: PointOut | None
    shared_files: list[FileOut]


# --- the family ----------------------------------------------------------------------------


class FamilyConnectionOut(BaseModel):
    id: uuid.UUID
    profile_id: uuid.UUID
    professional_name: str | None
    firm_name: str | None
    state: ConnectionState
    sent_at: datetime
    respond_by: datetime
    responded_at: datetime | None
    withdraw_reason: WithdrawReason | None
    professional_contact: ProfessionalContactOut | None = Field(
        description="Only once the professional accepted"
    )


class FamilyEngagementOut(BaseModel):
    id: uuid.UUID
    party: EngagementParty
    state: EngagementState
    started_at: datetime
    ended_at: datetime | None
    profile_id: uuid.UUID | None
    name: str | None
    firm: str | None
    contact: str | None = Field(description="An outside professional's contact as recorded")
    professional_contact: ProfessionalContactOut | None
    shared_file_ids: list[uuid.UUID]


class CategoryServiceOut(BaseModel):
    code: str
    name: str
    subtypes: dict[str, str]
    need: NeedState
    need_source: NeedSource
    chosen_subtypes: list[str]
    open_requests: int
    open_limit: int
    engagement: FamilyEngagementOut | None
    connections: list[FamilyConnectionOut]
    past_engagements: list[FamilyEngagementOut]


class QuoteReviewOut(BaseModel):
    id: uuid.UUID
    category: str
    quoted_by: str
    note: str | None
    files: list[FileOut]
    state: QuoteReviewState
    submitted_at: datetime


class ServicesOut(BaseModel):
    project_id: uuid.UUID
    project_code: str
    availability: PackageAvailability
    package_state: PackageState
    can_act: bool = Field(description="The caller is the owner and the project is eligible")
    has_contractor: bool | None
    response_hours: int
    categories: list[CategoryServiceOut]
    requirement_files: list[FileOut]
    quote_reviews: list[QuoteReviewOut]


class ConnectionTargetOut(BaseModel):
    """What the request screen needs: the professional, the category and whether a request
    can be sent now, with the reason when not."""

    project_id: uuid.UUID
    project_code: str
    category: str
    category_name: str
    profile_id: uuid.UUID
    professional_name: str | None
    firm_name: str | None
    package_state: PackageState
    blocked: str | None = Field(description="Why a request cannot be sent now, else null")
    open_requests: int
    open_limit: int
    response_hours: int
    contact_name: str | None


# --- the professional ----------------------------------------------------------------------


class ProConnectionOut(BaseModel):
    id: uuid.UUID
    category: str
    category_name: str
    state: ConnectionState
    sent_at: datetime
    respond_by: datetime
    responded_at: datetime | None
    brief: BriefOut
    decline_reason: DeclineReason | None
    decline_note: str | None
    withdraw_reason: WithdrawReason | None
    family_contact: FamilyContactOut | None = Field(description="Only after you accepted")
    location: PointOut | None = Field(description="The plot pin, while the engagement is active")
    engagement_id: uuid.UUID | None = Field(
        description="The engagement this request became once you accepted; its workspace is "
        "/pro/engagements/{engagement_id}"
    )
    engagement_state: EngagementState | None
    shared_files: list[FileOut]


class ProConnectionsOut(BaseModel):
    items: list[ProConnectionOut]


# --- operations ----------------------------------------------------------------------------


class OpsNeedOut(BaseModel):
    category: str
    state: NeedState
    source: NeedSource
    subtypes: list[str]


class OpsConnectionOut(BaseModel):
    id: uuid.UUID
    category: str
    profile_id: uuid.UUID
    professional_name: str | None
    state: ConnectionState
    sent_at: datetime
    respond_by: datetime
    responded_at: datetime | None
    decline_reason: DeclineReason | None
    decline_note: str | None
    withdraw_reason: WithdrawReason | None
    withdrawn_by_role: str | None
    withdraw_note: str | None
    family_contact: dict[str, Any]
    professional_contact: dict[str, Any] | None


class OpsEngagementOut(BaseModel):
    id: uuid.UUID
    category: str
    party: EngagementParty
    state: EngagementState
    profile_id: uuid.UUID | None
    name: str | None
    firm: str | None
    contact: str | None
    started_at: datetime
    ended_at: datetime | None
    ended_by_role: str | None
    end_reason: str | None
    shared_file_ids: list[uuid.UUID]


class OpsHistoryOut(BaseModel):
    subject: str
    subject_id: uuid.UUID
    category: str
    from_state: str | None
    to_state: str
    actor_role: str
    reason: str | None
    at: datetime


class OpsQuoteReviewOut(BaseModel):
    id: uuid.UUID
    category: str
    quoted_by: str
    note: str | None
    file_ids: list[uuid.UUID]
    state: QuoteReviewState
    submitted_at: datetime


class OpsEngagementsOut(BaseModel):
    project_id: uuid.UUID
    needs: list[OpsNeedOut]
    connections: list[OpsConnectionOut]
    engagements: list[OpsEngagementOut]
    quote_reviews: list[OpsQuoteReviewOut]
    history: list[OpsHistoryOut]
