"""Layout ruleset content, schema 1.1.0 (ADR-025, AD-05); 1.0.0 content still loads.

Every architectural number the engine uses lives here: room minimums, wall thicknesses, door and
window sizes, passage width, fixture sizes, clearances and templates, parking space sizes, the
base programme and the zoning roles the deterministic MVP solver uses. No engine function holds a
rule value of its own. A production ruleset needs a citation per value and an approver; the only
ruleset so far is synthetic test data (CP1-06). Version 1.1.0 adds what the Checkpoint 2 objective
needs: preferred proportions, aspect limits, circulation target, soft relations, zoning options,
objective weights, and the structure (not the values) for setbacks, parking placement and
orientation (CP2-U1, CP2-U7, CP2-U8)."""

from datetime import date
from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer

from p2b.core.vocabulary import (
    ConstraintKind,
    Facing,
    FixtureType,
    ParkingKind,
    ParkingPlacement,
    RoomType,
    Zone,
)

PosMm = Annotated[int, Field(gt=0, le=1_000_000)]
NonNegMm = Annotated[int, Field(ge=0, le=1_000_000)]


class _Rules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)
    # Fields added in content 1.1.0. Left at their default they are omitted when serialised, so a
    # 1.0.0 ruleset hashes exactly as it did in Checkpoint 1 and its plans still match it.
    _added_1_1: ClassVar[tuple[str, ...]] = ()

    @model_serializer(mode="wrap")
    def _omit_absent_1_1(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        fields = type(self).model_fields
        for name in self._added_1_1:
            field = fields[name]
            if getattr(self, name) == field.get_default(call_default_factory=True):
                data.pop(field.alias or name, None)
        return data


class RoomRule(_Rules):
    zone: Zone
    enclosed: bool
    needs_window: bool
    wet: bool
    min_short_mm: PosMm  # clear (inside-face) dimension
    min_area_mm2: Annotated[int, Field(gt=0)]  # clear area
    pref_area_mm2: Annotated[int, Field(gt=0)] | None = None
    max_area_mm2: Annotated[int, Field(gt=0)] | None = None
    # 1.1.0: preferred clear proportions, orientation-free (short and long side)
    pref_short_mm: PosMm | None = None
    pref_long_mm: PosMm | None = None
    aspect_limit_x10: Annotated[int, Field(ge=10, le=100)] | None = None  # long / short x 10

    _added_1_1 = ("pref_short_mm", "pref_long_mm", "aspect_limit_x10")


class FixtureRule(_Rules):
    w_mm: PosMm
    d_mm: PosMm
    clear_front_mm: NonNegMm
    count_group: Annotated[str, Field(min_length=1, max_length=40)]
    permitted_rooms: Annotated[list[RoomType], Field(min_length=1)]


class TemplateItem(_Rules):
    fixture: FixtureType
    count: Annotated[int, Field(ge=1, le=10)]
    max_count: Annotated[int, Field(ge=1, le=10)]


class WallRules(_Rules):
    exterior_mm: PosMm
    interior_mm: PosMm
    min_mm: PosMm
    max_mm: PosMm


class LevelRules(_Rules):
    floor_to_floor_mm: PosMm
    clear_height_mm: PosMm
    slab_mm: PosMm
    plinth_mm: NonNegMm


class OpeningRules(_Rules):
    main_entrance_width_mm: PosMm
    door_width_mm: PosMm
    door_height_mm: PosMm
    min_door_width_mm: PosMm
    void_width_mm: PosMm
    jamb_clearance_mm: NonNegMm
    window_width_mm: PosMm
    min_window_width_mm: PosMm
    window_height_mm: PosMm
    window_sill_mm: NonNegMm


class ParkingRule(_Rules):
    space_w_mm: PosMm
    space_d_mm: PosMm


class ZoningRules(_Rules):
    """Roles the deterministic MVP solver gives room types. Data, so a later programme can change
    them without touching geometry code (CP1-09)."""

    front_band: Annotated[list[RoomType], Field(min_length=1)]  # left to right, seen from the road
    entry_room: RoomType  # holds the main entrance and opens to the circulation spine
    anchored_to_entry: list[RoomType]  # the first present type sits directly behind the entry room
    column_order: list[RoomType]  # order in which room groups fill the columns beside the spine
    circulation_room: RoomType  # the spine's room type
    attached_to: dict[
        RoomType, RoomType
    ] = {}  # a room of the key type is reached through the host type
    # 1.1.0 (Checkpoint 2 zoning): types that may join the front band beside the entry room
    # (CP2-U2), types that may take the rear band, and the front-to-back privacy order of zones.
    front_band_extension: list[RoomType] = []
    rear_band: list[RoomType] = []
    depth_order: list[Zone] = []
    # 1.1.0 (Checkpoint 2.1): the narrowest open (unbuilt) strip a layout may leave inside the
    # envelope, for a rear or side yard. Absent: layouts fill the envelope, as in Checkpoint 2.
    open_space_min_mm: PosMm | None = None

    _added_1_1 = ("front_band_extension", "rear_band", "depth_order", "open_space_min_mm")


class CirculationRules(_Rules):
    target_share_milli: Annotated[int, Field(ge=0, le=1000)]  # passage area / total clear area


class SoftRelationRule(_Rules):
    """Two room types that should share a wall long enough for a door (soft)."""

    a: RoomType
    b: RoomType


class SetbackRow(_Rules):
    """Structure only (AD-05): setbacks by plot size and road width. Unused until approved."""

    max_plot_area_mm2: int | None = None
    max_road_width_mm: int | None = None
    front_mm: NonNegMm
    back_mm: NonNegMm
    side_mm: NonNegMm


class OrientationRule(_Rules):
    """Structure only (AD-13): preferred compass sectors for a room type. None exist yet, so the
    ORIENTATION term is NOT_EVALUATED; never a compliance claim."""

    room_type: RoomType
    sectors: Annotated[list[Facing], Field(min_length=1)]


class ObjectiveRules(_Rules):
    weights: dict[ConstraintKind, Annotated[int, Field(ge=0, le=1000)]]
    exposure_min_mm: PosMm  # exterior wall length a window-needing room should have
    candidate_limit: Annotated[int, Field(ge=1, le=200)]  # zoned candidates sized per plan
    split_limit: Annotated[int, Field(ge=1, le=64)]  # column splits kept per topology
    build_attempts: Annotated[int, Field(ge=1, le=20)]  # ranked candidates built before giving up
    # Checkpoint 2.1: candidates per topology family sized coarsely before the best
    # `candidate_limit` overall are sized fully
    family_pool: Annotated[int, Field(ge=1, le=200)] = 12


class Approval(_Rules):
    approver_role: str
    reference: str


class Citation(_Rules):
    document: Annotated[str, Field(min_length=1, max_length=200)]
    clause: Annotated[str, Field(min_length=1, max_length=120)]
    note: str | None = None


class RulesetContent(_Rules):
    schema_: Literal["p2b.layout-ruleset"] = Field(default="p2b.layout-ruleset", alias="schema")
    content_version: Literal["1.0.0", "1.1.0"]
    synthetic: bool
    effective_from: date | None = None
    effective_to: date | None = None
    approval: Approval | None = None
    note: str
    units: Literal["mm"]
    grid_mm: PosMm
    walls: WallRules
    levels: LevelRules
    rooms: dict[RoomType, RoomRule]
    base_programme: list[RoomType]
    zoning: ZoningRules
    passage_min_width_mm: PosMm
    openings: OpeningRules
    fixtures: dict[FixtureType, FixtureRule]
    templates: dict[RoomType, list[TemplateItem]]
    parking: dict[ParkingKind, ParkingRule]
    parking_placements: list[ParkingPlacement] = [ParkingPlacement.INSIDE_FOOTPRINT]
    circulation: CirculationRules | None = None
    relations_soft: list[SoftRelationRule] = []
    setback_table: list[SetbackRow] = []
    orientation: list[OrientationRule] = []
    objective: ObjectiveRules | None = None
    sources: dict[str, Citation]

    _added_1_1 = (
        "effective_from",
        "effective_to",
        "approval",
        "parking_placements",
        "circulation",
        "relations_soft",
        "setback_table",
        "orientation",
        "objective",
    )


VALUE_SECTIONS = (
    "grid_mm",
    "walls",
    "levels",
    "rooms",
    "base_programme",
    "zoning",
    "passage_min_width_mm",
    "openings",
    "fixtures",
    "templates",
    "parking",
    "parking_placements",
    "circulation",
    "relations_soft",
    "setback_table",
    "orientation",
    "objective",
)


def value_pointers(content: RulesetContent) -> list[str]:
    """JSON pointers of every rule value (leaves of the value sections)."""
    data = content.model_dump(mode="json", by_alias=True)
    out: list[str] = []

    def walk(node: object, path: str) -> None:
        if isinstance(node, dict):
            for key in sorted(node):
                walk(node[key], f"{path}/{key}")
        elif isinstance(node, list) and node and isinstance(node[0], dict):
            for i, item in enumerate(node):
                walk(item, f"{path}/{i}")
        else:
            out.append(path)

    for section in VALUE_SECTIONS:
        if section in data:  # a 1.1.0 section left at its default is absent and holds no value
            walk(data[section], f"/{section}")
    return out


def missing_citations(content: RulesetContent) -> list[str]:
    """Rule values without a citation. Publication requires none (AD-05); a pointer is covered by
    a citation on itself or on any parent pointer."""
    cited = set(content.sources)
    missing = []
    for pointer in value_pointers(content):
        parts = pointer.split("/")
        if not any("/".join(parts[:i]) in cited for i in range(2, len(parts) + 1)):
            missing.append(pointer)
    return missing
