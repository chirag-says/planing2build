"""Operations read-only routes for concept floor plans (AD-12; admin host, MFA, OPS or ADMIN)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Request

from p2b.core.db import DbSession
from p2b.core.vocabulary import Audience, StaffRole
from p2b.houseplans.router import detail_fields, summary
from p2b.houseplans.schemas import HousePlanListOut, OpsHousePlanDetailOut
from p2b.houseplans.service import get_any, list_for_project, require_enabled
from p2b.identity.interface import Actor, require_actor

router = APIRouter(tags=["houseplans-ops"])

STAFF = require_actor(Audience.OPS, mfa=True, roles=(StaffRole.OPS, StaffRole.ADMIN))


@router.get("/ops/projects/{project_id}/house-plans", response_model=HousePlanListOut)
async def ops_house_plans(
    project_id: uuid.UUID, request: Request, db: DbSession, _: Annotated[Actor, STAFF]
) -> HousePlanListOut:
    require_enabled(request.app.state.settings)
    return HousePlanListOut(items=[summary(v) for v in await list_for_project(db, project_id)])


@router.get("/ops/house-plans/{plan_id}", response_model=OpsHousePlanDetailOut)
async def ops_house_plan(
    plan_id: uuid.UUID, request: Request, db: DbSession, _: Annotated[Actor, STAFF]
) -> OpsHousePlanDetailOut:
    view = await get_any(db, request.app.state.settings, plan_id)
    return OpsHousePlanDetailOut(**detail_fields(view), failure_detail=view.row.failure_detail)
