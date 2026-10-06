"""Operations view of a project's needs, connections, engagements and quote-review intake
(admin host). Withdrawing a request or ending an engagement needs a staff role, MFA and a
reason, and leaves history and an audit row. Quote files download through `/ops/files`."""

import uuid
from typing import Annotated

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from p2b.core.db import DbSession
from p2b.core.errors import NotFound
from p2b.core.idempotency import IdempotencyKeyHeader, run_once
from p2b.core.vocabulary import Audience, StaffRole
from p2b.engagements import service
from p2b.engagements.schemas import OpsEngagementsOut, ReasonIn
from p2b.engagements.views import ops_out
from p2b.identity.interface import Actor, active_roles, require_actor
from p2b.projects.interface import connection_facts

router = APIRouter(tags=["engagements-operations"])

STAFF = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.OPS, StaffRole.ADMIN))


async def _out(db: DbSession, project_id: uuid.UUID) -> OpsEngagementsOut:
    facts = await connection_facts(db, project_id)
    if facts is None:
        raise NotFound
    return await ops_out(db, facts)


async def _who(db: DbSession, actor: Actor) -> service.Who:
    roles = await active_roles(db, actor.user_id)
    role = StaffRole.ADMIN.value if StaffRole.ADMIN in roles else StaffRole.OPS.value
    return service.Who(actor.user_id, role, actor.session_id)


@router.get("/ops/projects/{project_id}/engagements", response_model=OpsEngagementsOut)
async def get_project_engagements(
    project_id: uuid.UUID, db: DbSession, actor: Annotated[Actor, STAFF]
) -> OpsEngagementsOut:
    """Needs, every request with its decline reason and note, engagements, quote reviews and
    the history, newest first."""
    return await _out(db, project_id)


@router.post("/ops/connections/{connection_id}/withdraw", response_model=OpsEngagementsOut)
async def post_ops_withdraw(
    connection_id: uuid.UUID,
    body: ReasonIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    async def act() -> tuple[int, dict[str, object]]:
        connection = await service.withdraw_by_staff(
            db, await _who(db, actor), connection_id, body.reason
        )
        return 200, (await _out(db, connection.project_id)).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body={"connection_id": str(connection_id), **body.model_dump(mode="json")},
        action=act,
    )


@router.post("/ops/engagements/{engagement_id}/end", response_model=OpsEngagementsOut)
async def post_ops_end(
    engagement_id: uuid.UUID,
    body: ReasonIn,
    key: IdempotencyKeyHeader,
    db: DbSession,
    actor: Annotated[Actor, STAFF],
) -> JSONResponse:
    async def act() -> tuple[int, dict[str, object]]:
        engagement = await service.locked_engagement(db, engagement_id)
        await service.end_engagement(db, engagement, await _who(db, actor), body.reason)
        return 200, (await _out(db, engagement.project_id)).model_dump(mode="json")

    return await run_once(
        db,
        session_id=actor.session_id,
        key=key,
        request_body={"engagement_id": str(engagement_id), **body.model_dump(mode="json")},
        action=act,
    )
