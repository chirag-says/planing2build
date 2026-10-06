"""Public interface of the rfq module. Notifications read what an email may say about an RFQ
notice (SLICE3_6_READINESS R); nothing else calls in. A contractor's email never names the
homeowner, another contractor, a price or a ranking (QD-09, QD-20)."""

import uuid
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from p2b.professionals.interface import profile_names
from p2b.projects.interface import connection_facts
from p2b.rfq.common import LOCAL_TIMEZONE
from p2b.rfq.models import Rfq, RfqInvitation


@dataclass(frozen=True)
class RfqNotice:
    """`user_id` is None for an operations notice (the operations mailbox)."""

    user_id: uuid.UUID | None
    values: dict[str, str]


def _when(rfq: Rfq) -> str:
    if rfq.quotes_due_at is None:
        return "not set"
    local = rfq.quotes_due_at.astimezone(ZoneInfo(LOCAL_TIMEZONE))
    return local.strftime("%d %b %Y, %H:%M IST")


async def family_notice(session: AsyncSession, rfq_id: uuid.UUID) -> RfqNotice | None:
    rfq = await session.get(Rfq, rfq_id)
    facts = await connection_facts(session, rfq.project_id) if rfq else None
    if rfq is None or facts is None:
        return None
    return RfqNotice(facts.owner_user_id, {"code": facts.code, "deadline": _when(rfq)})


async def ops_notice(session: AsyncSession, rfq_id: uuid.UUID) -> RfqNotice | None:
    rfq = await session.get(Rfq, rfq_id)
    facts = await connection_facts(session, rfq.project_id) if rfq else None
    if rfq is None or facts is None:
        return None
    return RfqNotice(None, {"code": facts.code, "deadline": _when(rfq)})


async def contractor_notice(session: AsyncSession, invitation_id: uuid.UUID) -> RfqNotice | None:
    inv = await session.get(RfqInvitation, invitation_id)
    if inv is None or inv.profile_id is None:
        return None
    rfq = await session.get_one(Rfq, inv.rfq_id)
    names = await profile_names(session, [inv.profile_id])
    if inv.profile_id not in names:
        return None
    user_id = names[inv.profile_id][0]
    hours = "48"
    if inv.respond_by is not None and inv.sent_at is not None:
        hours = str(round((inv.respond_by - inv.sent_at).total_seconds() / 3600))
    return RfqNotice(
        user_id,
        {"locality": str(inv.brief.get("locality") or "your area"), "deadline": _when(rfq),
         "hours": hours},
    )  # fmt: skip


__all__ = ["RfqNotice", "contractor_notice", "family_notice", "ops_notice"]
