"""Staff accounts, roles and TOTP MFA (SECURITY 3.3, 4.1, 4.2; SLICE2_READINESS section 1)."""

import time

import pyotp
import pytest
from sqlalchemy import func, select, update

from p2b.audit.models import AuditEvent, SecurityEvent
from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.vocabulary import Audience, StaffRole, UserStatus
from p2b.identity import mfa
from p2b.identity.models import MfaSecret, Session, StaffRoleGrant, UserContact
from p2b.identity.staff import _main as staff_cli
from p2b.identity.staff import active_roles, grant_role, revoke_role
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.staff_support import OPS_HEADERS, enrol, make_staff, verified_staff

# Accounts and roles


async def test_granting_a_role_creates_a_pending_operations_account_once(
    database: Database,
) -> None:
    async with database.transaction() as session:
        user = await grant_role(
            session, email="New.Person@Example.in", role=StaffRole.OPS, reason="joined"
        )
        again = await grant_role(
            session, email="new.person@example.in", role=StaffRole.OPS, reason="again"
        )
        assert again.id == user.id
        assert user.audience == Audience.OPS.value
        assert user.status == UserStatus.PENDING_VERIFICATION.value  # verified at first sign-in
        contact = (
            await session.scalars(select(UserContact).where(UserContact.user_id == user.id))
        ).one()
        assert (contact.normalized, contact.verified_at) == ("new.person@example.in", None)
        assert await active_roles(session, user.id) == {StaffRole.OPS}
        grants = await session.scalar(select(func.count()).select_from(StaffRoleGrant))
        actions = list(await session.scalars(select(AuditEvent.action).order_by(AuditEvent.at)))
    assert grants == 1
    assert actions == ["user.registered", "staff_role.granted"]


async def test_a_reason_is_required(database: Database) -> None:
    async with database.transaction() as session:
        with pytest.raises(ValueError, match="reason"):
            await grant_role(session, email="a@example.in", role=StaffRole.OPS, reason=" ")


@pytest.mark.parametrize("email", ["not-an-email", "someone@plan2build.test", "a@localhost"])
async def test_staff_accounts_need_an_address_that_can_receive_a_code(
    database: Database, email: str
) -> None:
    async with database.transaction() as session:
        with pytest.raises(ValueError, match="not a usable email address"):
            await grant_role(session, email=email, role=StaffRole.OPS, reason="joined")


async def test_revoking_a_role_ends_the_accounts_sessions(
    database: Database, client_for: ClientFactory, sign_in: SignIn
) -> None:
    staff = await make_staff(database, client_for, sign_in, StaffRole.OPS)
    assert (await staff.client.get("/api/v1/auth/mfa")).status_code == 200
    async with database.transaction() as session:
        assert await revoke_role(session, email=staff.email, role=StaffRole.OPS, reason="left")
        assert not await revoke_role(session, email=staff.email, role=StaffRole.OPS, reason="again")
    assert (await staff.client.get("/api/v1/auth/mfa")).status_code == 401


async def test_the_staff_command_grants_and_revokes(database: Database) -> None:
    settings = get_settings()
    assert (
        await staff_cli(
            ["grant", "--email", "cli@example.in", "--role", "ADMIN", "--reason", "x"],
            settings,
        )
        == 0
    )
    async with database.transaction() as session:
        user_id = await session.scalar(
            select(UserContact.user_id).where(UserContact.normalized == "cli@example.in")
        )
        assert user_id is not None
        assert await active_roles(session, user_id) == {StaffRole.ADMIN}
    assert (
        await staff_cli(
            ["revoke", "--email", "cli@example.in", "--role", "ADMIN", "--reason", "x"],
            settings,
        )
        == 0
    )
    async with database.transaction() as session:
        assert await active_roles(session, user_id) == frozenset()


# Who reaches the staff routes


async def test_operations_routes_do_not_exist_on_the_homeowner_host(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    client = client_for(Audience.IHB)
    await sign_in(client, await make_user(Audience.IHB), Audience.IHB)
    for path in (
        "/api/v1/ops/queues/requirement-review",
        "/api/v1/admin/staff",
        "/api/v1/auth/mfa",
    ):
        assert (await client.get(path)).status_code == 404


async def test_a_homeowner_session_is_not_an_operations_session(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    homeowner = client_for(Audience.IHB)
    token = await sign_in(homeowner, await make_user(Audience.IHB), Audience.IHB)
    replay = client_for(Audience.OPS)
    replay.cookies.set("__Host-p2b_ops_session", token)
    assert (await replay.get("/api/v1/auth/mfa")).status_code == 401


async def test_an_operations_account_without_a_role_is_refused(
    database: Database, client_for: ClientFactory, sign_in: SignIn
) -> None:
    nobody = await make_staff(database, client_for, sign_in)
    response = await nobody.client.get("/api/v1/auth/mfa")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_operations_work_needs_mfa_first(
    database: Database, client_for: ClientFactory, sign_in: SignIn
) -> None:
    staff = await make_staff(database, client_for, sign_in, StaffRole.OPS)
    response = await staff.client.get("/api/v1/ops/queues/requirement-review")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "MFA_REQUIRED"
    me = (await staff.client.get("/api/v1/me")).json()
    assert me["staff"] == {"roles": ["OPS"], "mfa_enrolled": False, "mfa_verified": False}
    await enrol(staff)
    assert (await staff.client.get("/api/v1/ops/queues/requirement-review")).status_code == 200
    me = (await staff.client.get("/api/v1/me")).json()
    assert me["staff"] == {"roles": ["OPS"], "mfa_enrolled": True, "mfa_verified": True}


async def test_roles_are_separate(
    database: Database, client_for: ClientFactory, sign_in: SignIn
) -> None:
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    admin = await verified_staff(database, client_for, sign_in, StaffRole.ADMIN)
    assert (await ops.client.get("/api/v1/admin/staff")).status_code == 403
    assert (await admin.client.get("/api/v1/ops/queues/requirement-review")).status_code == 403
    listed = (await admin.client.get("/api/v1/admin/staff")).json()
    by_email = {member["email"]: member for member in listed}
    assert by_email[ops.email]["roles"] == ["OPS"]
    assert by_email[admin.email]["roles"] == ["ADMIN"]
    assert by_email[admin.email]["mfa_enabled"] is True


async def test_mfa_expires_after_eight_hours(
    database: Database, client_for: ClientFactory, sign_in: SignIn
) -> None:
    staff = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    async with database.transaction() as session:
        await session.execute(
            update(Session)
            .where(Session.user_id == staff.user_id, Session.revoked_at.is_(None))
            .values(mfa_verified_at=func.now() - func.make_interval(0, 0, 0, 0, 8, 1))
        )
    response = await staff.client.get("/api/v1/ops/queues/requirement-review")
    assert response.json()["error"]["code"] == "MFA_REQUIRED"


# Enrolment and verification


async def test_enrolment_gives_a_scannable_secret_and_recovery_codes_once(
    database: Database, client_for: ClientFactory, sign_in: SignIn
) -> None:
    staff = await make_staff(database, client_for, sign_in, StaffRole.OPS)
    started = (await staff.client.post("/api/v1/auth/mfa/enrolment", headers=OPS_HEADERS)).json()
    assert started["otpauth_uri"].startswith("otpauth://totp/Plan2Build:")
    assert started["qr_svg_data_uri"].startswith("data:image/svg+xml")
    staff.secret = started["secret"]

    wrong = await staff.client.post(
        "/api/v1/auth/mfa/enrolment/confirm", json={"code": "000000"}, headers=OPS_HEADERS
    )
    if staff.code() != "000000":
        assert wrong.json()["error"]["code"] == "MFA_INVALID"

    confirmed = await staff.client.post(
        "/api/v1/auth/mfa/enrolment/confirm", json={"code": staff.code()}, headers=OPS_HEADERS
    )
    codes = confirmed.json()["recovery_codes"]
    assert len(codes) == len(set(codes)) == 10
    assert "__Host-p2b_ops_session=" in confirmed.headers["set-cookie"]  # rotated session

    async with database.transaction() as session:
        row = await session.get_one(MfaSecret, staff.user_id)
        assert staff.secret.encode() not in row.secret_ciphertext  # encrypted at rest
        assert not any(code in "".join(row.recovery_code_hashes) for code in codes)
        kinds = list(await session.scalars(select(SecurityEvent.kind)))
    assert "mfa.enrolled" in kinds
    again = await staff.client.post("/api/v1/auth/mfa/enrolment", headers=OPS_HEADERS)
    assert again.json()["error"]["code"] == "MFA_ALREADY_ENROLLED"


async def test_the_old_session_dies_when_mfa_rotates_it(
    database: Database, client_for: ClientFactory, sign_in: SignIn
) -> None:
    staff = await make_staff(database, client_for, sign_in, StaffRole.OPS)
    before = next(c.value for c in staff.client.cookies.jar if c.name == "__Host-p2b_ops_session")
    async with database.transaction() as session:
        old = (await session.scalars(select(Session).where(Session.user_id == staff.user_id))).one()
        old_absolute = old.absolute_expires_at
    await enrol(staff)
    stale = client_for(Audience.OPS)
    stale.cookies.set("__Host-p2b_ops_session", str(before))
    assert (await stale.get("/api/v1/me")).status_code == 401
    async with database.transaction() as session:
        live = (
            await session.scalars(
                select(Session).where(
                    Session.user_id == staff.user_id, Session.revoked_at.is_(None)
                )
            )
        ).one()
    assert live.absolute_expires_at == old_absolute  # MFA never extends the absolute lifetime
    assert live.mfa_verified_at is not None


async def test_a_code_works_once_and_recovery_codes_are_single_use(
    database: Database, client_for: ClientFactory, sign_in: SignIn
) -> None:
    staff = await make_staff(database, client_for, sign_in, StaffRole.OPS)
    codes = await enrol(staff)
    reused = await staff.client.post(
        "/api/v1/auth/mfa/verify", json={"code": staff.code()}, headers=OPS_HEADERS
    )
    assert reused.json()["error"]["code"] == "MFA_INVALID"  # the enrolment step is spent
    nxt = await staff.client.post(
        "/api/v1/auth/mfa/verify", json={"code": staff.code(1)}, headers=OPS_HEADERS
    )
    assert nxt.json()["method"] == "totp"

    first = await staff.client.post(
        "/api/v1/auth/mfa/verify", json={"code": codes[0].upper()}, headers=OPS_HEADERS
    )
    assert first.json() == {"method": "recovery", "recovery_codes_left": 9}
    second = await staff.client.post(
        "/api/v1/auth/mfa/verify", json={"code": codes[0]}, headers=OPS_HEADERS
    )
    assert second.json()["error"]["code"] == "MFA_INVALID"


async def test_guessing_is_rate_limited_and_recorded(
    database: Database, client_for: ClientFactory, sign_in: SignIn
) -> None:
    staff = await make_staff(database, client_for, sign_in, StaffRole.OPS)
    await enrol(staff)
    wrong = "999999" if staff.code() != "999999" else "888888"
    statuses = [
        (
            await staff.client.post(
                "/api/v1/auth/mfa/verify", json={"code": wrong}, headers=OPS_HEADERS
            )
        ).status_code
        for _ in range(6)
    ]
    assert statuses == [400] * 5 + [429]
    async with database.transaction() as session:
        failures = await session.scalar(
            select(func.count())
            .select_from(SecurityEvent)
            .where(SecurityEvent.kind == "mfa.verify_failed")
        )
    assert failures == 5


async def test_mfa_needs_the_csrf_headers(
    database: Database, client_for: ClientFactory, sign_in: SignIn
) -> None:
    staff = await make_staff(database, client_for, sign_in, StaffRole.OPS)
    assert (await staff.client.post("/api/v1/auth/mfa/enrolment")).status_code == 403


def test_totp_allows_one_step_of_drift_and_no_more() -> None:
    secret = pyotp.random_base32()
    now = int(time.time())
    current = now // mfa.STEP_SECONDS
    totp = pyotp.TOTP(secret)
    assert mfa.matching_step(secret, totp.at(now), now) == current
    assert mfa.matching_step(secret, totp.at(now - 30), now) == current - 1
    assert mfa.matching_step(secret, totp.at(now + 30), now) == current + 1
    late = totp.at(now - 90)
    if late not in {totp.at(now - 30), totp.at(now), totp.at(now + 30)}:
        assert mfa.matching_step(secret, late, now) is None


def test_recovery_codes_are_normalised() -> None:
    code = mfa.new_recovery_code()
    assert len(code) == 11
    assert code[5] == "-"
    assert mfa.normalise_recovery_code(f" {code.upper().replace('-', ' ')} ") == code
