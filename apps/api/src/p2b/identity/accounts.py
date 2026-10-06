"""Accounts created by operations on someone's behalf (Slice 3.2, D-04: operations-created
professional accounts). The account waits in PENDING_VERIFICATION and becomes ACTIVE the first
time its owner signs in with the emailed code, as staff accounts do."""

import uuid

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.core.errors import ValidationFailed
from p2b.core.ids import new_id
from p2b.core.vocabulary import ActorType, Audience, ContactKind
from p2b.identity.models import User, UserContact
from p2b.identity.otp import normalize_email
from p2b.identity.service import USER_ACCOUNT


async def create_account_for(
    session: AsyncSession, *, audience: Audience, email: str, created_by: uuid.UUID
) -> tuple[uuid.UUID, bool]:
    """The account for `email` on `audience`, created if it does not exist. Returns the user id
    and whether it was created now."""
    try:
        validate_email(email, check_deliverability=False)
    except EmailNotValidError:
        raise ValidationFailed(
            details={"fields": {"email": ["Enter a valid email address."]}}
        ) from None
    normalized = normalize_email(email)
    existing = await session.scalar(
        select(UserContact.user_id).where(
            UserContact.audience == audience.value,
            UserContact.kind == ContactKind.EMAIL.value,
            UserContact.normalized == normalized,
        )
    )
    if existing is not None:
        return existing, False
    status = USER_ACCOUNT.target(None, "register")
    user = User(id=new_id(), audience=audience.value, status=status.value)
    session.add(user)
    await session.flush()
    session.add(
        UserContact(
            id=new_id(), user_id=user.id, audience=audience.value, kind=ContactKind.EMAIL.value,
            value=normalized, normalized=normalized, is_primary=True,
        )
    )  # fmt: skip
    await session.flush()
    await record(
        session, action="user.registered", entity_type="user", entity_id=user.id,
        actor_type=ActorType.USER, actor_user_id=created_by,
        new_value={"status": status.value, "audience": audience.value},
        reason="account created by operations",
    )  # fmt: skip
    return user.id, True
