"""The independent validator. Every generated plan, every repair pass and (later) every edit goes
through it; a plan with any ERROR is INVALID and is never presented as a result.

Stages: SCHEMA (parse, version) → REFERENCES (ids and references) → everything else on the
derived geometry. A failed stage stops the later ones, so one broken reference reports exactly
that, not a cascade. Issues are machine-readable and name the entities to highlight.

It does not trust anything the generator computed: it re-derives from the document, sharing only
the geometry definitions in `derive` (where a hosted element is) with the generator."""

from collections import Counter, deque
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from pydantic import ValidationError

from p2b.core.vocabulary import (
    ConstraintStrength,
    EntityKind,
    OpeningKind,
    RelationKind,
    RepairHint,
    RoomType,
    SetbackSide,
    ValidationCategory,
    ValidationCode,
    ValidationSeverity,
    WallKind,
)
from p2b.houseplans.engine.derive import (
    EXTERIOR,
    Analysis,
    FixtureInfo,
    WallInfo,
    analyse,
    half,
    with_clearances,
)
from p2b.houseplans.engine.geom import (
    Rect,
    is_axis_aligned,
    rect_or_none,
    segment_covered,
    signed_area2,
)
from p2b.houseplans.engine.intent import ArchitecturalIntent
from p2b.houseplans.engine.model import Floor, Frozen, HousePlan, ParamValue, Room
from p2b.houseplans.engine.programme import expected_counts, removed_rooms
from p2b.houseplans.engine.ruleset import RulesetContent
from p2b.houseplans.engine.upgrade import is_supported, schema_version_of

ENGINE_VERSION = "1.0.0"
C, V = ValidationCode, ValidationCategory

# code -> (category, repair hint, English message with {params})
CATALOGUE: dict[ValidationCode, tuple[ValidationCategory, RepairHint, str]] = {
    C.SCHEMA_INVALID: (
        V.SCHEMA,
        RepairHint.NONE,
        "The plan does not match the schema at {loc}: {problem}.",
    ),
    C.SCHEMA_VERSION_UNSUPPORTED: (
        V.SCHEMA,
        RepairHint.NONE,
        "Schema version {version} is not supported.",
    ),
    C.ID_DUPLICATE: (V.REFERENCES, RepairHint.NONE, "The id {id} is used more than once."),
    C.REF_MISSING: (
        V.REFERENCES,
        RepairHint.NONE,
        "{field} refers to {ref}, which does not exist.",
    ),
    C.OPENING_HOST_MISSING: (
        V.REFERENCES,
        RepairHint.USER,
        "The {kind} is hosted by wall {ref}, which does not exist.",
    ),
    C.FIXTURE_HOST_MISSING: (
        V.REFERENCES,
        RepairHint.USER,
        "The fixture refers to {field} {ref}, which does not exist.",
    ),
    C.PLOT_INVALID: (V.GEOMETRY, RepairHint.NONE, "The plot is not valid: {problem}."),
    C.GEOMETRY_UNSUPPORTED_V1: (
        V.GEOMETRY,
        RepairHint.NONE,
        "This version supports only {supported}.",
    ),
    C.ROOM_POLYGON_INVALID: (V.GEOMETRY, RepairHint.NONE, "{room} does not have a valid boundary."),
    C.ROOM_OVERLAP: (
        V.GEOMETRY,
        RepairHint.USER,
        "{room_a} overlaps {room_b} by {overlap_mm2} mm².",
    ),
    C.ROOM_OUTSIDE_ENVELOPE: (
        V.GEOMETRY,
        RepairHint.USER,
        "{entity} extends outside the buildable area (setbacks).",
    ),
    C.BUILDING_OUTSIDE_PLOT: (V.GEOMETRY, RepairHint.USER, "{entity} extends outside the plot."),
    C.ROOM_EDGE_NOT_ON_WALL: (V.GEOMETRY, RepairHint.NONE, "An edge of {room} has no wall."),
    C.WALL_ZERO_LENGTH: (V.GEOMETRY, RepairHint.NONE, "Wall {wall} has no length."),
    C.WALL_NOT_ORTHOGONAL: (
        V.GEOMETRY,
        RepairHint.NONE,
        "Wall {wall} is not horizontal or vertical.",
    ),
    C.WALL_OVERLAP: (V.GEOMETRY, RepairHint.NONE, "Walls {wall_a} and {wall_b} overlap."),
    C.WALL_DANGLING_END: (
        V.GEOMETRY,
        RepairHint.NONE,
        "Wall {wall} ends at a node no other wall meets.",
    ),
    C.WALL_THICKNESS_INVALID: (
        V.DIMENSIONS,
        RepairHint.NONE,
        "Wall {wall} is {thickness_mm} mm thick; allowed {min_mm} to {max_mm} mm.",
    ),
    C.OPENING_OUTSIDE_HOST: (
        V.OPENINGS,
        RepairHint.AUTO,
        "The {kind} does not fit on its wall ({start_mm} to {end_mm} mm on a {length_mm} mm wall).",
    ),
    C.OPENING_OVERLAP: (
        V.OPENINGS,
        RepairHint.AUTO,
        "Openings {opening_a} and {opening_b} overlap on one wall.",
    ),
    C.OPENING_DIMENSION_INVALID: (
        V.DIMENSIONS,
        RepairHint.USER,
        "The {kind} has invalid dimensions: {problem}.",
    ),
    C.WINDOW_ON_INTERIOR_WALL: (
        V.OPENINGS,
        RepairHint.USER,
        "A window is placed on interior wall {wall}.",
    ),
    C.FIXTURE_NOT_ON_ROOM_WALL: (
        V.FIXTURES,
        RepairHint.USER,
        "The {fixture_type} is not against a wall of {room}.",
    ),
    C.FIXTURE_OUTSIDE_ROOM: (
        V.FIXTURES,
        RepairHint.AUTO,
        "The {fixture_type} is not inside {room}.",
    ),
    C.FIXTURE_NOT_PERMITTED_IN_ROOM: (
        V.FIXTURES,
        RepairHint.USER,
        "A {fixture_type} is not permitted in a {room_type} room.",
    ),
    C.FIXTURE_COUNT_EXCEEDS_SPEC: (
        V.FIXTURES,
        RepairHint.USER,
        "{room} has {count} {group} fixtures; its specification allows {limit}.",
    ),
    C.FIXTURE_OVERLAP: (
        V.FIXTURES,
        RepairHint.USER,
        "Fixtures {fixture_a} and {fixture_b} overlap.",
    ),
    C.FIXTURE_CLEARANCE_BLOCKED: (
        V.FIXTURES,
        RepairHint.AUTO,
        "The space needed in front of {fixture} is blocked.",
    ),
    C.FIXTURE_BLOCKS_OPENING: (V.FIXTURES, RepairHint.AUTO, "{fixture} blocks opening {opening}."),
    C.ENTRANCE_MISSING: (
        V.CIRCULATION,
        RepairHint.USER,
        "The plan has no main entrance on an exterior wall.",
    ),
    C.ROOM_UNREACHABLE: (
        V.CIRCULATION,
        RepairHint.USER,
        "{room} cannot be reached from the main entrance.",
    ),
    C.PASSAGE_TOO_NARROW: (
        V.DIMENSIONS,
        RepairHint.USER,
        "{room} is {width_mm} mm wide; at least {min_mm} mm is needed.",
    ),
    C.ROOM_BELOW_MIN_SHORT_SIDE: (
        V.DIMENSIONS,
        RepairHint.USER,
        "{room} is {short_mm} mm across; at least {min_mm} mm is needed.",
    ),
    C.ROOM_BELOW_MIN_AREA: (
        V.DIMENSIONS,
        RepairHint.USER,
        "{room} is {area_mm2} mm²; at least {min_mm2} mm² is needed.",
    ),
    C.HABITABLE_ROOM_NO_WINDOW: (
        V.OPENINGS,
        RepairHint.USER,
        "{room} needs a window on an exterior wall.",
    ),
    C.ROOM_COUNT_MISMATCH: (
        V.REQUIREMENTS,
        RepairHint.USER,
        "The plan has {actual} {room_type} rooms; the requirement asks for {expected}.",
    ),
    C.PARKING_MISSING: (
        V.REQUIREMENTS,
        RepairHint.USER,
        "The requirement asks for parking and the plan has none.",
    ),
    C.PARKING_TOO_SMALL: (
        V.REQUIREMENTS,
        RepairHint.USER,
        "The parking is {clear_w_mm} by {clear_d_mm} mm; "
        "{needed_w_mm} by {needed_d_mm} mm is needed.",
    ),
    C.RELATION_UNMET: (
        V.REQUIREMENTS,
        RepairHint.USER,
        "{room} must be reached from {host} through a {connection}.",
    ),
}


class EntityRef(Frozen):
    kind: EntityKind
    id: str


class ValidationIssue(Frozen):
    code: ValidationCode
    category: ValidationCategory
    severity: ValidationSeverity
    entities: list[EntityRef]
    message_key: str
    params: dict[str, ParamValue]
    message: str
    repair: RepairHint


class ValidationReport(Frozen):
    valid: bool
    schema_version: str | None
    engine_version: str
    ruleset_version: int | None
    ruleset_sha256: str | None
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    checks_run: list[ValidationCode]


def issue(
    code: ValidationCode, entities: Iterable[tuple[EntityKind, str]], **params: ParamValue
) -> ValidationIssue:
    category, repair, template = CATALOGUE[code]
    return ValidationIssue(
        code=code,
        category=category,
        severity=ValidationSeverity.ERROR,
        entities=[EntityRef(kind=k, id=i) for k, i in entities],
        message_key=f"houseplans.validation.{code.value.lower()}",
        params=dict(params),
        message=template.format(**params),
        repair=repair,
    )


@dataclass
class Ctx:
    plan: HousePlan
    ruleset: RulesetContent
    intent: ArchitecturalIntent | None
    an: Analysis

    @property
    def floor(self) -> Floor:
        return self.plan.floors[0]

    def room_name(self, room_id: str) -> str:
        room = next((r for r in self.floor.rooms if r.id == room_id), None)
        return room.name if room else room_id


Check = Callable[[Ctx], list[ValidationIssue]]
CHECKS: list[tuple[tuple[ValidationCode, ...], Check]] = []


def check(*codes: ValidationCode) -> Callable[[Check], Check]:
    def register(fn: Check) -> Check:
        CHECKS.append((codes, fn))
        return fn

    return register


ROOM, WALL, OPENING, FIXTURE, NODE, PLOT = (
    EntityKind.ROOM,
    EntityKind.WALL,
    EntityKind.OPENING,
    EntityKind.FIXTURE,
    EntityKind.NODE,
    EntityKind.PLOT,
)


# ---------- stage 2: references ----------


def _references(plan: HousePlan) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    seen: Counter[str] = Counter()
    for edge in plan.site.plot.edges:
        seen[edge.id] += 1
    for floor in plan.floors:
        seen[floor.id] += 1
        for group in (
            floor.nodes,
            floor.walls,
            floor.rooms,
            floor.openings,
            floor.fixtures,
            floor.stairs,
        ):
            for item in group:
                seen[item.id] += 1
    for ident, n in sorted(seen.items()):
        if n > 1:
            out.append(issue(C.ID_DUPLICATE, [(EntityKind.DOCUMENT, ident)], id=ident))
    edges = {e.id for e in plan.site.plot.edges}
    vertex_count = len(plan.site.plot.vertices)
    for edge in plan.site.plot.edges:
        for field_name in ("start", "end"):
            index = getattr(edge, field_name)
            if index >= vertex_count:
                out.append(
                    issue(
                        C.REF_MISSING,
                        [(PLOT, edge.id)],
                        field=f"plot edge {edge.id}.{field_name}",
                        ref=str(index),
                    )
                )
    if plan.site.entry_edge not in edges:
        out.append(
            issue(
                C.REF_MISSING,
                [(PLOT, plan.site.entry_edge)],
                field="site.entry_edge",
                ref=plan.site.entry_edge,
            )
        )
    for s in plan.site.setbacks:
        if s.edge not in edges:
            out.append(issue(C.REF_MISSING, [(PLOT, s.edge)], field="setback.edge", ref=s.edge))
    for floor in plan.floors:
        nodes, walls, rooms = (
            {n.id for n in floor.nodes},
            {w.id for w in floor.walls},
            {r.id for r in floor.rooms},
        )
        for w in floor.walls:
            for node_ref in (w.a, w.b):
                if node_ref not in nodes:
                    out.append(
                        issue(C.REF_MISSING, [(WALL, w.id)], field=f"wall {w.id}", ref=node_ref)
                    )
        for r in floor.rooms:
            for boundary_node in r.boundary:
                if boundary_node not in nodes:
                    out.append(
                        issue(
                            C.REF_MISSING,
                            [(ROOM, r.id)],
                            field=f"room {r.id} boundary",
                            ref=boundary_node,
                        )
                    )
        for o in floor.openings:
            if o.wall not in walls:
                out.append(
                    issue(
                        C.OPENING_HOST_MISSING,
                        [(OPENING, o.id)],
                        kind=o.kind.value.lower(),
                        ref=o.wall,
                    )
                )
        for f in floor.fixtures:
            if f.room not in rooms:
                out.append(
                    issue(C.FIXTURE_HOST_MISSING, [(FIXTURE, f.id)], field="room", ref=f.room)
                )
            if f.wall not in walls:
                out.append(
                    issue(C.FIXTURE_HOST_MISSING, [(FIXTURE, f.id)], field="wall", ref=f.wall)
                )
    return out


# ---------- stage 3: geometry and the rest ----------


@check(C.PLOT_INVALID, C.GEOMETRY_UNSUPPORTED_V1)
def _plot(ctx: Ctx) -> list[ValidationIssue]:
    site, out = ctx.plan.site, []
    plot = ctx.an.plot
    if plot is None:
        pts = [(v.x, v.y) for v in site.plot.vertices]
        if is_axis_aligned(pts) and signed_area2(pts) > 0:
            return [
                issue(C.GEOMETRY_UNSUPPORTED_V1, [(PLOT, "plot")], supported="rectangular plots")
            ]
        return [
            issue(C.PLOT_INVALID, [(PLOT, "plot")], problem="the boundary is not a valid polygon")
        ]
    expected = {
        SetbackSide.FRONT: ("y", plot.y0),
        SetbackSide.BACK: ("y", plot.y1),
        SetbackSide.LEFT: ("x", plot.x0),
        SetbackSide.RIGHT: ("x", plot.x1),
    }
    sides = Counter(e.side for e in site.plot.edges)
    if any(sides[s] != 1 for s in SetbackSide) or len(site.plot.edges) != 4:
        out.append(
            issue(C.PLOT_INVALID, [(PLOT, "plot")], problem="each side needs exactly one edge")
        )
    for e in site.plot.edges:
        p, q = site.plot.vertices[e.start], site.plot.vertices[e.end]
        axis, value = expected[e.side]
        if getattr(p, axis) != value or getattr(q, axis) != value:
            out.append(
                issue(
                    C.PLOT_INVALID,
                    [(PLOT, e.id)],
                    problem=f"edge {e.id} is not the {e.side.value} side",
                )
            )
    entry = next((e for e in site.plot.edges if e.id == site.entry_edge), None)
    if entry is not None and (entry.side != SetbackSide.FRONT or entry.kind.value != "ROAD"):
        out.append(
            issue(
                C.PLOT_INVALID,
                [(PLOT, entry.id)],
                problem="the entry edge must be the FRONT road edge",
            )
        )
    if ctx.an.envelope is None:
        out.append(
            issue(C.PLOT_INVALID, [(PLOT, "plot")], problem="the setbacks leave no buildable area")
        )
    if len(ctx.plan.floors) > 1 or ctx.floor.stairs:
        out.append(
            issue(
                C.GEOMETRY_UNSUPPORTED_V1,
                [(EntityKind.DOCUMENT, "floors")],
                supported="one floor without stairs",
            )
        )
    return out


@check(C.ROOM_POLYGON_INVALID, C.GEOMETRY_UNSUPPORTED_V1)
def _room_polygons(ctx: Ctx) -> list[ValidationIssue]:
    out = []
    for room in ctx.floor.rooms:
        if ctx.an.room_rects.get(room.id) is not None:
            continue
        pts = [ctx.an.nodes[n] for n in room.boundary]
        if is_axis_aligned(pts) and signed_area2(pts) > 0 and len(set(pts)) == len(pts):
            out.append(
                issue(C.GEOMETRY_UNSUPPORTED_V1, [(ROOM, room.id)], supported="rectangular rooms")
            )
        else:
            out.append(issue(C.ROOM_POLYGON_INVALID, [(ROOM, room.id)], room=room.name))
    return out


@check(
    C.WALL_ZERO_LENGTH,
    C.WALL_NOT_ORTHOGONAL,
    C.WALL_THICKNESS_INVALID,
    C.WALL_OVERLAP,
    C.WALL_DANGLING_END,
)
def _walls(ctx: Ctx) -> list[ValidationIssue]:
    out, rules = [], ctx.ruleset.walls
    walls = list(ctx.an.walls.values())
    degree: Counter[str] = Counter()
    for wall in ctx.floor.walls:
        degree[wall.a] += 1
        degree[wall.b] += 1
    for w in walls:
        if w.a == w.b:
            out.append(issue(C.WALL_ZERO_LENGTH, [(WALL, w.id)], wall=w.id))
        elif not w.orthogonal:
            out.append(issue(C.WALL_NOT_ORTHOGONAL, [(WALL, w.id)], wall=w.id))
        if not rules.min_mm <= w.thickness <= rules.max_mm:
            out.append(
                issue(
                    C.WALL_THICKNESS_INVALID,
                    [(WALL, w.id)],
                    wall=w.id,
                    thickness_mm=w.thickness,
                    min_mm=rules.min_mm,
                    max_mm=rules.max_mm,
                )
            )
    from p2b.houseplans.engine.geom import collinear_overlap

    for w1, w2 in combinations([w for w in walls if w.orthogonal], 2):
        if collinear_overlap(w1.a, w1.b, w2.a, w2.b) > 0:
            out.append(
                issue(C.WALL_OVERLAP, [(WALL, w1.id), (WALL, w2.id)], wall_a=w1.id, wall_b=w2.id)
            )
    for wall in ctx.floor.walls:
        for node_id in (wall.a, wall.b):
            if degree[node_id] == 1:
                out.append(
                    issue(C.WALL_DANGLING_END, [(WALL, wall.id), (NODE, node_id)], wall=wall.id)
                )
    return out


@check(C.ROOM_OVERLAP)
def _room_overlap(ctx: Ctx) -> list[ValidationIssue]:
    rects: list[tuple[Room, Rect]] = []
    for r in ctx.floor.rooms:
        rect = ctx.an.room_rects.get(r.id)
        if rect is not None:
            rects.append((r, rect))
    out = []
    for (ra, a), (rb, b) in combinations(rects, 2):
        area = a.overlap_area(b)
        if area > 0:
            out.append(
                issue(
                    C.ROOM_OVERLAP,
                    [(ROOM, ra.id), (ROOM, rb.id)],
                    room_a=ra.name,
                    room_b=rb.name,
                    overlap_mm2=area,
                )
            )
    return out


def _wall_body(w: WallInfo) -> Rect | None:
    t = half(w.thickness)
    xs = [w.a[0], w.b[0]]
    ys = [w.a[1], w.b[1]]
    if w.direction[1] == 0:
        return rect_or_none(min(xs), min(ys) - t, max(xs), max(ys) + t)
    return rect_or_none(min(xs) - t, min(ys), max(xs) + t, max(ys))


@check(C.ROOM_OUTSIDE_ENVELOPE, C.BUILDING_OUTSIDE_PLOT)
def _containment(ctx: Ctx) -> list[ValidationIssue]:
    plot, envelope = ctx.an.plot, ctx.an.envelope
    out: list[ValidationIssue] = []
    if plot is None:
        return out
    items: list[tuple[EntityKind, str, str, Rect]] = []
    for r in ctx.floor.rooms:
        rect = ctx.an.room_rects.get(r.id)
        if rect is not None:
            items.append((ROOM, r.id, r.name, rect))
    for w in ctx.an.walls.values():
        body = _wall_body(w) if w.orthogonal else None
        if body is not None:
            items.append((WALL, w.id, f"Wall {w.id}", body))
    for kind, ident, label, rect in items:
        if not plot.contains(rect):
            out.append(issue(C.BUILDING_OUTSIDE_PLOT, [(kind, ident)], entity=label))
        elif envelope is not None and not envelope.contains(rect):
            out.append(issue(C.ROOM_OUTSIDE_ENVELOPE, [(kind, ident)], entity=label))
    return out


@check(C.ROOM_EDGE_NOT_ON_WALL)
def _edges_on_walls(ctx: Ctx) -> list[ValidationIssue]:
    pieces = [(w.a, w.b) for w in ctx.an.walls.values() if w.orthogonal]
    out = []
    for r in ctx.floor.rooms:
        rect = ctx.an.room_rects.get(r.id)
        if rect is None or not r.enclosed:
            continue
        corners = rect.corners()
        if not all(segment_covered(corners[i], corners[(i + 1) % 4], pieces) for i in range(4)):
            out.append(issue(C.ROOM_EDGE_NOT_ON_WALL, [(ROOM, r.id)], room=r.name))
    return out


@check(
    C.OPENING_OUTSIDE_HOST,
    C.OPENING_OVERLAP,
    C.OPENING_DIMENSION_INVALID,
    C.WINDOW_ON_INTERIOR_WALL,
)
def _openings(ctx: Ctx) -> list[ValidationIssue]:
    rules, out = ctx.ruleset.openings, []
    clear_height = ctx.floor.clear_height_mm
    infos = sorted(ctx.an.openings.values(), key=lambda i: i.opening.id)
    for info in infos:
        o, w = info.opening, info.wall
        kind = o.kind.value.lower()
        if info.start < rules.jamb_clearance_mm or info.end > w.length - rules.jamb_clearance_mm:
            out.append(
                issue(
                    C.OPENING_OUTSIDE_HOST,
                    [(OPENING, o.id), (WALL, w.id)],
                    kind=kind,
                    start_mm=info.start,
                    end_mm=info.end,
                    length_mm=w.length,
                )
            )
        problems = []
        if (
            o.kind in (OpeningKind.DOOR, OpeningKind.MAIN_ENTRANCE)
            and o.width_mm < rules.min_door_width_mm
        ):
            problems.append(f"width {o.width_mm} mm is below {rules.min_door_width_mm} mm")
        if o.kind == OpeningKind.WINDOW and o.width_mm < rules.min_window_width_mm:
            problems.append(f"width {o.width_mm} mm is below {rules.min_window_width_mm} mm")
        if o.sill_mm + o.height_mm > clear_height:
            problems.append(
                f"top at {o.sill_mm + o.height_mm} mm is above the {clear_height} mm ceiling"
            )
        if problems:
            out.append(
                issue(
                    C.OPENING_DIMENSION_INVALID,
                    [(OPENING, o.id)],
                    kind=kind,
                    problem="; ".join(problems),
                )
            )
        if o.kind == OpeningKind.WINDOW and w.kind == WallKind.INTERIOR:
            out.append(issue(C.WINDOW_ON_INTERIOR_WALL, [(OPENING, o.id), (WALL, w.id)], wall=w.id))
    for a, b in combinations(infos, 2):
        if a.wall.id == b.wall.id and min(a.end, b.end) > max(a.start, b.start):
            out.append(
                issue(
                    C.OPENING_OVERLAP,
                    [(OPENING, a.opening.id), (OPENING, b.opening.id)],
                    opening_a=a.opening.id,
                    opening_b=b.opening.id,
                )
            )
    return out


@check(
    C.FIXTURE_NOT_ON_ROOM_WALL,
    C.FIXTURE_OUTSIDE_ROOM,
    C.FIXTURE_NOT_PERMITTED_IN_ROOM,
    C.FIXTURE_COUNT_EXCEEDS_SPEC,
    C.FIXTURE_OVERLAP,
    C.FIXTURE_CLEARANCE_BLOCKED,
    C.FIXTURE_BLOCKS_OPENING,
)
def _fixtures(ctx: Ctx) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    rooms = {r.id: r for r in ctx.floor.rooms}
    infos = sorted(ctx.an.fixtures.values(), key=lambda i: i.fixture.id)
    placed: list[tuple[FixtureInfo, Rect]] = []
    for info in infos:
        f = info.fixture
        room = rooms[f.room]
        rule = ctx.ruleset.fixtures.get(f.type)
        if rule is None or room.type not in rule.permitted_rooms:
            out.append(
                issue(
                    C.FIXTURE_NOT_PERMITTED_IN_ROOM,
                    [(FIXTURE, f.id), (ROOM, room.id)],
                    fixture_type=f.type.value,
                    room_type=room.type.value,
                )
            )
        wall = info.wall
        if wall is None or room.id not in wall.rooms_on(f.side):
            out.append(
                issue(
                    C.FIXTURE_NOT_ON_ROOM_WALL,
                    [(FIXTURE, f.id), (ROOM, room.id)],
                    fixture_type=f.type.value,
                    room=room.name,
                )
            )
            continue
        clear = ctx.an.clear_rects.get(room.id)
        if info.footprint is None or clear is None or not clear.contains(info.footprint):
            out.append(
                issue(
                    C.FIXTURE_OUTSIDE_ROOM,
                    [(FIXTURE, f.id), (ROOM, room.id)],
                    fixture_type=f.type.value,
                    room=room.name,
                )
            )
            continue
        if info.clearance is not None and not clear.contains(info.clearance):
            out.append(issue(C.FIXTURE_CLEARANCE_BLOCKED, [(FIXTURE, f.id)], fixture=f.id))
        placed.append((info, info.footprint))
    for (a, a_fp), (b, b_fp) in combinations(placed, 2):
        if a_fp.overlap_area(b_fp) > 0:
            out.append(
                issue(
                    C.FIXTURE_OVERLAP,
                    [(FIXTURE, a.fixture.id), (FIXTURE, b.fixture.id)],
                    fixture_a=a.fixture.id,
                    fixture_b=b.fixture.id,
                )
            )
            continue
        for x, y, y_fp in ((a, b, b_fp), (b, a, a_fp)):
            if x.clearance is not None and x.clearance.overlap_area(y_fp) > 0:
                out.append(
                    issue(
                        C.FIXTURE_CLEARANCE_BLOCKED,
                        [(FIXTURE, x.fixture.id), (FIXTURE, y.fixture.id)],
                        fixture=x.fixture.id,
                    )
                )
    for info, footprint in placed:
        for o in sorted(ctx.an.openings.values(), key=lambda i: i.opening.id):
            if any(footprint.overlap_area(z) > 0 for z in o.zones):
                out.append(
                    issue(
                        C.FIXTURE_BLOCKS_OPENING,
                        [(FIXTURE, info.fixture.id), (OPENING, o.opening.id)],
                        fixture=info.fixture.id,
                        opening=o.opening.id,
                    )
                )
    # Counts per room and group: at most the template's allowance (1 if the template is silent).
    groups: dict[tuple[str, str], list[str]] = {}
    for info in infos:
        rule = ctx.ruleset.fixtures.get(info.fixture.type)
        if rule is not None:
            groups.setdefault((info.fixture.room, rule.count_group), []).append(info.fixture.id)
    for (room_id, group), ids in sorted(groups.items()):
        room = rooms[room_id]
        allowance = [
            t.max_count
            for t in ctx.ruleset.templates.get(room.type, [])
            if ctx.ruleset.fixtures[t.fixture].count_group == group
        ]
        limit = sum(allowance) if allowance else 1
        if len(ids) > limit:
            # Template fixtures count first, so the ones beyond the allowance are the additions.
            origin = {i.fixture.id: i.fixture.origin.kind.value for i in infos}
            extra = sorted(ids, key=lambda i: (origin[i] != "RULESET", i))[limit:]
            out.append(
                issue(
                    C.FIXTURE_COUNT_EXCEEDS_SPEC,
                    [(ROOM, room_id), *[(FIXTURE, i) for i in extra]],
                    room=room.name,
                    count=len(ids),
                    group=group,
                    limit=limit,
                )
            )
    return out


@check(C.ENTRANCE_MISSING, C.ROOM_UNREACHABLE)
def _circulation(ctx: Ctx) -> list[ValidationIssue]:
    out = []
    links: dict[str, set[str]] = {}
    starts: list[str] = []
    for info in sorted(ctx.an.openings.values(), key=lambda i: i.opening.id):
        if info.opening.kind == OpeningKind.WINDOW:
            continue
        a, b = info.connects
        if info.opening.kind == OpeningKind.MAIN_ENTRANCE:
            if info.wall.kind == WallKind.EXTERIOR and EXTERIOR in (a, b) and {a, b} != {EXTERIOR}:
                starts.append(b if a == EXTERIOR else a)
            continue
        if EXTERIOR not in (a, b):
            links.setdefault(a, set()).add(b)
            links.setdefault(b, set()).add(a)
    if not starts:
        out.append(issue(C.ENTRANCE_MISSING, [(EntityKind.DOCUMENT, "entrance")]))
    reached, queue = set(starts), deque(starts)
    while queue:
        for nxt in sorted(links.get(queue.popleft(), ())):
            if nxt not in reached:
                reached.add(nxt)
                queue.append(nxt)
    for r in ctx.floor.rooms:
        if r.enclosed and r.id not in reached:
            out.append(issue(C.ROOM_UNREACHABLE, [(ROOM, r.id)], room=r.name))
    return out


@check(
    C.ROOM_BELOW_MIN_SHORT_SIDE,
    C.ROOM_BELOW_MIN_AREA,
    C.PASSAGE_TOO_NARROW,
    C.HABITABLE_ROOM_NO_WINDOW,
)
def _dimensions(ctx: Ctx) -> list[ValidationIssue]:
    out = []
    windows: dict[str, int] = Counter()
    for info in ctx.an.openings.values():
        if info.opening.kind == OpeningKind.WINDOW and info.wall.kind == WallKind.EXTERIOR:
            for room in info.wall.left_rooms + info.wall.right_rooms:
                windows[room] += 1
    for r in ctx.floor.rooms:
        clear = ctx.an.clear_rects.get(r.id)
        rule = ctx.ruleset.rooms.get(r.type)
        if clear is None or rule is None:
            continue
        if r.type == ctx.ruleset.zoning.circulation_room:
            if clear.short_side < ctx.ruleset.passage_min_width_mm:
                out.append(
                    issue(
                        C.PASSAGE_TOO_NARROW,
                        [(ROOM, r.id)],
                        room=r.name,
                        width_mm=clear.short_side,
                        min_mm=ctx.ruleset.passage_min_width_mm,
                    )
                )
        elif r.type != RoomType.PARKING:
            if clear.short_side < rule.min_short_mm:
                out.append(
                    issue(
                        C.ROOM_BELOW_MIN_SHORT_SIDE,
                        [(ROOM, r.id)],
                        room=r.name,
                        short_mm=clear.short_side,
                        min_mm=rule.min_short_mm,
                    )
                )
            if clear.area < rule.min_area_mm2:
                out.append(
                    issue(
                        C.ROOM_BELOW_MIN_AREA,
                        [(ROOM, r.id)],
                        room=r.name,
                        area_mm2=clear.area,
                        min_mm2=rule.min_area_mm2,
                    )
                )
        if rule.needs_window and windows[r.id] == 0:
            out.append(issue(C.HABITABLE_ROOM_NO_WINDOW, [(ROOM, r.id)], room=r.name))
    return out


@check(C.ROOM_COUNT_MISMATCH, C.PARKING_MISSING, C.PARKING_TOO_SMALL, C.RELATION_UNMET)
def _requirements(ctx: Ctx) -> list[ValidationIssue]:
    out: list[ValidationIssue] = []
    rooms = {r.id: r for r in ctx.floor.rooms}
    parking_rooms = [r for r in ctx.floor.rooms if r.type == RoomType.PARKING]
    spec = ctx.plan.site.parking
    if spec is not None:
        for r in parking_rooms:
            clear = ctx.an.clear_rects.get(r.id)
            need_w, need_d = spec.spaces * spec.space_w_mm, spec.space_d_mm
            if clear is None or not (
                (clear.w >= need_w and clear.h >= need_d)
                or (clear.h >= need_w and clear.w >= need_d)
            ):
                out.append(
                    issue(
                        C.PARKING_TOO_SMALL,
                        [(ROOM, r.id)],
                        clear_w_mm=clear.w if clear else 0,
                        clear_d_mm=clear.h if clear else 0,
                        needed_w_mm=need_w,
                        needed_d_mm=need_d,
                    )
                )
    intent = ctx.intent
    if intent is None:
        return out
    if intent.parking is not None and (not parking_rooms or spec is None):
        out.append(issue(C.PARKING_MISSING, [(EntityKind.DOCUMENT, "parking")]))
    # the requirement plus the room changes the owner made while editing (Checkpoint 3.1)
    expected = expected_counts(Counter(p.room_type for p in intent.programme), ctx.plan.compromises)
    removed = removed_rooms(ctx.plan.compromises)
    actual = Counter(r.type for r in ctx.floor.rooms if r.origin.kind.value != "SOLVER")
    for room_type in sorted(set(expected) | set(actual)):
        if expected[room_type] != actual[room_type]:
            ids = [r.id for r in ctx.floor.rooms if r.type == room_type]
            targets = [(ROOM, i) for i in ids] or [
                (EntityKind.DOCUMENT, f"programme.{room_type.value}")
            ]
            out.append(
                issue(
                    C.ROOM_COUNT_MISMATCH,
                    targets,
                    room_type=room_type.value,
                    expected=expected[room_type],
                    actual=actual[room_type],
                )
            )
    for rel in intent.relations:
        if rel.strength != ConstraintStrength.HARD or {rel.room, rel.host} & removed:
            continue
        wanted = (
            {OpeningKind.DOOR}
            if rel.kind == RelationKind.ADJACENT_WITH_DOOR
            else {OpeningKind.VOID, OpeningKind.DOOR}
        )
        met = any(
            info.opening.kind in wanted and set(info.connects) == {rel.room, rel.host}
            for info in ctx.an.openings.values()
        )
        if not met:
            connection = (
                "door" if rel.kind == RelationKind.ADJACENT_WITH_DOOR else "open connection"
            )
            out.append(
                issue(
                    C.RELATION_UNMET,
                    [(ROOM, rel.room), (ROOM, rel.host)],
                    room=rooms[rel.room].name if rel.room in rooms else rel.room,
                    host=rooms[rel.host].name if rel.host in rooms else rel.host,
                    connection=connection,
                )
            )
    return out


# ---------- entry point ----------

CATEGORY_ORDER = {c: i for i, c in enumerate(ValidationCategory)}


def _report(
    errors: list[ValidationIssue],
    ran: Iterable[ValidationCode],
    *,
    version: str | None,
    ruleset_version: int | None,
    ruleset_sha256: str | None,
) -> ValidationReport:
    errors = sorted(
        errors,
        key=lambda i: (
            CATEGORY_ORDER[i.category],
            i.code.value,
            [(e.kind.value, e.id) for e in i.entities],
            i.message,
        ),
    )
    return ValidationReport(
        valid=not errors,
        schema_version=version,
        engine_version=ENGINE_VERSION,
        ruleset_version=ruleset_version,
        ruleset_sha256=ruleset_sha256,
        errors=errors,
        warnings=[],
        checks_run=sorted(set(ran), key=lambda c: c.value),
    )


def validate(
    document: Mapping[str, Any] | HousePlan,
    ruleset: RulesetContent,
    *,
    intent: ArchitecturalIntent | None = None,
    ruleset_version: int | None = None,
    ruleset_sha256: str | None = None,
) -> ValidationReport:
    schema_codes = (C.SCHEMA_INVALID, C.SCHEMA_VERSION_UNSUPPORTED)
    if isinstance(document, HousePlan):
        plan = document
    else:
        version = schema_version_of(document)
        if version is not None and not is_supported(version):
            return _report(
                [
                    issue(
                        C.SCHEMA_VERSION_UNSUPPORTED,
                        [(EntityKind.DOCUMENT, "meta")],
                        version=version,
                    )
                ],
                schema_codes,
                version=version,
                ruleset_version=ruleset_version,
                ruleset_sha256=ruleset_sha256,
            )
        try:
            plan = HousePlan.model_validate(document)
        except ValidationError as exc:
            errors = [
                issue(
                    C.SCHEMA_INVALID,
                    [(EntityKind.DOCUMENT, "/".join(str(p) for p in e["loc"]) or "/")],
                    loc="/".join(str(p) for p in e["loc"]) or "/",
                    problem=e["msg"],
                )
                for e in exc.errors()[:25]
            ]
            return _report(
                errors,
                schema_codes,
                version=version,
                ruleset_version=ruleset_version,
                ruleset_sha256=ruleset_sha256,
            )
    version = plan.meta.schema_version
    if not is_supported(version):
        return _report(
            [issue(C.SCHEMA_VERSION_UNSUPPORTED, [(EntityKind.DOCUMENT, "meta")], version=version)],
            schema_codes,
            version=version,
            ruleset_version=ruleset_version,
            ruleset_sha256=ruleset_sha256,
        )
    ref_codes = (C.ID_DUPLICATE, C.REF_MISSING, C.OPENING_HOST_MISSING, C.FIXTURE_HOST_MISSING)
    errors = _references(plan)
    if errors:
        return _report(
            errors,
            schema_codes + ref_codes,
            version=version,
            ruleset_version=ruleset_version,
            ruleset_sha256=ruleset_sha256,
        )
    ctx = Ctx(plan=plan, ruleset=ruleset, intent=intent, an=with_clearances(analyse(plan), ruleset))
    ran = list(schema_codes + ref_codes)
    for codes, fn in CHECKS:
        errors.extend(fn(ctx))
        ran.extend(codes)
    return _report(
        errors, ran, version=version, ruleset_version=ruleset_version, ruleset_sha256=ruleset_sha256
    )
