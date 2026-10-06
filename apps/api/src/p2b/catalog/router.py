from fastapi import APIRouter, Request

from p2b.catalog.estimator import EstimateInputs
from p2b.catalog.questions import QuestionSetDefinition
from p2b.catalog.schemas import EstimateRequest, EstimateResponse, RateCardRef, StageAmountOut
from p2b.catalog.service import active_question_set, active_stage_names, estimate
from p2b.core.authz import public_route
from p2b.core.config import Settings
from p2b.core.crypto import keyed_hash
from p2b.core.db import DbSession
from p2b.core.http import client_ip
from p2b.core.ratelimit import Limit, enforce

router = APIRouter(tags=["public"])

# Tier T0: 60 requests per minute per IP (API_ARCHITECTURE section 1).
PUBLIC_LIMIT = Limit("public_ip", 60, 60)


@router.post("/public/estimate", response_model=EstimateResponse, dependencies=[public_route])
async def post_estimate(body: EstimateRequest, request: Request, db: DbSession) -> EstimateResponse:
    settings: Settings = request.app.state.settings
    peer = request.client.host if request.client else None
    ip = client_ip(request.headers, peer)
    await enforce(
        request.app.state.database,
        PUBLIC_LIMIT,
        keyed_hash(settings.identifier_pepper.get_secret_value(), ip),
    )
    card, result = await estimate(
        db,
        city=body.city,
        inputs=EstimateInputs(body.built_up_area_sqft, body.floors, body.finish_level),
        allow_demo=settings.env != "production",
    )
    names = await active_stage_names(db)
    return EstimateResponse(
        total_low=result.total_low,
        total_high=result.total_high,
        total_mid=result.total_mid,
        per_sqft_low=result.per_sqft_low,
        per_sqft_high=result.per_sqft_high,
        duration_months=result.duration_months,
        stages=[
            StageAmountOut(
                stage_number=s.stage_number,
                stage_name=names.get(s.stage_number),
                share_pct=s.share_pct,
                amount=s.amount,
            )
            for s in result.stages
        ],
        rate_card=RateCardRef(
            city=card.city, version=card.version, is_demo=card.is_demo, label=card.label
        ),
    )


@router.get(
    "/public/requirement-questions",
    response_model=QuestionSetDefinition,
    dependencies=[public_route],
)
async def get_requirement_questions(db: DbSession) -> QuestionSetDefinition:
    """The active, locked question set (REQUIREMENT_QUESTIONS_V1 section L)."""
    return await active_question_set(db)
