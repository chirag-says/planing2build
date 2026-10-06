"""Contractor quotes (SLICE3_6_READINESS H, I, T.3; QD-06, QD-18, QD-19, QD-22).

Every quantity line of the frozen pack is priced with a unit rate or excluded with a reason; the
server computes each amount from the RFQ quantity and the comparable total; additional items stay
outside it. A submission is an immutable version; a new one supersedes the previous; a renewal
after expiry changes only the validity dates (its content hash must match). Late submissions are
refused (QD-05). Operations may capture a quote in the same structure, with the contractor's
document as evidence. Contractor costs or margins are never asked for (MVP:170)."""

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.config import Settings
from p2b.core.errors import StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.vocabulary import (
    EngagementParty,
    FilePurpose,
    FileState,
    InvitationState,
    QuoteCheckState,
    QuoteLineKind,
    QuoteVersionKind,
    QuoteVersionState,
    RfqState,
)
from p2b.documents.interface import file_facts
from p2b.identity.interface import Actor
from p2b.professionals.interface import connection_candidate
from p2b.rfq import rfqs
from p2b.rfq.common import (
    CATEGORY,
    QUOTE,
    REVIEW,
    SYSTEM,
    Who,
    conflict,
    db_now,
    history,
    notify,
    require_package,
    today,
)
from p2b.rfq.models import QuoteAdjustment, QuoteDraft, QuoteLine, QuoteVersion, Rfq, RfqInvitation
from p2b.rfq.schemas import QuoteDraftIn, QuoteIn

Q = QuoteVersionState
CENT = Decimal("0.01")


def _fields(errors: dict[str, list[str]]) -> ValidationFailed:
    return ValidationFailed(details={"fields": errors})


def manifest_lines(rfq: Rfq) -> dict[int, dict[str, Any]]:
    assert rfq.manifest is not None  # noqa: S101 (ISSUED)
    return {int(q["line_no"]): q for q in rfq.manifest["quantities"]}


def _amount(rate: Decimal, quantity: Decimal) -> Decimal:
    return (rate * quantity).quantize(CENT, rounding=ROUND_HALF_UP)


def content_of(body: QuoteIn) -> dict[str, Any]:
    """The commercial content a renewal may not change (QD-06): everything except the validity
    dates and the comment."""
    return {
        "lines": sorted(
            [
                {"line_no": line.line_no, "rate": str(line.rate) if line.rate else None,
                 "excluded": line.excluded, "reason": line.exclusion_reason,
                 "alternate_spec": line.alternate_spec}
                for line in body.lines
            ],
            key=lambda x: x["line_no"],
        ),
        "additional": [
            {"description": a.description, "unit": a.unit, "quantity": str(a.quantity),
             "rate": str(a.rate)}
            for a in body.additional_items
        ],
        "tax": [body.tax_treatment.value, body.tax_note],
        "duration_days": body.duration_days,
        "stage_durations": sorted(
            [[s.entry_key, s.days] for s in body.stage_durations], key=lambda x: str(x[0])
        ),
        "payment_terms": body.payment_terms,
        "warranty": body.warranty,
        "materials": body.materials,
        "exclusions": body.exclusions,
        "assumptions": body.assumptions,
        "attachments": sorted(str(f) for f in body.attachment_file_ids),
    }  # fmt: skip


async def _check(
    session: AsyncSession,
    settings: Settings,
    rfq: Rfq,
    body: QuoteIn,
    *,
    file_owner: uuid.UUID,
    renewal: bool = False,
) -> None:
    errors: dict[str, list[str]] = {}
    expected = manifest_lines(rfq)
    given = [line.line_no for line in body.lines]
    if len(set(given)) != len(given) or set(given) != set(expected):
        errors["lines"] = ["Answer every line of the request exactly once."]
    for line in body.lines:
        priced = line.rate is not None and not line.excluded
        excluded = line.excluded and line.rate is None and line.exclusion_reason
        if not (priced or excluded):
            errors.setdefault(f"lines.{line.line_no}", []).append(
                "Price this line, or exclude it with a reason."
            )
        if priced and line.exclusion_reason:
            errors.setdefault(f"lines.{line.line_no}", []).append("A priced line has no reason.")
    keys = {e["entry_key"] for e in (rfq.manifest or {}).get("schedule", [])}
    stage_keys = [s.entry_key for s in body.stage_durations]
    if len(set(stage_keys)) != len(stage_keys) or not set(stage_keys) <= keys:
        errors["stage_durations"] = ["Use each stage of the request at most once."]
    if body.valid_to <= body.valid_from:
        errors["valid_to"] = ["The end of validity must be after its start."]
    elif body.valid_to < await today(session):
        errors["valid_to"] = ["The quote would already have expired."]
    if len(body.attachment_file_ids) > settings.rfq_quote_attachments_max:
        errors["attachment_file_ids"] = [
            f"Attach at most {settings.rfq_quote_attachments_max} files."
        ]
    facts = await file_facts(session, list(body.attachment_file_ids))
    for file_id in body.attachment_file_ids:
        fact = facts.get(file_id)
        if (
            fact is None
            or fact.project_id != rfq.project_id
            or fact.purpose != FilePurpose.QUOTE_ATTACHMENT
            or (fact.owner_user_id != file_owner and not renewal)
            or fact.state != FileState.AVAILABLE
        ):
            errors["attachment_file_ids"] = ["Upload the files and wait for the check."]
    if errors:
        raise _fields(errors)


async def _versions(
    session: AsyncSession, invitation_id: uuid.UUID, *, lock: bool = False
) -> list[QuoteVersion]:
    query = (
        select(QuoteVersion)
        .where(QuoteVersion.invitation_id == invitation_id)
        .order_by(QuoteVersion.version_no)
    )
    return list(await session.scalars(query.with_for_update() if lock else query))


async def move(
    session: AsyncSession, qv: QuoteVersion, trigger: str, who: Who, reason: str | None = None
) -> None:
    old = qv.state
    qv.state = QUOTE.target(Q(old), trigger).value
    if qv.state != Q.SUBMITTED.value:
        qv.closed_at = await db_now(session)
    qv.version += 1
    await session.flush()
    await history(
        session, project_id=qv.project_id, rfq_id=qv.rfq_id, subject="QUOTE_VERSION",
        subject_id=qv.id, old=old, new=qv.state, who=who, reason=reason,
    )  # fmt: skip


async def _create(
    session: AsyncSession,
    who: Who,
    rfq: Rfq,
    inv: RfqInvitation,
    body: QuoteIn,
    *,
    kind: QuoteVersionKind,
    captured: bool = False,
    evidence_file_id: uuid.UUID | None = None,
    renewal_of: uuid.UUID | None = None,
) -> QuoteVersion:
    existing = await _versions(session, inv.id, lock=True)
    expected = manifest_lines(rfq)
    rates = {line.line_no: line for line in body.lines}
    amounts = {
        n: _amount(rates[n].rate, Decimal(str(expected[n]["quantity"])))  # type: ignore[arg-type]
        for n in expected
        if rates[n].rate is not None and not rates[n].excluded
    }
    additional = [_amount(a.rate, a.quantity) for a in body.additional_items]
    qv = QuoteVersion(
        id=new_id(),
        invitation_id=inv.id,
        rfq_id=rfq.id,
        project_id=rfq.project_id,
        version_no=max((v.version_no for v in existing), default=0) + 1,
        kind=kind.value,
        renewal_of=renewal_of,
        state=QUOTE.target(None, "submit").value,
        review_state=REVIEW.target(None, "open").value,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
        tax_treatment=body.tax_treatment.value,
        tax_note=body.tax_note,
        duration_days=body.duration_days,
        stage_durations=[{"entry_key": s.entry_key, "days": s.days} for s in body.stage_durations],
        payment_terms=body.payment_terms,
        warranty=body.warranty,
        materials=body.materials,
        exclusions=list(body.exclusions),
        assumptions=list(body.assumptions),
        comment=body.comment,
        attachment_file_ids=list(body.attachment_file_ids),
        comparable_total=sum(amounts.values(), Decimal("0.00")),
        additional_total=sum(additional, Decimal("0.00")),
        content_sha256=rfqs.sha256(content_of(body)),
        submitted_by=who.user_id,
        captured_by_staff=captured,
        evidence_file_id=evidence_file_id,
    )
    session.add(qv)
    await session.flush()
    for n, q in sorted(expected.items()):
        line = rates[n]
        session.add(
            QuoteLine(
                id=new_id(), quote_version_id=qv.id, kind=QuoteLineKind.RFQ_LINE.value,
                line_no=n, description=str(q["description"]), unit=str(q["unit"]),
                quantity=Decimal(str(q["quantity"])),
                rate=line.rate if n in amounts else None, amount=amounts.get(n),
                is_excluded=n not in amounts,
                exclusion_reason=line.exclusion_reason if n not in amounts else None,
                alternate_spec=line.alternate_spec,
            )
        )  # fmt: skip
    for i, (a, amount) in enumerate(zip(body.additional_items, additional, strict=True), 1):
        session.add(
            QuoteLine(
                id=new_id(), quote_version_id=qv.id, kind=QuoteLineKind.ADDITIONAL.value,
                line_no=i, description=a.description, unit=a.unit, quantity=a.quantity,
                rate=a.rate, amount=amount, is_excluded=False,
            )
        )  # fmt: skip
    await session.flush()
    await history(
        session, project_id=qv.project_id, rfq_id=rfq.id, subject="QUOTE_VERSION",
        subject_id=qv.id, old=None, new=qv.state, who=who,
        detail={"version_no": qv.version_no, "kind": kind.value, "captured": captured},
    )  # fmt: skip
    await history(
        session, project_id=qv.project_id, rfq_id=rfq.id, subject="REVIEW", subject_id=qv.id,
        old=None, new=qv.review_state, who=who,
    )  # fmt: skip
    for earlier in existing:
        if earlier.state == Q.SUBMITTED.value:
            await move(session, earlier, "supersede", who, f"version {qv.version_no} submitted")
            await rfqs.close_review(session, earlier, who, "superseded")
    draft = (
        await session.scalars(select(QuoteDraft).where(QuoteDraft.invitation_id == inv.id))
    ).one_or_none()
    if draft is not None:
        await session.delete(draft)
    await notify(
        session, "ops", "QUOTE_SUBMITTED", aggregate_id=rfq.id, rfq_id=rfq.id, ref_id=qv.id
    )
    return qv


async def _open_rfq_for_quotes(
    session: AsyncSession, inv: RfqInvitation, *, renewal: bool = False
) -> Rfq:
    if inv.state != InvitationState.ACCEPTED.value:
        raise StateConflict(details={"current_state": inv.state})
    rfq = await rfqs.rfq_row(session, inv.rfq_id, lock=True)
    if rfq.state != RfqState.ISSUED.value:
        raise conflict("RFQ_CLOSED", "This request for quotation is no longer open.")
    if not renewal and rfq.quotes_due_at is not None and rfq.quotes_due_at <= await db_now(session):
        raise conflict("DEADLINE_PASSED", "The quote deadline has passed.")
    await require_package(session, inv.project_id)
    return rfq


async def _still_listed(session: AsyncSession, inv: RfqInvitation) -> None:
    if inv.party != EngagementParty.LISTED.value:
        return
    assert inv.profile_id is not None  # noqa: S101 (LISTED)
    candidate = await connection_candidate(session, inv.profile_id, CATEGORY, (0.0, 0.0))
    if candidate is None or not candidate.listed:
        raise conflict("NOT_LISTED", "The contractor is not listed for contractor work now.")


async def submit(
    session: AsyncSession, settings: Settings, actor: Actor, who: Who, invitation_id: uuid.UUID,
    body: QuoteIn,
) -> QuoteVersion:  # fmt: skip
    inv = await rfqs.own_invitation(session, actor, invitation_id, lock=True)
    rfq = await _open_rfq_for_quotes(session, inv)
    await _still_listed(session, inv)
    await _check(session, settings, rfq, body, file_owner=actor.user_id)
    return await _create(session, who, rfq, inv, body, kind=QuoteVersionKind.STANDARD)


async def capture(
    session: AsyncSession, settings: Settings, who: Who, invitation_id: uuid.UUID, body: QuoteIn,
    evidence_file_id: uuid.UUID,
) -> QuoteVersion:  # fmt: skip
    """QD-22, BR-082: operations enter the quote in the standard structure; the contractor's own
    document is the evidence; a listed contractor is told."""
    inv = await session.get(RfqInvitation, invitation_id, with_for_update=True)
    if inv is None or inv.state == InvitationState.PROPOSED.value:
        raise StateConflict(details={"current_state": inv.state if inv else None})
    rfq = await _open_rfq_for_quotes(session, inv)
    await _still_listed(session, inv)
    assert who.user_id is not None  # noqa: S101 (staff)
    await _check(session, settings, rfq, body, file_owner=who.user_id)
    evidence = (await file_facts(session, [evidence_file_id])).get(evidence_file_id)
    if (
        evidence is None
        or evidence.project_id != rfq.project_id
        or evidence.purpose != FilePurpose.QUOTE_ATTACHMENT
        or evidence.state != FileState.AVAILABLE
    ):
        raise _fields({"evidence_file_id": ["Upload the contractor's quote document first."]})
    qv = await _create(
        session, who, rfq, inv, body, kind=QuoteVersionKind.STANDARD, captured=True,
        evidence_file_id=evidence_file_id,
    )  # fmt: skip
    if inv.profile_id is not None:
        await notify(
            session, "contractor", "QUOTE_CAPTURED", aggregate_id=inv.id, rfq_id=rfq.id,
            ref_id=qv.id,
        )  # fmt: skip
    return qv


def _as_input(qv: QuoteVersion, lines: list[QuoteLine], valid: tuple[date, date]) -> QuoteIn:
    return QuoteIn.model_validate(
        {
            "lines": [
                {"line_no": x.line_no, "rate": x.rate, "excluded": x.is_excluded,
                 "exclusion_reason": x.exclusion_reason, "alternate_spec": x.alternate_spec}
                for x in lines if x.kind == QuoteLineKind.RFQ_LINE.value
            ],
            "additional_items": [
                {"description": x.description, "unit": x.unit, "quantity": x.quantity,
                 "rate": x.rate}
                for x in lines if x.kind == QuoteLineKind.ADDITIONAL.value
            ],
            "valid_from": valid[0], "valid_to": valid[1],
            "tax_treatment": qv.tax_treatment, "tax_note": qv.tax_note,
            "duration_days": qv.duration_days, "stage_durations": qv.stage_durations,
            "payment_terms": qv.payment_terms, "warranty": qv.warranty,
            "materials": qv.materials, "exclusions": qv.exclusions,
            "assumptions": qv.assumptions, "attachment_file_ids": qv.attachment_file_ids,
            "comment": qv.comment,
        }
    )  # fmt: skip


async def lines_of(
    session: AsyncSession, version_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[QuoteLine]]:
    result: dict[uuid.UUID, list[QuoteLine]] = {v: [] for v in version_ids}
    if not version_ids:
        return result
    for line in await session.scalars(
        select(QuoteLine)
        .where(QuoteLine.quote_version_id.in_(version_ids))
        .order_by(QuoteLine.kind.desc(), QuoteLine.line_no)
    ):
        result[line.quote_version_id].append(line)
    return result


async def renew(
    session: AsyncSession, settings: Settings, actor: Actor, who: Who, invitation_id: uuid.UUID,
    valid_from: date, valid_to: date,
) -> QuoteVersion:  # fmt: skip
    """QD-06: after expiry, new validity dates on unchanged commercial content. A review
    finished on the expired version carries over with its adjustments (the content is
    identical, as its hash proves)."""
    inv = await rfqs.own_invitation(session, actor, invitation_id, lock=True)
    rfq = await _open_rfq_for_quotes(session, inv, renewal=True)
    await _still_listed(session, inv)
    versions = await _versions(session, inv.id, lock=True)
    if not versions or versions[-1].state != Q.EXPIRED.value:
        raise conflict("NOT_EXPIRED", "Only an expired quote can be renewed.")
    expired = versions[-1]
    body = _as_input(expired, (await lines_of(session, [expired.id]))[expired.id],
                     (valid_from, valid_to))  # fmt: skip
    await _check(session, settings, rfq, body, file_owner=actor.user_id, renewal=True)
    if rfqs.sha256(content_of(body)) != expired.content_sha256:
        raise conflict("CONTENT_CHANGED", "A renewal cannot change the quote.")
    qv = await _create(
        session, who, rfq, inv, body, kind=QuoteVersionKind.RENEWAL, renewal_of=expired.id
    )
    if expired.review_state == QuoteCheckState.REVIEWED.value:
        for adj in await session.scalars(
            select(QuoteAdjustment).where(QuoteAdjustment.quote_version_id == expired.id)
        ):
            session.add(
                QuoteAdjustment(
                    id=new_id(), quote_version_id=qv.id, project_id=qv.project_id,
                    line_no=adj.line_no, spec_line_code=adj.spec_line_code,
                    deviation_type=adj.deviation_type, description=adj.description,
                    rupee_impact=adj.rupee_impact, basis_note=adj.basis_note,
                    clarification_status=adj.clarification_status, created_by=adj.created_by,
                )
            )  # fmt: skip
        await session.flush()
        old = qv.review_state
        qv.review_state = REVIEW.target(QuoteCheckState(old), "review").value
        qv.reviewed_by = expired.reviewed_by
        qv.reviewed_at = await db_now(session)
        qv.version += 1
        await session.flush()
        await history(
            session, project_id=qv.project_id, rfq_id=rfq.id, subject="REVIEW",
            subject_id=qv.id, old=old, new=qv.review_state, who=who,
            reason=f"review carried from version {expired.version_no} (identical content)",
        )  # fmt: skip
    return qv


async def withdraw(
    session: AsyncSession, actor: Actor, who: Who, invitation_id: uuid.UUID, reason: str
) -> QuoteVersion:
    """QD-19: until selection, with a reason; the contractor may submit again before the
    deadline."""
    inv = await rfqs.own_invitation(session, actor, invitation_id, lock=True)
    rfq = await rfqs.rfq_row(session, inv.rfq_id, lock=True)
    if rfq.state != RfqState.ISSUED.value:
        raise conflict("RFQ_CLOSED", "This request for quotation is no longer open.")
    current = [v for v in await _versions(session, inv.id, lock=True) if v.state == Q.SUBMITTED]
    if not current:
        raise conflict("NO_QUOTE", "There is no submitted quote to withdraw.")
    qv = current[-1]
    qv.withdraw_reason = reason
    await move(session, qv, "withdraw", who, reason)
    await rfqs.close_review(session, qv, who, "quote withdrawn")
    await notify(
        session, "ops", "QUOTE_WITHDRAWN", aggregate_id=rfq.id, rfq_id=rfq.id, ref_id=qv.id
    )
    return qv


async def save_draft(
    session: AsyncSession, actor: Actor, invitation_id: uuid.UUID, body: QuoteDraftIn
) -> QuoteDraft:
    inv = await rfqs.own_invitation(session, actor, invitation_id, lock=True)
    if inv.state != InvitationState.ACCEPTED.value:
        raise StateConflict(details={"current_state": inv.state})
    rfq = await rfqs.rfq_row(session, inv.rfq_id)
    if rfq.state != RfqState.ISSUED.value:
        raise conflict("RFQ_CLOSED", "This request for quotation is no longer open.")
    draft = (
        await session.scalars(
            select(QuoteDraft).where(QuoteDraft.invitation_id == inv.id).with_for_update()
        )
    ).one_or_none()
    content = body.model_dump(mode="json")
    if draft is None:
        draft = QuoteDraft(
            id=new_id(), invitation_id=inv.id, content=content, updated_by=actor.user_id
        )
        session.add(draft)
    else:
        draft.content = content
        draft.updated_by = actor.user_id
        draft.updated_at = await db_now(session)
        draft.version += 1
    await session.flush()
    return draft


async def discard_draft(session: AsyncSession, actor: Actor, invitation_id: uuid.UUID) -> None:
    inv = await rfqs.own_invitation(session, actor, invitation_id)
    draft = (
        await session.scalars(select(QuoteDraft).where(QuoteDraft.invitation_id == inv.id))
    ).one_or_none()
    if draft is not None:
        await session.delete(draft)
        await session.flush()


async def expire_due(session: AsyncSession, *, limit: int = 500) -> int:
    """A SUBMITTED quote whose validity ended (calendar date in Raipur) becomes EXPIRED; it
    cannot be selected until renewed (QD-06). One email to the contractor."""
    current = await today(session)
    rows = list(
        await session.scalars(
            select(QuoteVersion)
            .where(QuoteVersion.state == Q.SUBMITTED.value, QuoteVersion.valid_to < current)
            .order_by(QuoteVersion.valid_to)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for qv in rows:
        await move(session, qv, "expire", SYSTEM)
        await rfqs.close_review(session, qv, SYSTEM, "quote expired")
        inv = await session.get_one(RfqInvitation, qv.invitation_id)
        if inv.profile_id is not None:
            await notify(
                session, "contractor", "QUOTE_EXPIRED", aggregate_id=inv.id, rfq_id=qv.rfq_id,
                ref_id=qv.id,
            )  # fmt: skip
    return len(rows)


async def latest_submitted(session: AsyncSession, rfq_id: uuid.UUID) -> list[QuoteVersion]:
    """The current SUBMITTED version of each invitation (at most one each)."""
    return list(
        await session.scalars(
            select(QuoteVersion)
            .where(QuoteVersion.rfq_id == rfq_id, QuoteVersion.state == Q.SUBMITTED.value)
            .order_by(QuoteVersion.invitation_id)
        )
    )


async def count_received(session: AsyncSession, rfq_id: uuid.UUID) -> int:
    """Invitations with at least one submission."""
    value = await session.scalar(
        select(func.count(func.distinct(QuoteVersion.invitation_id))).where(
            QuoteVersion.rfq_id == rfq_id
        )
    )
    return int(value or 0)
