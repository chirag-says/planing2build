"""The authorisation chain for authenticated routes (SECURITY_ARCHITECTURE section 4.1).

Layers in order: host audience allowed for the route, session, account status, staff role, MFA.
Ownership,
project membership and state preconditions belong to the module that owns the object and run in
its service.
"""

from collections.abc import Iterable
from datetime import datetime
from typing import Any

import structlog
from fastapi import Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.authz import mark_rule
from p2b.core.config import MFA_REVERIFY_WINDOW, Settings
from p2b.core.db import DbSession
from p2b.core.errors import Forbidden, MfaRequired, NotFound, Unauthenticated
from p2b.core.http import session_cookie_name
from p2b.core.vocabulary import Audience, StaffRole, UserStatus
from p2b.identity.service import Actor, resolve_session
from p2b.identity.staff import active_roles


def require_actor(
    *audiences: Audience,
    mfa: bool = False,
    allow_suspended: bool = False,
    roles: Iterable[StaffRole] = (),
) -> Any:
    """Build the rule dependency for a route. Use as a parameter
    (`actor: Annotated[Actor, require_actor(Audience.IHB)]`) or in `dependencies=[...]`.

    `roles`: staff roles, any one of which admits the caller (operations host only). Checked after
    the session and account status and before MFA (SECURITY 4.1), from the database every time."""
    if not audiences:
        raise ValueError("require_actor needs at least one audience")
    allowed = frozenset(audiences)
    required_roles = frozenset(roles)
    if required_roles and allowed != {Audience.OPS}:
        raise ValueError("staff roles exist only on the operations audience")

    async def dependency(request: Request, db: DbSession) -> Actor:
        settings: Settings = request.app.state.settings
        host_audience: Audience = request.state.audience
        if host_audience not in allowed:
            # The route does not exist for this host's audience.
            raise NotFound
        token = request.cookies.get(
            session_cookie_name(host_audience, secure=settings.cookie_secure)
        )
        if not token:
            raise Unauthenticated
        actor = await resolve_session(db, token=token, audience=host_audience)
        if actor is None:
            raise Unauthenticated
        structlog.contextvars.bind_contextvars(user_id=str(actor.user_id))
        if actor.status == UserStatus.SUSPENDED and not allow_suspended:
            raise Forbidden
        if actor.status not in (UserStatus.ACTIVE, UserStatus.SUSPENDED):
            raise Unauthenticated
        if required_roles and not required_roles & await active_roles(db, actor.user_id):
            raise Forbidden
        if mfa and not await mfa_fresh(db, actor.mfa_verified_at):
            raise MfaRequired
        return actor

    label = f"actor:{','.join(sorted(a.value for a in allowed))}" + (":mfa" if mfa else "")
    if required_roles:
        label += f":roles={'|'.join(sorted(role.value for role in required_roles))}"
    return Depends(mark_rule(dependency, label))


async def mfa_fresh(db: AsyncSession, verified_at: datetime | None) -> bool:
    if verified_at is None:
        return False
    now = (await db.execute(select(func.now()))).scalar_one()
    return bool(now - verified_at <= MFA_REVERIFY_WINDOW)
