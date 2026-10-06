"""The RFQ and its invitations (SLICE3_6_READINESS D, E, F, T.1, T.2).

The owner requests contractor quotes and nominates listed contractors; operations may introduce
another with a written reason, set the deadline and issue (QD-03). At issue the ACCEPTED Build
Plan version's contractor manifest is frozen into the RFQ with its sha256; a later version never
changes it (BP-05, QD-15, QD-16). At most `rfq_max_recipients` live invitations (QD-04). While
the category has an ACTIVE engagement, only that party may quote (QD-13). An invitation answered
within `rfq_invitation_response_hours` or it expires (QD-05)."""

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.buildplan.interface import accepted_manifest
from p2b.core.config import Settings
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.vocabulary import (
    DeclineReason,
    EngagementParty,
    InvitationSource,
    InvitationState,
    InvitationWithdrawReason,
    NeedState,
    QuoteCheckState,
    QuoteVersionState,
    RfqCancelReason,
    RfqState,
)
from p2b.engagements.interface import EngagementFacts, active_engagement, lock_category
from p2b.identity.interface import Actor, primary_emails
from p2b.professionals.interface import connection_candidate, profile_by_user
from p2b.projects.interface import ConnectionFacts
from p2b.rfq import common
from p2b.rfq.common import (
    CATEGORY,
    INVITATION,
    LIVE_INVITATIONS,
    OPEN_RFQ,
    QUOTE,
    REVIEW,
    RFQ,
    SYSTEM,
    Who,
    conflict,
    db_now,
    history,
    notify,
    require_package,
)
from p2b.rfq.models import QuoteDraft, QuoteVersion, Rfq, RfqClarification, RfqInvitation

I = InvitationState  # noqa: E741
R = RfqState

INVITE_BLOCKERS = {
    "NOT_LISTED": "This contractor is not listed for contractor work.",
    "OUTSIDE_AREA": "This contractor does not serve the project's area.",
    "NO_LOCATION": "The project has no plot location.",
    "SELF": "You cannot invite yourself.",
    "DUPLICATE": "This contractor is already invited.",
    "LIMIT": "The RFQ already has the most contractors allowed.",
    "ENGAGED": "The category has an active contractor; only that contractor may quote.",
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


async def rfq_row(session: AsyncSession, rfq_id: uuid.UUID, *, lock: bool = False) -> Rfq:
    row = await session.get(Rfq, rfq_id, with_for_update=lock)
    if row is None:
        raise NotFound
    if lock:
        await session.refresh(row)
    return row


async def invitations_of(
    session: AsyncSession, rfq_id: uuid.UUID, *, lock: bool = False
) -> list[RfqInvitation]:
    query = (
        select(RfqInvitation)
        .where(RfqInvitation.rfq_id == rfq_id)
        .order_by(RfqInvitation.created_at, RfqInvitation.id)
    )
    return list(await session.scalars(query.with_for_update() if lock else query))


async def _move_rfq(
    session: AsyncSession, rfq: Rfq, trigger: str, who: Who, reason: str | None = None
) -> None:
    old = rfq.state
    rfq.state = RFQ.target(R(old), trigger).value
    rfq.version += 1
    await session.flush()
    await history(
        session, project_id=rfq.project_id, rfq_id=rfq.id, subject="RFQ", subject_id=rfq.id,
        old=old, new=rfq.state, who=who, reason=reason,
    )  # fmt: skip


async def move_invitation(
    session: AsyncSession, inv: RfqInvitation, trigger: str, who: Who, reason: str | None = None
) -> None:
    old = inv.state
    inv.state = INVITATION.target(I(old), trigger).value
    inv.version += 1
    await session.flush()
    await history(
        session, project_id=inv.project_id, rfq_id=inv.rfq_id, subject="INVITATION",
        subject_id=inv.id, old=old, new=inv.state, who=who, reason=reason,
    )  # fmt: skip


async def _invite_blocker(
    session: AsyncSession,
    facts: ConnectionFacts,
    profile_id: uuid.UUID,
    existing: list[RfqInvitation],
    engaged: EngagementFacts | None,
    max_recipients: int,
) -> str | None:
    """Why this contractor cannot be invited now (a key of INVITE_BLOCKERS), else None."""
    if any(i.profile_id == profile_id for i in existing):
        return "DUPLICATE"
    if engaged is not None and engaged.profile_id != profile_id:
        return "ENGAGED"
    if sum(i.state in LIVE_INVITATIONS for i in existing) >= max_recipients:
        return "LIMIT"
    if facts.point is None:
        return "NO_LOCATION"
    candidate = await connection_candidate(session, profile_id, CATEGORY, facts.point)
    if candidate is None or not candidate.listed or candidate.hidden:
        return "NOT_LISTED"
    if candidate.user_id == facts.owner_user_id:
        return "SELF"
    if not candidate.covers:
        return "OUTSIDE_AREA"
    return None


def _brief(facts: ConnectionFacts) -> dict[str, Any]:
    """The connection-style brief (QD-09): no name, contact, address, pin, drawings or files."""
    return {**facts.brief, "category": CATEGORY, "build_plan_accepted": True}


async def _add_invitation(
    session: AsyncSession,
    who: Who,
    rfq: Rfq,
    facts: ConnectionFacts,
    *,
    source: InvitationSource,
    profile_id: uuid.UUID | None = None,
    engagement_id: uuid.UUID | None = None,
    reason: str | None = None,
) -> RfqInvitation:
    inv = RfqInvitation(
        id=new_id(),
        rfq_id=rfq.id,
        project_id=rfq.project_id,
        party=(EngagementParty.LISTED if profile_id else EngagementParty.OUTSIDE).value,
        profile_id=profile_id,
        engagement_id=engagement_id,
        source=source.value,
        introduced_reason=reason,
        state=I.PROPOSED.value,
        brief=_brief(facts),
        created_by=who.user_id,
    )
    session.add(inv)
    await session.flush()
    await history(
        session, project_id=rfq.project_id, rfq_id=rfq.id, subject="INVITATION",
        subject_id=inv.id, old=None, new=inv.state, who=who, reason=reason,
        detail={"source": source.value},
    )  # fmt: skip
    return inv


async def request(
    session: AsyncSession,
    settings: Settings,
    who: Who,
    facts: ConnectionFacts,
    profile_ids: list[uuid.UUID],
) -> Rfq:
    """The owner (or operations at the owner's direction) asks for contractor quotes: a DRAFT RFQ
    on the ACCEPTED Build Plan version with the nominated contractors PROPOSED."""
    await require_package(session, facts.project_id)
    need = await lock_category(session, facts.project_id, CATEGORY)
    if need == NeedState.NOT_NEEDED:
        raise conflict("NOT_NEEDED", "You marked contractor work as not needed.")
    baseline = await accepted_manifest(session, facts.project_id)
    if baseline is None:
        raise conflict(
            "NO_ACCEPTED_VERSION", "Contractor quotes need an accepted Build Plan (BP-08)."
        )
    open_now = await session.scalar(
        select(func.count())
        .select_from(Rfq)
        .where(Rfq.project_id == facts.project_id, Rfq.state.in_(OPEN_RFQ))
    )
    if open_now:
        raise conflict("OPEN_RFQ", "A request for contractor quotes is already open.")
    wanted = list(dict.fromkeys(profile_ids))
    engaged = await active_engagement(session, facts.project_id, CATEGORY)
    rfq = Rfq(
        id=new_id(),
        project_id=facts.project_id,
        category_code=CATEGORY,
        build_plan_version_id=baseline.version_id,
        state=RFQ.target(None, "request").value,
        max_recipients=settings.rfq_max_recipients,
        requested_by=who.user_id,
        requested_role=who.role,
    )
    session.add(rfq)
    await session.flush()
    await history(
        session, project_id=rfq.project_id, rfq_id=rfq.id, subject="RFQ", subject_id=rfq.id,
        old=None, new=rfq.state, who=who, detail={"build_plan_version": baseline.version_no},
    )  # fmt: skip
    added: list[RfqInvitation] = []
    if engaged is not None:  # QD-13: only the engaged party may quote
        if engaged.party == EngagementParty.OUTSIDE.value:
            if wanted:
                raise conflict("ENGAGED", INVITE_BLOCKERS["ENGAGED"])
            added.append(
                await _add_invitation(
                    session, who, rfq, facts, source=InvitationSource.ENGAGED,
                    engagement_id=engaged.id,
                )
            )  # fmt: skip
        else:
            assert engaged.profile_id is not None  # noqa: S101 (LISTED has a profile)
            if any(p != engaged.profile_id for p in wanted):
                raise conflict("ENGAGED", INVITE_BLOCKERS["ENGAGED"])
            wanted = [engaged.profile_id]
    for profile_id in wanted:
        blocker = await _invite_blocker(
            session, facts, profile_id, added, engaged, rfq.max_recipients
        )
        if blocker is not None:
            raise conflict(blocker, INVITE_BLOCKERS[blocker], profile_id=str(profile_id))
        source = (
            InvitationSource.ENGAGED
            if engaged is not None and engaged.profile_id == profile_id
            else InvitationSource.NOMINATED
        )
        added.append(
            await _add_invitation(session, who, rfq, facts, source=source, profile_id=profile_id)
        )
    if who.role == "FAMILY":
        await notify(session, "ops", "RFQ_REQUESTED", aggregate_id=rfq.id, rfq_id=rfq.id)
    return rfq


async def set_deadline(session: AsyncSession, who: Who, rfq_id: uuid.UUID, due: datetime) -> Rfq:
    rfq = await rfq_row(session, rfq_id, lock=True)
    if rfq.state != R.DRAFT.value:
        raise StateConflict(details={"current_state": rfq.state})
    if due <= await db_now(session):
        raise ValidationFailed(details={"fields": {"quotes_due_at": ["Choose a future time."]}})
    rfq.quotes_due_at = due
    rfq.version += 1
    await session.flush()
    await history(
        session, project_id=rfq.project_id, rfq_id=rfq.id, subject="RFQ", subject_id=rfq.id,
        old=rfq.state, new=rfq.state, who=who, reason="deadline set",
        detail={"quotes_due_at": due.isoformat()},
    )  # fmt: skip
    return rfq


async def _send(
    session: AsyncSession, settings: Settings, inv: RfqInvitation, who: Who, now: datetime
) -> None:
    inv.sent_at = now
    inv.respond_by = now + timedelta(hours=settings.rfq_invitation_response_hours)
    await move_invitation(session, inv, "send", who)
    await notify(
        session, "contractor", "INVITATION", aggregate_id=inv.id, rfq_id=inv.rfq_id, ref_id=inv.id
    )


async def introduce(
    session: AsyncSession,
    settings: Settings,
    who: Who,
    rfq_id: uuid.UUID,
    profile_id: uuid.UUID,
    reason: str,
) -> RfqInvitation:
    """Operations add a contractor with a written reason (QD-03): PROPOSED on a DRAFT, sent at
    once on an ISSUED RFQ before its deadline."""
    rfq = await rfq_row(session, rfq_id, lock=True)
    if rfq.state not in OPEN_RFQ:
        raise StateConflict(details={"current_state": rfq.state})
    now = await db_now(session)
    if rfq.state == R.ISSUED.value and rfq.quotes_due_at and rfq.quotes_due_at <= now:
        raise conflict("DEADLINE_PASSED", "The quote deadline has passed.")
    await require_package(session, rfq.project_id)
    facts = await common.project(session, rfq.project_id)
    await lock_category(session, rfq.project_id, CATEGORY)
    engaged = await active_engagement(session, rfq.project_id, CATEGORY)
    existing = await invitations_of(session, rfq.id)
    blocker = await _invite_blocker(
        session, facts, profile_id, existing, engaged, rfq.max_recipients
    )
    if blocker is not None:
        raise conflict(blocker, INVITE_BLOCKERS[blocker], profile_id=str(profile_id))
    inv = await _add_invitation(
        session, who, rfq, facts, source=InvitationSource.INTRODUCED, profile_id=profile_id,
        reason=reason,
    )  # fmt: skip
    if rfq.state == R.ISSUED.value:
        await _send(session, settings, inv, who, now)
    return inv


async def issue(session: AsyncSession, settings: Settings, who: Who, rfq_id: uuid.UUID) -> Rfq:
    """Freeze the pack and send the invitations (T.1 DRAFT to ISSUED)."""
    rfq = await rfq_row(session, rfq_id, lock=True)
    if rfq.state != R.DRAFT.value:
        raise StateConflict(details={"current_state": rfq.state})
    await require_package(session, rfq.project_id)
    now = await db_now(session)
    if rfq.quotes_due_at is None or rfq.quotes_due_at <= now:
        raise conflict("NO_DEADLINE", "Set a quote deadline in the future first.")
    baseline = await accepted_manifest(session, rfq.project_id)
    if baseline is None or baseline.version_id != rfq.build_plan_version_id:
        raise conflict("BASELINE_CHANGED", "The accepted Build Plan version has changed.")
    facts = await common.project(session, rfq.project_id)
    invitations = [i for i in await invitations_of(session, rfq.id, lock=True)
                   if i.state == I.PROPOSED.value]  # fmt: skip
    if not invitations:
        raise conflict("NO_RECIPIENTS", "Add at least one contractor.")
    for inv in invitations:
        if inv.profile_id is None:
            continue
        candidate = await connection_candidate(
            session, inv.profile_id, CATEGORY, facts.point or (0.0, 0.0)
        )
        if candidate is None or not candidate.listed or candidate.hidden or not candidate.covers:
            raise conflict(
                "NOT_ELIGIBLE", "A proposed contractor is no longer eligible.",
                profile_id=str(inv.profile_id),
            )  # fmt: skip
    rfq.manifest = baseline.manifest
    rfq.manifest_sha256 = sha256(baseline.manifest)
    rfq.issued_by = who.user_id
    rfq.issued_at = now
    await _move_rfq(session, rfq, "issue", who)
    for inv in invitations:
        if inv.profile_id is None:  # the family's outside contractor: operations capture
            inv.responded_at = now
            await move_invitation(session, inv, "capture", who, "outside party: staff capture")
        else:
            await _send(session, settings, inv, who, now)
    await notify(session, "family", "RFQ_ISSUED", aggregate_id=rfq.id, rfq_id=rfq.id)
    return rfq


async def extend_deadline(
    session: AsyncSession, who: Who, rfq_id: uuid.UUID, due: datetime, reason: str
) -> Rfq:
    """QD-05: audited, and every affected recipient gets the same notice."""
    rfq = await rfq_row(session, rfq_id, lock=True)
    if rfq.state != R.ISSUED.value:
        raise StateConflict(details={"current_state": rfq.state})
    now = await db_now(session)
    if due <= now or (rfq.quotes_due_at is not None and due <= rfq.quotes_due_at):
        raise ValidationFailed(
            details={"fields": {"quotes_due_at": ["Choose a time after the current deadline."]}}
        )
    old = rfq.quotes_due_at
    rfq.quotes_due_at = due
    rfq.deadline_noticed_at = None
    rfq.version += 1
    await session.flush()
    await history(
        session, project_id=rfq.project_id, rfq_id=rfq.id, subject="RFQ", subject_id=rfq.id,
        old=rfq.state, new=rfq.state, who=who, reason=reason,
        detail={"quotes_due_at": due.isoformat(), "was": old.isoformat() if old else None},
    )  # fmt: skip
    for inv in await invitations_of(session, rfq.id):
        if inv.profile_id is not None and inv.state in (I.SENT.value, I.ACCEPTED.value):
            await notify(
                session, "contractor", "DEADLINE_EXTENDED", aggregate_id=inv.id, rfq_id=rfq.id,
                ref_id=uuid.uuid5(inv.id, due.isoformat()),
            )  # fmt: skip
    return rfq


async def close_open_work(
    session: AsyncSession, rfq: Rfq, reason: InvitationWithdrawReason, who: Who
) -> None:
    """When an RFQ is cancelled or closed: invitations not yet answered are withdrawn, drafts
    discarded, open questions closed, open reviews closed; submitted quotes stay as history."""
    now = await db_now(session)
    for inv in await invitations_of(session, rfq.id, lock=True):
        if inv.state in (I.PROPOSED.value, I.SENT.value):
            sent = inv.state == I.SENT.value
            inv.withdraw_reason = reason.value
            inv.withdrawn_at = now
            await move_invitation(session, inv, "withdraw", who, reason.value)
            if sent and inv.profile_id is not None:
                await notify(
                    session, "contractor", "RFQ_CLOSED", aggregate_id=inv.id, rfq_id=rfq.id,
                    ref_id=inv.id,
                )  # fmt: skip
        draft = (
            await session.scalars(select(QuoteDraft).where(QuoteDraft.invitation_id == inv.id))
        ).one_or_none()
        if draft is not None:
            await session.delete(draft)
    for question in await session.scalars(
        select(RfqClarification)
        .where(RfqClarification.rfq_id == rfq.id, RfqClarification.state == "OPEN")
        .with_for_update()
    ):
        old = question.state
        question.state = "CLOSED"
        question.close_reason = reason.value
        question.version += 1
        await session.flush()
        await history(
            session, project_id=rfq.project_id, rfq_id=rfq.id, subject="CLARIFICATION",
            subject_id=question.id, old=old, new="CLOSED", who=who, reason=reason.value,
        )  # fmt: skip
    for qv in await session.scalars(
        select(QuoteVersion)
        .where(QuoteVersion.rfq_id == rfq.id, QuoteVersion.review_state.in_(common.OPEN_REVIEW))
        .with_for_update()
    ):
        await close_review(session, qv, who, reason.value)


async def close_review(session: AsyncSession, qv: QuoteVersion, who: Who, reason: str) -> None:
    old = qv.review_state
    if old not in common.OPEN_REVIEW:
        return
    qv.review_state = REVIEW.target(QuoteCheckState(old), "close").value
    qv.version += 1
    await session.flush()
    await history(
        session, project_id=qv.project_id, rfq_id=qv.rfq_id, subject="REVIEW", subject_id=qv.id,
        old=old, new=qv.review_state, who=who, reason=reason,
    )  # fmt: skip


async def cancel(
    session: AsyncSession, who: Who, rfq: Rfq, reason: RfqCancelReason, note: str | None
) -> Rfq:
    """T.1 to CANCELLED: by the owner, operations or the system (QD-14, QD-15). Submitted
    quotes and published comparisons stay readable as history."""
    if rfq.state not in OPEN_RFQ:
        raise StateConflict(details={"current_state": rfq.state})
    was_issued = rfq.state == R.ISSUED.value
    rfq.cancel_reason = reason.value
    rfq.cancel_note = note
    rfq.cancelled_by_role = who.role
    rfq.cancelled_at = await db_now(session)
    await _move_rfq(session, rfq, "cancel", who, note or reason.value)
    for inv in await invitations_of(session, rfq.id):
        if was_issued and inv.state == I.ACCEPTED.value and inv.profile_id is not None:
            await notify(
                session, "contractor", "RFQ_CLOSED", aggregate_id=inv.id, rfq_id=rfq.id,
                ref_id=inv.id,
            )  # fmt: skip
    await close_open_work(session, rfq, InvitationWithdrawReason.RFQ_CANCELLED, who)
    if reason != RfqCancelReason.OWNER:
        await notify(session, "family", "RFQ_CANCELLED", aggregate_id=rfq.id, rfq_id=rfq.id)
    return rfq


async def cancel_open(
    session: AsyncSession,
    reason: RfqCancelReason,
    *,
    project_id: uuid.UUID,
    keep_version_id: uuid.UUID | None = None,
) -> int:
    """System cancellation: the package ended (QD-14), the project was cancelled, or a newer
    Build Plan version was accepted (QD-15, every open RFQ on another version)."""
    rows = list(
        await session.scalars(
            select(Rfq)
            .where(Rfq.project_id == project_id, Rfq.state.in_(OPEN_RFQ))
            .with_for_update()
        )
    )
    count = 0
    for rfq in rows:
        if keep_version_id is not None and rfq.build_plan_version_id == keep_version_id:
            continue
        await cancel(session, SYSTEM, rfq, reason, None)
        count += 1
    return count


async def withdraw_invitation(
    session: AsyncSession, who: Who, inv: RfqInvitation, reason: InvitationWithdrawReason,
    note: str | None,
) -> None:  # fmt: skip
    """Operations, or the system when the contractor leaves LISTED. A withdrawn ACCEPTED
    invitation's current quote is withdrawn with it (history kept)."""
    if inv.state not in LIVE_INVITATIONS:
        raise StateConflict(details={"current_state": inv.state})
    was = inv.state
    if was == I.PROPOSED.value and reason == InvitationWithdrawReason.OPERATIONS:
        reason = InvitationWithdrawReason.REMOVED
    inv.withdraw_reason = reason.value
    inv.withdraw_note = note
    inv.withdrawn_at = await db_now(session)
    await move_invitation(session, inv, "withdraw", who, note or reason.value)
    for qv in await session.scalars(
        select(QuoteVersion)
        .where(
            QuoteVersion.invitation_id == inv.id,
            QuoteVersion.state == QuoteVersionState.SUBMITTED.value,
        )
        .with_for_update()
    ):
        qv.withdraw_reason = f"invitation withdrawn: {note or reason.value}"
        old = qv.state
        qv.state = QUOTE.target(QuoteVersionState(old), "withdraw").value
        qv.closed_at = await db_now(session)
        qv.version += 1
        await session.flush()
        await history(
            session, project_id=qv.project_id, rfq_id=qv.rfq_id, subject="QUOTE_VERSION",
            subject_id=qv.id, old=old, new=qv.state, who=who, reason=qv.withdraw_reason,
        )  # fmt: skip
        await close_review(session, qv, who, "quote withdrawn")
    if was in (I.SENT.value, I.ACCEPTED.value) and inv.profile_id is not None:
        await notify(
            session, "contractor", "RFQ_CLOSED", aggregate_id=inv.id, rfq_id=inv.rfq_id,
            ref_id=inv.id,
        )  # fmt: skip


async def withdraw_for_profile(session: AsyncSession, profile_id: uuid.UUID) -> int:
    """The contractor left LISTED: invitations not yet answered are withdrawn. Accepted ones keep
    their quotes as history; selection refuses a contractor who is not LISTED (QD-12)."""
    rows = list(
        await session.scalars(
            select(RfqInvitation)
            .where(
                RfqInvitation.profile_id == profile_id,
                RfqInvitation.state.in_((I.PROPOSED.value, I.SENT.value)),
            )
            .with_for_update()
        )
    )
    for inv in rows:
        await withdraw_invitation(session, SYSTEM, inv, InvitationWithdrawReason.NOT_LISTED, None)
    return len(rows)


# --- the contractor -----------------------------------------------------------------------


async def own_invitation(
    session: AsyncSession, actor: Actor, invitation_id: uuid.UUID, *, lock: bool = False
) -> RfqInvitation:
    """Only the invited contractor's own invitation; anything else is 404 (no enumeration)."""
    profile_id = await profile_by_user(session, actor.user_id)
    inv = await session.get(RfqInvitation, invitation_id, with_for_update=lock)
    if profile_id is None or inv is None or inv.profile_id != profile_id:
        raise NotFound
    if inv.state == I.PROPOSED.value:  # nothing was sent yet
        raise NotFound
    return inv


async def accept(
    session: AsyncSession, actor: Actor, who: Who, invitation_id: uuid.UUID, phone: str | None
) -> RfqInvitation:
    """Agreeing to quote (QD-01): no engagement, no connection. The contractor's contact is held
    for the homeowner and shown only after a selection."""
    inv = await own_invitation(session, actor, invitation_id, lock=True)
    if inv.state != I.SENT.value:
        raise StateConflict(details={"current_state": inv.state})
    rfq = await rfq_row(session, inv.rfq_id)
    now = await db_now(session)
    if inv.respond_by is None or inv.respond_by <= now:
        raise conflict("EXPIRED", "The time to respond has passed.")
    if rfq.state != R.ISSUED.value:
        raise conflict("RFQ_CLOSED", "This request for quotation is no longer open.")
    if rfq.quotes_due_at is not None and rfq.quotes_due_at <= now:
        raise conflict("DEADLINE_PASSED", "The quote deadline has passed.")
    await require_package(session, inv.project_id)
    assert inv.profile_id is not None  # noqa: S101 (LISTED)
    candidate = await connection_candidate(session, inv.profile_id, CATEGORY, (0.0, 0.0))
    if candidate is None or not candidate.listed:
        raise conflict("NOT_LISTED", "You are not listed for contractor work now.")
    email = (await primary_emails(session, [actor.user_id])).get(actor.user_id)
    inv.professional_contact = {
        "name": candidate.display_name, "firm": candidate.firm_name, "phone": phone,
        "email": email,
    }  # fmt: skip
    inv.responded_at = now
    await move_invitation(session, inv, "accept", who)
    return inv


async def decline(
    session: AsyncSession,
    actor: Actor,
    who: Who,
    invitation_id: uuid.UUID,
    reason: DeclineReason,
    note: str | None,
) -> RfqInvitation:
    note = (note or "").strip() or None
    if reason == DeclineReason.OTHER and note is None:
        raise ValidationFailed(details={"fields": {"note": ["Explain the reason."]}})
    inv = await own_invitation(session, actor, invitation_id, lock=True)
    if inv.state != I.SENT.value:
        raise StateConflict(details={"current_state": inv.state})
    if inv.respond_by is None or inv.respond_by <= await db_now(session):
        raise conflict("EXPIRED", "The time to respond has passed.")
    inv.decline_reason = reason.value
    inv.decline_note = note
    inv.responded_at = await db_now(session)
    await move_invitation(session, inv, "decline", who, reason.value)
    return inv


async def expire_due(session: AsyncSession, *, limit: int = 500) -> int:
    """QD-05: SENT past `respond_by` becomes EXPIRED. No reminder, no countdown."""
    rows = list(
        await session.scalars(
            select(RfqInvitation)
            .where(RfqInvitation.state == I.SENT.value, RfqInvitation.respond_by <= func.now())
            .order_by(RfqInvitation.respond_by)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for inv in rows:
        inv.responded_at = await db_now(session)
        await move_invitation(session, inv, "expire", SYSTEM)
    return len(rows)


async def notice_deadlines(session: AsyncSession, *, limit: int = 200) -> int:
    """One operations email per RFQ when its quote deadline passes."""
    rows = list(
        await session.scalars(
            select(Rfq)
            .where(
                Rfq.state == R.ISSUED.value,
                Rfq.quotes_due_at <= func.now(),
                Rfq.deadline_noticed_at.is_(None),
            )
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for rfq in rows:
        rfq.deadline_noticed_at = await db_now(session)
        rfq.version += 1
        assert rfq.quotes_due_at is not None  # noqa: S101 (filtered)
        await notify(
            session, "ops", "DEADLINE_REACHED", aggregate_id=rfq.id, rfq_id=rfq.id,
            ref_id=uuid.uuid5(rfq.id, rfq.quotes_due_at.isoformat()),
        )  # fmt: skip
    await session.flush()
    return len(rows)
