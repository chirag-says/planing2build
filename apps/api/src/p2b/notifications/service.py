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

from p2b.buildplan.interface import issued_notice
from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.messaging import EmailMessage, MessageProvider
from p2b.engagements.interface import connection_notice, quote_review_notice
from p2b.identity.interface import primary_emails
from p2b.projects.interface import enquiry_summary, review_snapshots

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
}

FLAG_LABELS = {
    "PROPERTY_TYPE_OTHER": "Other property type",
    "CONSTRUCTION_STARTED": "Construction started",
}


def kinds_for(event_type: str, payload: dict[str, object]) -> list[Kind]:
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
