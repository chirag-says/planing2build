"""AI credits (L-04; SLICE3_3_READINESS C). The ledger is append-only, one row per change with
the running balance, serialised per account by an advisory lock and a UNIQUE sequence. A credit
exists only once a captured, verified payment granted it; a generation spends one only when the
family chose "Use 1 AI credit"; a failed paid generation gets it back exactly once (UNIQUE on
generation and entry)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.billing.models import AiCreditEntry
from p2b.core.errors import NoCredit
from p2b.core.ids import new_id
from p2b.core.vocabulary import ActorType, CreditEntry


async def _lock(session: AsyncSession, account_user_id: uuid.UUID) -> None:
    await session.execute(
        select(func.pg_advisory_xact_lock(func.hashtext(f"billing-credits:{account_user_id}")))
    )


async def _last(session: AsyncSession, account_user_id: uuid.UUID) -> AiCreditEntry | None:
    return (
        await session.scalars(
            select(AiCreditEntry)
            .where(AiCreditEntry.account_user_id == account_user_id)
            .order_by(AiCreditEntry.sequence.desc())
            .limit(1)
        )
    ).one_or_none()


async def credit_balance(session: AsyncSession, account_user_id: uuid.UUID) -> int:
    last = await _last(session, account_user_id)
    return last.balance_after if last else 0


async def _append(
    session: AsyncSession,
    account_user_id: uuid.UUID,
    entry: CreditEntry,
    quantity: int,
    **refs: uuid.UUID | None,
) -> AiCreditEntry:
    last = await _last(session, account_user_id)
    balance = (last.balance_after if last else 0) + quantity
    if balance < 0:
        raise NoCredit
    row = AiCreditEntry(
        id=new_id(),
        account_user_id=account_user_id,
        sequence=(last.sequence if last else 0) + 1,
        entry=entry.value,
        quantity=quantity,
        balance_after=balance,
        **refs,
    )
    session.add(row)
    await session.flush()
    await record(
        session,
        action=f"ai_credit.{entry.value.lower()}",
        entity_type="ai_credit_entry",
        entity_id=row.id,
        actor_type=ActorType.SYSTEM,
        actor_user_id=account_user_id,
        new_value={"quantity": quantity, "balance_after": balance},
    )
    return row


async def grant_credits(
    session: AsyncSession, *, account_user_id: uuid.UUID, order_id: uuid.UUID, quantity: int
) -> None:
    """Called only by payment processing, after a verified capture. Once per order."""
    await _lock(session, account_user_id)
    exists = await session.scalar(
        select(AiCreditEntry.id).where(
            AiCreditEntry.order_id == order_id, AiCreditEntry.entry == CreditEntry.GRANT.value
        )
    )
    if exists is None:
        await _append(session, account_user_id, CreditEntry.GRANT, quantity, order_id=order_id)


async def consume_credit(
    session: AsyncSession, *, account_user_id: uuid.UUID, generation_id: uuid.UUID
) -> uuid.UUID:
    """Spend one credit on a named generation, in the caller's transaction; NoCredit (409) when
    the balance is zero. Returns the ledger entry, which the generation names as `credit_ref`."""
    await _lock(session, account_user_id)
    return (
        await _append(
            session, account_user_id, CreditEntry.CONSUME, -1, generation_id=generation_id
        )
    ).id


async def return_credit(session: AsyncSession, *, generation_id: uuid.UUID) -> bool:
    """Give back the credit a failed paid generation spent. Exactly once: a second call finds
    the RETURN and does nothing. Returns whether a credit was returned now."""
    consumed = (
        await session.scalars(
            select(AiCreditEntry).where(
                AiCreditEntry.generation_id == generation_id,
                AiCreditEntry.entry == CreditEntry.CONSUME.value,
            )
        )
    ).one_or_none()
    if consumed is None:
        return False
    await _lock(session, consumed.account_user_id)
    returned = await session.scalar(
        select(AiCreditEntry.id).where(
            AiCreditEntry.generation_id == generation_id,
            AiCreditEntry.entry == CreditEntry.RETURN.value,
        )
    )
    if returned is not None:
        return False
    await _append(
        session, consumed.account_user_id, CreditEntry.RETURN, 1, generation_id=generation_id
    )
    return True


async def revoke_credits(
    session: AsyncSession,
    *,
    account_user_id: uuid.UUID,
    order_id: uuid.UUID,
    refund_request_id: uuid.UUID,
    quantity: int,
) -> None:
    """Remove refunded, unused credits; NoCredit when fewer remain than asked."""
    await _lock(session, account_user_id)
    for _ in range(quantity):
        await _append(
            session,
            account_user_id,
            CreditEntry.REVOKE,
            -1,
            order_id=order_id,
            refund_request_id=refund_request_id,
        )


async def ledger(session: AsyncSession, account_user_id: uuid.UUID) -> list[AiCreditEntry]:
    return list(
        await session.scalars(
            select(AiCreditEntry)
            .where(AiCreditEntry.account_user_id == account_user_id)
            .order_by(AiCreditEntry.sequence.desc())
            .limit(100)
        )
    )
