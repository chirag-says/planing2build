"""Read models per audience (SECURITY 4.2): the contractor sees its own invitation, pack, quote
versions and visible clarifications; the homeowner sees status until a comparison is published
(QD-07); operations see everything. Disclosure is decided here, in one place."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.billing.interface import package_state
from p2b.core.config import Settings
from p2b.core.vocabulary import (
    AdjustmentClarification,
    ComparisonState,
    DeclineReason,
    DeviationType,
    EngagementParty,
    InvitationSource,
    InvitationState,
    InvitationWithdrawReason,
    MembershipRole,
    PackageAvailability,
    QuoteCheckState,
    QuoteLineKind,
    QuoteVersionKind,
    QuoteVersionState,
    RfqCancelReason,
    RfqState,
    TaxTreatment,
)
from p2b.documents.interface import FileFacts, file_facts
from p2b.engagements.interface import active_engagement, engagement_facts
from p2b.identity.interface import Actor
from p2b.professionals.interface import profile_names
from p2b.projects.interface import ConnectionFacts, member_role
from p2b.rfq import review
from p2b.rfq.common import CATEGORY, OPEN_RFQ, db_now
from p2b.rfq.models import (
    Comparison,
    QuoteAdjustment,
    QuoteDraft,
    QuoteLine,
    QuoteVersion,
    Rfq,
    RfqClarification,
    RfqEvent,
    RfqInvitation,
    Selection,
)
from p2b.rfq.quotes import lines_of
from p2b.rfq.schemas import (
    AdjustmentOut,
    BriefOut,
    ComparisonCountsOut,
    ComparisonLineOut,
    ComparisonOut,
    ComparisonQuoteOut,
    FamilyInvitationOut,
    FamilyQuoteStatusOut,
    FamilyRfqOut,
    FamilyRfqsOut,
    FileOut,
    OpsClarificationOut,
    OpsEventOut,
    OpsInvitationOut,
    OpsQuoteVersionOut,
    OpsRfqOut,
    PackOut,
    ProClarificationOut,
    ProInvitationOut,
    ProInvitationSummaryOut,
    ProQuoteVersionOut,
    QuoteContentOut,
    QuoteLineOut,
    SelectionOut,
    StageDurationOut,
)

I = InvitationState  # noqa: E741
Q = QuoteVersionState


def file_out(f: FileFacts) -> FileOut:
    return FileOut(
        file_id=f.file_id, file_name=f.file_name, content_type=f.content_type,
        size_bytes=f.size_bytes, state=f.state,
    )  # fmt: skip


def _line(x: QuoteLine) -> QuoteLineOut:
    return QuoteLineOut(
        line_no=x.line_no, description=x.description, unit=x.unit, quantity=x.quantity,
        rate=x.rate, amount=x.amount, excluded=x.is_excluded, exclusion_reason=x.exclusion_reason,
        alternate_spec=x.alternate_spec,
    )  # fmt: skip


def quote_content(
    qv: QuoteVersion, lines: list[QuoteLine], files: dict[uuid.UUID, FileFacts]
) -> QuoteContentOut:
    return QuoteContentOut(
        id=qv.id,
        version_no=qv.version_no,
        kind=QuoteVersionKind(qv.kind),
        submitted_at=qv.submitted_at,
        captured_by_staff=qv.captured_by_staff,
        valid_from=qv.valid_from,
        valid_to=qv.valid_to,
        tax_treatment=TaxTreatment(qv.tax_treatment),
        tax_note=qv.tax_note,
        duration_days=qv.duration_days,
        stage_durations=[StageDurationOut.model_validate(s) for s in qv.stage_durations],
        payment_terms=qv.payment_terms,
        warranty=qv.warranty,
        materials=qv.materials,
        exclusions=qv.exclusions,
        assumptions=qv.assumptions,
        comparable_total=qv.comparable_total,
        additional_total=qv.additional_total,
        lines=[_line(x) for x in lines if x.kind == QuoteLineKind.RFQ_LINE.value],
        additional_items=[_line(x) for x in lines if x.kind == QuoteLineKind.ADDITIONAL.value],
        attachments=[file_out(files[f]) for f in qv.attachment_file_ids if f in files],
    )


def adjustment_out(a: QuoteAdjustment) -> AdjustmentOut:
    return AdjustmentOut(
        line_no=a.line_no, spec_line_code=a.spec_line_code,
        deviation_type=DeviationType(a.deviation_type), description=a.description,
        rupee_impact=a.rupee_impact, basis_note=a.basis_note,
        clarification_status=AdjustmentClarification(a.clarification_status),
    )  # fmt: skip


async def party_names(
    session: AsyncSession, invitations: list[RfqInvitation]
) -> dict[uuid.UUID, tuple[str | None, str | None]]:
    names = await profile_names(session, [i.profile_id for i in invitations if i.profile_id])
    result: dict[uuid.UUID, tuple[str | None, str | None]] = {}
    for inv in invitations:
        if inv.profile_id is not None:
            _, display, firm = names.get(inv.profile_id, (None, None, None))
            result[inv.id] = (display, firm)
        elif inv.engagement_id is not None:
            facts = await engagement_facts(session, inv.engagement_id)
            result[inv.id] = (facts.outside_name, facts.outside_firm) if facts else (None, None)
    return result


async def _versions(session: AsyncSession, rfq_id: uuid.UUID) -> list[QuoteVersion]:
    return list(
        await session.scalars(
            select(QuoteVersion)
            .where(QuoteVersion.rfq_id == rfq_id)
            .order_by(QuoteVersion.invitation_id, QuoteVersion.version_no)
        )
    )


def comparison_out(row: Comparison) -> ComparisonOut:
    snap = row.snapshot
    return ComparisonOut(
        id=row.id,
        version_no=row.version_no,
        state=ComparisonState(row.state),
        published_at=row.published_at,
        document_file_id=row.document_file_id,
        snapshot_sha256=row.snapshot_sha256,
        build_plan_version_no=snap["build_plan_version_no"],
        counts=ComparisonCountsOut.model_validate(snap["counts"]),
        lines=[ComparisonLineOut.model_validate(x) for x in snap["lines"]],
        quotes=[ComparisonQuoteOut.model_validate(x) for x in snap["quotes"]],
        notes=snap["notes"],
    )


async def current_comparison(session: AsyncSession, rfq_id: uuid.UUID) -> Comparison | None:
    return (
        await session.scalars(
            select(Comparison).where(
                Comparison.rfq_id == rfq_id,
                Comparison.state.in_((ComparisonState.PUBLISHED.value,
                                      ComparisonState.DECIDED.value)),
            )
        )
    ).one_or_none()  # fmt: skip


async def selection_out(
    session: AsyncSession, rfq_id: uuid.UUID, invitations: list[RfqInvitation]
) -> SelectionOut | None:
    row = (await session.scalars(select(Selection).where(Selection.rfq_id == rfq_id))).one_or_none()
    if row is None:
        return None
    names = await party_names(session, invitations)
    display, firm = names.get(row.invitation_id, (None, None))
    return SelectionOut(
        quote_version_id=row.quote_version_id, contractor_name=display, firm_name=firm,
        selected_at=row.selected_at, engagement_id=row.engagement_id,
        statement_text=row.statement_text,
    )  # fmt: skip


# --- the homeowner -------------------------------------------------------------------------


async def family_rfq_out(
    session: AsyncSession, rfq: Rfq, *, owner: bool, package_ok: bool
) -> FamilyRfqOut:
    invitations = [i for i in await _invitations(session, rfq.id) if i.state != I.PROPOSED.value
                   or rfq.state == RfqState.DRAFT.value]  # fmt: skip
    names = await party_names(session, invitations)
    versions = await _versions(session, rfq.id)
    latest: dict[uuid.UUID, QuoteVersion] = {}
    for v in versions:
        latest[v.invitation_id] = v
    comparison = await current_comparison(session, rfq.id)
    version_no = (rfq.manifest or {}).get("version_no")
    selection = await selection_out(session, rfq.id, invitations)
    return FamilyRfqOut(
        id=rfq.id,
        state=RfqState(rfq.state),
        build_plan_version_no=version_no,
        created_at=rfq.created_at,
        issued_at=rfq.issued_at,
        quotes_due_at=rfq.quotes_due_at,
        cancel_reason=RfqCancelReason(rfq.cancel_reason) if rfq.cancel_reason else None,
        closed_at=rfq.closed_at,
        max_recipients=rfq.max_recipients,
        invitations=[
            FamilyInvitationOut(
                id=i.id,
                party=EngagementParty(i.party),
                source=InvitationSource(i.source),
                contractor_name=names.get(i.id, (None, None))[0],
                firm_name=names.get(i.id, (None, None))[1],
                state=I(i.state),
                sent_at=i.sent_at,
                responded_at=i.responded_at,
                latest_quote=FamilyQuoteStatusOut(
                    version_no=latest[i.id].version_no,
                    kind=QuoteVersionKind(latest[i.id].kind),
                    state=Q(latest[i.id].state),
                    submitted_at=latest[i.id].submitted_at,
                    valid_to=latest[i.id].valid_to,
                )
                if i.id in latest
                else None,
            )
            for i in invitations
        ],
        comparison=comparison_out(comparison) if comparison else None,
        selection=selection,
        can_cancel=owner and rfq.state in OPEN_RFQ,
        can_select=owner
        and package_ok
        and rfq.state == RfqState.ISSUED.value
        and comparison is not None
        and comparison.state == ComparisonState.PUBLISHED.value,
    )


async def _invitations(session: AsyncSession, rfq_id: uuid.UUID) -> list[RfqInvitation]:
    return list(
        await session.scalars(
            select(RfqInvitation)
            .where(RfqInvitation.rfq_id == rfq_id)
            .order_by(RfqInvitation.created_at, RfqInvitation.id)
        )
    )


async def family_rfqs_out(
    session: AsyncSession, settings: Settings, actor: Actor, facts: ConnectionFacts,
    accepted_version_no: int | None,
) -> FamilyRfqsOut:  # fmt: skip
    membership = await member_role(session, user_id=actor.user_id, project_id=facts.project_id)
    owner = membership is not None and membership.role == MembershipRole.OWNER
    state = await package_state(session, facts.project_id)
    package_ok = state.value == "ACTIVE"
    rows = list(
        await session.scalars(
            select(Rfq).where(Rfq.project_id == facts.project_id).order_by(Rfq.created_at.desc())
        )
    )
    engaged = await active_engagement(session, facts.project_id, CATEGORY)
    engaged_name = None
    if engaged is not None:
        if engaged.profile_id:
            names = await profile_names(session, [engaged.profile_id])
            engaged_name = names.get(engaged.profile_id, (None, None, None))[1]
        else:
            engaged_name = engaged.outside_name
    return FamilyRfqsOut(
        project_id=facts.project_id,
        package_state=state,
        accepted_build_plan_version_no=accepted_version_no,
        engaged_contractor=engaged_name,
        can_request=owner
        and package_ok
        and facts.availability == PackageAvailability.ELIGIBLE
        and accepted_version_no is not None
        and not any(r.state in OPEN_RFQ for r in rows),
        max_recipients=settings.rfq_max_recipients,
        rfqs=[await family_rfq_out(session, r, owner=owner, package_ok=package_ok) for r in rows],
    )


# --- the contractor ------------------------------------------------------------------------


def _brief(inv: RfqInvitation) -> BriefOut:
    b = inv.brief
    return BriefOut(
        locality=b.get("locality"), plot_area_sqft=b.get("plot_area_sqft"),
        built_up_area_sqft=b.get("built_up_area_sqft"), floors=b.get("floors"),
        basement=b.get("basement"), budget_band=b.get("budget_band"),
        start_window=b.get("start_window"), build_plan_accepted=bool(b.get("build_plan_accepted")),
    )  # fmt: skip


SCOPE_KEYS = ("inclusions", "exclusions", "assumptions")


def pack_out(rfq: Rfq) -> PackOut:
    """Built field by field from the frozen manifest: a key not named here never reaches a
    contractor (BP-08)."""
    m: dict[str, Any] = rfq.manifest or {}
    assert rfq.manifest_sha256 is not None  # noqa: S101 (issued)
    keep = {
        "drawings": ("file_id", "drawing_class", "floor", "title", "sheet_no", "sha256"),
        "specifications": ("code", "item", "criteria", "applicability", "value",
                           "not_applicable_reason"),
        "quantities": ("line_no", "item_code", "description", "unit", "quantity", "stage_number",
                       "floor", "spec_line_codes", "assumptions"),
        "schedule": ("entry_key", "stage_number", "stage_name", "floor", "duration_days",
                     "predecessors"),
    }  # fmt: skip
    picked = {
        k: [{f: row.get(f) for f in fields} for row in m.get(k, [])] for k, fields in keep.items()
    }
    scope = m.get("scope") or {}
    return PackOut.model_validate(
        {
            "build_plan_version_no": m["version_no"], "content_hash": m["content_hash"],
            "manifest_sha256": rfq.manifest_sha256, **picked,
            "dates_status": m.get("dates_status", ""),
            "scope": {k: list(scope.get(k) or []) for k in SCOPE_KEYS},
            "quote_format_version": int((m.get("quote_format") or {}).get("version", 1)),
        }
    )  # fmt: skip


async def _outcome(session: AsyncSession, inv: RfqInvitation) -> QuoteVersionState | None:
    states = list(
        await session.scalars(
            select(QuoteVersion.state).where(
                QuoteVersion.invitation_id == inv.id,
                QuoteVersion.state.in_((Q.SELECTED.value, Q.NOT_SELECTED.value)),
            )
        )
    )
    return Q(states[0]) if states else None


async def pro_summaries(
    session: AsyncSession, invitations: list[RfqInvitation]
) -> list[ProInvitationSummaryOut]:
    result = []
    for inv in invitations:
        rfq = await session.get_one(Rfq, inv.rfq_id)
        result.append(
            ProInvitationSummaryOut(
                id=inv.id, state=I(inv.state), locality=inv.brief.get("locality"),
                sent_at=inv.sent_at, respond_by=inv.respond_by, quotes_due_at=rfq.quotes_due_at,
                rfq_open=rfq.state == RfqState.ISSUED.value, outcome=await _outcome(session, inv),
            )
        )  # fmt: skip
    return result


async def pro_invitation_out(
    session: AsyncSession, settings: Settings, inv: RfqInvitation
) -> ProInvitationOut:
    rfq = await session.get_one(Rfq, inv.rfq_id)
    outcome = await _outcome(session, inv)
    rfq_open = rfq.state == RfqState.ISSUED.value
    accepted = inv.state == I.ACCEPTED.value
    show_pack = accepted and (rfq_open or outcome == Q.SELECTED)
    versions = list(
        await session.scalars(
            select(QuoteVersion)
            .where(QuoteVersion.invitation_id == inv.id)
            .order_by(QuoteVersion.version_no)
        )
    )
    lines = await lines_of(session, [v.id for v in versions])
    files = await file_facts(session, [f for v in versions for f in v.attachment_file_ids])
    draft = (
        await session.scalars(select(QuoteDraft).where(QuoteDraft.invitation_id == inv.id))
    ).one_or_none()
    latest = versions[-1] if versions else None
    now = await db_now(session)
    before_deadline = rfq.quotes_due_at is not None and now < rfq.quotes_due_at
    selection = (
        await session.scalars(select(Selection).where(Selection.invitation_id == inv.id))
    ).one_or_none()
    clarifications = await review.visible_to_contractor(session, inv) if accepted else []
    return ProInvitationOut(
        id=inv.id,
        state=I(inv.state),
        sent_at=inv.sent_at,
        respond_by=inv.respond_by,
        responded_at=inv.responded_at,
        decline_reason=DeclineReason(inv.decline_reason) if inv.decline_reason else None,
        withdraw_reason=InvitationWithdrawReason(inv.withdraw_reason)
        if inv.withdraw_reason
        else None,
        brief=_brief(inv),
        quotes_due_at=rfq.quotes_due_at,
        rfq_open=rfq_open,
        pack=pack_out(rfq) if show_pack else None,
        draft=draft.content if draft and rfq_open and accepted else None,
        versions=[
            ProQuoteVersionOut(
                state=Q(v.state),
                withdraw_reason=v.withdraw_reason,
                comment=v.comment,
                quote=quote_content(v, lines[v.id], files),
            )
            for v in versions
        ],
        clarifications=[
            ProClarificationOut(
                id=c.id,
                direction=c.direction,
                question=c.question,
                answer=c.answer,
                state=c.state,
                asked_at=c.asked_at,
                answered_at=c.answered_at,
                yours=yours,
            )
            for c, yours in clarifications
        ],
        outcome=outcome,
        engagement_id=selection.engagement_id if selection else None,
        can_submit=accepted and rfq_open and before_deadline,
        can_renew=accepted and rfq_open and latest is not None and latest.state == Q.EXPIRED.value,
        can_withdraw=accepted
        and rfq_open
        and latest is not None
        and latest.state == Q.SUBMITTED.value,
        attachments_max=settings.rfq_quote_attachments_max,
    )


# --- operations ----------------------------------------------------------------------------


async def ops_rfq_out(session: AsyncSession, rfq: Rfq, facts: ConnectionFacts) -> OpsRfqOut:
    invitations = await _invitations(session, rfq.id)
    names = await party_names(session, invitations)
    versions = await _versions(session, rfq.id)
    lines = await lines_of(session, [v.id for v in versions])
    adjustments = await review.adjustments_of(session, [v.id for v in versions])
    files = await file_facts(session, [f for v in versions for f in v.attachment_file_ids])
    clarifications = await session.scalars(
        select(RfqClarification)
        .where(RfqClarification.rfq_id == rfq.id)
        .order_by(RfqClarification.asked_at, RfqClarification.id)
    )
    comparisons = await session.scalars(
        select(Comparison).where(Comparison.rfq_id == rfq.id).order_by(Comparison.version_no)
    )
    events = await session.scalars(
        select(RfqEvent)
        .where(RfqEvent.rfq_id == rfq.id)
        .order_by(RfqEvent.at.desc(), RfqEvent.id)
        .limit(300)
    )
    return OpsRfqOut(
        id=rfq.id,
        project_id=rfq.project_id,
        project_code=facts.code,
        state=RfqState(rfq.state),
        package_state=await package_state(session, rfq.project_id),
        build_plan_version_id=rfq.build_plan_version_id,
        manifest_sha256=rfq.manifest_sha256,
        requested_role=rfq.requested_role,
        created_at=rfq.created_at,
        issued_at=rfq.issued_at,
        quotes_due_at=rfq.quotes_due_at,
        cancel_reason=RfqCancelReason(rfq.cancel_reason) if rfq.cancel_reason else None,
        cancel_note=rfq.cancel_note,
        max_recipients=rfq.max_recipients,
        invitations=[
            OpsInvitationOut(
                id=i.id, party=EngagementParty(i.party), source=InvitationSource(i.source),
                profile_id=i.profile_id, engagement_id=i.engagement_id,
                contractor_name=names.get(i.id, (None, None))[0],
                firm_name=names.get(i.id, (None, None))[1], introduced_reason=i.introduced_reason,
                state=I(i.state), sent_at=i.sent_at, respond_by=i.respond_by,
                responded_at=i.responded_at,
                decline_reason=DeclineReason(i.decline_reason) if i.decline_reason else None,
                decline_note=i.decline_note,
                withdraw_reason=InvitationWithdrawReason(i.withdraw_reason)
                if i.withdraw_reason else None,
                withdraw_note=i.withdraw_note, professional_contact=i.professional_contact,
            )
            for i in invitations
        ],
        quote_versions=[
            OpsQuoteVersionOut(
                invitation_id=v.invitation_id, state=Q(v.state),
                review_state=QuoteCheckState(v.review_state), withdraw_reason=v.withdraw_reason,
                comment=v.comment, evidence_file_id=v.evidence_file_id,
                content_sha256=v.content_sha256, quote=quote_content(v, lines[v.id], files),
                adjustments=[adjustment_out(a) for a in adjustments[v.id]],
            )
            for v in versions
        ],
        clarifications=[
            OpsClarificationOut(
                id=c.id, invitation_id=c.invitation_id, quote_version_id=c.quote_version_id,
                direction=c.direction, question=c.question, answer=c.answer,
                shared_with_all=c.shared_with_all, state=c.state, asked_at=c.asked_at,
                answered_at=c.answered_at, close_reason=c.close_reason,
            )
            for c in clarifications
        ],
        comparisons=[comparison_out(c) for c in comparisons],
        selection=await selection_out(session, rfq.id, invitations),
        history=[
            OpsEventOut(
                subject=e.subject, subject_id=e.subject_id, from_state=e.from_state,
                to_state=e.to_state, actor_role=e.actor_role, reason=e.reason, at=e.at,
            )
            for e in events
        ],
    )  # fmt: skip


def money(value: Decimal) -> str:
    return f"{value:,.2f}"
