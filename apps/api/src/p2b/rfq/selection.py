"""The homeowner's selection (SLICE3_6_READINESS M, N, T.6; QD-01, QD-02, QD-12, QD-13).

The owner selects one quote version of the current published comparison with a one-time code,
confirming the ACTIVE selection statement (versioned configuration; wording pending final client
and legal confirmation). Guards: the quote is still SUBMITTED, REVIEWED and valid today, the
contractor still LISTED, the package ACTIVE, no other party engaged. In one transaction: the
selection row, the engagement created or reused through the engagements module (ADR-024), the
other open connections withdrawn (N-02), every other submitted quote NOT_SELECTED, invitations
closed, the comparison DECIDED, the RFQ CLOSED, and the RFQ_SELECTION substantial-work record
written through billing's interface (QD-02, a new product decision; N-12 unchanged). There is no
second contractor confirmation and no contract value. Immutable."""

import uuid
from string import Template

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.billing.interface import record_service_usage
from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.vocabulary import (
    ComparisonState,
    ConfigStatus,
    EngagementParty,
    InvitationState,
    InvitationWithdrawReason,
    NeedState,
    OtpPurpose,
    PackageServiceKind,
    QuoteCheckState,
    QuoteVersionState,
    RfqState,
)
from p2b.engagements.interface import engage_for_selection, lock_category
from p2b.identity.interface import Actor, primary_emails, verify_confirmation
from p2b.professionals.interface import connection_candidate
from p2b.projects.interface import ConnectionFacts
from p2b.rfq import comparison, quotes, rfqs
from p2b.rfq.common import (
    CATEGORY,
    RFQ,
    Who,
    conflict,
    db_now,
    history,
    notify,
    require_package,
    today,
)
from p2b.rfq.models import (
    Comparison,
    QuoteVersion,
    Rfq,
    RfqInvitation,
    Selection,
    SelectionStatement,
)
from p2b.rfq.views import party_names

Q = QuoteVersionState
STATEMENT_FIELDS = {"project_code": "P2B-TEST", "contractor": "TEST", "version_no": "1"}


# --- statements (versioned configuration, like the acceptance statement) -------------------


async def active_statement(session: AsyncSession) -> SelectionStatement:
    row = (
        await session.scalars(
            select(SelectionStatement).where(SelectionStatement.status == ConfigStatus.ACTIVE.value)
        )
    ).one_or_none()
    if row is None:
        raise conflict("NO_STATEMENT", "No selection statement is active.")
    return row


async def statements(session: AsyncSession) -> list[SelectionStatement]:
    return list(
        await session.scalars(select(SelectionStatement).order_by(SelectionStatement.version))
    )


async def draft_statement(
    session: AsyncSession, who: Who, text: str, note: str
) -> SelectionStatement:
    try:
        Template(text).substitute(STATEMENT_FIELDS)
    except (KeyError, ValueError):
        raise ValidationFailed(
            details={"fields": {"text": ["Use only $project_code, $contractor, $version_no."]}}
        ) from None
    latest = max((s.version for s in await statements(session)), default=0)
    row = SelectionStatement(
        id=new_id(), version=latest + 1, text=text.strip(), status=ConfigStatus.DRAFT.value,
        note=note, created_by=who.user_id,
    )  # fmt: skip
    session.add(row)
    await session.flush()
    return row


async def activate_statement(session: AsyncSession, who: Who, statement_id: uuid.UUID) -> None:
    row = await session.get(SelectionStatement, statement_id, with_for_update=True)
    if row is None:
        raise NotFound
    if row.status != ConfigStatus.DRAFT.value:
        raise StateConflict(details={"current_state": row.status})
    current = (
        await session.scalars(
            select(SelectionStatement)
            .where(SelectionStatement.status == ConfigStatus.ACTIVE.value)
            .with_for_update()
        )
    ).one_or_none()
    if current is not None:
        current.status = ConfigStatus.RETIRED.value
        await session.flush()
    row.status = ConfigStatus.ACTIVE.value
    row.activated_by = who.user_id
    row.activated_at = await db_now(session)
    await session.flush()


async def statement_text(
    session: AsyncSession, facts: ConnectionFacts, qv: QuoteVersion, inv: RfqInvitation
) -> tuple[SelectionStatement, str]:
    row = await active_statement(session)
    display, firm = (await party_names(session, [inv])).get(inv.id, (None, None))
    text = Template(row.text).substitute(
        project_code=facts.code, contractor=firm or display or "the contractor",
        version_no=str(qv.version_no),
    )  # fmt: skip
    return row, text


# --- selection ----------------------------------------------------------------------------


async def selectable(
    session: AsyncSession, rfq_id: uuid.UUID, project_id: uuid.UUID, qv_id: uuid.UUID,
    *, lock: bool = False,
) -> tuple[Rfq, Comparison, QuoteVersion, RfqInvitation]:  # fmt: skip
    """Every QD-12 guard except the code; the code request and the selection share it."""
    rfq = await rfqs.rfq_row(session, rfq_id, lock=lock)
    if rfq.project_id != project_id:
        raise NotFound
    if rfq.state != RfqState.ISSUED.value:
        raise StateConflict(details={"current_state": rfq.state})
    await require_package(session, project_id)
    current = (
        await session.scalars(
            select(Comparison).where(
                Comparison.rfq_id == rfq.id, Comparison.state == ComparisonState.PUBLISHED.value
            )
        )
    ).one_or_none()
    if current is None:
        raise conflict("NO_COMPARISON", "No comparison is published.")
    qv = await session.get(QuoteVersion, qv_id, with_for_update=lock)
    if qv is None or qv.rfq_id != rfq.id:
        raise NotFound
    if qv.id not in current.quote_version_ids:
        raise conflict("STALE", "Choose a quote from the current comparison.")
    if qv.state != Q.SUBMITTED.value or qv.review_state != QuoteCheckState.REVIEWED.value:
        raise conflict("STALE", "This quote version is no longer current.")
    day = await today(session)
    if not qv.valid_from <= day <= qv.valid_to:
        raise conflict("EXPIRED", "This quote is not valid today.")
    inv = await session.get_one(RfqInvitation, qv.invitation_id)
    if inv.profile_id is not None:
        candidate = await connection_candidate(session, inv.profile_id, CATEGORY, (0.0, 0.0))
        if candidate is None or not candidate.listed:
            raise conflict("NOT_LISTED", "This contractor is not listed now.")
    return rfq, current, qv, inv


async def select_quote(
    session: AsyncSession,
    database: Database,
    settings: Settings,
    actor: Actor,
    facts: ConnectionFacts,
    rfq_id: uuid.UUID,
    *,
    quote_version_id: uuid.UUID,
    challenge_id: uuid.UUID,
    code: str,
    statement_id: uuid.UUID,
    contact_name: str,
    contact_phone: str,
    ip_hash: str,
) -> Selection:
    who = Who(actor.user_id, "FAMILY", actor.session_id)
    rfq, current, qv, inv = await selectable(
        session, rfq_id, facts.project_id, quote_version_id, lock=True
    )
    if await lock_category(session, facts.project_id, CATEGORY) == NeedState.NOT_NEEDED:
        raise conflict("NOT_NEEDED", "You marked contractor work as not needed.")
    statement, text = await statement_text(session, facts, qv, inv)
    if statement.id != statement_id:
        raise conflict("STATEMENT_CHANGED", "The selection statement changed; read it again.")
    await verify_confirmation(
        database, settings, challenge_id=challenge_id, code=code, user_id=actor.user_id,
        purpose=OtpPurpose.SELECT_QUOTE, subject_id=qv.id, ip_hash=ip_hash,
    )  # fmt: skip
    email = (await primary_emails(session, [actor.user_id])).get(actor.user_id)
    selection_id = new_id()
    engagement_id, created = await engage_for_selection(
        session, project_id=facts.project_id, code=CATEGORY, profile_id=inv.profile_id,
        outside_engagement_id=inv.engagement_id, selection_id=selection_id,
        family_contact={"name": contact_name, "phone": contact_phone, "email": email,
                        "site_address": None},
        professional_contact=inv.professional_contact, by_user_id=actor.user_id,
    )  # fmt: skip
    row = Selection(
        id=selection_id, rfq_id=rfq.id, project_id=rfq.project_id, comparison_id=current.id,
        quote_version_id=qv.id, invitation_id=inv.id, engagement_id=engagement_id,
        engagement_created=created, selected_by=actor.user_id, challenge_id=challenge_id,
        statement_id=statement.id, statement_text=text, ip_hash=ip_hash,
    )  # fmt: skip
    session.add(row)
    await session.flush()
    await history(
        session, project_id=rfq.project_id, rfq_id=rfq.id, subject="SELECTION",
        subject_id=row.id, old=None, new="CONFIRMED", who=who,
        detail={"quote_version_id": str(qv.id), "engagement_created": created},
    )  # fmt: skip
    await quotes.move(session, qv, "select", who)
    for other in await quotes.latest_submitted(session, rfq.id):
        if other.id != qv.id:
            await quotes.move(session, other, "not_select", who)
    await comparison.move(session, current, "decide", who)
    rfq.closed_at = await db_now(session)
    old = rfq.state
    rfq.state = RFQ.target(RfqState(old), "select").value
    rfq.version += 1
    await session.flush()
    await history(
        session, project_id=rfq.project_id, rfq_id=rfq.id, subject="RFQ", subject_id=rfq.id,
        old=old, new=rfq.state, who=who,
    )  # fmt: skip
    # Notices before the clean-up, which withdraws unanswered invitations with their own notice.
    for other_inv in await rfqs.invitations_of(session, rfq.id):
        if other_inv.profile_id is None or other_inv.state != InvitationState.ACCEPTED.value:
            continue
        outcome = await session.scalar(
            select(QuoteVersion.state).where(
                QuoteVersion.invitation_id == other_inv.id,
                QuoteVersion.state.in_((Q.SELECTED.value, Q.NOT_SELECTED.value)),
            )
        )
        notice = {Q.SELECTED.value: "SELECTED", Q.NOT_SELECTED.value: "NOT_SELECTED"}.get(
            str(outcome), "RFQ_CLOSED"
        )
        await notify(
            session, "contractor", notice, aggregate_id=other_inv.id, rfq_id=rfq.id,
            ref_id=other_inv.id,
        )  # fmt: skip
    await rfqs.close_open_work(session, rfq, InvitationWithdrawReason.RFQ_CLOSED, who)
    # QD-02: a new product decision. N-12 (CONNECTION_ACCEPTED) is unchanged and untouched here.
    await record_service_usage(session, rfq.project_id, PackageServiceKind.RFQ_SELECTION, row.id)
    await notify(session, "family", "SELECTION_CONFIRMED", aggregate_id=rfq.id, rfq_id=rfq.id)
    await notify(session, "ops", "SELECTION_CONFIRMED", aggregate_id=rfq.id, rfq_id=rfq.id)
    return row


def party_is_outside(inv: RfqInvitation) -> bool:
    return inv.party == EngagementParty.OUTSIDE.value
