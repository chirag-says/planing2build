from typing import Annotated

from fastapi import APIRouter, Request, Response, status

from p2b.audit.interface import record_security_event
from p2b.core.authz import public_route
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import Database, DbSession
from p2b.core.errors import MfaInvalid
from p2b.core.http import client_ip, session_cookie_name
from p2b.core.ratelimit import enforce
from p2b.core.vocabulary import Audience, SecuritySeverity, StaffRole, UserStatus
from p2b.identity import mfa
from p2b.identity.dependencies import mfa_fresh, require_actor
from p2b.identity.otp import start_otp, verify_otp
from p2b.identity.schemas import (
    MeResponse,
    MfaConfirmRequest,
    MfaConfirmResponse,
    MfaEnrolmentResponse,
    MfaStatusResponse,
    MfaVerifyRequest,
    MfaVerifyResponse,
    OtpStartRequest,
    OtpStartResponse,
    OtpVerifyRequest,
    OtpVerifyResponse,
    StaffInfo,
    StaffMemberOut,
)
from p2b.identity.service import (
    Actor,
    IssuedSession,
    elevate_session,
    primary_email,
    revoke_session,
)
from p2b.identity.staff import active_roles, list_staff

router = APIRouter(tags=["identity"])

ANY_AUDIENCE = (Audience.IHB, Audience.PRO, Audience.OPS)
ANY_STAFF = (StaffRole.OPS, StaffRole.ADMIN)
# Staff who have not yet passed MFA on this session: enrolment and verification themselves.
STAFF_BEFORE_MFA = require_actor(Audience.OPS, roles=ANY_STAFF)


def _ip_hash(request: Request, settings: Settings) -> str:
    peer = request.client.host if request.client else None
    ip = client_ip(request.headers, peer)
    return keyed_hash(settings.identifier_pepper.get_secret_value(), ip)


def _set_session_cookie(
    response: Response, settings: Settings, audience: Audience, issued: IssuedSession
) -> None:
    response.set_cookie(
        session_cookie_name(audience, secure=settings.cookie_secure),
        issued.token,
        max_age=issued.max_age_seconds,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


@router.post("/auth/otp/start", response_model=OtpStartResponse, dependencies=[public_route])
async def otp_start(body: OtpStartRequest, request: Request) -> OtpStartResponse:
    """Same response for every contact, known or not (no enumeration)."""
    settings: Settings = request.app.state.settings
    database: Database = request.app.state.database
    started = await start_otp(
        database,
        settings,
        email=str(body.email),
        audience=request.state.audience,
        ip_hash=_ip_hash(request, settings),
    )
    return OtpStartResponse(
        challenge_id=started.challenge_id,
        expires_at=started.expires_at,
        masked_contact=started.masked_contact,
    )


@router.post("/auth/otp/verify", response_model=OtpVerifyResponse, dependencies=[public_route])
async def otp_verify(
    body: OtpVerifyRequest, request: Request, response: Response
) -> OtpVerifyResponse:
    settings: Settings = request.app.state.settings
    database: Database = request.app.state.database
    audience: Audience = request.state.audience
    signed_in = await verify_otp(
        database,
        settings,
        challenge_id=body.challenge_id,
        code=body.code,
        audience=audience,
        ip_hash=_ip_hash(request, settings),
    )
    _set_session_cookie(response, settings, audience, signed_in.session)
    user = signed_in.user
    return OtpVerifyResponse(
        user=MeResponse(
            user_id=user.id,
            audience=Audience(user.audience),
            status=UserStatus(user.status),
            display_name=user.display_name,
            locale=user.locale,
        ),
        is_new=signed_in.is_new,
        mfa_required=audience == Audience.OPS,
    )


@router.get("/me", response_model=MeResponse)
async def get_me(
    db: DbSession, actor: Annotated[Actor, require_actor(*ANY_AUDIENCE)]
) -> MeResponse:
    staff = None
    if actor.audience == Audience.OPS:
        enrolled, _ = await mfa.status(db, actor.user_id)
        staff = StaffInfo(
            roles=sorted(await active_roles(db, actor.user_id)),
            mfa_enrolled=enrolled,
            mfa_verified=await mfa_fresh(db, actor.mfa_verified_at),
        )
    return MeResponse(
        user_id=actor.user_id,
        audience=actor.audience,
        status=actor.status,
        display_name=actor.display_name,
        locale=actor.locale,
        staff=staff,
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    db: DbSession,
    actor: Annotated[Actor, require_actor(*ANY_AUDIENCE, allow_suspended=True)],
) -> Response:
    await revoke_session(db, actor=actor, reason="logout")
    settings: Settings = request.app.state.settings
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(
        session_cookie_name(actor.audience, secure=settings.cookie_secure),
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response


# Second factor for operations and admin (SECURITY 3.3).


@router.get("/auth/mfa", response_model=MfaStatusResponse)
async def get_mfa(db: DbSession, actor: Annotated[Actor, STAFF_BEFORE_MFA]) -> MfaStatusResponse:
    enrolled, left = await mfa.status(db, actor.user_id)
    return MfaStatusResponse(
        enrolled=enrolled,
        verified=await mfa_fresh(db, actor.mfa_verified_at),
        recovery_codes_left=left,
    )


@router.post("/auth/mfa/enrolment", response_model=MfaEnrolmentResponse)
async def post_mfa_enrolment(
    request: Request, db: DbSession, actor: Annotated[Actor, STAFF_BEFORE_MFA]
) -> MfaEnrolmentResponse:
    settings: Settings = request.app.state.settings
    account = await primary_email(db, actor.user_id) or str(actor.user_id)
    enrolment = await mfa.start_enrolment(db, settings, user_id=actor.user_id, account_name=account)
    return MfaEnrolmentResponse(
        secret=enrolment.secret,
        otpauth_uri=enrolment.otpauth_uri,
        qr_svg_data_uri=enrolment.qr_svg_data_uri,
    )


async def _limit_mfa_attempts(request: Request, actor: Actor) -> None:
    database: Database = request.app.state.database
    await enforce(database, mfa.VERIFY_PER_SESSION, str(actor.session_id))
    await enforce(database, mfa.VERIFY_PER_ACCOUNT, str(actor.user_id))


async def _mfa_event(
    request: Request, actor: Actor, kind: str, severity: SecuritySeverity, **details: str
) -> None:
    settings: Settings = request.app.state.settings
    await record_security_event(
        request.app.state.database,
        kind=kind,
        severity=severity,
        audience=actor.audience,
        user_id=actor.user_id,
        ip_hash=_ip_hash(request, settings),
        details=details or None,
    )


@router.post("/auth/mfa/enrolment/confirm", response_model=MfaConfirmResponse)
async def post_mfa_confirm(
    body: MfaConfirmRequest,
    request: Request,
    response: Response,
    db: DbSession,
    actor: Annotated[Actor, STAFF_BEFORE_MFA],
) -> MfaConfirmResponse:
    settings: Settings = request.app.state.settings
    await _limit_mfa_attempts(request, actor)
    try:
        codes = await mfa.confirm_enrolment(db, settings, user_id=actor.user_id, code=body.code)
    except MfaInvalid:
        await _mfa_event(request, actor, "mfa.enrolment_failed", SecuritySeverity.WARNING)
        raise
    issued = await elevate_session(db, actor=actor)
    _set_session_cookie(response, settings, actor.audience, issued)
    await _mfa_event(request, actor, "mfa.enrolled", SecuritySeverity.INFO)
    return MfaConfirmResponse(recovery_codes=codes)


@router.post("/auth/mfa/verify", response_model=MfaVerifyResponse)
async def post_mfa_verify(
    body: MfaVerifyRequest,
    request: Request,
    response: Response,
    db: DbSession,
    actor: Annotated[Actor, STAFF_BEFORE_MFA],
) -> MfaVerifyResponse:
    settings: Settings = request.app.state.settings
    await _limit_mfa_attempts(request, actor)
    try:
        method = await mfa.verify(db, settings, user_id=actor.user_id, code=body.code)
    except MfaInvalid:
        await _mfa_event(request, actor, "mfa.verify_failed", SecuritySeverity.WARNING)
        raise
    issued = await elevate_session(db, actor=actor)
    _set_session_cookie(response, settings, actor.audience, issued)
    _, left = await mfa.status(db, actor.user_id)
    # A recovery code in use means the authenticator may be lost: worth a warning.
    severity = SecuritySeverity.INFO if method == "totp" else SecuritySeverity.WARNING
    await _mfa_event(request, actor, "mfa.verified", severity, method=method)
    return MfaVerifyResponse(method=method, recovery_codes_left=left)


@router.get(
    "/admin/staff",
    response_model=list[StaffMemberOut],
    dependencies=[require_actor(Audience.OPS, mfa=True, roles=[StaffRole.ADMIN])],
)
async def get_staff(db: DbSession) -> list[StaffMemberOut]:
    """Account administration view (API 18): ADMIN with MFA, admin host only."""
    return [
        StaffMemberOut(
            user_id=member.user_id,
            email=member.email,
            status=member.status,
            roles=sorted(member.roles),
            mfa_enabled=member.mfa_enabled,
        )
        for member in await list_staff(db)
    ]
