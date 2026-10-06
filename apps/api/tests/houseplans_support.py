"""Shared helpers for the concept floor plan tests (Checkpoint 1): the synthetic ruleset, the
requirement fixtures, the golden plans and the negative corpus.

The negative corpus is a table of named defects. Each case takes a golden VALID plan as JSON,
breaks exactly one thing, and states the codes that must appear (`expected`) and the only other
codes that may appear as a direct consequence (`allowed`)."""

import copy
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from sqlalchemy import text

from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.vocabulary import ValidationCode as C
from p2b.houseplans.engine import (
    ArchitecturalIntent,
    DesignInputs,
    DeterministicMVPLayoutSolver,
    GenerationResult,
    Normalised,
    RulesetContent,
    generate,
    normalise,
    sha256_of,
)
from p2b.houseplans.engine.derive import analyse, fixture_info, with_clearances
from p2b.houseplans.engine.model import Fixture, HousePlan, dump

FIXTURES = Path(__file__).parent / "fixtures" / "houseplans"
GOLDEN = FIXTURES / "golden"
RULESET_VERSION = 1
SEED = 7


@cache
def ruleset_json() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (FIXTURES / "ruleset_synthetic_test_only.json").read_text("utf-8")
    )
    return data


def ruleset() -> RulesetContent:
    return RulesetContent.model_validate(ruleset_json())


def ruleset_sha() -> str:
    return sha256_of(ruleset())


@cache
def cases() -> dict[str, dict[str, Any]]:
    data: dict[str, dict[str, Any]] = json.loads(
        (FIXTURES / "requirements.json").read_text("utf-8")
    )["cases"]
    return data


def intent_for(name: str) -> ArchitecturalIntent:
    case = cases()[name]
    outcome = normalise(
        case["answers"],
        DesignInputs.model_validate(case["design_inputs"]),
        ruleset(),
        question_set_version=1,
        requirement_version=1,
        ruleset_version=RULESET_VERSION,
        ruleset_sha256=ruleset_sha(),
    )
    assert isinstance(outcome, Normalised), outcome
    return outcome.intent


def generate_case(name: str) -> GenerationResult:
    return generate(
        intent_for(name),
        ruleset(),
        ruleset_version=RULESET_VERSION,
        ruleset_sha256=ruleset_sha(),
        solver=DeterministicMVPLayoutSolver(),
        seed=SEED,
    )


def valid_cases() -> list[str]:
    return [n for n, c in cases().items() if c["expect"] == "VALID"]


def golden_plan(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((GOLDEN / f"{name}.json").read_text("utf-8"))
    return data


async def install_ruleset(
    database: Database, *, status: str = "DRAFT", synthetic: bool = True
) -> uuid.UUID:
    content = copy.deepcopy(ruleset_json())
    content["synthetic"] = synthetic
    ruleset_id = new_id()
    async with database.transaction() as session:
        await session.execute(
            text(
                "INSERT INTO layout_rulesets (id, version, status, is_synthetic, schema_version,"
                " content,"
                " content_sha256, note) VALUES (:id, :version, :status, :synthetic, '1.0.0',"
                " CAST(:content AS jsonb), :sha, 'test fixture')"
            ),
            {
                "id": ruleset_id,
                "version": RULESET_VERSION,
                "status": status,
                "synthetic": synthetic,
                "content": json.dumps(content),
                "sha": sha256_of(content),
            },
        )
    return ruleset_id


# ---------- the negative corpus ----------

Plan = dict[str, Any]


def floor(plan: Plan) -> dict[str, Any]:
    out: dict[str, Any] = plan["floors"][0]
    return out


def item(plan: Plan, group: str, ident: str) -> dict[str, Any]:
    found: dict[str, Any] = next(x for x in floor(plan)[group] if x["id"] == ident)
    return found


def find_free_spot(
    plan: Plan, room: str, fixture_type: str, *, ident: str = "extra_fixture"
) -> Fixture | None:
    """A valid position for a fixture in `room` (inside its clear area, clear of door zones and
    other fixtures), using the same derived geometry the validator uses."""
    model = HousePlan.model_validate(plan)
    rules = ruleset()
    an = with_clearances(analyse(model), rules)
    clear = an.clear_rects[room]
    assert clear is not None
    taken = [f.footprint for f in an.fixtures.values() if f.footprint] + [
        f.clearance for f in an.fixtures.values() if f.clearance
    ]
    zones = [z for o in an.openings.values() for z in o.zones]
    rule = rules.fixtures[fixture_type]  # type: ignore[index]
    walls = sorted(
        (w for w in an.walls.values() if room in w.left_rooms + w.right_rooms),
        key=lambda w: (-w.length, w.id),
    )
    for wall in walls:
        side = "LEFT" if room in wall.left_rooms else "RIGHT"
        for offset in range(0, wall.length - rule.w_mm + 1, rules.grid_mm):
            candidate = Fixture.model_validate(
                {
                    "id": ident,
                    "type": fixture_type,
                    "room": room,
                    "wall": wall.id,
                    "offset_mm": offset,
                    "side": side,
                    "w_mm": rule.w_mm,
                    "d_mm": rule.d_mm,
                    "origin": {"kind": "USER_EDIT", "ref": "test:negative_corpus"},
                }
            )
            info = fixture_info(candidate, wall, rule.clear_front_mm)
            fp, cl = info.footprint, info.clearance
            if (
                fp is not None
                and clear.contains(fp)
                and (cl is None or clear.contains(cl))
                and all(fp.overlap_area(z) == 0 for z in zones)
                and all(fp.overlap_area(t) == 0 for t in taken)
                and (cl is None or all(cl.overlap_area(t) == 0 for t in taken))
            ):
                return candidate
    return None


def opening_into(plan: Plan, room: str, kind: str) -> dict[str, Any]:
    model = HousePlan.model_validate(plan)
    an = analyse(model)
    found = next(
        dump(info.opening)
        for info in sorted(an.openings.values(), key=lambda i: i.opening.id)
        if info.opening.kind.value == kind and room in info.connects
    )
    return item(plan, "openings", found["id"])


def _wc_in_living(plan: Plan) -> None:
    spot = find_free_spot(plan, "living", "WC_WESTERN", ident="wc_western_living")
    assert spot is not None
    floor(plan)["fixtures"].append(dump(spot))


def _duplicate_wc(plan: Plan) -> None:
    for n in range(2):  # three WCs in one bath, as in the reported image-generation failure
        spot = find_free_spot(plan, "bath_common_1", "WC_WESTERN", ident=f"extra_wc_{n}")
        if spot is None:  # no free spot left: place it over the existing WC
            wc = copy.deepcopy(item(plan, "fixtures", "wc_western_bath_common_1"))
            wc["id"] = f"extra_wc_{n}"
            floor(plan)["fixtures"].append(wc)
        else:
            floor(plan)["fixtures"].append(dump(spot))


def _room_overlap(plan: Plan) -> None:
    """bedroom_1 grows over its attached bath: both rooms now claim the same floor."""
    nodes = {n["id"]: (n["x"], n["y"]) for n in floor(plan)["nodes"]}
    a, b = item(plan, "rooms", "bedroom_1"), item(plan, "rooms", "bath_attached_1")
    pts = [nodes[i] for i in a["boundary"] + b["boundary"]]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    by_xy = {xy: i for i, xy in nodes.items()}
    a["boundary"] = [by_xy[(x0, y0)], by_xy[(x1, y0)], by_xy[(x1, y1)], by_xy[(x0, y1)]]


def _room_outside_envelope(plan: Plan) -> None:
    """The rear wall line moves 600 mm into the back setback (still inside the plot)."""
    rear = max(n["y"] for n in floor(plan)["nodes"])
    for n in floor(plan)["nodes"]:
        if n["y"] == rear:
            n["y"] = rear + 600


def _door_host_missing(plan: Plan) -> None:
    opening_into(plan, "bedroom_2", "DOOR")["wall"] = "w_missing"


def _door_off_wall(plan: Plan) -> None:
    door = opening_into(plan, "bedroom_2", "DOOR")
    wall = item(plan, "walls", door["wall"])
    nodes = {n["id"]: (n["x"], n["y"]) for n in floor(plan)["nodes"]}
    (ax, ay), (bx, by) = nodes[wall["a"]], nodes[wall["b"]]
    door["offset_mm"] = abs(bx - ax) + abs(by - ay) + 200


def _door_with_coordinates(plan: Plan) -> None:
    door = opening_into(plan, "bedroom_2", "DOOR")
    door["x"], door["y"] = 1000, 2000


def _window_host_missing(plan: Plan) -> None:
    item(plan, "openings", "window_bedroom_1")["wall"] = "w_missing"


def _window_on_interior(plan: Plan) -> None:
    window = item(plan, "openings", "window_bedroom_1")
    model = HousePlan.model_validate(plan)
    an = analyse(model)
    interior = sorted(
        (
            w
            for w in an.walls.values()
            if w.kind.value == "INTERIOR" and "bedroom_1" in w.left_rooms + w.right_rooms
        ),
        key=lambda w: (-w.length, w.id),
    )
    for wall in interior:
        used = [(o.start, o.end) for o in an.openings.values() if o.wall.id == wall.id]
        for offset in range(100, wall.length - window["width_mm"] - 100, 50):
            if all(offset + window["width_mm"] + 100 <= s or offset >= e + 100 for s, e in used):
                window["wall"], window["offset_mm"] = wall.id, offset
                return
    raise AssertionError("no interior wall with room for the window")


def _delete_opening(plan: Plan, ident: str) -> None:
    floor(plan)["openings"] = [o for o in floor(plan)["openings"] if o["id"] != ident]


def _room_unreachable(plan: Plan) -> None:
    _delete_opening(plan, opening_into(plan, "bedroom_2", "DOOR")["id"])


def _attached_door_missing(plan: Plan) -> None:
    _delete_opening(plan, opening_into(plan, "bath_attached_1", "DOOR")["id"])


def _no_entrance(plan: Plan) -> None:
    _delete_opening(plan, "main_entrance")


def _fixture_outside_room(plan: Plan) -> None:
    basin = item(plan, "fixtures", "wash_basin_bath_common_1")
    basin["offset_mm"] = 0  # the corner of the wall's centreline, inside the neighbouring wall


def _parking_missing(plan: Plan) -> None:
    floor(plan)["rooms"] = [r for r in floor(plan)["rooms"] if r["id"] != "parking"]


def _dangling_wall(plan: Plan) -> None:
    room = item(plan, "rooms", "bedroom_2")
    nodes = {n["id"]: (n["x"], n["y"]) for n in floor(plan)["nodes"]}
    x, y = nodes[room["boundary"][0]]
    floor(plan)["nodes"] += [
        {"id": "n_free_a", "x": x + 800, "y": y + 800},
        {"id": "n_free_b", "x": x + 1600, "y": y + 800},
    ]
    floor(plan)["walls"].append(
        {
            "id": "w_dangling",
            "a": "n_free_a",
            "b": "n_free_b",
            "thickness_mm": 100,
            "kind": "INTERIOR",
        }
    )


def _unknown_major(plan: Plan) -> None:
    plan["meta"]["schema_version"] = "2.0.0"


def _duplicate_id(plan: Plan) -> None:
    opening_into(plan, "bedroom_2", "DOOR")["id"] = "bedroom_2"


def _missing_node(plan: Plan) -> None:
    item(plan, "rooms", "bedroom_2")["boundary"][0] = "n_missing"


def _door_too_narrow(plan: Plan) -> None:
    opening_into(plan, "bedroom_2", "DOOR")["width_mm"] = 500


def _negative_width(plan: Plan) -> None:
    opening_into(plan, "bedroom_2", "DOOR")["width_mm"] = -5


def _wall_too_thin(plan: Plan) -> None:
    floor(plan)["walls"][0]["thickness_mm"] = 10


@dataclass(frozen=True)
class NegativeCase:
    name: str
    defect: str
    mutate: Callable[[Plan], None]
    expected: frozenset[C]
    allowed: frozenset[C] = field(default_factory=frozenset)
    repairable: bool = False


def _case(
    name: str,
    defect: str,
    mutate: Callable[[Plan], None],
    expected: set[C],
    allowed: set[C] | None = None,
    repairable: bool = False,
) -> NegativeCase:
    return NegativeCase(
        name, defect, mutate, frozenset(expected), frozenset(allowed or set()), repairable
    )


FIXTURE_SIDE_EFFECTS = {C.FIXTURE_OVERLAP, C.FIXTURE_CLEARANCE_BLOCKED, C.FIXTURE_BLOCKS_OPENING}

NEGATIVE_CASES = [
    _case(
        "wc_in_living", "A WC in the living room", _wc_in_living, {C.FIXTURE_NOT_PERMITTED_IN_ROOM}
    ),
    _case(
        "duplicate_wc",
        "Three WCs in one ordinary bathroom",
        _duplicate_wc,
        {C.FIXTURE_COUNT_EXCEEDS_SPEC},
        FIXTURE_SIDE_EFFECTS,
    ),
    _case(
        "room_overlap",
        "Bedroom 1 grows over its attached bathroom",
        _room_overlap,
        {C.ROOM_OVERLAP},
        # the bath's door now opens from inside the bedroom's claimed area, not from its edge
        {C.ROOM_UNREACHABLE, C.RELATION_UNMET},
    ),
    _case(
        "room_outside_envelope",
        "The rear rooms extend into the back setback",
        _room_outside_envelope,
        {C.ROOM_OUTSIDE_ENVELOPE},
    ),
    _case(
        "door_host_missing",
        "A door hosted by a wall that does not exist",
        _door_host_missing,
        {C.OPENING_HOST_MISSING},
    ),
    _case(
        "door_off_wall",
        "A door placed past the end of its wall",
        _door_off_wall,
        {C.OPENING_OUTSIDE_HOST},
        {C.FIXTURE_BLOCKS_OPENING},
        repairable=True,
    ),
    _case(
        "door_with_coordinates",
        "A door given free coordinates",
        _door_with_coordinates,
        {C.SCHEMA_INVALID},
    ),
    _case(
        "window_host_missing",
        "A window hosted by a wall that does not exist",
        _window_host_missing,
        {C.OPENING_HOST_MISSING},
    ),
    _case(
        "window_on_interior",
        "A bedroom window moved to an interior wall",
        _window_on_interior,
        {C.WINDOW_ON_INTERIOR_WALL, C.HABITABLE_ROOM_NO_WINDOW},
        {C.FIXTURE_BLOCKS_OPENING},
    ),
    _case("room_unreachable", "Bedroom 2 has no door", _room_unreachable, {C.ROOM_UNREACHABLE}),
    _case(
        "attached_door_missing",
        "The attached bathroom has no door from its bedroom",
        _attached_door_missing,
        {C.RELATION_UNMET, C.ROOM_UNREACHABLE},
    ),
    _case(
        "no_entrance",
        "The main entrance is removed",
        _no_entrance,
        {C.ENTRANCE_MISSING, C.ROOM_UNREACHABLE},
    ),
    _case(
        "fixture_outside_room",
        "A basin pushed into the wall corner",
        _fixture_outside_room,
        {C.FIXTURE_OUTSIDE_ROOM},
        repairable=True,
    ),
    _case(
        "parking_missing",
        "The parking room is removed",
        _parking_missing,
        {C.PARKING_MISSING, C.ROOM_COUNT_MISMATCH},
    ),
    _case(
        "dangling_wall",
        "A wall that ends in the middle of a room",
        _dangling_wall,
        {C.WALL_DANGLING_END},
    ),
    _case(
        "unknown_major",
        "A document of schema 2.0.0",
        _unknown_major,
        {C.SCHEMA_VERSION_UNSUPPORTED},
    ),
    _case("duplicate_id", "A door with the same id as a room", _duplicate_id, {C.ID_DUPLICATE}),
    _case(
        "missing_node",
        "A room boundary naming a node that does not exist",
        _missing_node,
        {C.REF_MISSING},
    ),
    _case(
        "door_too_narrow",
        "A door narrower than the ruleset minimum",
        _door_too_narrow,
        {C.OPENING_DIMENSION_INVALID},
    ),
    _case("negative_width", "A door with a negative width", _negative_width, {C.SCHEMA_INVALID}),
    _case(
        "wall_too_thin",
        "A wall thinner than the ruleset minimum",
        _wall_too_thin,
        {C.WALL_THICKNESS_INVALID},
    ),
]
