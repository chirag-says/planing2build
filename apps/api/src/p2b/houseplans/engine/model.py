"""The HousePlan document, schema 1.0.0: the single source of truth for a concept floor plan
(PD-28, ADR-025). SVG, PDF, 3D and images are derived from it and never written back.

Rules the shape enforces:
- lengths are integer millimetres;
- walls join wall nodes, and a room boundary is a cycle of node ids, so rooms and walls share one
  planar graph;
- openings and fixtures have no coordinates of their own: an opening is (host wall, offset,
  width), a fixture is (room, host wall, offset, side). A payload that gives either free
  coordinates fails the schema (`extra="forbid"`).
Plot-local frame: origin at the front-left plot corner as seen standing on the primary road edge
looking at the plot (CP1-01, CP1-02); +x along the road edge to the right; +y away from the
road. Polygons are counter-clockwise. `north_angle_deg` is the clockwise angle from +y to north.
"""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StringConstraints,
    model_serializer,
    model_validator,
)

from p2b.core.vocabulary import (
    ConstraintKind,
    ConstraintOutcome,
    ConstraintStrength,
    DoorLeaf,
    Facing,
    FixtureType,
    HingeSide,
    OpeningKind,
    OriginKind,
    ParkingKind,
    ParkingPlacement,
    PlanSource,
    PlotEdgeKind,
    RoomType,
    SetbackSide,
    SetbackSource,
    SolverKind,
    WallKind,
    WallSide,
    Zone,
)

SCHEMA = "p2b.houseplan"
SCHEMA_VERSION = "1.1.0"  # 1.1.0 adds Constraint.score_milli (soft quality terms)
SCHEMA_VERSION_1_0 = "1.0.0"
SCHEMA_MAJOR = 1

Mm = Annotated[int, Field(ge=-10_000_000, le=10_000_000)]
PosMm = Annotated[int, Field(gt=0, le=1_000_000)]
NonNegMm = Annotated[int, Field(ge=0, le=1_000_000)]
Id = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,47}$")]
Text = Annotated[str, StringConstraints(min_length=1, max_length=120)]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Origin(Frozen):
    kind: OriginKind
    ref: Text  # e.g. "requirement:bedrooms", "ruleset:base_programme", "solver:circulation"


class Point(Frozen):
    x: Mm
    y: Mm


class PlotEdge(Frozen):
    id: Id
    start: Annotated[int, Field(ge=0)]  # vertex index
    end: Annotated[int, Field(ge=0)]
    kind: PlotEdgeKind
    side: SetbackSide
    road_width_mm: PosMm | None = None


class Plot(Frozen):
    vertices: Annotated[list[Point], Field(min_length=4, max_length=64)]
    edges: Annotated[list[PlotEdge], Field(min_length=4, max_length=64)]


class Setback(Frozen):
    edge: Id
    distance_mm: NonNegMm
    source: SetbackSource


class Parking(Frozen):
    spaces: Annotated[int, Field(ge=1, le=4)]
    kind: ParkingKind
    space_w_mm: PosMm
    space_d_mm: PosMm
    placement: ParkingPlacement
    origin: Origin


class Site(Frozen):
    plot: Plot
    north_angle_deg: Annotated[int, Field(ge=0, lt=360)]
    facing: Facing
    entry_edge: Id
    setbacks: Annotated[list[Setback], Field(min_length=1, max_length=64)]
    parking: Parking | None = None


class Node(Frozen):
    id: Id
    x: Mm
    y: Mm


class Wall(Frozen):
    id: Id
    a: Id
    b: Id
    thickness_mm: PosMm
    kind: WallKind
    structural_role: Literal["UNASSESSED"] = "UNASSESSED"  # never asserted (PD-28, R-07)


class SizeSpec(Frozen):
    min_short_mm: PosMm
    min_area_mm2: Annotated[int, Field(gt=0)]
    pref_area_mm2: Annotated[int, Field(gt=0)] | None = None
    max_area_mm2: Annotated[int, Field(gt=0)] | None = None


class Room(Frozen):
    id: Id
    type: RoomType
    name: Text
    boundary: Annotated[list[Id], Field(min_length=4, max_length=256)]
    zone: Zone
    enclosed: bool
    required: bool
    size_spec: SizeSpec
    origin: Origin


class DoorSpec(Frozen):
    leaf: DoorLeaf
    hinge: HingeSide
    opens_to: WallSide


class Opening(Frozen):
    id: Id
    kind: OpeningKind
    wall: Id  # the host: the only position reference
    offset_mm: NonNegMm  # from node a to the near jamb, along the wall
    width_mm: PosMm
    height_mm: PosMm
    sill_mm: NonNegMm
    door: DoorSpec | None = None

    @model_validator(mode="after")
    def _door_spec_iff_door(self) -> "Opening":
        is_door = self.kind in (OpeningKind.DOOR, OpeningKind.MAIN_ENTRANCE)
        if is_door != (self.door is not None):
            raise ValueError(
                "a door or main entrance needs `door`; other openings must not have it"
            )
        if self.kind != OpeningKind.WINDOW and self.sill_mm != 0:
            raise ValueError("only a window has a sill")
        return self


class Stair(Frozen):
    """Present for schema stability; Checkpoint 1 generates none; the v1 validator refuses one."""

    id: Id
    room: Id
    width_mm: PosMm
    riser_mm: PosMm
    tread_mm: PosMm
    risers: Annotated[int, Field(ge=1, le=60)]


class Fixture(Frozen):
    id: Id
    type: FixtureType
    room: Id
    wall: Id
    offset_mm: NonNegMm  # from the wall's node a to the fixture's near edge, along the wall
    side: WallSide  # the face of the wall the fixture stands against
    w_mm: PosMm  # along the wall
    d_mm: PosMm  # away from the wall
    origin: Origin


class Floor(Frozen):
    id: Id
    level: Annotated[int, Field(ge=0, le=3)]
    name: Text
    ffl_mm: Mm
    floor_to_floor_mm: PosMm
    clear_height_mm: PosMm
    slab_mm: PosMm
    plinth_mm: NonNegMm
    nodes: list[Node]
    walls: list[Wall]
    rooms: list[Room]
    openings: list[Opening]
    stairs: list[Stair] = []
    fixtures: list[Fixture]


ParamValue = int | str | bool | list[str]


class Constraint(Frozen):
    id: Id
    kind: ConstraintKind
    strength: ConstraintStrength
    weight: Annotated[int, Field(ge=0, le=1000)]
    subjects: list[str]
    params: dict[str, ParamValue]
    origin: Origin
    outcome: ConstraintOutcome
    # 1.1.0: a soft term's measured score (milli; 0 = fully met). Absent on hard constraints and
    # in 1.0.0 documents, and then omitted from the JSON, so 1.0.0 hashes do not change.
    score_milli: Annotated[int, Field(ge=0)] | None = None

    @model_serializer(mode="wrap")
    def _omit_absent_score(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        if self.score_milli is None:
            data.pop("score_milli", None)
        return data


class Compromise(Frozen):
    id: Id
    constraint: Id
    change_key: Text
    params: dict[str, ParamValue]
    accepted_by_user: bool | None = None


class GeneratorInfo(Frozen):
    engine: Literal["p2b-houseplans"]
    engine_version: str
    solver: SolverKind
    solver_version: str
    seed: int
    ruleset_version: int
    ruleset_sha256: str
    intent_sha256: str


class Meta(Frozen):
    schema_: Literal["p2b.houseplan"] = Field(default="p2b.houseplan", alias="schema")
    schema_version: Annotated[str, StringConstraints(pattern=r"^\d+\.\d+\.\d+$")]
    plan_id: UUID | None = None
    project_id: UUID | None = None
    question_set_version: int | None = None
    requirement_version: int | None = None
    revision_no: Annotated[int, Field(ge=0)] = 0
    source: PlanSource
    generator: GeneratorInfo
    created_at: datetime | None = None
    created_by: str | None = None
    body_sha256: str | None = None


class HousePlanBody(Frozen):
    site: Site
    floors: Annotated[list[Floor], Field(min_length=1, max_length=4)]
    constraints: list[Constraint]
    compromises: list[Compromise]


class HousePlan(HousePlanBody):
    meta: Meta

    def body(self) -> HousePlanBody:
        return HousePlanBody(
            site=self.site,
            floors=self.floors,
            constraints=self.constraints,
            compromises=self.compromises,
        )


def dump(model: BaseModel) -> dict[str, Any]:
    """The JSON form used for storage, hashing and the API."""
    return model.model_dump(mode="json", by_alias=True)
