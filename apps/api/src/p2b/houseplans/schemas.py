"""API shapes for concept floor plans. The plan, intent, geometry and report are the engine's own
models, so the contract the web app receives is the canonical schema, not a copy of it."""

from datetime import datetime
from typing import Annotated, Any, Literal

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
    PlanOpRejection,
    PlanValidity,
    RoomSide,
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
from p2b.houseplans.engine.assist import RefusalReason
from p2b.houseplans.engine.edit import MAX_BATCH
from p2b.houseplans.engine.ops import PlanOp
from p2b.houseplans.engine.validate import ValidationIssue


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
    min_area_mm2: int | None = None  # Checkpoint 3.2: clear area, for the add-room check


class InsertionSlotOut(_Out):
    """Where a room can be added in open space against an outside wall (Checkpoint 3.2),
    derived from the document on read (`engine/insertion.py`). Lengths are centreline lengths;
    the clear size is smaller by the allowances. A suggestion: the server checks every
    ADD_ROOM_OUTSIDE again and the validator judges the result."""

    host_room: str
    side: RoomSide
    offset_mm: int
    length_mm: int
    max_depth_mm: int
    open_area: str | None
    open_area_kind: str | None
    depth_allowance_mm: int
    length_allowance_mm: int


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
    insertion_slots: list[InsertionSlotOut] = []
    # Checkpoint 4: the AI assistant is on for this owner (feature flag and a configured model)
    assistant: bool = False


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


class AssistantEditRequest(_Out):
    """One sentence from the owner about the plan the editor shows (`expected_revision`)."""

    text: Annotated[str, Field(min_length=1, max_length=400)]
    expected_revision: Annotated[int, Field(ge=0)]


class AssistantCallOut(_Out):
    provider: str
    model: str
    request_id: str
    duration_ms: int
    model_calls: int
    input_tokens: int
    output_tokens: int


class RoomChangeOut(_Out):
    room: str
    name: str
    kind: Literal["CHANGED", "ADDED", "REMOVED", "RETYPED", "RENAMED"]
    area_before_mm2: int | None
    area_after_mm2: int | None
    type_before: str | None
    type_after: str | None


class OpeningChangeOut(_Out):
    opening: str
    kind: Literal["MOVED", "RESIZED"]
    width_before_mm: int
    width_after_mm: int


class AssistantRejectionOut(_Out):
    """An operation the engine refused, as the operations route reports one."""

    op: str
    code: PlanOpRejection
    entities: list[str]


class AssistantRefusalOut(_Out):
    """The engine's reason for making no proposal. `reason` is final: the model may have read
    the request again, but it never rewords or replaces this. `rejections` and `issues` are the
    first operation rejection and validator error of each code the candidates met."""

    reason: RefusalReason
    rejections: list[AssistantRejectionOut]
    issues: list[ValidationIssue]


class AssistantEditOut(_Out):
    """A proposal, never a change: PROPOSED carries typed operations already validated against
    the plan at `expected_revision`, to be sent through the operations route if the owner
    applies them; UNSUPPORTED and CLARIFY say why there is none; FAILED means no reading of the
    request passed the plan's rules within the bounded attempts: `refusal` gives the engine's
    reason, with `intent` the reading it refused (no `refusal`: the model's answers could not be
    read as a change). The disclaimer applies."""

    status: Literal["PROPOSED", "UNSUPPORTED", "CLARIFY", "FAILED"]
    intent: dict[str, Any] | None
    ops: list[PlanOp]
    expected_revision: int
    preview: PlanGeometry | None  # the proposed plan's geometry, for the preview only
    rooms: list[RoomChangeOut]
    openings: list[OpeningChangeOut]
    detail: str | None
    refusal: AssistantRefusalOut | None
    call: AssistantCallOut


class AssistantRequirementRequest(_Out):
    text: Annotated[str, Field(min_length=1, max_length=400)]


class RequirementConflictOut(_Out):
    key: str
    requirement: Any
    said: Any


class AssistantRequirementOut(_Out):
    """The owner's description as requirement facts and provisional design inputs. The
    submitted requirement stays the authority: `conflicts` lists where the words differ, and
    generation uses the existing route with `design_inputs` once the owner confirms."""

    status: Literal["INTERPRETED", "FAILED"]
    intent: dict[str, Any] | None
    design_inputs: DesignInputs | None
    missing: list[str]
    assumed: list[str]
    unsupported: list[str]
    preferences: list[str]
    clarifications: list[str]
    conflicts: list[RequirementConflictOut]
    call: AssistantCallOut


class OpsHousePlanDetailOut(HousePlanDetailOut):
    failure_detail: str | None
