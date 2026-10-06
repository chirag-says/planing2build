"""Item rate cards for Build Plan BOQs (Slice 3.5, BP-06). Operations prepare a DRAFT card and
its lines; an ADMIN publishes it; published and retired cards never change (lines frozen by
trigger). No Raipur rate is invented: production cards hold what operations enter, with their
source. DEMO cards are development values only: production refuses to publish or price with
them. Callers audit."""

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.catalog.models import ItemRateCard, ItemRateCardLine
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.vocabulary import RateCardStatus

ITEM_CODE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,39}$")
MAX_LINES = 2000


@dataclass(frozen=True)
class RateLine:
    item_code: str
    description: str
    unit: str
    rate: Decimal


@dataclass(frozen=True)
class ItemRateCardView:
    id: uuid.UUID
    geography: str
    version: int
    status: RateCardStatus
    is_demo: bool
    effective_from: date
    effective_to: date | None
    source_reference: str
    note: str | None
    prepared_by: uuid.UUID
    published_by: uuid.UUID | None
    lines: dict[str, RateLine]


async def _now(session: AsyncSession) -> datetime:
    with session.sync_session.no_autoflush:
        now: datetime = (await session.execute(select(func.now()))).scalar_one()
    return now


async def _row(session: AsyncSession, card_id: uuid.UUID, *, lock: bool = False) -> ItemRateCard:
    card = await session.get(ItemRateCard, card_id, with_for_update=lock)
    if card is None:
        raise NotFound
    return card


async def item_rate_card(session: AsyncSession, card_id: uuid.UUID) -> ItemRateCardView:
    card = await _row(session, card_id)
    lines = await session.scalars(
        select(ItemRateCardLine)
        .where(ItemRateCardLine.card_id == card_id)
        .order_by(ItemRateCardLine.item_code)
    )
    return ItemRateCardView(
        card.id, card.geography, card.version, RateCardStatus(card.status), card.is_demo,
        card.effective_from, card.effective_to, card.source_reference, card.note,
        card.prepared_by, card.published_by,
        {line.item_code: RateLine(line.item_code, line.description, line.unit, line.rate)
         for line in lines},
    )  # fmt: skip


async def item_rate_cards(session: AsyncSession) -> list[ItemRateCardView]:
    ids = await session.scalars(
        select(ItemRateCard.id).order_by(ItemRateCard.geography, ItemRateCard.version.desc())
    )
    return [await item_rate_card(session, card_id) for card_id in ids]


async def create_item_rate_card(
    session: AsyncSession,
    *,
    geography: str,
    effective_from: date,
    effective_to: date | None,
    source_reference: str,
    note: str | None,
    is_demo: bool,
    prepared_by: uuid.UUID,
) -> ItemRateCard:
    if effective_to is not None and effective_to < effective_from:
        raise ValidationFailed(details={"fields": {"effective_to": ["Ends before it starts."]}})
    latest = await session.scalar(
        select(func.max(ItemRateCard.version)).where(ItemRateCard.geography == geography)
    )
    card = ItemRateCard(
        id=new_id(),
        geography=geography,
        version=(latest or 0) + 1,
        status=RateCardStatus.DRAFT.value,
        is_demo=is_demo,
        effective_from=effective_from,
        effective_to=effective_to,
        source_reference=source_reference,
        note=note,
        prepared_by=prepared_by,
    )
    session.add(card)
    await session.flush()
    return card


async def set_item_rate_lines(
    session: AsyncSession, card_id: uuid.UUID, lines: list[RateLine]
) -> None:
    """Replace a DRAFT card's lines."""
    card = await _row(session, card_id, lock=True)
    if card.status != RateCardStatus.DRAFT.value:
        raise StateConflict(details={"current_state": card.status})
    if len(lines) > MAX_LINES:
        raise ValidationFailed(details={"fields": {"lines": ["Too many lines."]}})
    codes = [line.item_code for line in lines]
    bad = [code for code in codes if not ITEM_CODE.match(code)]
    if bad or len(set(codes)) != len(codes):
        raise ValidationFailed(
            details={"fields": {"lines": ["Item codes must be unique: A-Z, 0-9, '.', '_', '-'."]}}
        )
    if any(
        line.rate < 0 or not line.unit.strip() or not line.description.strip() for line in lines
    ):
        raise ValidationFailed(
            details={"fields": {"lines": ["Each line needs a unit and a rate."]}}
        )
    await session.execute(delete(ItemRateCardLine).where(ItemRateCardLine.card_id == card_id))
    for line in lines:
        session.add(
            ItemRateCardLine(
                id=new_id(), card_id=card_id, item_code=line.item_code,
                description=line.description.strip(), unit=line.unit.strip(), rate=line.rate,
            )
        )  # fmt: skip
    await session.flush()


async def publish_item_rate_card(
    session: AsyncSession, card_id: uuid.UUID, *, publisher: uuid.UUID, allow_demo: bool
) -> ItemRateCard:
    """DRAFT to PUBLISHED. A DEMO card is refused where DEMO values are not allowed
    (production)."""
    card = await _row(session, card_id, lock=True)
    if card.status != RateCardStatus.DRAFT.value:
        raise StateConflict(details={"current_state": card.status})
    if card.is_demo and not allow_demo:
        raise StateConflict(
            message="DEMO rate cards cannot be published here.", details={"reason": "DEMO_CARD"}
        )
    count = await session.scalar(
        select(func.count())
        .select_from(ItemRateCardLine)
        .where(ItemRateCardLine.card_id == card_id)
    )
    if not count:
        raise ValidationFailed(details={"fields": {"lines": ["Add at least one line."]}})
    now = await _now(session)
    card.status = RateCardStatus.PUBLISHED.value
    card.published_by = publisher
    card.published_at = now
    await session.flush()
    return card


async def retire_item_rate_card(session: AsyncSession, card_id: uuid.UUID) -> ItemRateCard:
    card = await _row(session, card_id, lock=True)
    if card.status != RateCardStatus.PUBLISHED.value:
        raise StateConflict(details={"current_state": card.status})
    now = await _now(session)
    card.status = RateCardStatus.RETIRED.value
    card.retired_at = now
    await session.flush()
    return card
