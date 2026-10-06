"""The one place where state names and enumerations are defined (STATE_MODEL section 1; ADR-019).

Migrations copy these values as literals (a migration is a frozen snapshot); a test asserts that
the database CHECK constraints still equal these sets. `apps/api/scripts/export_contracts.py`
exports them to TypeScript so the web app never spells a state differently.
"""

from enum import StrEnum


class Audience(StrEnum):
    """Who a host and a session belong to (SYSTEM_ARCHITECTURE section 5)."""

    IHB = "ihb"
    PRO = "pro"
    OPS = "ops"


class UserStatus(StrEnum):
    """User account machine (STATE_MODEL section 2)."""

    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class ActorType(StrEnum):
    """Who performed an audited action (DATA_ARCHITECTURE 4.14, audit_events.actor_type)."""

    USER = "USER"
    SYSTEM = "SYSTEM"
    JOB = "JOB"


class SecuritySeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ContactKind(StrEnum):
    """DATA_ARCHITECTURE 4.2, user_contacts.kind. Email now; phone when SMS is enabled (ADR-010)."""

    EMAIL = "EMAIL"
    PHONE = "PHONE"


class OtpPurpose(StrEnum):
    """SECURITY 3.1. LOGIN covers registration since B-03; acknowledgement purposes arrive with
    the modules that need them."""

    LOGIN = "LOGIN"
    ACCEPT_BUILD_PLAN = "ACCEPT_BUILD_PLAN"  # the owner accepts one issued version (BP-05)
    SIGN_STRUCTURAL = "SIGN_STRUCTURAL"  # a verified engineer signs structural lines (BP-04)
    SELECT_QUOTE = "SELECT_QUOTE"  # the owner selects one contractor quote version (QD-12)


class OtpState(StrEnum):
    """OTP challenge machine (STATE_MODEL section 2, related machines)."""

    ISSUED = "ISSUED"
    VERIFIED = "VERIFIED"
    EXPIRED = "EXPIRED"
    LOCKED = "LOCKED"


class FinishLevel(StrEnum):
    """Estimator finish level (S14 prototype; S05 "quality tier"; API_ARCHITECTURE section 3)."""

    STANDARD = "STANDARD"
    PREMIUM = "PREMIUM"
    LUXURY = "LUXURY"


class ProjectStatus(StrEnum):
    """Project machine (STATE_MODEL section 5). All states are declared so the CHECK constraint
    does not change when later slices add transitions; slice 1 moves only DRAFT -> SUBMITTED."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    NEEDS_INFO = "NEEDS_INFO"
    ACCEPTED = "ACCEPTED"
    PLANNING = "PLANNING"
    PLAN_ISSUED = "PLAN_ISSUED"
    SOURCING = "SOURCING"
    CONTRACTED = "CONTRACTED"
    BUILDING = "BUILDING"
    HANDOVER_PENDING = "HANDOVER_PENDING"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"
    ON_HOLD = "ON_HOLD"
    CANCELLED = "CANCELLED"


class ProjectType(StrEnum):
    """Only new homes at the MVP (CD-03)."""

    NEW_HOME = "NEW_HOME"


class MembershipRole(StrEnum):
    """Per-project roles (DATA_ARCHITECTURE 4.3, project_memberships.role)."""

    OWNER = "OWNER"
    HOUSEHOLD = "HOUSEHOLD"
    CONTRACTOR = "CONTRACTOR"
    ARCHITECT = "ARCHITECT"
    OPS_ADVISOR = "OPS_ADVISOR"
    OPS_FIELD = "OPS_FIELD"
    AUDITOR_ASSIGNED = "AUDITOR_ASSIGNED"


class ReviewFlag(StrEnum):
    """Signals for operations review raised by a submission (REQUIREMENT_QUESTIONS_V1 L.4)."""

    PROPERTY_TYPE_OTHER = "PROPERTY_TYPE_OTHER"
    CONSTRUCTION_STARTED = "CONSTRUCTION_STARTED"


class EnquiryKind(StrEnum):
    """The two capture paths (REQUIREMENT_QUESTIONS_V1 L.3)."""

    COMING_SOON_HELP = "COMING_SOON_HELP"
    OTHER_CITY = "OTHER_CITY"


class ComingSoonWork(StrEnum):
    RENOVATION = "RENOVATION"
    INTERIORS = "INTERIORS"
    REPAIRS = "REPAIRS"


class FileState(StrEnum):
    """File object machine (STATE_MODEL section 16)."""

    PENDING_UPLOAD = "PENDING_UPLOAD"
    UPLOADED = "UPLOADED"
    SCANNING = "SCANNING"
    AVAILABLE = "AVAILABLE"
    QUARANTINED = "QUARANTINED"
    FAILED = "FAILED"
    DELETED = "DELETED"


class FilePurpose(StrEnum):
    """Why a file exists; each purpose has its own limits (ADR-011)."""

    REQUIREMENT_UPLOAD = "REQUIREMENT_UPLOAD"
    AI_CONCEPT = "AI_CONCEPT"  # an illustrative AI design image (Slice 3.1); never authoritative
    VERIFICATION_EVIDENCE = "VERIFICATION_EVIDENCE"  # a professional's documents; never public
    PORTFOLIO = "PORTFOLIO"  # a professional's work; public only once operations approve it
    INVOICE = "INVOICE"  # a rendered tax invoice or credit note (Slice 3.3); buyer and staff only
    QUOTE_DOCUMENT = "QUOTE_DOCUMENT"  # a quote the family holds, for Plan2Build's review (3.4)
    DRAWING = "DRAWING"  # a file of a drawing set (Slice 3.5); authoritative only once approved
    BUILD_PLAN_EVIDENCE = "BUILD_PLAN_EVIDENCE"  # signed sign-off documents, certificates, notes
    BUILD_PLAN_DOCUMENT = "BUILD_PLAN_DOCUMENT"  # a rendered Build Plan PDF; never changed
    QUOTE_ATTACHMENT = "QUOTE_ATTACHMENT"  # a contractor's file with an RFQ quote (3.6)
    COMPARISON_DOCUMENT = "COMPARISON_DOCUMENT"  # a rendered quote comparison PDF; never changed


class ConfigStatus(StrEnum):
    """Lifecycle of versioned reference data (stage masters, question sets)."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class StageState(StrEnum):
    """STATE_MODEL section 6."""

    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETION_REQUESTED = "COMPLETION_REQUESTED"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    ON_HOLD = "ON_HOLD"


class GateStatus(StrEnum):
    """STATE_MODEL section 6, gate stages only."""

    NOT_INSPECTED = "NOT_INSPECTED"
    SCHEDULED = "SCHEDULED"
    OPEN_NC = "OPEN_NC"
    CLEARED = "CLEARED"


class SpecLineState(StrEnum):
    """STATE_MODEL section 7."""

    SPECIFIED = "SPECIFIED"
    OPTIONS_ISSUED = "OPTIONS_ISSUED"
    CHOSEN = "CHOSEN"
    PURCHASED = "PURCHASED"
    INSTALLED = "INSTALLED"
    VERIFIED = "VERIFIED"


class EngineerSignoff(StrEnum):
    """Structural criteria wait for a registered structural engineer's sign-off (ruling 2.4)."""

    PENDING = "PENDING"
    SIGNED = "SIGNED"
    NOT_REQUIRED = "NOT_REQUIRED"


class StaffRole(StrEnum):
    """Global staff roles (SECURITY 4.1 actor sets "ops" and "admin"; SLICE2_READINESS 1). A person
    may hold both. Project roles such as OPS_ADVISOR stay in project_memberships."""

    OPS = "OPS"
    ADMIN = "ADMIN"


class QueueKind(StrEnum):
    """Operations work queues (API 18). Slice 2 builds the first."""

    REQUIREMENT_REVIEW = "REQUIREMENT_REVIEW"
    PROFESSIONAL_REVIEW = "PROFESSIONAL_REVIEW"


class QueueItemState(StrEnum):
    OPEN = "OPEN"
    CLAIMED = "CLAIMED"
    RESOLVED = "RESOLVED"


class EstimateStatus(StrEnum):
    """A project's indicative estimate (Slice 3.0). UNAVAILABLE carries the reason; it is never a
    guess."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class EstimateUnavailableReason(StrEnum):
    BUILT_UP_AREA_NOT_GIVEN = "BUILT_UP_AREA_NOT_GIVEN"  # the family answered "Not sure yet"
    NO_RATE_CARD = "NO_RATE_CARD"  # no rate card in force for the city (production until D-16)


class PackageAvailability(StrEnum):
    """Whether the Plan2Build package can be offered on a project (PD-21). ELIGIBLE means the
    project passed Plan2Build's initial eligibility review (ACCEPTED); it approves nothing else."""

    NOT_SUBMITTED = "NOT_SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


class DesignView(StrEnum):
    """What an AI concept shows (F-08, first version): never a plan or a drawing."""

    EXTERIOR = "EXTERIOR"
    INTERIOR = "INTERIOR"


class DesignGenerationState(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class DesignFunding(StrEnum):
    """How a generation is paid for: a free generation, or one AI credit (Slice 3.3)."""

    FREE = "FREE"
    PAID = "PAID"


class DesignFailureReason(StrEnum):
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_REJECTED = "PROVIDER_REJECTED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    STALE = "STALE"  # in flight far longer than any attempt can take; the worker was lost


class DesignBlock(StrEnum):
    """Why a project cannot generate now; computed by the server, never by the client."""

    NOT_SUBMITTED = "NOT_SUBMITTED"
    REQUIREMENT_BEING_UPDATED = "REQUIREMENT_BEING_UPDATED"
    PROJECT_CLOSED = "PROJECT_CLOSED"
    FREE_QUOTA_USED = "FREE_QUOTA_USED"
    ACCOUNT_DAILY_GENERATIONS = "ACCOUNT_DAILY_GENERATIONS"
    ACCOUNT_DAILY_PROJECTS = "ACCOUNT_DAILY_PROJECTS"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"


class ListingState(StrEnum):
    """One professional category's place in the review workflow (D-04). Only LISTED is public,
    and only while the professional has not hidden it (D-11)."""

    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    LISTED = "LISTED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"


class CheckKind(StrEnum):
    """What a listing requirement can ask for (D-02; S01 T5, T10; S02 P71 to P83; S03)."""

    IDENTITY = "IDENTITY"
    BUSINESS = "BUSINESS"
    REGISTRATION = "REGISTRATION"  # registration, credential, qualification or licence
    PORTFOLIO = "PORTFOLIO"
    REFERENCE = "REFERENCE"
    SITE_VISIT = "SITE_VISIT"


class CheckOutcome(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RequirementLevel(StrEnum):
    REQUIRED = "REQUIRED"
    WHERE_APPLICABLE = "WHERE_APPLICABLE"


class VerificationDecision(StrEnum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    REJECTED = "REJECTED"


class ProfessionalDocumentKind(StrEnum):
    """Documents the professional supplies; evidence for the IDENTITY, BUSINESS and
    REGISTRATION checks."""

    IDENTITY = "IDENTITY"
    BUSINESS = "BUSINESS"
    REGISTRATION = "REGISTRATION"


class PortfolioReviewState(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class EligibilityOutcome(StrEnum):
    """One item of the package-eligibility checklist (F-05), recorded by operations."""

    PASSED = "PASSED"
    FAILED = "FAILED"


class OfferingKind(StrEnum):
    """What Plan2Build sells (SLICE3_3_READINESS G.1): a closed set. Construction money is never
    one of them."""

    PACKAGE = "PACKAGE"
    AI_CREDIT = "AI_CREDIT"


class PaymentMode(StrEnum):
    FULL = "FULL"  # 100% upfront
    INSTALMENTS = "INSTALMENTS"  # per a published instalment plan version


class DueRule(StrEnum):
    """When an instalment falls due. Never a construction stage (L-06)."""

    ON_ORDER = "ON_ORDER"
    DAYS_AFTER_ACTIVATION = "DAYS_AFTER_ACTIVATION"


class OrderState(StrEnum):
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PART_PAID = "PART_PAID"
    PAID = "PAID"
    CANCELLED = "CANCELLED"
    PARTLY_REFUNDED = "PARTLY_REFUNDED"
    REFUNDED = "REFUNDED"


class DueState(StrEnum):
    DUE = "DUE"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class AttemptState(StrEnum):
    CREATED = "CREATED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class PackageState(StrEnum):
    """The package on a project (L-05). NOT_ACTIVE is the absence of an entitlement row."""

    NOT_ACTIVE = "NOT_ACTIVE"
    ACTIVE = "ACTIVE"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class CreditEntry(StrEnum):
    GRANT = "GRANT"  # a verified, captured credit purchase
    CONSUME = "CONSUME"  # spent on one named generation
    RETURN = "RETURN"  # that paid generation failed
    REVOKE = "REVOKE"  # an unused credit refunded


class RefundRequestState(StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


class RefundState(StrEnum):
    PROCESSING = "PROCESSING"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


class InvoiceKind(StrEnum):
    TAX_INVOICE = "TAX_INVOICE"
    CREDIT_NOTE = "CREDIT_NOTE"


class BillingExceptionKind(StrEnum):
    """A payment Plan2Build cannot apply automatically; operations decide (never applied)."""

    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    UNKNOWN_ORDER = "UNKNOWN_ORDER"
    DUPLICATE_CAPTURE = "DUPLICATE_CAPTURE"
    CAPTURE_AFTER_CANCEL = "CAPTURE_AFTER_CANCEL"
    AUTHORISED_NOT_CAPTURED = "AUTHORISED_NOT_CAPTURED"
    REFUND_MISMATCH = "REFUND_MISMATCH"


class BillingExceptionState(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class NeedState(StrEnum):
    """A project's need for one professional category (Slice 3.4, N-01)."""

    UNDECIDED = "UNDECIDED"
    NEEDED = "NEEDED"
    NOT_NEEDED = "NOT_NEEDED"


class NeedSource(StrEnum):
    REQUIREMENT = "REQUIREMENT"  # from the requirement's services answer
    FAMILY = "FAMILY"  # set by the family on the services screen


class EngagementParty(StrEnum):
    """Who provides a category. Professionals verified for one project only wait for F-03."""

    LISTED = "LISTED"
    OUTSIDE = "OUTSIDE"


class EngagementState(StrEnum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"


class EngagementOrigin(StrEnum):
    """How an engagement started (ADR-024): an accepted connection (3.4), an outside professional
    the family recorded (3.4), or the homeowner's selection of an RFQ quote (3.6, QD-01)."""

    CONNECTION = "CONNECTION"
    OUTSIDE = "OUTSIDE"
    RFQ_SELECTION = "RFQ_SELECTION"


class PackageServiceKind(StrEnum):
    """Substantial-work events recorded per package (package_service_usage.service). N-12:
    a professional accepting a connection. QD-02 (a new product decision, 2026-10-06): an
    engagement from an RFQ selection. Nothing else counts."""

    CONNECTION_ACCEPTED = "CONNECTION_ACCEPTED"
    RFQ_SELECTION = "RFQ_SELECTION"


class ConnectionState(StrEnum):
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    WITHDRAWN = "WITHDRAWN"


class DeclineReason(StrEnum):
    """N-06. The family sees a neutral label; an explanation for OTHER stays internal."""

    UNAVAILABLE = "UNAVAILABLE"
    OUTSIDE_SERVICE_AREA = "OUTSIDE_SERVICE_AREA"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    SCHEDULE_MISMATCH = "SCHEDULE_MISMATCH"
    COMPLIANCE = "COMPLIANCE"
    ALREADY_ENGAGED = "ALREADY_ENGAGED"
    OTHER = "OTHER"


class WithdrawReason(StrEnum):
    FAMILY = "FAMILY"  # the family withdrew it
    ANOTHER_ENGAGED = "ANOTHER_ENGAGED"  # another request in the category was accepted (N-02)
    PACKAGE_ENDED = "PACKAGE_ENDED"  # N-10
    PROFESSIONAL_UNAVAILABLE = "PROFESSIONAL_UNAVAILABLE"  # no longer listed for the category
    PROJECT_CLOSED = "PROJECT_CLOSED"
    OPERATIONS = "OPERATIONS"


class QuoteReviewState(StrEnum):
    """Quote-holder review intake (3.4). Review itself belongs to the later quote workflow."""

    SUBMITTED = "SUBMITTED"


class RateCardStatus(StrEnum):
    """An item rate card (BP-06): operations prepare a DRAFT, an ADMIN publishes it; a published
    card never changes."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    RETIRED = "RETIRED"


class DesignRequestKind(StrEnum):
    """Who provides the drawings of a design request (BP-03: Plan2Build generates none)."""

    LISTED_PROFESSIONAL = "LISTED_PROFESSIONAL"  # a listed professional with an ACTIVE engagement
    OUTSIDE_PROFESSIONAL = "OUTSIDE_PROFESSIONAL"  # the family's own professional (OUTSIDE)
    HOMEOWNER_PROVIDED = "HOMEOWNER_PROVIDED"  # drawings the family already holds
    PLAN2BUILD_ARRANGED = "PLAN2BUILD_ARRANGED"  # a qualified professional Plan2Build arranges


class DrawingSetState(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"  # waiting for the family's review
    IN_CHECK = "IN_CHECK"  # waiting for the appointed checker (BP-01)
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    APPROVED = "APPROVED"  # authoritative, immutable
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class DrawingClass(StrEnum):
    """BP-02: the classes an issued plan needs, where applicable, plus OTHER. No other type is
    mandatory."""

    SITE_PLAN = "SITE_PLAN"
    FLOOR_PLAN = "FLOOR_PLAN"
    ELEVATION = "ELEVATION"
    SECTION = "SECTION"
    STRUCTURAL = "STRUCTURAL"
    OTHER = "OTHER"


class BuildPlanState(StrEnum):
    """SLICE3_5_READINESS 0.2."""

    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    ISSUED = "ISSUED"
    ACCEPTED = "ACCEPTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"


class ValueApplicability(StrEnum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ValueBasis(StrEnum):
    """Where a project specification value comes from (PD-14)."""

    STRUCTURAL_DESIGN = "STRUCTURAL_DESIGN"
    ARCHITECT_DRAWING = "ARCHITECT_DRAWING"
    HOMEOWNER_PROVIDED = "HOMEOWNER_PROVIDED"
    ADVISOR = "ADVISOR"
    STANDARD_REFERENCE = "STANDARD_REFERENCE"


class QuantityBasis(StrEnum):
    """Never AI (PD-05)."""

    MEASURED_FROM_DRAWING = "MEASURED_FROM_DRAWING"
    PROVIDED_BY_PROFESSIONAL = "PROVIDED_BY_PROFESSIONAL"
    ADVISOR_ESTIMATE = "ADVISOR_ESTIMATE"


class SignoffMode(StrEnum):
    """BP-04. ONE_TIME_CODE is a confirmation step, not a legally recognised electronic
    signature."""

    ONE_TIME_CODE = "ONE_TIME_CODE"
    SIGNED_DOCUMENT = "SIGNED_DOCUMENT"  # operations upload an outside engineer's signed document


class SignerKind(StrEnum):
    LISTED = "LISTED"
    OUTSIDE = "OUTSIDE"


class SignoffState(StrEnum):
    SIGNED = "SIGNED"
    VOID = "VOID"


# --- Slice 3.6: RFQ to contractor selection (SLICE3_6_READINESS section 0) -------------------


class RfqState(StrEnum):
    DRAFT = "DRAFT"  # requested; operations prepare recipients and the deadline
    ISSUED = "ISSUED"  # the pack is frozen; invitations are out
    CLOSED = "CLOSED"  # a selection was confirmed
    CANCELLED = "CANCELLED"


class RfqCancelReason(StrEnum):
    OWNER = "OWNER"
    OPERATIONS = "OPERATIONS"
    PACKAGE_ENDED = "PACKAGE_ENDED"  # QD-14
    BASELINE_SUPERSEDED = "BASELINE_SUPERSEDED"  # QD-15
    PROJECT_CLOSED = "PROJECT_CLOSED"


class InvitationState(StrEnum):
    """An invitation asks one contractor to quote (QD-01); accepting it is agreeing to quote, never
    an engagement."""

    PROPOSED = "PROPOSED"  # named on a DRAFT RFQ; nothing sent yet
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    WITHDRAWN = "WITHDRAWN"


class InvitationSource(StrEnum):
    NOMINATED = "NOMINATED"  # the owner chose the contractor (QD-03)
    INTRODUCED = "INTRODUCED"  # operations added it, with a written reason (QD-03)
    ENGAGED = "ENGAGED"  # the contractor already engaged for the category (QD-13)


class InvitationWithdrawReason(StrEnum):
    REMOVED = "REMOVED"  # taken off a DRAFT RFQ before anything was sent
    OPERATIONS = "OPERATIONS"
    RFQ_CANCELLED = "RFQ_CANCELLED"
    RFQ_CLOSED = "RFQ_CLOSED"
    NOT_LISTED = "NOT_LISTED"  # the contractor left LISTED


class QuoteVersionState(StrEnum):
    SUBMITTED = "SUBMITTED"
    SUPERSEDED = "SUPERSEDED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"
    SELECTED = "SELECTED"
    NOT_SELECTED = "NOT_SELECTED"


class QuoteVersionKind(StrEnum):
    STANDARD = "STANDARD"
    RENEWAL = "RENEWAL"  # new validity dates only; commercial content unchanged (QD-06)


class QuoteCheckState(StrEnum):
    """Plan2Build's review of one submitted quote version (K.2). Distinct from the 3.4
    quote-holder review intake (QuoteReviewState)."""

    PENDING = "PENDING"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    REVIEWED = "REVIEWED"  # adjustment list complete; may be compared
    CLOSED = "CLOSED"  # the version left SUBMITTED before the review finished


class TaxTreatment(StrEnum):
    INCLUSIVE = "INCLUSIVE"  # prices include GST
    EXCLUSIVE = "EXCLUSIVE"


class QuoteLineKind(StrEnum):
    RFQ_LINE = "RFQ_LINE"  # a quantity line of the frozen pack
    ADDITIONAL = "ADDITIONAL"  # proposed by the contractor; never in the comparable total


class DeviationType(StrEnum):
    EXCLUDED = "EXCLUDED"
    GRADE = "GRADE"
    QUANTITY = "QUANTITY"
    ADDITIONAL = "ADDITIONAL"
    OTHER = "OTHER"


class AdjustmentClarification(StrEnum):
    NONE = "NONE"
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class ClarificationDirection(StrEnum):
    CONTRACTOR_ASKS = "CONTRACTOR_ASKS"
    PLAN2BUILD_ASKS = "PLAN2BUILD_ASKS"


class ClarificationState(StrEnum):
    OPEN = "OPEN"
    ANSWERED = "ANSWERED"
    CLOSED = "CLOSED"


class ComparisonState(StrEnum):
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"
    DECIDED = "DECIDED"


ALL_ENUMS: tuple[type[StrEnum], ...] = (
    Audience, UserStatus, ActorType, SecuritySeverity, ContactKind, OtpPurpose, OtpState,
    FinishLevel, ProjectStatus, ProjectType, MembershipRole, ReviewFlag, EnquiryKind,
    ComingSoonWork, FileState, FilePurpose, ConfigStatus, StageState, GateStatus, SpecLineState,
    EngineerSignoff, StaffRole, QueueKind, QueueItemState, EstimateStatus,
    EstimateUnavailableReason, PackageAvailability, DesignView, DesignGenerationState,
    DesignFunding, DesignFailureReason, DesignBlock, ListingState, CheckKind, CheckOutcome,
    RequirementLevel, VerificationDecision, ProfessionalDocumentKind, PortfolioReviewState,
    EligibilityOutcome, OfferingKind, PaymentMode, DueRule, OrderState, DueState, AttemptState,
    PackageState, CreditEntry, RefundRequestState, RefundState, InvoiceKind, BillingExceptionKind,
    BillingExceptionState, NeedState, NeedSource, EngagementParty, EngagementState,
    ConnectionState, DeclineReason, WithdrawReason, QuoteReviewState, RateCardStatus,
    DesignRequestKind, DrawingSetState, DrawingClass, BuildPlanState, ValueApplicability,
    ValueBasis, QuantityBasis, SignoffMode, SignerKind, SignoffState, EngagementOrigin,
    PackageServiceKind, RfqState, RfqCancelReason, InvitationState, InvitationSource,
    InvitationWithdrawReason, QuoteVersionState, QuoteVersionKind, QuoteCheckState, TaxTreatment,
    QuoteLineKind, DeviationType, AdjustmentClarification, ClarificationDirection,
    ClarificationState, ComparisonState,
)  # fmt: skip
