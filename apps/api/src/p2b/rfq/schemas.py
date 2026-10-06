"""RFQ API contracts (Slice 3.6). Requests refuse unknown fields. One response model per audience
(SECURITY 4.2): the contractor's models have no field for Plan2Build's rates, adjustments,
review states, other contractors or the comparison; the homeowner's models carry no prices until
a comparison is published (QD-07); no model has a rank, score or recommendation (QD-10, QD-11)."""

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from p2b.core.vocabulary import (
    AdjustmentClarification,
    ClarificationDirection,
    ClarificationState,
    ComparisonState,
    DeclineReason,
    DeviationType,
    EngagementParty,
    FileState,
    InvitationSource,
    InvitationState,
    InvitationWithdrawReason,
    PackageState,
    QuoteCheckState,
    QuoteVersionKind,
    QuoteVersionState,
    RfqCancelReason,
    RfqState,
    TaxTreatment,
)

PHONE_CHARS = re.compile(r"^\+?[0-9 ()-]+$")


def _text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("This is required.")
    return value


def _phone(value: str) -> str:
    value = value.strip()
    digits = sum(ch.isdigit() for ch in value)
    if not PHONE_CHARS.match(value) or not 10 <= digits <= 15:
        raise ValueError("Enter a phone number with 10 to 15 digits.")
    return value


Text = Annotated[str, Field(min_length=1, max_length=2000), AfterValidator(_text)]
Short = Annotated[str, Field(min_length=1, max_length=500), AfterValidator(_text)]
Phone = Annotated[str, Field(max_length=24), AfterValidator(_phone)]
Name = Annotated[str, Field(min_length=1, max_length=120), AfterValidator(_text)]
Money = Annotated[Decimal, Field(gt=0, le=Decimal("9999999999.99"), decimal_places=2)]
Impact = Annotated[
    Decimal, Field(ge=Decimal("-9999999999.99"), le=Decimal("9999999999.99"), decimal_places=2)
]
Quantity = Annotated[Decimal, Field(gt=0, le=Decimal("99999999999"), decimal_places=3)]
Days = Annotated[int, Field(ge=1, le=3650)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- requests ------------------------------------------------------------------------------


class RfqRequestIn(Strict):
    profile_ids: list[uuid.UUID] = Field(
        default_factory=list, max_length=10,
        description="Listed contractors the owner nominates (QD-03)",
    )  # fmt: skip


class CancelIn(Strict):
    note: Annotated[str, Field(max_length=1000)] | None = None


class ReasonIn(Strict):
    reason: Text


class DeadlineIn(Strict):
    quotes_due_at: datetime


class ExtendIn(Strict):
    quotes_due_at: datetime
    reason: Text


class IntroduceIn(Strict):
    profile_id: uuid.UUID
    reason: Text = Field(description="Why operations add this contractor (QD-03)")


class InvitationAcceptIn(Strict):
    phone: Phone | None = Field(
        default=None, description="Shown to the homeowner only if your quote is selected"
    )


class DeclineIn(Strict):
    reason: DeclineReason
    note: Annotated[str, Field(max_length=1000)] | None = Field(
        default=None, description="Required for OTHER; never shown to the homeowner"
    )


class QuoteLineIn(Strict):
    line_no: int = Field(ge=1)
    rate: Money | None = Field(default=None, description="Unit rate; the amount is computed")
    excluded: bool = False
    exclusion_reason: Short | None = None
    alternate_spec: Short | None = None


class AdditionalItemIn(Strict):
    description: Short
    unit: Annotated[str, Field(min_length=1, max_length=20), AfterValidator(_text)]
    quantity: Quantity
    rate: Money


class StageDurationIn(Strict):
    entry_key: Annotated[str, Field(min_length=1, max_length=40)]
    days: Days


class QuoteIn(Strict):
    """A complete quote (QD-18): every RFQ quantity line priced or excluded with a reason."""

    lines: list[QuoteLineIn] = Field(max_length=2000)
    additional_items: list[AdditionalItemIn] = Field(default_factory=list, max_length=50)
    valid_from: date
    valid_to: date
    tax_treatment: TaxTreatment
    tax_note: Short | None = None
    duration_days: Days
    stage_durations: list[StageDurationIn] = Field(default_factory=list, max_length=200)
    payment_terms: Text | None = None
    warranty: Text | None = None
    materials: Text | None = None
    exclusions: list[Short] = Field(default_factory=list, max_length=30)
    assumptions: list[Short] = Field(default_factory=list, max_length=30)
    attachment_file_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    comment: Text | None = None


class QuoteDraftIn(Strict):
    """A working copy: any field may be missing. Never part of the record."""

    lines: list[QuoteLineIn] = Field(default_factory=list, max_length=2000)
    additional_items: list[AdditionalItemIn] = Field(default_factory=list, max_length=50)
    valid_from: date | None = None
    valid_to: date | None = None
    tax_treatment: TaxTreatment | None = None
    tax_note: Short | None = None
    duration_days: Days | None = None
    stage_durations: list[StageDurationIn] = Field(default_factory=list, max_length=200)
    payment_terms: Text | None = None
    warranty: Text | None = None
    materials: Text | None = None
    exclusions: list[Short] = Field(default_factory=list, max_length=30)
    assumptions: list[Short] = Field(default_factory=list, max_length=30)
    attachment_file_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    comment: Text | None = None


class CaptureIn(QuoteIn):
    """Operations enter a quote in the standard structure for an outside contractor, or for a
    listed contractor who sent it outside the portal; the contractor's document is the
    evidence (QD-22, BR-082)."""

    evidence_file_id: uuid.UUID


class RenewIn(Strict):
    valid_from: date
    valid_to: date


class AdjustmentIn(Strict):
    line_no: int | None = Field(default=None, ge=1)
    spec_line_code: Annotated[str, Field(max_length=8)] | None = None
    deviation_type: DeviationType
    description: Text
    rupee_impact: Impact
    basis_note: Text | None = None
    clarification_status: AdjustmentClarification = AdjustmentClarification.NONE


class AdjustmentsIn(Strict):
    adjustments: list[AdjustmentIn] = Field(max_length=200)


class QuestionIn(Strict):
    question: Text


class OpsQuestionIn(Strict):
    invitation_id: uuid.UUID
    quote_version_id: uuid.UUID | None = None
    question: Text


class AnswerIn(Strict):
    answer: Text


class OpsAnswerIn(Strict):
    answer: Text
    shared_with_all: bool = Field(
        default=False, description="Send to every accepted invitation without the asker's name"
    )


class SelectionCodeIn(Strict):
    quote_version_id: uuid.UUID


class SelectIn(Strict):
    quote_version_id: uuid.UUID
    challenge_id: uuid.UUID
    code: Annotated[str, Field(min_length=4, max_length=12)]
    statement_id: uuid.UUID
    contact_name: Name
    contact_phone: Phone


class StatementIn(Strict):
    text: Text
    note: Text


class UploadIn(Strict):
    file_name: Annotated[str, Field(min_length=1, max_length=200)]
    content_type: Annotated[str, Field(max_length=100)]
    size_bytes: int = Field(gt=0)


# --- shared responses ----------------------------------------------------------------------


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


class StatementOut(BaseModel):
    id: uuid.UUID
    version: int
    text: str
    status: str
    note: str


class StageDurationOut(BaseModel):
    entry_key: str
    days: int


class QuoteLineOut(BaseModel):
    line_no: int
    description: str
    unit: str
    quantity: Decimal
    rate: Decimal | None
    amount: Decimal | None
    excluded: bool
    exclusion_reason: str | None
    alternate_spec: str | None


class QuoteContentOut(BaseModel):
    """A quote as submitted, the same for every reader who may see it."""

    id: uuid.UUID
    version_no: int
    kind: QuoteVersionKind
    submitted_at: datetime
    captured_by_staff: bool
    valid_from: date
    valid_to: date
    tax_treatment: TaxTreatment
    tax_note: str | None
    duration_days: int
    stage_durations: list[StageDurationOut]
    payment_terms: str | None
    warranty: str | None
    materials: str | None
    exclusions: list[str]
    assumptions: list[str]
    comparable_total: Decimal
    additional_total: Decimal
    lines: list[QuoteLineOut]
    additional_items: list[QuoteLineOut]
    attachments: list[FileOut]


# --- the pack a contractor sees (no rate, amount or rate card: BP-08) -----------------------


class PackDrawingOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: uuid.UUID
    drawing_class: str
    floor: int | None
    title: str
    sheet_no: str | None
    sha256: str | None


class PackSpecOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    item: str
    criteria: str
    applicability: str
    value: str | None
    not_applicable_reason: str | None


class PackQuantityOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_no: int
    item_code: str
    description: str
    unit: str
    quantity: str
    stage_number: int | None
    floor: int | None
    spec_line_codes: list[str]
    assumptions: str | None


class PackScheduleOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_key: str
    stage_number: int
    stage_name: str
    floor: int | None
    duration_days: int | None
    predecessors: list[str]


class PackScopeOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inclusions: list[str]
    exclusions: list[str]
    assumptions: list[str]


class PackOut(BaseModel):
    """The frozen RFQ pack (E.1): never Plan2Build's rates, amounts, totals or rate card."""

    model_config = ConfigDict(extra="forbid")

    build_plan_version_no: int
    content_hash: str
    manifest_sha256: str
    drawings: list[PackDrawingOut]
    specifications: list[PackSpecOut]
    quantities: list[PackQuantityOut]
    schedule: list[PackScheduleOut]
    dates_status: str
    scope: PackScopeOut
    quote_format_version: int


class BriefOut(BaseModel):
    """Before accepting: no name, phone, email, address, pin, drawings or documents (QD-09)."""

    locality: str | None
    plot_area_sqft: str | None
    built_up_area_sqft: int | None
    floors: int | None
    basement: bool | None
    budget_band: str | None
    start_window: str | None
    build_plan_accepted: bool


# --- the contractor -----------------------------------------------------------------------


class ProClarificationOut(BaseModel):
    id: uuid.UUID
    direction: ClarificationDirection
    question: str
    answer: str | None
    state: ClarificationState
    asked_at: datetime
    answered_at: datetime | None
    yours: bool = Field(description="False for an answer Plan2Build shared with every contractor")


class ProQuoteVersionOut(BaseModel):
    """Your own quote version and its state; never Plan2Build's review or adjustments (QD-08)."""

    state: QuoteVersionState
    withdraw_reason: str | None
    comment: str | None
    quote: QuoteContentOut


class ProInvitationSummaryOut(BaseModel):
    id: uuid.UUID
    state: InvitationState
    locality: str | None
    sent_at: datetime | None
    respond_by: datetime | None
    quotes_due_at: datetime | None
    rfq_open: bool
    outcome: QuoteVersionState | None


class ProInvitationsOut(BaseModel):
    items: list[ProInvitationSummaryOut]


class ProInvitationOut(BaseModel):
    id: uuid.UUID
    state: InvitationState
    sent_at: datetime | None
    respond_by: datetime | None
    responded_at: datetime | None
    decline_reason: DeclineReason | None
    withdraw_reason: InvitationWithdrawReason | None
    brief: BriefOut
    quotes_due_at: datetime | None
    rfq_open: bool
    pack: PackOut | None = Field(description="Only after you accept, while the RFQ is open")
    draft: dict[str, Any] | None
    versions: list["ProQuoteVersionOut"]
    clarifications: list[ProClarificationOut]
    outcome: QuoteVersionState | None
    engagement_id: uuid.UUID | None = Field(description="Your engagement, once selected")
    can_submit: bool
    can_renew: bool
    can_withdraw: bool
    attachments_max: int


# --- the homeowner -------------------------------------------------------------------------


class FamilyQuoteStatusOut(BaseModel):
    """A quote's existence and identity before publication: never its prices (QD-07)."""

    version_no: int
    kind: QuoteVersionKind
    state: QuoteVersionState
    submitted_at: datetime
    valid_to: date


class FamilyInvitationOut(BaseModel):
    id: uuid.UUID
    party: EngagementParty
    source: InvitationSource
    contractor_name: str | None
    firm_name: str | None
    state: InvitationState
    sent_at: datetime | None
    responded_at: datetime | None
    latest_quote: FamilyQuoteStatusOut | None


class AdjustmentOut(BaseModel):
    line_no: int | None
    spec_line_code: str | None
    deviation_type: DeviationType
    description: str
    rupee_impact: Decimal
    basis_note: str | None
    clarification_status: AdjustmentClarification


class ComparisonQuoteOut(BaseModel):
    """One quote in the comparison: as submitted, the adjustment list, the totals. No rank."""

    quote_version_id: uuid.UUID
    invitation_id: uuid.UUID
    contractor_name: str | None
    firm_name: str | None
    party: EngagementParty
    quote: QuoteContentOut
    adjustments: list[AdjustmentOut]
    adjustments_total: Decimal
    normalised_total: Decimal


class ComparisonLineOut(BaseModel):
    line_no: int
    description: str
    unit: str
    quantity: str


class ComparisonCountsOut(BaseModel):
    invited: int
    quotes_received: int
    included: int


class ComparisonOut(BaseModel):
    id: uuid.UUID
    version_no: int
    state: ComparisonState
    published_at: datetime
    document_file_id: uuid.UUID
    snapshot_sha256: str
    build_plan_version_no: int
    counts: ComparisonCountsOut
    lines: list[ComparisonLineOut]
    quotes: list[ComparisonQuoteOut]
    notes: list[str]


class SelectionOut(BaseModel):
    quote_version_id: uuid.UUID
    contractor_name: str | None
    firm_name: str | None
    selected_at: datetime
    engagement_id: uuid.UUID
    statement_text: str


class FamilyRfqOut(BaseModel):
    id: uuid.UUID
    state: RfqState
    build_plan_version_no: int | None
    created_at: datetime
    issued_at: datetime | None
    quotes_due_at: datetime | None
    cancel_reason: RfqCancelReason | None
    closed_at: datetime | None
    max_recipients: int
    invitations: list[FamilyInvitationOut]
    comparison: ComparisonOut | None
    selection: SelectionOut | None
    can_cancel: bool
    can_select: bool


class FamilyRfqsOut(BaseModel):
    project_id: uuid.UUID
    package_state: PackageState
    accepted_build_plan_version_no: int | None
    engaged_contractor: str | None
    can_request: bool
    max_recipients: int
    rfqs: list[FamilyRfqOut]


# --- operations ----------------------------------------------------------------------------


class OpsInvitationOut(BaseModel):
    id: uuid.UUID
    party: EngagementParty
    source: InvitationSource
    profile_id: uuid.UUID | None
    engagement_id: uuid.UUID | None
    contractor_name: str | None
    firm_name: str | None
    introduced_reason: str | None
    state: InvitationState
    sent_at: datetime | None
    respond_by: datetime | None
    responded_at: datetime | None
    decline_reason: DeclineReason | None
    decline_note: str | None
    withdraw_reason: InvitationWithdrawReason | None
    withdraw_note: str | None
    professional_contact: dict[str, Any] | None


class OpsQuoteVersionOut(BaseModel):
    invitation_id: uuid.UUID
    state: QuoteVersionState
    review_state: QuoteCheckState
    withdraw_reason: str | None
    comment: str | None
    evidence_file_id: uuid.UUID | None
    content_sha256: str
    quote: QuoteContentOut
    adjustments: list[AdjustmentOut]


class OpsClarificationOut(BaseModel):
    id: uuid.UUID
    invitation_id: uuid.UUID
    quote_version_id: uuid.UUID | None
    direction: ClarificationDirection
    question: str
    answer: str | None
    shared_with_all: bool
    state: ClarificationState
    asked_at: datetime
    answered_at: datetime | None
    close_reason: str | None


class OpsEventOut(BaseModel):
    subject: str
    subject_id: uuid.UUID
    from_state: str | None
    to_state: str
    actor_role: str
    reason: str | None
    at: datetime


class OpsRfqOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_code: str
    state: RfqState
    package_state: PackageState
    build_plan_version_id: uuid.UUID
    manifest_sha256: str | None
    requested_role: str
    created_at: datetime
    issued_at: datetime | None
    quotes_due_at: datetime | None
    cancel_reason: RfqCancelReason | None
    cancel_note: str | None
    max_recipients: int
    invitations: list[OpsInvitationOut]
    quote_versions: list[OpsQuoteVersionOut]
    clarifications: list[OpsClarificationOut]
    comparisons: list[ComparisonOut]
    selection: SelectionOut | None
    history: list[OpsEventOut]


class OpsRfqSummaryOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    project_code: str
    state: RfqState
    created_at: datetime
    quotes_due_at: datetime | None
    invitations: int
    quotes: int
    pending_reviews: int


class OpsRfqsOut(BaseModel):
    items: list[OpsRfqSummaryOut]
