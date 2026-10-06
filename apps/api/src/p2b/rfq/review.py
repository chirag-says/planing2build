"""Plan2Build's review of quotes and the structured clarifications (SLICE3_6_READINESS J, K;
QD-08, QD-17).

Adjustments are Plan2Build's findings on one quote version, editable only while its review is
open (database trigger too), never shown to any contractor, never changing a contractor's price.
A clarification is one question and one answer through Plan2Build: contractors ask operations;
operations ask a contractor; an answer may be shared with every contractor who accepted, without
the asker's identity. A clarification never changes the RFQ or a quote."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.vocabulary import (
    ClarificationDirection,
    ClarificationState,
    InvitationState,
    QuoteCheckState,
    QuoteVersionState,
    RfqState,
)
from p2b.identity.interface import Actor
from p2b.rfq import rfqs
from p2b.rfq.common import OPEN_REVIEW, REVIEW, Who, conflict, db_now, history, notify
from p2b.rfq.models import QuoteAdjustment, QuoteVersion, RfqClarification, RfqInvitation
from p2b.rfq.quotes import manifest_lines
from p2b.rfq.schemas import AdjustmentIn

C = QuoteCheckState
D = ClarificationDirection


async def version_row(
    session: AsyncSession, qv_id: uuid.UUID, *, lock: bool = False
) -> QuoteVersion:
    qv = await session.get(QuoteVersion, qv_id, with_for_update=lock)
    if qv is None:
        raise NotFound
    return qv


async def _review(
    session: AsyncSession, qv: QuoteVersion, trigger: str, who: Who, reason: str | None = None
) -> None:
    old = qv.review_state
    qv.review_state = REVIEW.target(C(old), trigger).value
    if qv.review_state == C.REVIEWED.value:
        qv.reviewed_by = who.user_id
        qv.reviewed_at = await db_now(session)
    qv.version += 1
    await session.flush()
    await history(
        session, project_id=qv.project_id, rfq_id=qv.rfq_id, subject="REVIEW", subject_id=qv.id,
        old=old, new=qv.review_state, who=who, reason=reason,
    )  # fmt: skip


def _reviewable(qv: QuoteVersion) -> None:
    if qv.state != QuoteVersionState.SUBMITTED.value or qv.review_state not in OPEN_REVIEW:
        raise StateConflict(details={"current_state": qv.review_state})


async def set_adjustments(
    session: AsyncSession, who: Who, qv_id: uuid.UUID, items: list[AdjustmentIn]
) -> QuoteVersion:
    """Replace the adjustment list while the review is open (K.3)."""
    qv = await version_row(session, qv_id, lock=True)
    _reviewable(qv)
    rfq = await rfqs.rfq_row(session, qv.rfq_id)
    lines = manifest_lines(rfq)
    specs = {s["code"] for s in (rfq.manifest or {}).get("specifications", [])}
    for i, item in enumerate(items):
        if item.line_no is not None and item.line_no not in lines:
            raise ValidationFailed(details={"fields": {f"adjustments.{i}.line_no": ["Unknown."]}})
        if item.spec_line_code is not None and item.spec_line_code not in specs:
            raise ValidationFailed(
                details={"fields": {f"adjustments.{i}.spec_line_code": ["Unknown."]}}
            )
    await session.execute(delete(QuoteAdjustment).where(QuoteAdjustment.quote_version_id == qv.id))
    for item in items:
        session.add(
            QuoteAdjustment(
                id=new_id(), quote_version_id=qv.id, project_id=qv.project_id,
                line_no=item.line_no, spec_line_code=item.spec_line_code,
                deviation_type=item.deviation_type.value, description=item.description,
                rupee_impact=item.rupee_impact, basis_note=item.basis_note,
                clarification_status=item.clarification_status.value,
                created_by=who.user_id,
            )
        )  # fmt: skip
    await session.flush()
    await record(
        session, action="rfq_adjustments.set", entity_type="rfq_quote_version", entity_id=qv.id,
        project_id=qv.project_id, actor_type=who.actor_type, actor_user_id=who.user_id,
        actor_role=who.role, session_id=who.session_id, new_value={"count": len(items)},
    )  # fmt: skip
    return qv


async def mark_reviewed(session: AsyncSession, who: Who, qv_id: uuid.UUID) -> QuoteVersion:
    """REVIEWED: the adjustment list is complete (it may be empty). Unresolved points stay
    recorded as adjustments with clarification status OPEN."""
    qv = await version_row(session, qv_id, lock=True)
    _reviewable(qv)
    rfq = await rfqs.rfq_row(session, qv.rfq_id)
    if rfq.state != RfqState.ISSUED.value:
        raise conflict("RFQ_CLOSED", "This request for quotation is no longer open.")
    await _review(session, qv, "review", who)
    return qv


async def adjustments_of(
    session: AsyncSession, version_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[QuoteAdjustment]]:
    result: dict[uuid.UUID, list[QuoteAdjustment]] = {v: [] for v in version_ids}
    if not version_ids:
        return result
    for adj in await session.scalars(
        select(QuoteAdjustment)
        .where(QuoteAdjustment.quote_version_id.in_(version_ids))
        .order_by(QuoteAdjustment.created_at, QuoteAdjustment.id)
    ):
        result[adj.quote_version_id].append(adj)
    return result


# --- clarifications -----------------------------------------------------------------------


async def _asked(
    session: AsyncSession, who: Who, inv: RfqInvitation, direction: ClarificationDirection,
    question: str, quote_version_id: uuid.UUID | None,
) -> RfqClarification:  # fmt: skip
    row = RfqClarification(
        id=new_id(), rfq_id=inv.rfq_id, project_id=inv.project_id, invitation_id=inv.id,
        quote_version_id=quote_version_id, direction=direction.value, question=question,
        state=ClarificationState.OPEN.value, asked_by=who.user_id,
    )  # fmt: skip
    session.add(row)
    await session.flush()
    await history(
        session, project_id=inv.project_id, rfq_id=inv.rfq_id, subject="CLARIFICATION",
        subject_id=row.id, old=None, new=row.state, who=who, detail={"direction": direction.value},
    )  # fmt: skip
    return row


async def _open_rfq(session: AsyncSession, inv: RfqInvitation) -> None:
    if inv.state != InvitationState.ACCEPTED.value:
        raise StateConflict(details={"current_state": inv.state})
    rfq = await rfqs.rfq_row(session, inv.rfq_id)
    if rfq.state != RfqState.ISSUED.value:
        raise conflict("RFQ_CLOSED", "This request for quotation is no longer open.")


async def contractor_asks(
    session: AsyncSession, actor: Actor, who: Who, invitation_id: uuid.UUID, question: str
) -> RfqClarification:
    inv = await rfqs.own_invitation(session, actor, invitation_id)
    await _open_rfq(session, inv)
    row = await _asked(session, who, inv, D.CONTRACTOR_ASKS, question, None)
    await notify(
        session, "ops", "CLARIFICATION", aggregate_id=inv.rfq_id, rfq_id=inv.rfq_id, ref_id=row.id
    )
    return row


async def plan2build_asks(
    session: AsyncSession, who: Who, rfq_id: uuid.UUID, invitation_id: uuid.UUID,
    quote_version_id: uuid.UUID | None, question: str,
) -> RfqClarification:  # fmt: skip
    inv = await session.get(RfqInvitation, invitation_id)
    if inv is None or inv.rfq_id != rfq_id:
        raise NotFound
    await _open_rfq(session, inv)
    if quote_version_id is not None:
        qv = await version_row(session, quote_version_id, lock=True)
        if qv.invitation_id != inv.id:
            raise NotFound
        _reviewable(qv)
        if qv.review_state == C.PENDING.value:
            await _review(session, qv, "ask", who)
    row = await _asked(session, who, inv, D.PLAN2BUILD_ASKS, question, quote_version_id)
    if inv.profile_id is not None:
        await notify(
            session, "contractor", "QUESTION", aggregate_id=inv.id, rfq_id=rfq_id, ref_id=row.id
        )
    return row


async def _answered(session: AsyncSession, row: RfqClarification, who: Who, answer: str) -> None:
    old = row.state
    if old != ClarificationState.OPEN.value:
        raise StateConflict(details={"current_state": old})
    row.answer = answer
    row.answered_by = who.user_id
    row.answered_at = await db_now(session)
    row.state = ClarificationState.ANSWERED.value
    row.version += 1
    await session.flush()
    await history(
        session, project_id=row.project_id, rfq_id=row.rfq_id, subject="CLARIFICATION",
        subject_id=row.id, old=old, new=row.state, who=who,
    )  # fmt: skip


async def _settle_review(session: AsyncSession, row: RfqClarification, who: Who) -> None:
    """Back to PENDING once no question on the version is open."""
    if row.quote_version_id is None:
        return
    qv = await version_row(session, row.quote_version_id, lock=True)
    if qv.review_state != C.NEEDS_CLARIFICATION.value:
        return
    still_open = await session.scalar(
        select(RfqClarification.id)
        .where(
            RfqClarification.quote_version_id == qv.id,
            RfqClarification.state == ClarificationState.OPEN.value,
        )
        .limit(1)
    )
    if still_open is None:
        await _review(session, qv, "answered", who)


async def answer_by_ops(
    session: AsyncSession, who: Who, clarification_id: uuid.UUID, answer: str, shared: bool
) -> RfqClarification:
    row = await session.get(RfqClarification, clarification_id, with_for_update=True)
    if row is None or row.direction != D.CONTRACTOR_ASKS.value:
        raise NotFound
    rfq = await rfqs.rfq_row(session, row.rfq_id)
    if rfq.state != RfqState.ISSUED.value:
        raise conflict("RFQ_CLOSED", "This request for quotation is no longer open.")
    row.shared_with_all = shared
    await _answered(session, row, who, answer)
    await notify(
        session, "contractor", "ANSWER", aggregate_id=row.invitation_id, rfq_id=row.rfq_id,
        ref_id=row.id,
    )  # fmt: skip
    if shared:
        for inv in await rfqs.invitations_of(session, row.rfq_id):
            if (
                inv.id != row.invitation_id
                and inv.profile_id is not None
                and inv.state == InvitationState.ACCEPTED.value
            ):
                await notify(
                    session, "contractor", "SHARED_ANSWER", aggregate_id=inv.id,
                    rfq_id=row.rfq_id, ref_id=row.id,
                )  # fmt: skip
    return row


async def answer_by_contractor(
    session: AsyncSession, actor: Actor, who: Who, invitation_id: uuid.UUID,
    clarification_id: uuid.UUID, answer: str,
) -> RfqClarification:  # fmt: skip
    inv = await rfqs.own_invitation(session, actor, invitation_id)
    row = await session.get(RfqClarification, clarification_id, with_for_update=True)
    if row is None or row.invitation_id != inv.id or row.direction != D.PLAN2BUILD_ASKS.value:
        raise NotFound
    await _open_rfq(session, inv)
    await _answered(session, row, who, answer)
    await _settle_review(session, row, who)
    await notify(
        session, "ops", "CLARIFICATION", aggregate_id=row.rfq_id, rfq_id=row.rfq_id,
        ref_id=uuid.uuid5(row.id, "answer"),
    )  # fmt: skip
    return row


async def close_by_ops(
    session: AsyncSession, who: Who, clarification_id: uuid.UUID, reason: str
) -> RfqClarification:
    row = await session.get(RfqClarification, clarification_id, with_for_update=True)
    if row is None:
        raise NotFound
    old = row.state
    if old != ClarificationState.OPEN.value:
        raise StateConflict(details={"current_state": old})
    row.state = ClarificationState.CLOSED.value
    row.close_reason = reason
    row.version += 1
    await session.flush()
    await history(
        session, project_id=row.project_id, rfq_id=row.rfq_id, subject="CLARIFICATION",
        subject_id=row.id, old=old, new=row.state, who=who, reason=reason,
    )  # fmt: skip
    await _settle_review(session, row, who)
    return row


async def visible_to_contractor(
    session: AsyncSession, inv: RfqInvitation
) -> list[tuple[RfqClarification, bool]]:
    """Its own questions and answers, plus answers operations shared with everyone (no asker
    identity). Never another contractor's private exchange."""
    rows = await session.scalars(
        select(RfqClarification)
        .where(RfqClarification.rfq_id == inv.rfq_id)
        .order_by(RfqClarification.asked_at, RfqClarification.id)
    )
    result = []
    for row in rows:
        if row.invitation_id == inv.id:
            result.append((row, True))
        elif row.shared_with_all and row.state == ClarificationState.ANSWERED.value:
            result.append((row, False))
    return result
