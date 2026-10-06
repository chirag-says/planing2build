"""Auditor appointments (EX-09; SLICE3_7_READINESS F.3). ADMIN appoints and ends; the record
holds a unique auditor ID, qualification and credential information, and optionally a linked
professionals-host account. Auditors need not be Plan2Build professionals. An auditor with an
account reaches only the inspections assigned to its active appointment."""

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.assurance.common import conflict, db_now, history
from p2b.assurance.models import AuditorAppointment
from p2b.construction.interface import Who
from p2b.core.errors import NotFound
from p2b.core.ids import new_id
from p2b.core.vocabulary import AppointmentStatus, Audience
from p2b.identity.interface import Actor, create_account_for


async def appoint(
    session: AsyncSession, who: Who, *, name: str, qualification: str,
    registration_reference: str | None, credential_file_id: uuid.UUID | None,
    account_email: str | None,
) -> AuditorAppointment:  # fmt: skip
    assert who.user_id is not None  # noqa: S101 (ADMIN acts)
    user_id = None
    if account_email:
        user_id, _ = await create_account_for(
            session, audience=Audience.PRO, email=account_email, created_by=who.user_id
        )
        taken = await session.scalar(
            select(AuditorAppointment.id).where(
                AuditorAppointment.user_id == user_id,
                AuditorAppointment.status == AppointmentStatus.ACTIVE.value,
            )
        )
        if taken is not None:
            raise conflict("ACCOUNT_APPOINTED", "That account already has an active appointment.")
    number = (await session.execute(text("SELECT nextval('auditor_code_seq')"))).scalar_one()
    row = AuditorAppointment(
        id=new_id(), auditor_code=f"AUD-{number:05d}", name=name, qualification=qualification,
        registration_reference=registration_reference, credential_file_id=credential_file_id,
        user_id=user_id, status=AppointmentStatus.ACTIVE.value, appointed_by=who.user_id,
    )  # fmt: skip
    session.add(row)
    await session.flush()
    await history(
        session, subject="APPOINTMENT", subject_id=row.id, project_id=None, old=None,
        new=AppointmentStatus.ACTIVE.value, who=who,
        detail={"auditor_code": row.auditor_code, "has_account": user_id is not None},
    )  # fmt: skip
    return row


async def end(session: AsyncSession, who: Who, appointment_id: uuid.UUID, reason: str) -> None:
    """Inspections already assigned stay with it; operations cancel or reassign them."""
    row = await session.get(AuditorAppointment, appointment_id, with_for_update=True)
    if row is None:
        raise NotFound
    if row.status != AppointmentStatus.ACTIVE.value:
        raise conflict("ENDED", "This appointment has ended.")
    now = await db_now(session)
    row.status = AppointmentStatus.ENDED.value
    row.ended_by = who.user_id
    row.ended_at = now
    row.end_reason = reason
    await session.flush()
    await history(
        session, subject="APPOINTMENT", subject_id=row.id, project_id=None,
        old=AppointmentStatus.ACTIVE.value, new=AppointmentStatus.ENDED.value, who=who,
        reason=reason,
    )  # fmt: skip


async def active(session: AsyncSession, appointment_id: uuid.UUID) -> AuditorAppointment:
    row = await session.get(AuditorAppointment, appointment_id)
    if row is None:
        raise NotFound
    if row.status != AppointmentStatus.ACTIVE.value:
        raise conflict("APPOINTMENT_ENDED", "This auditor's appointment has ended.")
    return row


async def of_actor(session: AsyncSession, actor: Actor) -> AuditorAppointment:
    """The signed-in auditor's active appointment; anything else is 404."""
    row = (
        await session.scalars(
            select(AuditorAppointment).where(
                AuditorAppointment.user_id == actor.user_id,
                AuditorAppointment.status == AppointmentStatus.ACTIVE.value,
            )
        )
    ).one_or_none()
    if row is None:
        raise NotFound
    return row


async def listing(session: AsyncSession) -> list[AuditorAppointment]:
    return list(
        await session.scalars(select(AuditorAppointment).order_by(AuditorAppointment.auditor_code))
    )
