"""Helpers for operations staff in tests: create the account through the real service, sign in on
the admin host, and pass MFA through the real endpoints with a code computed from the secret."""

import time
import uuid
from dataclasses import dataclass

import pyotp
from httpx import AsyncClient
from sqlalchemy import update

from p2b.core.db import Database
from p2b.core.vocabulary import Audience, StaffRole, UserStatus
from p2b.identity.models import User
from p2b.identity.staff import grant_role, revoke_role
from tests.conftest import ClientFactory, SignIn, csrf_headers

OPS_HEADERS = csrf_headers(Audience.OPS)


@dataclass
class Staff:
    user_id: uuid.UUID
    email: str
    client: AsyncClient
    secret: str | None = None

    def code(self, offset_steps: int = 0) -> str:
        assert self.secret, "MFA is not enrolled"
        return pyotp.TOTP(self.secret).at(int(time.time()) + 30 * offset_steps)


async def make_staff(
    database: Database,
    client_for: ClientFactory,
    sign_in: SignIn,
    *roles: StaffRole,
    email: str | None = None,
) -> Staff:
    """An active operations account holding `roles`, signed in, MFA not yet enrolled."""
    email = email or f"staff-{uuid.uuid4().hex[:8]}@example.in"
    async with database.transaction() as session:
        user = None
        for role in roles:
            user = await grant_role(session, email=email, role=role, reason="test")
        if user is None:  # an operations account without any role
            user = await grant_role(session, email=email, role=StaffRole.OPS, reason="test")
            await revoke_role(session, email=email, role=StaffRole.OPS, reason="test")
        # The first emailed-code sign-in activates the account (otp._sign_in); do it directly here.
        await session.execute(
            update(User).where(User.id == user.id).values(status=UserStatus.ACTIVE.value)
        )
        user_id = user.id
    client = client_for(Audience.OPS)
    await sign_in(client, user_id, Audience.OPS)
    return Staff(user_id=user_id, email=email, client=client)


async def enrol(staff: Staff) -> list[str]:
    """Enrol TOTP through the API; the session is MFA-verified after. Returns the recovery codes."""
    started = await staff.client.post("/api/v1/auth/mfa/enrolment", headers=OPS_HEADERS)
    assert started.status_code == 200, started.text
    staff.secret = started.json()["secret"]
    confirmed = await staff.client.post(
        "/api/v1/auth/mfa/enrolment/confirm", json={"code": staff.code()}, headers=OPS_HEADERS
    )
    assert confirmed.status_code == 200, confirmed.text
    codes: list[str] = confirmed.json()["recovery_codes"]
    return codes


async def verified_staff(
    database: Database, client_for: ClientFactory, sign_in: SignIn, *roles: StaffRole
) -> Staff:
    staff = await make_staff(database, client_for, sign_in, *roles)
    await enrol(staff)
    return staff
