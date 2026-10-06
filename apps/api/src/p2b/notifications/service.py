"""Email notifications for review events (ruling 2.8; EVENT_AND_BACKGROUND_JOB_ARCHITECTURE
section 5). An outbox subscriber turns each event into one job per notification kind; the job
renders a template, finds the recipient at send time, and sends through the configured
`MessageProvider` (Mailpit locally, Resend in production).

Recipients: operations notifications go to `P2B_OPS_NOTIFICATION_EMAIL`, and are skipped with a
log line when it is not configured (no address is ever guessed). Family notifications go to the
account's primary email.

Templates live beside this module; their wording is a draft awaiting the product owner's approval
(FOUNDATION_PLAN section 4e).
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum
from importlib import resources
from string import Template

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.assurance.interface import assurance_notice
from p2b.buildplan.interface import issued_notice
from p2b.construction.interface import execution_notice
from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.messaging import EmailMessage, MessageProvider
from p2b.engagements.interface import connection_notice, quote_review_notice
from p2b.identity.interface import primary_emails
from p2b.projects.interface import enquiry_summary, review_snapshots
from p2b.rfq.interface import contractor_notice, family_notice, ops_notice

log = structlog.get_logger(__name__)


class Kind(StrEnum):
    OPS_REQUIREMENT_SUBMITTED = "ops_requirement_submitted"
    OPS_REQUIREMENT_FLAGGED = "ops_requirement_flagged"
    OPS_ENQUIRY_RECEIVED = "ops_enquiry_received"
    FAMILY_NEEDS_INFO = "family_needs_info"
    FAMILY_ACCEPTED = "family_accepted"
    FAMILY_CANCELLED = "family_cancelled"
    # Connections (Slice 3.4, N-11): transactional only, nothing private before acceptance.
    FAMILY_CONNECTION_SENT = "family_connection_sent"
    FAMILY_CONNECTION_ACCEPTED = "family_connection_accepted"
    FAMILY_CONNECTION_DECLINED = "family_connection_declined"
    FAMILY_CONNECTION_EXPIRED = "family_connection_expired"
    FAMILY_CONNECTION_WITHDRAWN = "family_connection_withdrawn"
    PRO_CONNECTION_RECEIVED = "pro_connection_received"
    PRO_CONNECTION_WITHDRAWN = "pro_connection_withdrawn"
    OPS_QUOTE_REVIEW_SUBMITTED = "ops_quote_review_submitted"
    FAMILY_BUILD_PLAN_ISSUED = "family_build_plan_issued"  # Slice 3.5
    # RFQs (Slice 3.6, SLICE3_6_READINESS R): one email per event; nothing private before
    # selection; a contractor's email never names a winner, a price or a ranking (QD-20).
    FAMILY_RFQ_ISSUED = "family_rfq_issued"
    FAMILY_COMPARISON_PUBLISHED = "family_comparison_published"
    FAMILY_SELECTION_CONFIRMED = "family_selection_confirmed"
    FAMILY_RFQ_CANCELLED = "family_rfq_cancelled"
    PRO_RFQ_INVITATION = "pro_rfq_invitation"
    PRO_RFQ_CLOSED = "pro_rfq_closed"
    PRO_RFQ_DEADLINE_EXTENDED = "pro_rfq_deadline_extended"
    PRO_RFQ_QUESTION = "pro_rfq_question"
    PRO_RFQ_ANSWER = "pro_rfq_answer"
    PRO_RFQ_SHARED_ANSWER = "pro_rfq_shared_answer"
    PRO_QUOTE_CAPTURED = "pro_quote_captured"
    PRO_QUOTE_EXPIRED = "pro_quote_expired"
    PRO_QUOTE_SELECTED = "pro_quote_selected"
    PRO_QUOTE_NOT_SELECTED = "pro_quote_not_selected"
    OPS_RFQ_REQUESTED = "ops_rfq_requested"
    OPS_QUOTE_SUBMITTED = "ops_quote_submitted"
    OPS_QUOTE_WITHDRAWN = "ops_quote_withdrawn"
    OPS_RFQ_CLARIFICATION = "ops_rfq_clarification"
    OPS_RFQ_DEADLINE_REACHED = "ops_rfq_deadline_reached"
    OPS_SELECTION_CONFIRMED = "ops_selection_confirmed"
    # Execution (Slice 3.7A, SLICE3_7_READINESS O): no reminders, no amounts.
    FAMILY_STAGE_COMPLETION_REQUESTED = "family_stage_completion_requested"
    FAMILY_PAYMENT_MILESTONE_DUE = "family_payment_milestone_due"
    PRO_STAGE_CONFIRMED = "pro_stage_confirmed"
    PRO_STAGE_RETURNED = "pro_stage_returned"
    PRO_PAYMENT_MARKED_PAID = "pro_payment_marked_paid"
    OPS_GATE_COMPLETION_REQUESTED = "ops_gate_completion_requested"
    # Assurance (Slice 3.7B, SLICE3_7_READINESS O): no finding text in any email.
    FAMILY_INSPECTION_SCHEDULED = "family_inspection_scheduled"
    FAMILY_INSPECTION_CANCELLED = "family_inspection_cancelled"
    FAMILY_INSPECTION_REPORT = "family_inspection_report"
    PRO_INSPECTION_SCHEDULED = "pro_inspection_scheduled"
    PRO_REINSPECTION_SCHEDULED = "pro_reinspection_scheduled"
    PRO_FINDINGS = "pro_findings"
    PRO_FINDINGS_CLOSED = "pro_findings_closed"
    PRO_GATE_CLEARED = "pro_gate_cleared"
    AUDITOR_INSPECTION_ASSIGNED = "auditor_inspection_assigned"
    AUDITOR_INSPECTION_RETURNED = "auditor_inspection_returned"
    AUDITOR_INSPECTION_CANCELLED = "auditor_inspection_cancelled"
    OPS_INSPECTION_SUBMITTED = "ops_inspection_submitted"
    OPS_RECTIFICATION_SUBMITTED = "ops_rectification_submitted"


OPS_KINDS = frozenset(
    {
        Kind.OPS_REQUIREMENT_SUBMITTED,
        Kind.OPS_REQUIREMENT_FLAGGED,
        Kind.OPS_ENQUIRY_RECEIVED,
        Kind.OPS_QUOTE_REVIEW_SUBMITTED,
    }
)
CONNECTION_KINDS = frozenset(
    {
        Kind.FAMILY_CONNECTION_SENT,
        Kind.FAMILY_CONNECTION_ACCEPTED,
        Kind.FAMILY_CONNECTION_DECLINED,
        Kind.FAMILY_CONNECTION_EXPIRED,
        Kind.FAMILY_CONNECTION_WITHDRAWN,
        Kind.PRO_CONNECTION_RECEIVED,
        Kind.PRO_CONNECTION_WITHDRAWN,
    }
)
PRO_KINDS = frozenset({Kind.PRO_CONNECTION_RECEIVED, Kind.PRO_CONNECTION_WITHDRAWN})
# RFQ notices (`rfq.<audience>_notice`, payload `notice`) to their notification kind.
RFQ_NOTICES: dict[str, dict[str, Kind]] = {
    "rfq.family_notice": {
        "RFQ_ISSUED": Kind.FAMILY_RFQ_ISSUED,
        "COMPARISON_PUBLISHED": Kind.FAMILY_COMPARISON_PUBLISHED,
        "SELECTION_CONFIRMED": Kind.FAMILY_SELECTION_CONFIRMED,
        "RFQ_CANCELLED": Kind.FAMILY_RFQ_CANCELLED,
    },
    "rfq.contractor_notice": {
        "INVITATION": Kind.PRO_RFQ_INVITATION,
        "RFQ_CLOSED": Kind.PRO_RFQ_CLOSED,
        "DEADLINE_EXTENDED": Kind.PRO_RFQ_DEADLINE_EXTENDED,
        "QUESTION": Kind.PRO_RFQ_QUESTION,
        "ANSWER": Kind.PRO_RFQ_ANSWER,
        "SHARED_ANSWER": Kind.PRO_RFQ_SHARED_ANSWER,
        "QUOTE_CAPTURED": Kind.PRO_QUOTE_CAPTURED,
        "QUOTE_EXPIRED": Kind.PRO_QUOTE_EXPIRED,
        "SELECTED": Kind.PRO_QUOTE_SELECTED,
        "NOT_SELECTED": Kind.PRO_QUOTE_NOT_SELECTED,
    },
    "rfq.ops_notice": {
        "RFQ_REQUESTED": Kind.OPS_RFQ_REQUESTED,
        "QUOTE_SUBMITTED": Kind.OPS_QUOTE_SUBMITTED,
        "QUOTE_WITHDRAWN": Kind.OPS_QUOTE_WITHDRAWN,
        "CLARIFICATION": Kind.OPS_RFQ_CLARIFICATION,
        "DEADLINE_REACHED": Kind.OPS_RFQ_DEADLINE_REACHED,
        "SELECTION_CONFIRMED": Kind.OPS_SELECTION_CONFIRMED,
    },
}
RFQ_KINDS = {kind: event for event, kinds in RFQ_NOTICES.items() for kind in kinds.values()}
# Execution notices (`construction.<audience>_notice`, payload `notice`, Slice 3.7A).
EXECUTION_NOTICES: dict[str, dict[str, Kind]] = {
    "construction.family_notice": {
        "COMPLETION_REQUESTED": Kind.FAMILY_STAGE_COMPLETION_REQUESTED,
        "PAYMENT_DUE": Kind.FAMILY_PAYMENT_MILESTONE_DUE,
    },
    "construction.contractor_notice": {
        "STAGE_CONFIRMED": Kind.PRO_STAGE_CONFIRMED,
        "STAGE_RETURNED": Kind.PRO_STAGE_RETURNED,
        "MARKED_PAID": Kind.PRO_PAYMENT_MARKED_PAID,
    },
    "construction.ops_notice": {
        "GATE_COMPLETION_REQUESTED": Kind.OPS_GATE_COMPLETION_REQUESTED,
    },
}
EXECUTION_KINDS = {
    kind: event.removeprefix("construction.").removesuffix("_notice")
    for event, kinds in EXECUTION_NOTICES.items()
    for kind in kinds.values()
}
# Assurance notices (`assurance.<audience>_notice`, payload `notice`, Slice 3.7B).
ASSURANCE_NOTICES: dict[str, dict[str, Kind]] = {
    "assurance.family_notice": {
        "INSPECTION_SCHEDULED": Kind.FAMILY_INSPECTION_SCHEDULED,
        "INSPECTION_CANCELLED": Kind.FAMILY_INSPECTION_CANCELLED,
        "REPORT_APPROVED": Kind.FAMILY_INSPECTION_REPORT,
    },
    "assurance.contractor_notice": {
        "INSPECTION_SCHEDULED": Kind.PRO_INSPECTION_SCHEDULED,
        "REINSPECTION_SCHEDULED": Kind.PRO_REINSPECTION_SCHEDULED,
        "FINDINGS": Kind.PRO_FINDINGS,
        "FINDINGS_CLOSED": Kind.PRO_FINDINGS_CLOSED,
        "GATE_CLEARED": Kind.PRO_GATE_CLEARED,
    },
    "assurance.auditor_notice": {
        "INSPECTION_ASSIGNED": Kind.AUDITOR_INSPECTION_ASSIGNED,
        "INSPECTION_RETURNED": Kind.AUDITOR_INSPECTION_RETURNED,
        "INSPECTION_CANCELLED": Kind.AUDITOR_INSPECTION_CANCELLED,
    },
    "assurance.ops_notice": {
        "INSPECTION_SUBMITTED": Kind.OPS_INSPECTION_SUBMITTED,
        "RECTIFICATION_SUBMITTED": Kind.OPS_RECTIFICATION_SUBMITTED,
    },
}
ASSURANCE_KINDS = {
    kind: event.removeprefix("assurance.").removesuffix("_notice")
    for event, kinds in ASSURANCE_NOTICES.items()
    for kind in kinds.values()
}
NOTICES = {**RFQ_NOTICES, **EXECUTION_NOTICES, **ASSURANCE_NOTICES}

# Event type to the notifications it produces. `requirement.submitted` with review flags also
# produces the flagged notice.
BY_EVENT: dict[str, tuple[Kind, ...]] = {
    "requirement.submitted": (Kind.OPS_REQUIREMENT_SUBMITTED,),
    "enquiry.created": (Kind.OPS_ENQUIRY_RECEIVED,),
    "project.needs_info": (Kind.FAMILY_NEEDS_INFO,),
    "project.accepted": (Kind.FAMILY_ACCEPTED,),
    "project.cancelled": (Kind.FAMILY_CANCELLED,),
    "connection.sent": (Kind.FAMILY_CONNECTION_SENT, Kind.PRO_CONNECTION_RECEIVED),
    "connection.accepted": (Kind.FAMILY_CONNECTION_ACCEPTED,),
    "connection.declined": (Kind.FAMILY_CONNECTION_DECLINED,),
    "connection.expired": (Kind.FAMILY_CONNECTION_EXPIRED,),
    "connection.withdrawn": (Kind.FAMILY_CONNECTION_WITHDRAWN, Kind.PRO_CONNECTION_WITHDRAWN),
    "quote_review.submitted": (Kind.OPS_QUOTE_REVIEW_SUBMITTED,),
    "buildplan.issued": (Kind.FAMILY_BUILD_PLAN_ISSUED,),
    # Slice 3.6: the kind comes from the payload's notice (kinds_for).
    "rfq.family_notice": (),
    "rfq.contractor_notice": (),
    "rfq.ops_notice": (),
    # Slice 3.7A: likewise.
    "construction.family_notice": (),
    "construction.contractor_notice": (),
    "construction.ops_notice": (),
    # Slice 3.7B: likewise.
    "assurance.family_notice": (),
    "assurance.contractor_notice": (),
    "assurance.auditor_notice": (),
    "assurance.ops_notice": (),
}

FLAG_LABELS = {
    "PROPERTY_TYPE_OTHER": "Other property type",
    "CONSTRUCTION_STARTED": "Construction started",
}


def kinds_for(event_type: str, payload: dict[str, object]) -> list[Kind]:
    if event_type in NOTICES:
        kind = NOTICES[event_type].get(str(payload.get("notice")))
        return [kind] if kind else []
    kinds = list(BY_EVENT.get(event_type, ()))
    if event_type == "requirement.submitted" and payload.get("review_flags"):
        kinds.append(Kind.OPS_REQUIREMENT_FLAGGED)
    if event_type == "connection.withdrawn" and payload.get("reason") == "FAMILY":
        kinds.remove(Kind.FAMILY_CONNECTION_WITHDRAWN)  # the family did it themselves
    return kinds


def render(kind: Kind, to: str, idempotency_key: str, values: dict[str, str]) -> EmailMessage:
    raw = (
        resources.files("p2b.notifications")
        .joinpath(f"templates/{kind.value}.en.txt")
        .read_text("utf-8")
    )
    subject, _, body = raw.partition("\n---\n")
    return EmailMessage(
        to=to,
        subject=Template(subject.strip()).substitute(values),
        text=Template(body).substitute(values),
        idempotency_key=idempotency_key,
    )


@dataclass(frozen=True)
class Prepared:
    to: str | None
    values: dict[str, str]


async def _prepare(
    session: AsyncSession,
    settings: Settings,
    kind: Kind,
    ref_id: uuid.UUID,
    payload: dict[str, object],
) -> Prepared:
    if kind in CONNECTION_KINDS:
        notice = await connection_notice(session, ref_id)
        if notice is None:
            return Prepared(None, {})
        values = {
            "code": notice.project_code,
            "category": notice.category_name,
            "locality": notice.locality,
            "professional": notice.professional_name,
            "hours": str(notice.respond_hours),
        }
        user_id = notice.professional_user_id if kind in PRO_KINDS else notice.family_user_id
        return Prepared((await primary_emails(session, [user_id])).get(user_id), values)
    if kind in RFQ_KINDS:
        event = RFQ_KINDS[kind]
        if event == "rfq.contractor_notice":
            rfq_notice = await contractor_notice(session, ref_id)
        elif event == "rfq.family_notice":
            rfq_notice = await family_notice(session, ref_id)
        else:
            rfq_notice = await ops_notice(session, ref_id)
        if rfq_notice is None:
            return Prepared(None, {})
        if rfq_notice.user_id is None:
            return Prepared(settings.ops_notification_email, rfq_notice.values)
        to = (await primary_emails(session, [rfq_notice.user_id])).get(rfq_notice.user_id)
        return Prepared(to, rfq_notice.values)
    if kind in ASSURANCE_KINDS:
        found = await assurance_notice(session, ASSURANCE_KINDS[kind], ref_id, payload)
        if found is None:
            return Prepared(None, {})
        if found.user_id is None:
            return Prepared(settings.ops_notification_email, found.values)
        to = (await primary_emails(session, [found.user_id])).get(found.user_id)
        return Prepared(to, found.values)
    if kind in EXECUTION_KINDS:
        stage = await execution_notice(session, EXECUTION_KINDS[kind], ref_id, payload)
        if stage is None:
            return Prepared(None, {})
        if stage.user_id is None:
            return Prepared(settings.ops_notification_email, stage.values)
        to = (await primary_emails(session, [stage.user_id])).get(stage.user_id)
        return Prepared(to, stage.values)
    if kind == Kind.FAMILY_BUILD_PLAN_ISSUED:
        issued = await issued_notice(session, ref_id)
        if issued is None:
            return Prepared(None, {})
        values = {"code": issued.project_code, "version": str(issued.version_no)}
        owner = (await primary_emails(session, [issued.owner_user_id])).get(issued.owner_user_id)
        return Prepared(owner, values)
    if kind == Kind.OPS_QUOTE_REVIEW_SUBMITTED:
        review = await quote_review_notice(session, ref_id)
        if review is None:
            return Prepared(None, {})
        values = {"code": review.project_code, "category": review.category_name}
        return Prepared(settings.ops_notification_email, values)
    if kind == Kind.OPS_ENQUIRY_RECEIVED:
        enquiry = await enquiry_summary(session, ref_id)
        if enquiry is None:
            return Prepared(None, {})
        values = {
            "kind": enquiry.kind.value,
            "work_type": enquiry.work_type.value if enquiry.work_type else "not applicable",
            "email": enquiry.email,
        }
        return Prepared(settings.ops_notification_email, values)
    snapshot = (await review_snapshots(session, [ref_id])).get(ref_id)
    if snapshot is None:
        return Prepared(None, {})
    flags = [FLAG_LABELS.get(flag, flag) for flag in snapshot.review_flags]
    values = {
        "code": snapshot.code,
        "locality": snapshot.locality or "not given",
        "flags": ", ".join(flags) if flags else "none",
        "message": str(payload.get("message") or ""),
    }
    if kind in OPS_KINDS:
        return Prepared(settings.ops_notification_email, values)
    owner = (await primary_emails(session, [snapshot.owner_user_id])).get(snapshot.owner_user_id)
    return Prepared(owner, values)


async def send_notification(
    database: Database,
    settings: Settings,
    provider: MessageProvider,
    *,
    kind: Kind,
    event_id: uuid.UUID,
    ref_id: uuid.UUID,
    payload: dict[str, object],
) -> bool:
    """Send one notification. False when there is nobody to send to (no operations mailbox
    configured, no email on the account, or the record is gone). The provider idempotency key
    is the event and kind, so a retried job sends once where the provider supports it."""
    async with database.transaction() as session:
        prepared = await _prepare(session, settings, kind, ref_id, payload)
    if prepared.to is None:
        log.info("notification.skipped", kind=kind.value, reason="no recipient")
        return False
    message = render(kind, prepared.to, f"{kind.value}:{event_id}", prepared.values)
    await provider.send_email(message)
    log.info("notification.sent", kind=kind.value)
    return True
