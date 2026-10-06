"""Staff accounts and their global roles (SECURITY 4.1 and 4.2; gap G-01; SLICE2_READINESS 1).

There is no self-registration on the operations host. A staff account is created here as
PENDING_VERIFICATION with an unverified email; the person's first sign-in by emailed code verifies
it (the "account created by operations" path in `otp._sign_in`). Roles are granted and revoked
here, always with a reason, always audited. Revoking a role ends every session of that account,
so a removed permission cannot outlive the change.

Until an admin screen exists, grants are made from the server shell:
    python -m p2b.identity.staff grant --email a@b.in --role OPS --reason "Joined operations"
    python -m p2b.identity.staff revoke --email a@b.in --role OPS --reason "Left the team"
"""

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.core.config import Settings, get_settings
from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.vocabulary import ActorType, Audience, ContactKind, StaffRole, UserStatus
from p2b.identity.models import MfaSecret, Session, StaffRoleGrant, User, UserContact
from p2b.identity.otp import normalize_email
from p2b.identity.service import USER_ACCOUNT


async def active_roles(session: AsyncSession, user_id: uuid.UUID) -> frozenset[StaffRole]:
    rows = await session.scalars(
        select(StaffRoleGrant.role).where(
            StaffRoleGrant.user_id == user_id, StaffRoleGrant.revoked_at.is_(None)
        )
    )
    return frozenset(StaffRole(role) for role in rows)


async def _staff_user(session: AsyncSession, normalized: str) -> User | None:
    contact = (
        await session.scalars(
            select(UserContact).where(
                UserContact.audience == Audience.OPS.value,
                UserContact.kind == ContactKind.EMAIL.value,
                UserContact.normalized == normalized,
            )
        )
    ).one_or_none()
    return None if contact is None else await session.get_one(User, contact.user_id)


async def grant_role(
    session: AsyncSession,
    *,
    email: str,
    role: StaffRole,
    reason: str,
    granted_by: uuid.UUID | None = None,
) -> User:
    """Create the staff account if needed, then grant the role. Granting a held role is a no-op."""
    if not reason.strip():
        raise ValueError("a reason is required")
    try:
        # The same rules as the sign-in form, so the account can actually receive its code.
        validate_email(email, check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValueError(f"not a usable email address: {exc}") from None
    normalized = normalize_email(email)
    actor_type = ActorType.USER if granted_by else ActorType.SYSTEM
    user = await _staff_user(session, normalized)
    if user is None:
        status = USER_ACCOUNT.target(None, "register")
        user = User(id=new_id(), audience=Audience.OPS.value, status=status.value)
        session.add(user)
        await session.flush()
        session.add(
            UserContact(
                id=new_id(),
                user_id=user.id,
                audience=Audience.OPS.value,
                kind=ContactKind.EMAIL.value,
                value=normalized,
                normalized=normalized,
                is_primary=True,
            )
        )
        await record(
            session,
            action="user.registered",
            entity_type="user",
            entity_id=user.id,
            actor_type=actor_type,
            actor_user_id=granted_by,
            new_value={"status": status.value, "audience": Audience.OPS.value},
            reason="staff account created by operations",
        )
    if user.status == UserStatus.CLOSED.value:
        raise ValueError("the account is closed")
    if role in await active_roles(session, user.id):
        return user
    grant_id = new_id()
    session.add(
        StaffRoleGrant(
            id=grant_id, user_id=user.id, role=role.value, granted_by=granted_by, reason=reason
        )
    )
    await session.flush()
    await record(
        session,
        action="staff_role.granted",
        entity_type="user",
        entity_id=user.id,
        actor_type=actor_type,
        actor_user_id=granted_by,
        new_value={"role": role.value},
        reason=reason,
    )
    return user


async def revoke_role(
    session: AsyncSession,
    *,
    email: str,
    role: StaffRole,
    reason: str,
    revoked_by: uuid.UUID | None = None,
) -> bool:
    """Revoke a held role and end the account's sessions. False if the role was not held."""
    if not reason.strip():
        raise ValueError("a reason is required")
    user = await _staff_user(session, normalize_email(email))
    if user is None:
        return False
    result = await session.execute(
        update(StaffRoleGrant)
        .where(
            StaffRoleGrant.user_id == user.id,
            StaffRoleGrant.role == role.value,
            StaffRoleGrant.revoked_at.is_(None),
        )
        .values(revoked_at=func.now(), revoked_by=revoked_by)
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        return False
    await session.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=func.now())
    )
    await record(
        session,
        action="staff_role.revoked",
        entity_type="user",
        entity_id=user.id,
        actor_type=ActorType.USER if revoked_by else ActorType.SYSTEM,
        actor_user_id=revoked_by,
        old_value={"role": role.value},
        reason=reason,
    )
    return True


@dataclass(frozen=True)
class StaffMember:
    user_id: uuid.UUID
    email: str
    status: UserStatus
    roles: frozenset[StaffRole]
    mfa_enabled: bool


async def list_staff(session: AsyncSession) -> list[StaffMember]:
    """Every operations account with its active roles (admin view; API 18). Two queries."""
    rows = (
        await session.execute(
            select(User, UserContact.normalized, MfaSecret.enabled_at)
            .join(UserContact, (UserContact.user_id == User.id) & UserContact.is_primary)
            .outerjoin(MfaSecret, MfaSecret.user_id == User.id)
            .where(User.audience == Audience.OPS.value)
            .order_by(UserContact.normalized)
        )
    ).all()
    grants = await session.execute(
        select(StaffRoleGrant.user_id, StaffRoleGrant.role).where(
            StaffRoleGrant.revoked_at.is_(None),
            StaffRoleGrant.user_id.in_([user.id for user, _, _ in rows]),
        )
    )
    roles: dict[uuid.UUID, set[StaffRole]] = {}
    for user_id, role in grants.all():
        roles.setdefault(user_id, set()).add(StaffRole(role))
    return [
        StaffMember(
            user_id=user.id,
            email=email,
            status=UserStatus(user.status),
            roles=frozenset(roles.get(user.id, set())),
            mfa_enabled=enabled_at is not None,
        )
        for user, email, enabled_at in rows
    ]


async def _main(argv: list[str], settings: Settings) -> int:
    parser = argparse.ArgumentParser(prog="python -m p2b.identity.staff")
    parser.add_argument("action", choices=["grant", "revoke"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", required=True, choices=[role.value for role in StaffRole])
    parser.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    database = Database(settings)
    try:
        async with database.transaction() as session:
            if args.action == "grant":
                await grant_role(
                    session, email=args.email, role=StaffRole(args.role), reason=args.reason
                )
                sys.stdout.write(f"granted {args.role}\n")
            else:
                done = await revoke_role(
                    session, email=args.email, role=StaffRole(args.role), reason=args.reason
                )
                sys.stdout.write(f"revoked {args.role}\n" if done else "role was not held\n")
    finally:
        await database.dispose()
    return 0


if __name__ == "__main__":
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    sys.exit(asyncio.run(_main(sys.argv[1:], get_settings()), loop_factory=loop_factory))
