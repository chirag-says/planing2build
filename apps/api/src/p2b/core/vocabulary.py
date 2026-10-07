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
    SUBMIT_INSPECTION = "SUBMIT_INSPECTION"  # an appointed auditor submits an inspection (EX-09)
    ACKNOWLEDGE_HANDOVER = "ACKNOWLEDGE_HANDOVER"  # the owner acknowledges the handover (EX-15)


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
    STAGE_EVIDENCE = "STAGE_EVIDENCE"  # photos with a progress update or a rectification (3.7)
    INSPECTION_EVIDENCE = "INSPECTION_EVIDENCE"  # photos and files of an inspection (3.7B, P3)
    INSPECTION_REPORT = "INSPECTION_REPORT"  # the rendered report of an approved inspection
    HANDOVER_DOCUMENT = "HANDOVER_DOCUMENT"  # warranties, manuals, certificates at handover (3.7C)
    BUILD_RECORD_DOCUMENT = "BUILD_RECORD_DOCUMENT"  # an issued Build Record version as PDF
    BUILD_RECORD_EXPORT = "BUILD_RECORD_EXPORT"  # the same version as structured JSON


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


# --- Slice 3.7: execution, assurance, handover and Build Record (SLICE3_7_READINESS 0) ------


class StageUpdateKind(StrEnum):
    """EX-02: evidence and history, never a promise of schedule completion."""

    PROGRESS = "PROGRESS"
    COMPLETION_REQUEST = "COMPLETION_REQUEST"


class PaymentMarkSide(StrEnum):
    """EX-05: the owner's "paid" mark and the contractor's "received" mark."""

    PAID = "PAID"
    RECEIVED = "RECEIVED"


class PaymentMarkValue(StrEnum):
    YES = "YES"
    NO = "NO"


class AppointmentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"


class ChecklistStatus(StrEnum):
    """EX-08: versioned configuration; PUBLISHED is immutable, one at a time."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    RETIRED = "RETIRED"


class InspectionKind(StrEnum):
    INITIAL = "INITIAL"  # the gate stage instance's inspection (EX-07), or its amendment
    REINSPECTION = "REINSPECTION"  # of open non-conformances after rectification (EX-11)


class InspectionState(StrEnum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"


class InspectionCancelReason(StrEnum):
    OPERATIONS = "OPERATIONS"
    PACKAGE_ENDED = "PACKAGE_ENDED"  # EX-18
    PROJECT_CLOSED = "PROJECT_CLOSED"


class CheckpointResult(StrEnum):
    PASS = "PASS"  # noqa: S105 (a result, not a password)
    OBSERVATION = "OBSERVATION"
    NON_CONFORMANCE = "NON_CONFORMANCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Severity(StrEnum):
    """EX-11."""

    MINOR = "MINOR"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


class NcState(StrEnum):
    """EX-11: closed only by an approved re-inspection."""

    OPEN = "OPEN"
    RECTIFICATION_SUBMITTED = "RECTIFICATION_SUBMITTED"
    REINSPECTION_SCHEDULED = "REINSPECTION_SCHEDULED"
    CLOSED = "CLOSED"


class HandoverState(StrEnum):
    """EX-15: an operations issue is never an acknowledgement."""

    OPEN = "OPEN"
    READY = "READY"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ISSUED_BY_OPERATIONS = "ISSUED_BY_OPERATIONS"


class HandoverDocumentKind(StrEnum):
    WARRANTY = "WARRANTY"
    MANUAL = "MANUAL"
    DRAWING = "DRAWING"
    CERTIFICATE = "CERTIFICATE"
    PHOTO = "PHOTO"
    OTHER = "OTHER"


class BuildRecordState(StrEnum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    SUPERSEDED = "SUPERSEDED"


class BuildRecordBasis(StrEnum):
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ISSUED_BY_OPERATIONS = "ISSUED_BY_OPERATIONS"


# ---------- Concept floor plans (module houseplans; PD-28, ADR-025) ----------


class Facing(StrEnum):
    """The side of the road and main entrance (AD-15), one of eight compass directions."""

    N = "N"
    NE = "NE"
    E = "E"
    SE = "SE"
    S = "S"
    SW = "SW"
    W = "W"
    NW = "NW"


class SetbackSide(StrEnum):
    """Sides of a rectangular plot as seen standing on the primary road edge, looking at the
    plot (CP1-02): FRONT is the road edge; LEFT and RIGHT are the viewer's left and right."""

    FRONT = "FRONT"
    BACK = "BACK"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class PlotEdgeKind(StrEnum):
    ROAD = "ROAD"
    NEIGHBOUR = "NEIGHBOUR"


class SetbackSource(StrEnum):
    REQUIREMENT = "REQUIREMENT"
    DESIGN_INPUT = "DESIGN_INPUT"


class ParkingKind(StrEnum):
    CAR = "CAR"
    TWO_WHEELER = "TWO_WHEELER"


class ParkingPlacement(StrEnum):
    INSIDE_FOOTPRINT = "INSIDE_FOOTPRINT"


class OriginKind(StrEnum):
    """Why a plan element exists: a requirement answer, a provisional design input, ruleset data,
    the solver's circulation, or a person's edit."""

    REQUIREMENT = "REQUIREMENT"
    DESIGN_INPUT = "DESIGN_INPUT"
    RULESET = "RULESET"
    SOLVER = "SOLVER"
    USER_EDIT = "USER_EDIT"


class RoomType(StrEnum):
    LIVING = "LIVING"
    DINING = "DINING"
    KITCHEN = "KITCHEN"
    BEDROOM = "BEDROOM"
    BATH_ATTACHED = "BATH_ATTACHED"
    BATH_COMMON = "BATH_COMMON"
    WC = "WC"
    PUJA = "PUJA"
    UTILITY = "UTILITY"
    STORE = "STORE"
    PASSAGE = "PASSAGE"
    FOYER = "FOYER"
    STAIR_HALL = "STAIR_HALL"
    PARKING = "PARKING"


class Zone(StrEnum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    SERVICE = "SERVICE"
    CIRCULATION = "CIRCULATION"
    OUTDOOR = "OUTDOOR"


class WallKind(StrEnum):
    EXTERIOR = "EXTERIOR"
    INTERIOR = "INTERIOR"


class OpeningKind(StrEnum):
    MAIN_ENTRANCE = "MAIN_ENTRANCE"
    DOOR = "DOOR"
    VOID = "VOID"
    WINDOW = "WINDOW"


class DoorLeaf(StrEnum):
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"
    SLIDING = "SLIDING"


class HingeSide(StrEnum):
    """The jamb a door hangs on, relative to its host wall's a-to-b direction."""

    A_SIDE = "A_SIDE"
    B_SIDE = "B_SIDE"


class WallSide(StrEnum):
    """A side of a wall, relative to its a-to-b direction."""

    LEFT = "LEFT"
    RIGHT = "RIGHT"


class FixtureType(StrEnum):
    WC_WESTERN = "WC_WESTERN"
    WC_INDIAN = "WC_INDIAN"
    WASH_BASIN = "WASH_BASIN"
    SHOWER_AREA = "SHOWER_AREA"
    KITCHEN_COUNTER = "KITCHEN_COUNTER"
    KITCHEN_SINK = "KITCHEN_SINK"


class ConstraintKind(StrEnum):
    ROOM_PRESENT = "ROOM_PRESENT"
    ROOM_MIN_SIZE = "ROOM_MIN_SIZE"
    RELATION = "RELATION"
    INSIDE_ENVELOPE = "INSIDE_ENVELOPE"
    ENTRANCE_ON_EDGE = "ENTRANCE_ON_EDGE"
    PARKING_PROVIDED = "PARKING_PROVIDED"
    # Soft quality terms (Checkpoint 2): scored by the Scorer, never validation errors.
    AREA_DEVIATION = "AREA_DEVIATION"
    DIMENSION_DEVIATION = "DIMENSION_DEVIATION"
    ASPECT_EXCESS = "ASPECT_EXCESS"
    CIRCULATION_SHARE = "CIRCULATION_SHARE"
    OVERSIZE = "OVERSIZE"
    ADJACENCY = "ADJACENCY"
    WET_CLUSTER = "WET_CLUSTER"
    EXTERIOR_EXPOSURE = "EXTERIOR_EXPOSURE"
    PRIVACY = "PRIVACY"
    PARKING_CONVENIENCE = "PARKING_CONVENIENCE"
    ZONE_ORDER = "ZONE_ORDER"
    ROOM_SIZE_OUTLIER = "ROOM_SIZE_OUTLIER"
    BEDROOM_GROUPING = "BEDROOM_GROUPING"
    ORIENTATION = "ORIENTATION"


class ConstraintStrength(StrEnum):
    HARD = "HARD"
    SOFT = "SOFT"


class ConstraintOutcome(StrEnum):
    MET = "MET"
    PARTIAL = "PARTIAL"
    RELAXED = "RELAXED"
    UNMET = "UNMET"
    NOT_EVALUATED = "NOT_EVALUATED"


class RelationKind(StrEnum):
    ADJACENT_WITH_DOOR = "ADJACENT_WITH_DOOR"
    ADJACENT_OPEN = "ADJACENT_OPEN"


class OrientationMode(StrEnum):
    """From the Vastu answer. Recorded only: no orientation table exists until AD-13."""

    OFF = "OFF"
    SOFT = "SOFT"
    SOFT_HIGH = "SOFT_HIGH"


class DiningArrangement(StrEnum):
    SEPARATE = "SEPARATE"
    IN_LIVING = "IN_LIVING"


class KitchenArrangement(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"


class StairChoice(StrEnum):
    NONE = "NONE"
    INTERNAL = "INTERNAL"
    EXTERNAL = "EXTERNAL"


class DesignInputKey(StrEnum):
    """A fact the requirement (RQ v1) does not give, asked through the provisional design inputs
    (CP1-03) until AD-03 decides the design brief."""

    FACING = "FACING"
    SETBACK_FRONT = "SETBACK_FRONT"
    SETBACK_BACK = "SETBACK_BACK"
    SETBACK_LEFT = "SETBACK_LEFT"
    SETBACK_RIGHT = "SETBACK_RIGHT"
    BEDROOMS_EXACT = "BEDROOMS_EXACT"
    BATHROOMS_EXACT = "BATHROOMS_EXACT"
    ATTACHED_BATHROOMS = "ATTACHED_BATHROOMS"
    PARKING_SPACES = "PARKING_SPACES"
    PARKING_KIND = "PARKING_KIND"
    DINING = "DINING"
    KITCHEN = "KITCHEN"
    STAIR = "STAIR"
    UTILITY = "UTILITY"


class MissingInputReason(StrEnum):
    NOT_ANSWERED = "NOT_ANSWERED"
    NOT_SURE = "NOT_SURE"
    OUT_OF_RANGE = "OUT_OF_RANGE"


class UnsupportedReason(StrEnum):
    QUESTION_SET_NOT_SUPPORTED = "QUESTION_SET_NOT_SUPPORTED"
    ANSWER_INVALID = "ANSWER_INVALID"
    PLOT_NOT_RECTANGULAR = "PLOT_NOT_RECTANGULAR"
    FLOORS_NOT_SUPPORTED = "FLOORS_NOT_SUPPORTED"
    BASEMENT_NOT_SUPPORTED = "BASEMENT_NOT_SUPPORTED"
    STAIR_NOT_YET_SUPPORTED = "STAIR_NOT_YET_SUPPORTED"


class InfeasibleReason(StrEnum):
    ENVELOPE_EMPTY = "ENVELOPE_EMPTY"
    AREA_BUDGET = "AREA_BUDGET"
    WIDTH_TOO_NARROW = "WIDTH_TOO_NARROW"
    DEPTH_EXCEEDED = "DEPTH_EXCEEDED"
    PARKING_TOO_WIDE = "PARKING_TOO_WIDE"
    ACCESS_SPAN = "ACCESS_SPAN"
    FIXTURE_FIT = "FIXTURE_FIT"
    OPENING_FIT = "OPENING_FIT"
    RULESET_INCOMPLETE = "RULESET_INCOMPLETE"


class PlanSource(StrEnum):
    GENERATED = "GENERATED"
    EDITED = "EDITED"
    REGENERATED = "REGENERATED"


class SolverKind(StrEnum):
    DETERMINISTIC_MVP = "DETERMINISTIC_MVP"
    ZONED_LOCAL_SEARCH = "ZONED_LOCAL_SEARCH"
    CP_SAT = "CP_SAT"


class RulesetStatus(StrEnum):
    """A layout ruleset (ADR-025): DRAFT; APPROVED after an architect's review; PUBLISHED (one at a
    time, the only status production may use); RETIRED. Content never changes."""

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    RETIRED = "RETIRED"


class PlanGenerationState(StrEnum):
    """The concept plan generation lifecycle (CP1-04: its own, not Slice 3.1's). VALID is the
    only outcome that carries a plan, and only a plan the validator passed. INFEASIBLE: the
    requirement does not fit under the ruleset, with reasons. FAILED: an engine fault."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VALID = "VALID"
    INFEASIBLE = "INFEASIBLE"
    FAILED = "FAILED"


class PlanFailureReason(StrEnum):
    ENGINE_ERROR = "ENGINE_ERROR"
    ENGINE_INVALID_OUTPUT = "ENGINE_INVALID_OUTPUT"
    ENGINE_TIMEOUT = "ENGINE_TIMEOUT"
    STALE = "STALE"


class PlanValidity(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"


class ValidationCategory(StrEnum):
    SCHEMA = "SCHEMA"
    REFERENCES = "REFERENCES"
    GEOMETRY = "GEOMETRY"
    OPENINGS = "OPENINGS"
    FIXTURES = "FIXTURES"
    CIRCULATION = "CIRCULATION"
    DIMENSIONS = "DIMENSIONS"
    REQUIREMENTS = "REQUIREMENTS"


class ValidationSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


class RepairHint(StrEnum):
    AUTO = "AUTO"
    USER = "USER"
    NONE = "NONE"


class EntityKind(StrEnum):
    DOCUMENT = "DOCUMENT"
    PLOT = "PLOT"
    ENVELOPE = "ENVELOPE"
    NODE = "NODE"
    WALL = "WALL"
    ROOM = "ROOM"
    OPENING = "OPENING"
    FIXTURE = "FIXTURE"


class ValidationCode(StrEnum):
    SCHEMA_INVALID = "SCHEMA_INVALID"
    SCHEMA_VERSION_UNSUPPORTED = "SCHEMA_VERSION_UNSUPPORTED"
    ID_DUPLICATE = "ID_DUPLICATE"
    REF_MISSING = "REF_MISSING"
    PLOT_INVALID = "PLOT_INVALID"
    GEOMETRY_UNSUPPORTED_V1 = "GEOMETRY_UNSUPPORTED_V1"
    ROOM_POLYGON_INVALID = "ROOM_POLYGON_INVALID"
    ROOM_OVERLAP = "ROOM_OVERLAP"
    ROOM_OUTSIDE_ENVELOPE = "ROOM_OUTSIDE_ENVELOPE"
    BUILDING_OUTSIDE_PLOT = "BUILDING_OUTSIDE_PLOT"
    ROOM_EDGE_NOT_ON_WALL = "ROOM_EDGE_NOT_ON_WALL"
    WALL_ZERO_LENGTH = "WALL_ZERO_LENGTH"
    WALL_NOT_ORTHOGONAL = "WALL_NOT_ORTHOGONAL"
    WALL_OVERLAP = "WALL_OVERLAP"
    WALL_DANGLING_END = "WALL_DANGLING_END"
    WALL_THICKNESS_INVALID = "WALL_THICKNESS_INVALID"
    OPENING_HOST_MISSING = "OPENING_HOST_MISSING"
    OPENING_OUTSIDE_HOST = "OPENING_OUTSIDE_HOST"
    OPENING_OVERLAP = "OPENING_OVERLAP"
    OPENING_DIMENSION_INVALID = "OPENING_DIMENSION_INVALID"
    WINDOW_ON_INTERIOR_WALL = "WINDOW_ON_INTERIOR_WALL"
    FIXTURE_HOST_MISSING = "FIXTURE_HOST_MISSING"
    FIXTURE_NOT_ON_ROOM_WALL = "FIXTURE_NOT_ON_ROOM_WALL"
    FIXTURE_OUTSIDE_ROOM = "FIXTURE_OUTSIDE_ROOM"
    FIXTURE_NOT_PERMITTED_IN_ROOM = "FIXTURE_NOT_PERMITTED_IN_ROOM"
    FIXTURE_COUNT_EXCEEDS_SPEC = "FIXTURE_COUNT_EXCEEDS_SPEC"
    FIXTURE_OVERLAP = "FIXTURE_OVERLAP"
    FIXTURE_CLEARANCE_BLOCKED = "FIXTURE_CLEARANCE_BLOCKED"
    FIXTURE_BLOCKS_OPENING = "FIXTURE_BLOCKS_OPENING"
    ENTRANCE_MISSING = "ENTRANCE_MISSING"
    ROOM_UNREACHABLE = "ROOM_UNREACHABLE"
    ROOM_BELOW_MIN_SHORT_SIDE = "ROOM_BELOW_MIN_SHORT_SIDE"
    ROOM_BELOW_MIN_AREA = "ROOM_BELOW_MIN_AREA"
    PASSAGE_TOO_NARROW = "PASSAGE_TOO_NARROW"
    HABITABLE_ROOM_NO_WINDOW = "HABITABLE_ROOM_NO_WINDOW"
    ROOM_COUNT_MISMATCH = "ROOM_COUNT_MISMATCH"
    PARKING_MISSING = "PARKING_MISSING"
    PARKING_TOO_SMALL = "PARKING_TOO_SMALL"
    RELATION_UNMET = "RELATION_UNMET"


class PlanOpKind(StrEnum):
    """Typed HousePlan operations (CP1-11): the one way a plan changes after generation, shared by
    deterministic repair, the future editor and future natural-language edits."""

    MOVE_OPENING = "MOVE_OPENING"
    SET_OPENING = "SET_OPENING"
    ADD_OPENING = "ADD_OPENING"
    DELETE_OPENING = "DELETE_OPENING"
    MOVE_FIXTURE = "MOVE_FIXTURE"
    ADD_FIXTURE = "ADD_FIXTURE"
    DELETE_FIXTURE = "DELETE_FIXTURE"
    RENAME_ROOM = "RENAME_ROOM"
    SET_ROOM_TYPE = "SET_ROOM_TYPE"
    MOVE_WALL = "MOVE_WALL"
    ADD_ROOM = "ADD_ROOM"
    DELETE_ROOM = "DELETE_ROOM"
    MOVE_EDGE = "MOVE_EDGE"
    ADD_ROOM_OUTSIDE = "ADD_ROOM_OUTSIDE"
    REVERT_TO_REVISION = "REVERT_TO_REVISION"
    REVERT_TO_VERSION = "REVERT_TO_VERSION"


class PlanOpRejection(StrEnum):
    """Why a typed operation could not apply (Checkpoint 3). Rejection happens before validation;
    a plan that applies but breaks a rule is reported by the validator instead."""

    UNKNOWN_ENTITY = "UNKNOWN_ENTITY"
    ENTITY_EXISTS = "ENTITY_EXISTS"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    NO_MOVEMENT = "NO_MOVEMENT"
    NOT_AXIS_ALIGNED = "NOT_AXIS_ALIGNED"
    WALL_WOULD_COLLAPSE = "WALL_WOULD_COLLAPSE"
    HOSTED_ITEM_LEAVES_WALL = "HOSTED_ITEM_LEAVES_WALL"
    NOT_RECTANGULAR = "NOT_RECTANGULAR"
    HOSTED_ITEM_CHANGES_ROOMS = "HOSTED_ITEM_CHANGES_ROOMS"
    DOOR_DOES_NOT_FIT = "DOOR_DOES_NOT_FIT"
    ROOMS_WOULD_OVERLAP = "ROOMS_WOULD_OVERLAP"
    NOT_A_SLICE = "NOT_A_SLICE"
    ROOMS_NOT_MERGEABLE = "ROOMS_NOT_MERGEABLE"
    ROOM_TYPE_NOT_ALLOWED = "ROOM_TYPE_NOT_ALLOWED"
    REVERT_NOT_ALONE = "REVERT_NOT_ALONE"
    UNKNOWN_REVISION = "UNKNOWN_REVISION"
    # Checkpoint 3.1, E-5: a home keeps at least one kitchen and one bathroom or toilet
    LAST_KITCHEN_REQUIRED = "LAST_KITCHEN_REQUIRED"
    LAST_BATHROOM_REQUIRED = "LAST_BATHROOM_REQUIRED"
    # Checkpoint 3.2: a room added in open space against an outside wall
    NOT_ON_OUTSIDE_WALL = "NOT_ON_OUTSIDE_WALL"
    OUTSIDE_BUILDABLE_AREA = "OUTSIDE_BUILDABLE_AREA"


class RoomSide(StrEnum):
    """A side of a rectangular room in the plot frame (Checkpoint 3.1, MOVE_EDGE): LEFT is -x,
    RIGHT +x, FRONT the road side (-y), BACK +y."""

    LEFT = "LEFT"
    RIGHT = "RIGHT"
    FRONT = "FRONT"
    BACK = "BACK"


class ProgrammeChange(StrEnum):
    """A change the owner made to the requirement's room programme while editing (Checkpoint
    3.1), recorded as a HousePlan compromise (I-P6). The validator counts rooms against the
    requirement plus these recorded changes; the requirement itself is never modified."""

    ROOM_ADDED_BY_OWNER = "ROOM_ADDED_BY_OWNER"
    ROOM_REMOVED_BY_OWNER = "ROOM_REMOVED_BY_OWNER"
    ROOM_TYPE_CHANGED_BY_OWNER = "ROOM_TYPE_CHANGED_BY_OWNER"


class PlanOpReason(StrEnum):
    """Why an operation batch was applied (`house_plan_ops.reason`)."""

    USER = "USER"
    AUTO_REPAIR = "AUTO_REPAIR"
    REVERT = "REVERT"


class TopologyFamily(StrEnum):
    """Layout families the zoning engine can produce. Checkpoint 2: SPINE (front band, passage
    spine, columns, optional rear band) and FRONT_EXTENSION (one more room beside the entry room).
    Checkpoint 2.1: SIDE_WING (a spine with a public and service column and a private column),
    FRONT_LIVING_REAR_BEDROOM (compact: rooms entered from the living or dining room, no
    corridor), FRONT_PUBLIC_REAR_PRIVATE (public band, a cross corridor, a private band at the
    rear), L_CIRCULATION (a spine that turns into a rear cross corridor serving the private band)
    CENTRAL_LIVING_BEDROOM_WINGS (living and dining in the middle, room wings on both sides) and
    LINEAR_REAR_CORRIDOR (one row of rooms along the road, a corridor behind them, parking at an
    end: wide, shallow plots)."""

    SPINE = "SPINE"
    FRONT_EXTENSION = "FRONT_EXTENSION"
    SIDE_WING = "SIDE_WING"
    FRONT_LIVING_REAR_BEDROOM = "FRONT_LIVING_REAR_BEDROOM"
    FRONT_PUBLIC_REAR_PRIVATE = "FRONT_PUBLIC_REAR_PRIVATE"
    L_CIRCULATION = "L_CIRCULATION"
    CENTRAL_LIVING_BEDROOM_WINGS = "CENTRAL_LIVING_BEDROOM_WINGS"
    LINEAR_REAR_CORRIDOR = "LINEAR_REAR_CORRIDOR"


class FeasibilityClass(StrEnum):
    """PROVEN: no rectangle arrangement can satisfy the hard rules. NO_SUPPORTED_LAYOUT: none of
    the layouts this engine version can produce fits (CP2-U4); never presented as impossible."""

    PROVEN = "PROVEN"
    NO_SUPPORTED_LAYOUT = "NO_SUPPORTED_LAYOUT"


class RepairReason(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    OBJECTIVE = "OBJECTIVE"


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
    ClarificationState, ComparisonState, StageUpdateKind, PaymentMarkSide, PaymentMarkValue,
    AppointmentStatus, ChecklistStatus, InspectionKind, InspectionState, InspectionCancelReason,
    CheckpointResult, Severity, NcState, HandoverState, HandoverDocumentKind, BuildRecordState,
    BuildRecordBasis, Facing, SetbackSide, PlotEdgeKind, SetbackSource, ParkingKind,
    ParkingPlacement, OriginKind, RoomType, Zone, WallKind, OpeningKind, DoorLeaf, HingeSide,
    WallSide, FixtureType, ConstraintKind, ConstraintStrength, ConstraintOutcome, RelationKind,
    OrientationMode, DiningArrangement, KitchenArrangement, StairChoice, DesignInputKey,
    MissingInputReason, UnsupportedReason, InfeasibleReason, PlanSource, SolverKind, RulesetStatus,
    PlanGenerationState, PlanFailureReason, PlanValidity, ValidationCategory, ValidationSeverity,
    RepairHint, EntityKind, ValidationCode, PlanOpKind, TopologyFamily, FeasibilityClass,
    RepairReason, PlanOpRejection, PlanOpReason, RoomSide, ProgrammeChange,
)  # fmt: skip
