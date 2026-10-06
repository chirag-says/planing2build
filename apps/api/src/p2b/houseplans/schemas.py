"""API shapes for concept floor plans. The plan, intent, geometry and report are the engine's own
models, so the contract the web app receives is the canonical schema, not a copy of it."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from p2b.core.vocabulary import (
    InfeasibleReason,
    PlanFailureReason,
    PlanGenerationState,
    PlanValidity,
    RulesetStatus,
)
from p2b.houseplans.engine import (
    ArchitecturalIntent,
    DesignInputs,
    HousePlan,
    PlanGeometry,
    ValidationReport,
)


class _Out(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerateHousePlanRequest(_Out):
    """`design_inputs` is PROVISIONAL (CP1-03): it stands in for the design brief until AD-03, is
    stored apart from the requirement and never changes an answer the requirement gives."""

    design_inputs: DesignInputs | None = None


class HousePlanSummaryOut(_Out):
    plan_id: str
    sequence: int
    state: PlanGenerationState
    validity: PlanValidity | None
    failure_reason: PlanFailureReason | None
    ruleset_version: int
    ruleset_status: RulesetStatus
    ruleset_is_synthetic: bool
    is_authoritative: Literal[False] = False
    created_at: datetime
    completed_at: datetime | None


class HousePlanListOut(_Out):
    items: list[HousePlanSummaryOut]


class InfeasibleReasonOut(_Out):
    code: InfeasibleReason
    params: dict[str, int | str]
    message_key: str


class InfeasibilityOut(_Out):
    reasons: list[InfeasibleReasonOut]


class HousePlanDetailOut(HousePlanSummaryOut):
    intent: ArchitecturalIntent
    design_inputs: DesignInputs | None
    document: HousePlan | None
    geometry: PlanGeometry | None  # derived on read from `document`; never stored
    validation: ValidationReport | None
    infeasibility: InfeasibilityOut | None


class OpsHousePlanDetailOut(HousePlanDetailOut):
    failure_detail: str | None
