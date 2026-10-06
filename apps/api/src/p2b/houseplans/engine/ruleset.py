"""Layout ruleset content, schema 1.0.0 (ADR-025, AD-05).

Every architectural number the engine uses lives here: room minimums, wall thicknesses, door and
window sizes, passage width, fixture sizes, clearances and templates, parking space sizes, the
base programme and the zoning roles the deterministic MVP solver uses. No engine function holds a
rule value of its own. A production ruleset needs a citation per value and an approver; the only
ruleset in Checkpoint 1 is synthetic test data (CP1-06)."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from p2b.core.vocabulary import FixtureType, ParkingKind, RoomType, Zone

PosMm = Annotated[int, Field(gt=0, le=1_000_000)]
NonNegMm = Annotated[int, Field(ge=0, le=1_000_000)]


class _Rules(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class RoomRule(_Rules):
    zone: Zone
    enclosed: bool
    needs_window: bool
    wet: bool
    min_short_mm: PosMm  # clear (inside-face) dimension
    min_area_mm2: Annotated[int, Field(gt=0)]  # clear area
    pref_area_mm2: Annotated[int, Field(gt=0)] | None = None
    max_area_mm2: Annotated[int, Field(gt=0)] | None = None


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


class Citation(_Rules):
    document: Annotated[str, Field(min_length=1, max_length=200)]
    clause: Annotated[str, Field(min_length=1, max_length=120)]
    note: str | None = None


class RulesetContent(_Rules):
    schema_: Literal["p2b.layout-ruleset"] = Field(default="p2b.layout-ruleset", alias="schema")
    content_version: Literal["1.0.0"]
    synthetic: bool
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
    sources: dict[str, Citation]


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
