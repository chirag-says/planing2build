"""API shapes for concept floor plans. The plan, intent, geometry and report are the engine's own
models, so the contract the web app receives is the canonical schema, not a copy of it."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from p2b.core.vocabulary import (
    ConstraintKind,
    ConstraintOutcome,
    FeasibilityClass,
    InfeasibleReason,
    PlanFailureReason,
    PlanGenerationState,
    PlanOpKind,
    PlanOpReason,
    PlanValidity,
    RoomType,
    RulesetStatus,
)
from p2b.houseplans.engine import (
    ArchitecturalIntent,
    DesignInputs,
    HousePlan,
    PlanGeometry,
    ValidationReport,
)
from p2b.houseplans.engine.edit import MAX_BATCH
from p2b.houseplans.engine.ops import PlanOp


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


class InvolvedConstraintOut(_Out):
    kind: str
    subject: str
    origin: str


class InfeasibilityOut(_Out):
    """Why no plan was produced. `classification` PROVEN: no arrangement can meet the hard rules;
    NO_SUPPORTED_LAYOUT: none of the layouts this engine version produces fits, which never means
    impossible (CP2-U4). Plans from Checkpoint 1 carry `reasons` only."""

    reasons: list[InfeasibleReasonOut]
    classification: FeasibilityClass | None = None
    message_key: str | None = None
    message: str | None = None
    explanation: str | None = None
    constraints: list[InvolvedConstraintOut] = []


class QualityTermOut(_Out):
    kind: ConstraintKind
    weight: int
    score_milli: int | None  # None: NOT_EVALUATED
    outcome: ConstraintOutcome
    subjects: list[str]


class RoomQualityOut(_Out):
    room: str
    room_type: RoomType
    clear_w_mm: int
    clear_d_mm: int
    aspect_x100: int
    over_aspect: bool


class QualityOut(_Out):
    """The Scorer's measure of a plan (derived on read; never stored apart from the document's
    soft constraints). Lower is better; it never decides validity."""

    total: int
    circulation_share_milli: int
    aspect_violations: int
    terms: list[QualityTermOut]
    rooms: list[RoomQualityOut]


class RoomTypeOut(_Out):
    """A room type the editor may offer (Checkpoint 3.1): enclosed types of the plan's ruleset.
    `name` is the default room name the engine gives the type."""

    type: RoomType
    name: str
    needs_window: bool
    min_short_mm: int


class OpeningSizesOut(_Out):
    """The plan ruleset's opening sizes, for new and resized doors and windows."""

    door_width_mm: int
    min_door_width_mm: int
    door_height_mm: int
    window_width_mm: int
    min_window_width_mm: int
    window_height_mm: int
    window_sill_mm: int
    jamb_clearance_mm: int


class EditingOut(_Out):
    """What the editor needs besides the document (Checkpoint 3). `can_edit` is the API's answer
    for this caller (owner of the project, plan with a document); the server checks it again on
    every edit. `grid_mm` is the ruleset's planning grid, the editor's snap step. Checkpoint 3.1
    adds the room types and opening sizes the editor offers, and the wall thicknesses it needs to
    show clear sizes; the server checks every value again."""

    can_edit: bool
    revision_no: int
    grid_mm: int
    room_types: list[RoomTypeOut] = []
    openings: OpeningSizesOut | None = None
    interior_wall_mm: int | None = None
    exterior_wall_mm: int | None = None


class HousePlanDetailOut(HousePlanSummaryOut):
    intent: ArchitecturalIntent
    design_inputs: DesignInputs | None
    document: HousePlan | None
    geometry: PlanGeometry | None  # derived on read from `document`; never stored
    validation: ValidationReport | None
    infeasibility: InfeasibilityOut | None
    quality: QualityOut | None = None  # derived on read from `document` with the plan's ruleset
    editing: EditingOut | None = None  # present when the plan has a document


class EditHousePlanRequest(_Out):
    """One batch of typed operations against the head revision the editor last saw. Applied
    whole or not at all; never stored unless the validator passes."""

    expected_revision: Annotated[int, Field(ge=0)]
    ops: Annotated[list[PlanOp], Field(min_length=1, max_length=MAX_BATCH)]


class EditHousePlanOut(HousePlanDetailOut):
    """The plan after the batch, and the batch that undoes it (send it as a new edit to undo)."""

    inverse: list[PlanOp]


class HousePlanVersionOut(_Out):
    """A named, immutable snapshot of the plan (version 1 is the generated plan)."""

    version_no: int
    name: str
    revision_no: int
    validity: PlanValidity
    created_at: datetime
    created_by_you: bool


class HousePlanVersionListOut(_Out):
    items: list[HousePlanVersionOut]


class SaveHousePlanVersionRequest(_Out):
    """Keep the head the editor shows (`expected_revision`) as a named version."""

    name: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[^\x00-\x1f]+$")]
    expected_revision: Annotated[int, Field(ge=0)]


class HousePlanRevisionOut(_Out):
    """One logged revision: what kinds of operation made it, or what it restored."""

    revision_no: int
    reason: PlanOpReason
    ops: list[PlanOpKind]
    restored_revision: int | None = None
    restored_version: int | None = None
    created_at: datetime
    by_you: bool


class HousePlanRevisionListOut(_Out):
    head_revision_no: int
    items: list[HousePlanRevisionOut]
    next_before: int | None  # pass as `before` for older revisions; None when there are none


class OpsHousePlanDetailOut(HousePlanDetailOut):
    failure_detail: str | None
