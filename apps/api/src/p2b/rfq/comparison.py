"""The structured comparison (SLICE3_6_READINESS L, T.5; QD-10, QD-11, QD-23, QD-24).

Publishing freezes a snapshot of every current, REVIEWED quote version of the RFQ: each quote as
submitted, its adjustment list, the submitted, adjustment and normalised totals, and the RFQ's
quantity lines. Quotes appear in an order drawn from a seed stored with the version: the order
depends on nothing but the seed and the version ids, never on price, identity or preference. No
rank, score, "lowest", "best" or recommendation exists (the recommendation engine is deferred,
QD-10). A deterministic fpdf2 document is rendered and stored at publication and never again
(ADR-023). A later change needs a new comparison version."""

import hashlib
import secrets
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.config import Settings
from p2b.core.errors import StateConflict
from p2b.core.ids import new_id
from p2b.core.storage import Storage
from p2b.core.vocabulary import (
    ComparisonState,
    FilePurpose,
    InvitationState,
    QuoteCheckState,
    QuoteVersionState,
    RfqState,
)
from p2b.documents.interface import file_facts, store_generated_file
from p2b.rfq import pdf, review, rfqs
from p2b.rfq.common import COMPARISON, Who, conflict, db_now, history, notify, require_package
from p2b.rfq.models import Comparison, QuoteVersion
from p2b.rfq.quotes import count_received, lines_of
from p2b.rfq.views import adjustment_out, party_names, quote_content

NOTES = (
    "Quotes are shown as each contractor submitted them. Plan2Build's adjustments are listed "
    "separately and never change a contractor's price.",
    "The order of the quotes is neutral: it is drawn at random for this comparison version and "
    "does not depend on price, contractor or any commercial interest.",
    "Plan2Build does not rank quotes or name a winner. You choose.",
    "Plan2Build is not a party to the construction contract and receives no construction money.",
)


def neutral_order(seed: str, version_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """QD-11: sorted by a hash of the stored seed and the version id only."""
    return sorted(version_ids, key=lambda v: hashlib.sha256(f"{seed}:{v}".encode()).hexdigest())


async def candidates(session: AsyncSession, rfq_id: uuid.UUID) -> list[QuoteVersion]:
    """The current SUBMITTED, REVIEWED version of each invitation."""
    return list(
        await session.scalars(
            select(QuoteVersion).where(
                QuoteVersion.rfq_id == rfq_id,
                QuoteVersion.state == QuoteVersionState.SUBMITTED.value,
                QuoteVersion.review_state == QuoteCheckState.REVIEWED.value,
            )
        )
    )


async def build_snapshot(
    session: AsyncSession, rfq_id: uuid.UUID, versions: list[QuoteVersion], seed: str
) -> dict[str, Any]:
    rfq = await rfqs.rfq_row(session, rfq_id)
    assert rfq.manifest is not None  # noqa: S101 (ISSUED)
    invitations = await rfqs.invitations_of(session, rfq.id)
    by_inv = {i.id: i for i in invitations}
    names = await party_names(session, invitations)
    by_id = {v.id: v for v in versions}
    ids = neutral_order(seed, list(by_id))
    lines = await lines_of(session, ids)
    adjustments = await review.adjustments_of(session, ids)
    files = await file_facts(session, [f for v in versions for f in v.attachment_file_ids])
    quotes = []
    for vid in ids:
        v = by_id[vid]
        adj_total = sum((a.rupee_impact for a in adjustments[vid]), Decimal("0.00"))
        display, firm = names.get(v.invitation_id, (None, None))
        quotes.append(
            {
                "quote_version_id": str(v.id), "invitation_id": str(v.invitation_id),
                "contractor_name": display, "firm_name": firm,
                "party": by_inv[v.invitation_id].party,
                "quote": quote_content(v, lines[vid], files).model_dump(mode="json"),
                "adjustments": [adjustment_out(a).model_dump(mode="json")
                                for a in adjustments[vid]],
                "adjustments_total": str(adj_total),
                "normalised_total": str(v.comparable_total + adj_total),
            }
        )  # fmt: skip
    invited = sum(
        i.state not in (InvitationState.PROPOSED.value,)
        and not (i.state == InvitationState.WITHDRAWN.value and i.withdraw_reason == "REMOVED")
        for i in invitations
    )
    return {
        "rfq_id": str(rfq.id),
        "project_code": rfq.manifest["project_code"],
        "build_plan_version_no": rfq.manifest["version_no"],
        "manifest_sha256": rfq.manifest_sha256,
        "counts": {
            "invited": invited,
            "quotes_received": await count_received(session, rfq.id),
            "included": len(quotes),
        },
        "lines": [
            {
                "line_no": q["line_no"],
                "description": q["description"],
                "unit": q["unit"],
                "quantity": q["quantity"],
            }
            for q in rfq.manifest["quantities"]
        ],
        "quotes": quotes,
        "notes": list(NOTES),
    }


async def publish(
    session: AsyncSession, settings: Settings, storage: Storage, who: Who, rfq_id: uuid.UUID
) -> Comparison:
    """T.5: one or more REVIEWED versions (QD-24); the previous published version is
    SUPERSEDED, never edited."""
    rfq = await rfqs.rfq_row(session, rfq_id, lock=True)
    if rfq.state != RfqState.ISSUED.value:
        raise StateConflict(details={"current_state": rfq.state})
    await require_package(session, rfq.project_id)
    versions = await candidates(session, rfq.id)
    if not versions:
        raise conflict("NO_REVIEWED_QUOTES", "No reviewed quote can be compared yet.")
    seed = secrets.token_hex(16)
    snapshot = await build_snapshot(session, rfq.id, versions, seed)
    digest = rfqs.sha256(snapshot)
    now = await db_now(session)
    number = (
        await session.scalar(
            select(func.coalesce(func.max(Comparison.version_no), 0)).where(
                Comparison.rfq_id == rfq.id
            )
        )
        or 0
    ) + 1
    data = pdf.render(settings, snapshot, version_no=number, published_at=now)
    document_id = await store_generated_file(
        session, settings, storage, project_id=rfq.project_id, owner_user_id=who.user_id
        or rfq.requested_by, purpose=FilePurpose.COMPARISON_DOCUMENT, data=data,
        mime="application/pdf",
        file_name=f"{snapshot['project_code']}-quote-comparison-v{number}.pdf",
    )  # fmt: skip
    for earlier in await session.scalars(
        select(Comparison)
        .where(Comparison.rfq_id == rfq.id, Comparison.state == ComparisonState.PUBLISHED.value)
        .with_for_update()
    ):
        await move(session, earlier, "supersede", who, f"version {number} published")
    row = Comparison(
        id=new_id(), rfq_id=rfq.id, project_id=rfq.project_id, version_no=number,
        state=COMPARISON.target(None, "publish").value,
        quote_version_ids=[uuid.UUID(q["quote_version_id"]) for q in snapshot["quotes"]],
        order_seed=seed, snapshot=snapshot, snapshot_sha256=digest,
        document_file_id=document_id, published_by=who.user_id, published_at=now,
    )  # fmt: skip
    session.add(row)
    await session.flush()
    await history(
        session, project_id=rfq.project_id, rfq_id=rfq.id, subject="COMPARISON",
        subject_id=row.id, old=None, new=row.state, who=who,
        detail={"version_no": number, "quotes": len(snapshot["quotes"])},
    )  # fmt: skip
    await notify(
        session, "family", "COMPARISON_PUBLISHED", aggregate_id=rfq.id, rfq_id=rfq.id,
        ref_id=row.id,
    )  # fmt: skip
    return row


async def move(
    session: AsyncSession, row: Comparison, trigger: str, who: Who, reason: str | None = None
) -> None:
    old = row.state
    row.state = COMPARISON.target(ComparisonState(old), trigger).value
    row.version += 1
    await session.flush()
    await history(
        session, project_id=row.project_id, rfq_id=row.rfq_id, subject="COMPARISON",
        subject_id=row.id, old=old, new=row.state, who=who, reason=reason,
    )  # fmt: skip


def document_sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
