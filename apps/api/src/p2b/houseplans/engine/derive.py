"""Derived geometry. One definition of where everything is, computed from a HousePlan:

- `analyse` gives the exact integer facts the validator and the generator's fixture placement
  rely on (room rectangles, clear rectangles, wall sides, opening intervals and zones, fixture
  footprints and clearances). It never raises on bad geometry: what cannot be derived is None.
- `plan_geometry` gives PlanGeometry, the only geometry a renderer, PDF or 3D view consumes.

Nothing here is stored as truth; it is recomputed from the document on every read."""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict

from p2b.core.vocabulary import (
    FixtureType,
    OpeningKind,
    RoomType,
    SetbackSide,
    WallKind,
    WallSide,
    Zone,
)
from p2b.houseplans.engine.geom import Pt, Rect, as_rect, collinear_overlap, rect_or_none
from p2b.houseplans.engine.model import Fixture, Floor, HousePlan, Opening
from p2b.houseplans.engine.ruleset import RulesetContent

EXTERIOR = "EXTERIOR"


def half(t: int) -> int:
    """Half a wall's thickness, rounded up, so faces stay on whole millimetres."""
    return (t + 1) // 2


# ---------- analysis (integer facts) ----------


@dataclass(frozen=True)
class WallInfo:
    id: str
    a: Pt
    b: Pt
    kind: WallKind
    thickness: int
    length: int
    direction: Pt  # unit step from a to b; (0, 0) for a zero-length or diagonal wall
    left_rooms: tuple[str, ...]
    right_rooms: tuple[str, ...]

    @property
    def orthogonal(self) -> bool:
        return self.direction != (0, 0)

    def normal(self, side: WallSide) -> Pt:
        dx, dy = self.direction
        return (-dy, dx) if side == WallSide.LEFT else (dy, -dx)

    def local_rect(self, s0: int, s1: int, side: WallSide, d0: int, d1: int) -> Rect | None:
        """The rectangle spanning [s0, s1] along the wall from a, and [d0, d1] away from the
        centreline toward `side`."""
        (dx, dy), (nx, ny) = self.direction, self.normal(side)
        xs = [self.a[0] + dx * s + nx * d for s in (s0, s1) for d in (d0, d1)]
        ys = [self.a[1] + dy * s + ny * d for s in (s0, s1) for d in (d0, d1)]
        return rect_or_none(min(xs), min(ys), max(xs), max(ys))

    def rooms_on(self, side: WallSide) -> tuple[str, ...]:
        return self.left_rooms if side == WallSide.LEFT else self.right_rooms


@dataclass(frozen=True)
class OpeningInfo:
    opening: Opening
    wall: WallInfo
    start: int
    end: int
    zones: tuple[Rect, ...]  # floor area kept clear in front of the opening, per side
    connects: tuple[str, str]  # room ids or EXTERIOR, left side first


@dataclass(frozen=True)
class FixtureInfo:
    fixture: Fixture
    wall: WallInfo | None
    footprint: Rect | None
    clearance: Rect | None


@dataclass
class Analysis:
    plot: Rect | None
    envelope: Rect | None
    nodes: dict[str, Pt]
    walls: dict[str, WallInfo]
    room_rects: dict[str, Rect | None]
    clear_rects: dict[str, Rect | None]
    openings: dict[str, OpeningInfo] = field(default_factory=dict)
    fixtures: dict[str, FixtureInfo] = field(default_factory=dict)


def plot_and_envelope(plan: HousePlan) -> tuple[Rect | None, Rect | None]:
    plot = as_rect([(v.x, v.y) for v in plan.site.plot.vertices])
    if plot is None:
        return None, None
    side_of = {e.id: e.side for e in plan.site.plot.edges}
    setback = {side_of[s.edge]: s.distance_mm for s in plan.site.setbacks if s.edge in side_of}
    envelope = plot.inset(
        setback.get(SetbackSide.LEFT, 0),
        setback.get(SetbackSide.FRONT, 0),
        setback.get(SetbackSide.RIGHT, 0),
        setback.get(SetbackSide.BACK, 0),
    )
    return plot, envelope


def _direction(a: Pt, b: Pt) -> Pt:
    if a == b or (a[0] != b[0] and a[1] != b[1]):
        return (0, 0)
    return ((b[0] > a[0]) - (b[0] < a[0]), (b[1] > a[1]) - (b[1] < a[1]))


def _room_side(rect: Rect, a: Pt, b: Pt) -> WallSide | None:
    """The side of segment a→b the room lies on, if the segment runs along the room's edge."""
    edges = {
        "bottom": ((rect.x0, rect.y0), (rect.x1, rect.y0)),
        "top": ((rect.x0, rect.y1), (rect.x1, rect.y1)),
        "left": ((rect.x0, rect.y0), (rect.x0, rect.y1)),
        "right": ((rect.x1, rect.y0), (rect.x1, rect.y1)),
    }
    for name, (p, q) in edges.items():
        if collinear_overlap(a, b, p, q) > 0:
            inward = {"bottom": (0, 1), "top": (0, -1), "left": (1, 0), "right": (-1, 0)}[name]
            dx, dy = _direction(a, b)
            left = (-dy, dx)
            return WallSide.LEFT if left == inward else WallSide.RIGHT
    return None


def analyse(plan: HousePlan, floor_index: int = 0) -> Analysis:
    floor = plan.floors[floor_index]
    plot, envelope = plot_and_envelope(plan)
    nodes = {n.id: (n.x, n.y) for n in floor.nodes}
    room_rects = {
        r.id: as_rect([nodes[n] for n in r.boundary if n in nodes])
        if all(n in nodes for n in r.boundary)
        else None
        for r in floor.rooms
    }

    walls: dict[str, WallInfo] = {}
    for w in floor.walls:
        if w.a not in nodes or w.b not in nodes:
            continue
        a, b = nodes[w.a], nodes[w.b]
        left: list[str] = []
        right: list[str] = []
        for room_id, rect in room_rects.items():
            if rect is None:
                continue
            side = _room_side(rect, a, b)
            if side == WallSide.LEFT:
                left.append(room_id)
            elif side == WallSide.RIGHT:
                right.append(room_id)
        walls[w.id] = WallInfo(
            id=w.id,
            a=a,
            b=b,
            kind=w.kind,
            thickness=w.thickness_mm,
            length=abs(b[0] - a[0]) + abs(b[1] - a[1]),
            direction=_direction(a, b),
            left_rooms=tuple(left),
            right_rooms=tuple(right),
        )

    clear_rects: dict[str, Rect | None] = {}
    for room_id, rect in room_rects.items():
        if rect is None:
            clear_rects[room_id] = None
            continue
        insets = []
        for p, q in (
            ((rect.x0, rect.y0), (rect.x0, rect.y1)),
            ((rect.x0, rect.y0), (rect.x1, rect.y0)),
            ((rect.x1, rect.y0), (rect.x1, rect.y1)),
            ((rect.x0, rect.y1), (rect.x1, rect.y1)),
        ):
            on_edge = [
                w.thickness
                for w in walls.values()
                if w.orthogonal and collinear_overlap(w.a, w.b, p, q) > 0
            ]
            insets.append(half(max(on_edge)) if on_edge else 0)
        clear_rects[room_id] = rect.inset(*insets)  # left, bottom, right, top

    analysis = Analysis(
        plot=plot,
        envelope=envelope,
        nodes=nodes,
        walls=walls,
        room_rects=room_rects,
        clear_rects=clear_rects,
    )
    for o in floor.openings:
        info = opening_info(o, walls.get(o.wall))
        if info is not None:
            analysis.openings[o.id] = info
    for f in floor.fixtures:
        analysis.fixtures[f.id] = fixture_info(f, walls.get(f.wall), None)
    return analysis


def opening_info(o: Opening, wall: WallInfo | None) -> OpeningInfo | None:
    if wall is None or not wall.orthogonal:
        return None
    start, end = o.offset_mm, o.offset_mm + o.width_mm
    face = half(wall.thickness)
    zone_sides: list[WallSide] = []
    if o.kind in (OpeningKind.DOOR, OpeningKind.MAIN_ENTRANCE) and o.door is not None:
        zone_sides = [o.door.opens_to]
    elif o.kind == OpeningKind.VOID:
        zone_sides = [WallSide.LEFT, WallSide.RIGHT]
    zones = tuple(
        z
        for side in zone_sides
        if (z := wall.local_rect(start, end, side, face, face + o.width_mm)) is not None
    )
    left = wall.left_rooms[0] if wall.left_rooms else EXTERIOR
    right = wall.right_rooms[0] if wall.right_rooms else EXTERIOR
    return OpeningInfo(o, wall, start, end, zones, (left, right))


def fixture_info(f: Fixture, wall: WallInfo | None, clear_front_mm: int | None) -> FixtureInfo:
    if wall is None or not wall.orthogonal:
        return FixtureInfo(f, wall, None, None)
    face = half(wall.thickness)
    footprint = wall.local_rect(f.offset_mm, f.offset_mm + f.w_mm, f.side, face, face + f.d_mm)
    clearance = None
    if clear_front_mm:
        clearance = wall.local_rect(
            f.offset_mm, f.offset_mm + f.w_mm, f.side, face + f.d_mm, face + f.d_mm + clear_front_mm
        )
    return FixtureInfo(f, wall, footprint, clearance)


def with_clearances(analysis: Analysis, ruleset: RulesetContent) -> Analysis:
    for fid, info in list(analysis.fixtures.items()):
        rule = ruleset.fixtures.get(info.fixture.type)
        analysis.fixtures[fid] = fixture_info(
            info.fixture, info.wall, rule.clear_front_mm if rule else None
        )
    return analysis


# ---------- PlanGeometry (the renderer's input) ----------


class _G(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GPoint(_G):
    x: int
    y: int


Polygon = list[GPoint]


class WallPiece(_G):
    s0_mm: int  # along the wall from node a (negative: the corner extension)
    s1_mm: int
    z0_mm: int  # above the floor's finished level
    z1_mm: int


class RoomGeom(_G):
    id: str
    type: RoomType
    name: str
    zone: Zone
    polygon: Polygon
    clear_polygon: Polygon | None
    clear_w_mm: int | None
    clear_d_mm: int | None
    carpet_area_mm2: int | None
    label_at: GPoint | None


class WallGeom(_G):
    id: str
    kind: WallKind
    a: GPoint
    b: GPoint
    thickness_mm: int
    length_mm: int
    outline: list[Polygon]  # solid parts in plan, openings cut out
    pieces: list[WallPiece]  # solid, sill and lintel pieces, for the 3D view


class Swing(_G):
    hinge: GPoint
    radius_mm: int
    start_deg: int
    end_deg: int


class OpeningGeom(_G):
    id: str
    kind: OpeningKind
    wall: str
    jamb_a: GPoint
    jamb_b: GPoint
    swing: Swing | None
    connects: list[str]


class FixtureGeom(_G):
    id: str
    type: FixtureType
    room: str
    footprint: Polygon | None
    clearance: Polygon | None


class DimensionChain(_G):
    id: str
    kind: Literal["PLOT", "ENVELOPE", "ROOM_CLEAR"]
    start: GPoint
    end: GPoint
    value_mm: int


OpenAreaKind = Literal["FORECOURT", "SIDE_YARD", "REAR_YARD", "COURT"]


class OpenArea(_G):
    """Unbuilt space inside the buildable area (geometry 1.1.0, Checkpoint 3): a presentation
    label for the 2D view, never a room and never stored. `cells` are rectangles that together
    make the area; `kind` says where it lies (see `open_areas`)."""

    id: str
    kind: OpenAreaKind
    cells: list[Polygon]
    area_mm2: int
    label_at: GPoint


class FloorGeometry(_G):
    level: int
    rooms: list[RoomGeom]
    walls: list[WallGeom]
    openings: list[OpeningGeom]
    fixtures: list[FixtureGeom]
    dimensions: list[DimensionChain]
    open_areas: list[OpenArea] = []


class BBox(_G):
    min_x: int
    min_y: int
    max_x: int
    max_y: int


class PlanGeometry(_G):
    # 1.1.0 (Checkpoint 3): floors carry `open_areas`. Derived on read, never stored, so the
    # version names the shape the web app receives, nothing else.
    geometry_version: Literal["1.1.0"] = "1.1.0"
    units: Literal["mm"] = "mm"
    bounds: BBox
    plot: Polygon
    envelope: Polygon | None
    floors: list[FloorGeometry]


def _poly(rect: Rect | None) -> Polygon | None:
    return [GPoint(x=x, y=y) for x, y in rect.corners()] if rect is not None else None


def _gp(p: Pt) -> GPoint:
    return GPoint(x=p[0], y=p[1])


def _subtract(lo: int, hi: int, cuts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out, cursor = [], lo
    for c0, c1 in sorted(cuts):
        if c0 > cursor:
            out.append((cursor, min(c0, hi)))
        cursor = max(cursor, c1)
    if cursor < hi:
        out.append((cursor, hi))
    return [(a, b) for a, b in out if b > a]


def _wall_geom(
    w: WallInfo, openings: list[OpeningInfo], all_walls: list[WallInfo], height: int
) -> WallGeom:
    def extension(p: Pt) -> int:
        meets = [
            o.thickness
            for o in all_walls
            if o.id != w.id
            and o.orthogonal
            and p in (o.a, o.b)
            and o.direction[0] != w.direction[0]
        ]
        return half(max(meets)) if meets else 0

    e_a, e_b = extension(w.a), extension(w.b)
    cuts = [(o.start, o.end) for o in openings]
    t = half(w.thickness)
    solid = _subtract(-e_a, w.length + e_b, cuts)
    outline = [
        p for s0, s1 in solid if (p := _poly(rect_or_none(*_span_rect(w, s0, s1, t)))) is not None
    ]
    pieces = [WallPiece(s0_mm=s0, s1_mm=s1, z0_mm=0, z1_mm=height) for s0, s1 in solid]
    for o in openings:
        op = o.opening
        if op.kind == OpeningKind.WINDOW and op.sill_mm > 0:
            pieces.append(WallPiece(s0_mm=o.start, s1_mm=o.end, z0_mm=0, z1_mm=op.sill_mm))
        head = op.sill_mm + op.height_mm
        if head < height:
            pieces.append(WallPiece(s0_mm=o.start, s1_mm=o.end, z0_mm=head, z1_mm=height))
    return WallGeom(
        id=w.id,
        kind=w.kind,
        a=_gp(w.a),
        b=_gp(w.b),
        thickness_mm=w.thickness,
        length_mm=w.length,
        outline=outline,
        pieces=pieces,
    )


def _span_rect(w: WallInfo, s0: int, s1: int, t: int) -> tuple[int, int, int, int]:
    dx, dy = w.direction
    xs = [w.a[0] + dx * s + dy * d for s in (s0, s1) for d in (-t, t)]
    ys = [w.a[1] + dy * s + dx * d for s in (s0, s1) for d in (-t, t)]
    return min(xs), min(ys), max(xs), max(ys)


def _swing(info: OpeningInfo) -> Swing | None:
    op = info.opening
    if op.door is None:
        return None
    w = info.wall
    theta = {(1, 0): 0, (0, 1): 90, (-1, 0): 180, (0, -1): 270}[w.direction]
    dx, dy = w.direction
    hinge_at_a = op.door.hinge.value == "A_SIDE"
    s = info.start if hinge_at_a else info.end
    hinge = (w.a[0] + dx * s, w.a[1] + dy * s)
    closed = theta if hinge_at_a else theta + 180
    turn = 90 if (op.door.opens_to == WallSide.LEFT) == hinge_at_a else -90
    return Swing(
        hinge=_gp(hinge),
        radius_mm=op.width_mm,
        start_deg=closed % 360,
        end_deg=(closed + turn) % 360,
    )


def plan_geometry(plan: HousePlan, ruleset: RulesetContent) -> PlanGeometry:
    floors: list[FloorGeometry] = []
    plot, envelope = plot_and_envelope(plan)
    all_points: list[Pt] = [(v.x, v.y) for v in plan.site.plot.vertices]
    for index, floor in enumerate(plan.floors):
        analysis = with_clearances(analyse(plan, index), ruleset)
        geometry = _floor_geometry(floor, analysis)
        if envelope is not None and (
            region := envelope.inset(*(half(ruleset.walls.exterior_mm),) * 4)
        ):
            rooms = [
                [analysis.nodes[n] for n in r.boundary if n in analysis.nodes] for r in floor.rooms
            ]
            geometry = geometry.model_copy(update={"open_areas": open_areas(region, rooms)})
        floors.append(geometry)
        all_points.extend(analysis.nodes.values())
    xs, ys = [p[0] for p in all_points], [p[1] for p in all_points]
    dims: list[DimensionChain] = []
    if plot is not None:
        dims += [
            DimensionChain(
                id="plot_width",
                kind="PLOT",
                start=_gp((plot.x0, plot.y0)),
                end=_gp((plot.x1, plot.y0)),
                value_mm=plot.w,
            ),
            DimensionChain(
                id="plot_depth",
                kind="PLOT",
                start=_gp((plot.x0, plot.y0)),
                end=_gp((plot.x0, plot.y1)),
                value_mm=plot.h,
            ),
        ]
    if envelope is not None:
        dims += [
            DimensionChain(
                id="envelope_width",
                kind="ENVELOPE",
                start=_gp((envelope.x0, envelope.y0)),
                end=_gp((envelope.x1, envelope.y0)),
                value_mm=envelope.w,
            ),
            DimensionChain(
                id="envelope_depth",
                kind="ENVELOPE",
                start=_gp((envelope.x0, envelope.y0)),
                end=_gp((envelope.x0, envelope.y1)),
                value_mm=envelope.h,
            ),
        ]
    if floors:
        floors[0] = floors[0].model_copy(update={"dimensions": dims + floors[0].dimensions})
    return PlanGeometry(
        bounds=BBox(min_x=min(xs), min_y=min(ys), max_x=max(xs), max_y=max(ys)),
        plot=[GPoint(x=v.x, y=v.y) for v in plan.site.plot.vertices],
        envelope=_poly(envelope),
        floors=floors,
    )


def _floor_geometry(floor: Floor, analysis: Analysis) -> FloorGeometry:
    rooms: list[RoomGeom] = []
    dims: list[DimensionChain] = []
    for room in floor.rooms:
        rect, clear = analysis.room_rects.get(room.id), analysis.clear_rects.get(room.id)
        polygon = [_gp(analysis.nodes[n]) for n in room.boundary if n in analysis.nodes]
        rooms.append(
            RoomGeom(
                id=room.id,
                type=room.type,
                name=room.name,
                zone=room.zone,
                polygon=polygon,
                clear_polygon=_poly(clear),
                clear_w_mm=clear.w if clear else None,
                clear_d_mm=clear.h if clear else None,
                carpet_area_mm2=clear.area if clear else None,
                label_at=_gp((rect.centre2[0] // 2, rect.centre2[1] // 2)) if rect else None,
            )
        )
        if clear is not None:
            dims.append(
                DimensionChain(
                    id=f"{room.id}_clear_w",
                    kind="ROOM_CLEAR",
                    start=_gp((clear.x0, clear.y0)),
                    end=_gp((clear.x1, clear.y0)),
                    value_mm=clear.w,
                )
            )
            dims.append(
                DimensionChain(
                    id=f"{room.id}_clear_d",
                    kind="ROOM_CLEAR",
                    start=_gp((clear.x0, clear.y0)),
                    end=_gp((clear.x0, clear.y1)),
                    value_mm=clear.h,
                )
            )
    walls = list(analysis.walls.values())
    by_wall: dict[str, list[OpeningInfo]] = {}
    for info in analysis.openings.values():
        by_wall.setdefault(info.wall.id, []).append(info)
    wall_geoms = [
        _wall_geom(w, by_wall.get(w.id, []), walls, floor.floor_to_floor_mm)
        for w in walls
        if w.orthogonal
    ]
    openings = []
    for info in analysis.openings.values():
        dx, dy = info.wall.direction
        a = info.wall.a
        openings.append(
            OpeningGeom(
                id=info.opening.id,
                kind=info.opening.kind,
                wall=info.wall.id,
                jamb_a=_gp((a[0] + dx * info.start, a[1] + dy * info.start)),
                jamb_b=_gp((a[0] + dx * info.end, a[1] + dy * info.end)),
                swing=_swing(info),
                connects=list(info.connects),
            )
        )
    fixtures = [
        FixtureGeom(
            id=f.fixture.id,
            type=f.fixture.type,
            room=f.fixture.room,
            footprint=_poly(f.footprint),
            clearance=_poly(f.clearance),
        )
        for f in analysis.fixtures.values()
    ]
    return FloorGeometry(
        level=floor.level,
        rooms=rooms,
        walls=wall_geoms,
        openings=openings,
        fixtures=fixtures,
        dimensions=dims,
    )


# ---------- open areas (geometry 1.1.0) ----------


def _inside(point2: Pt, polygon: list[Pt]) -> bool:
    """Even-odd test of a doubled-coordinate point against a polygon (no point lies on an edge:
    the points tested are cell centres between distinct coordinates)."""
    x, y = point2
    inside = False
    for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1], strict=True):
        a0, b0, a1, b1 = 2 * x0, 2 * y0, 2 * x1, 2 * y1
        if (b0 > y) == (b1 > y):
            continue
        # does the edge cross the ray from the point towards +x? exact, in integers:
        # x < a0 + (y - b0)(a1 - a0)/(b1 - b0)
        lhs, rhs = (x - a0) * (b1 - b0), (y - b0) * (a1 - a0)
        if (lhs < rhs) if b1 > b0 else (lhs > rhs):
            inside = not inside
    return inside


def _cells_of(group: list[tuple[int, int]], xs: list[int], ys: list[int]) -> list[Rect]:
    """A group of grid cells as few rectangles: runs along x in each row, then rows with the same
    run stacked."""
    rows: dict[int, list[int]] = {}
    for i, j in group:
        rows.setdefault(j, []).append(i)
    strips: list[tuple[int, int, int]] = []  # (i0, i1, j): cells i0..i1 of row j
    for j in sorted(rows):
        run = sorted(rows[j])
        start = prev = run[0]
        for i in run[1:]:
            if i != prev + 1:
                strips.append((start, prev, j))
                start = i
            prev = i
        strips.append((start, prev, j))
    rects: list[list[int]] = []  # [i0, i1, j0, j1]
    for i0, i1, j in strips:
        for r in rects:
            if r[0] == i0 and r[1] == i1 and r[3] == j - 1:
                r[3] = j
                break
        else:
            rects.append([i0, i1, j, j])
    return [Rect(xs[i0], ys[j0], xs[i1 + 1], ys[j1 + 1]) for i0, i1, j0, j1 in rects]


def open_areas(region: Rect, rooms: list[list[Pt]]) -> list[OpenArea]:
    """The parts of the wall-centreline region no room covers, as connected areas.

    The region is cut on every room corner coordinate into a grid; a cell is open when its centre
    lies in no room. Open cells sharing an edge form one area. Each area is classified by where it
    lies, for its label only: SIDE_YARD when it runs from the road edge to the back, FORECOURT
    when it touches the road edge, REAR_YARD when it touches the back, SIDE_YARD when it touches
    only a side, COURT when it touches no side of the region.
    Deterministic: the order follows the grid (rows from the road, then left to right)."""
    xs = sorted(
        {region.x0, region.x1, *(x for r in rooms for x, _ in r if region.x0 < x < region.x1)}
    )
    ys = sorted(
        {region.y0, region.y1, *(y for r in rooms for _, y in r if region.y0 < y < region.y1)}
    )
    open_cells = {
        (i, j)
        for j in range(len(ys) - 1)
        for i in range(len(xs) - 1)
        if not any(
            len(r) >= 3 and _inside((xs[i] + xs[i + 1], ys[j] + ys[j + 1]), r) for r in rooms
        )
    }
    out: list[OpenArea] = []
    seen: set[tuple[int, int]] = set()
    for start in sorted(open_cells, key=lambda c: (c[1], c[0])):
        if start in seen:
            continue
        group, stack = [], [start]
        seen.add(start)
        while stack:
            i, j = stack.pop()
            group.append((i, j))
            for nb in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                if nb in open_cells and nb not in seen:
                    seen.add(nb)
                    stack.append(nb)
        cells = _cells_of(group, xs, ys)
        x0, y0 = min(c.x0 for c in cells), min(c.y0 for c in cells)
        x1, y1 = max(c.x1 for c in cells), max(c.y1 for c in cells)
        front, back = y0 == region.y0, y1 == region.y1
        side = x0 == region.x0 or x1 == region.x1
        kind: OpenAreaKind
        if front and back:
            kind = "SIDE_YARD"  # a strip from the road to the back
        elif front:
            kind = "FORECOURT"
        elif back:
            kind = "REAR_YARD"
        else:
            kind = "SIDE_YARD" if side else "COURT"
        largest = max(cells, key=lambda c: (c.area, -c.y0, -c.x0))
        out.append(
            OpenArea(
                id=f"open_{len(out) + 1}",
                kind=kind,
                cells=[p for c in cells if (p := _poly(c)) is not None],
                area_mm2=sum(c.area for c in cells),
                label_at=_gp((largest.centre2[0] // 2, largest.centre2[1] // 2)),
            )
        )
    return out
