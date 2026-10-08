"""Structural edits on the planar graph (Checkpoint 3.1): MOVE_EDGE, ADD_ROOM and DELETE_ROOM.

Every room is a rectangle (generated layouts are slicing layouts). A structural edit changes room
rectangles and then rebuilds nodes, walls and boundaries with the builder the generator uses
(`graph.build_graph`), so the result is a graph a generated plan could have: T-junctions split
walls, a jog in a line splits it, a merge joins collinear walls again.

Identity is kept where the geometry allows. A node keeps its id where its point survives, or where
it moved to; a wall keeps its id when it still joins the same two nodes; anything new gets the
next free id. Openings and fixtures keep their place on the ground (D-8): each is re-hosted on
the new wall that holds its whole span on the same line (the line itself moves only when the
item's wall was part of the moved edge) and must still stand between the same rooms. One that
cannot is rejected with the reason; nothing is slid, resized or dropped to make an edit fit.

Size, envelope, window, access and fixture rules are the validator's to judge afterwards."""

from collections.abc import Callable
from dataclasses import dataclass, field

from p2b.core.vocabulary import (
    DoorLeaf,
    HingeSide,
    OpeningKind,
    OriginKind,
    PlanOpRejection,
    RoomSide,
    RoomType,
    WallKind,
    WallSide,
)
from p2b.houseplans.engine import programme
from p2b.houseplans.engine.build import ROOM_NAMES, room_name
from p2b.houseplans.engine.geom import Pt, Rect, rect_or_none, signed_area2
from p2b.houseplans.engine.graph import build_graph
from p2b.houseplans.engine.model import (
    DoorSpec,
    Floor,
    HousePlan,
    Node,
    Opening,
    Origin,
    Room,
    SizeSpec,
    Wall,
)
from p2b.houseplans.engine.ruleset import RulesetContent

ADDED_ROOM_ORIGIN = Origin(kind=OriginKind.USER_EDIT, ref="editor:add_room")


class GraphEditRejected(Exception):
    def __init__(self, reason: str, code: PlanOpRejection, *entities: str):
        super().__init__(reason)
        self.reason, self.code, self.entities = reason, code, entities


@dataclass(frozen=True)
class Seg:
    """An axis-aligned span: along x on the line y = coord ('x'), or along y on x = coord ('y').
    Its left side is the left of the low-to-high direction: +y for 'x', -x for 'y'."""

    axis: str
    coord: int
    lo: int
    hi: int


def room_rects(floor: Floor) -> dict[str, Rect]:
    """Each room's rectangle, in room order. GraphEditRejected(NOT_RECTANGULAR) for a room
    whose boundary is not an axis-aligned rectangle."""
    nodes = {n.id: (n.x, n.y) for n in floor.nodes}
    out: dict[str, Rect] = {}
    for room in floor.rooms:
        pts = [nodes[i] for i in room.boundary]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        rect = rect_or_none(min(xs), min(ys), max(xs), max(ys))
        if (
            rect is None
            or signed_area2(pts) != 2 * rect.area
            or not all(_on_perimeter(p, rect) for p in pts)
        ):
            raise GraphEditRejected(
                f"{room.id} is not a rectangle", PlanOpRejection.NOT_RECTANGULAR, room.id
            )
        out[room.id] = rect
    return out


def _on_perimeter(p: Pt, r: Rect) -> bool:
    return (p[0] in (r.x0, r.x1) and r.y0 <= p[1] <= r.y1) or (
        p[1] in (r.y0, r.y1) and r.x0 <= p[0] <= r.x1
    )


def _seg_of(a: Pt, b: Pt) -> tuple[Seg, bool]:
    """The wall a-b as a span, and whether a is its high end."""
    if a[1] == b[1] and a[0] != b[0]:
        return Seg("x", a[1], min(a[0], b[0]), max(a[0], b[0])), a[0] > b[0]
    if a[0] == b[0] and a[1] != b[1]:
        return Seg("y", a[0], min(a[1], b[1]), max(a[1], b[1])), a[1] > b[1]
    raise GraphEditRejected("a wall is not axis-aligned", PlanOpRejection.NOT_AXIS_ALIGNED)


def _beside(rects: dict[str, Rect], seg: Seg) -> tuple[str | None, str | None]:
    """The rooms whose edge holds the whole span, (left, right)."""
    left = right = None
    for key, r in rects.items():
        if seg.axis == "x" and r.x0 <= seg.lo and seg.hi <= r.x1:
            if r.y0 == seg.coord:
                left = key
            elif r.y1 == seg.coord:
                right = key
        elif seg.axis == "y" and r.y0 <= seg.lo and seg.hi <= r.y1:
            if r.x1 == seg.coord:
                left = key
            elif r.x0 == seg.coord:
                right = key
    return left, right


def _fresh(prefix: str, used: set[str]) -> Callable[[], str]:
    numbers = [
        int(i[len(prefix) :]) for i in used if i.startswith(prefix) and i[len(prefix) :].isdigit()
    ]
    counter = [max(numbers, default=0)]

    def next_id() -> str:
        counter[0] += 1
        return f"{prefix}{counter[0]}"

    return next_id


@dataclass
class Change:
    """The new rooms and how hosted items follow them."""

    rects: dict[str, Rect]  # every room of the floor after the edit
    rooms: list[Room]  # in their new order; boundaries are rebuilt
    moved: Callable[[Pt], Pt | None] = lambda _p: None  # where a node's point went, if it moved
    shift: Callable[[Seg], int] = lambda s: s.coord  # the line a hosted item's wall is on now
    alias: dict[str, str] = field(default_factory=dict)  # a room now standing in for another
    window_alias: dict[str, str] = field(default_factory=dict)  # windows may change room here
    drop_openings: set[str] = field(default_factory=set)
    drop_fixtures: set[str] = field(default_factory=set)


def _rebuild(
    floor: Floor, old_rects: dict[str, Rect], change: Change, ruleset: RulesetContent
) -> Floor:
    graph = build_graph(
        change.rects,
        {r.id: r.enclosed for r in change.rooms},
        exterior_mm=ruleset.walls.exterior_mm,
        interior_mm=ruleset.walls.interior_mm,
    )
    old_nodes = {n.id: (n.x, n.y) for n in floor.nodes}

    # nodes: a surviving point keeps its id, then a moved point, then fresh ids
    claimed: dict[Pt, str] = {}
    at_old = {p: i for i, p in reversed(old_nodes.items())}
    new_points = set(graph.nodes.values())
    for p in graph.nodes.values():
        if p in at_old:
            claimed[p] = at_old[p]
    taken = set(claimed.values())
    for i, p in old_nodes.items():
        q = change.moved(p)
        if i not in taken and q is not None and q in new_points and q not in claimed:
            claimed[q] = i
            taken.add(i)
    fresh_node = _fresh("n", set(old_nodes))
    node_id: dict[str, str] = {}
    for builder_id, p in graph.nodes.items():
        if p not in claimed:
            claimed[p] = fresh_node()
        node_id[builder_id] = claimed[p]

    old_wall = {frozenset((w.a, w.b)): w.id for w in floor.walls}
    fresh_wall = _fresh("w", {w.id for w in floor.walls})
    walls: list[Wall] = []
    for gw in graph.walls:
        a, b = node_id[gw.a], node_id[gw.b]
        walls.append(
            Wall(
                id=old_wall.get(frozenset((a, b))) or fresh_wall(),
                a=a,
                b=b,
                thickness_mm=gw.thickness_mm,
                kind=gw.kind,
            )
        )
    nodes = [Node(id=node_id[i], x=p[0], y=p[1]) for i, p in graph.nodes.items()]
    points = {n.id: (n.x, n.y) for n in nodes}
    new_segs = [(w, _seg_of(points[w.a], points[w.b])[0]) for w in walls]
    old_walls = {w.id: w for w in floor.walls}

    def rehost(
        item: str, wall: str, offset: int, width: int, window: bool
    ) -> tuple[Wall, int, bool]:
        """(new host, offset from its node a, whether the old host ran high to low)."""
        old = old_walls[wall]
        seg, reversed_ = _seg_of(old_nodes[old.a], old_nodes[old.b])
        start = seg.hi - offset - width if reversed_ else seg.lo + offset
        span = Seg(seg.axis, seg.coord, start, start + width)
        moved = Seg(span.axis, change.shift(seg), span.lo, span.hi)
        host = next(
            (
                w
                for w, s in new_segs
                if s.axis == moved.axis
                and s.coord == moved.coord
                and s.lo <= moved.lo
                and moved.hi <= s.hi
            ),
            None,
        )
        if host is None:
            raise GraphEditRejected(
                f"{item} would no longer sit on a wall",
                PlanOpRejection.HOSTED_ITEM_LEAVES_WALL,
                item,
            )
        before = tuple(change.alias.get(r, r) if r else None for r in _beside(old_rects, span))
        after = _beside(change.rects, moved)
        if before != after:
            relaxed = tuple(change.window_alias.get(r, r) if r else None for r in before)
            if not (window and relaxed == after):
                raise GraphEditRejected(
                    f"{item} would end up between other rooms",
                    PlanOpRejection.HOSTED_ITEM_CHANGES_ROOMS,
                    item,
                )
        host_seg = next(s for w, s in new_segs if w.id == host.id)
        return host, moved.lo - host_seg.lo, reversed_

    openings = []
    for o in floor.openings:
        if o.id in change.drop_openings:
            continue
        host, offset, flip = rehost(
            o.id, o.wall, o.offset_mm, o.width_mm, o.kind == OpeningKind.WINDOW
        )
        door = o.door
        if flip and door is not None:
            door = DoorSpec(
                leaf=door.leaf, hinge=_other_hinge(door.hinge), opens_to=_other_side(door.opens_to)
            )
        openings.append(o.model_copy(update={"wall": host.id, "offset_mm": offset, "door": door}))
    fixtures = []
    for f in floor.fixtures:
        if f.id in change.drop_fixtures:
            continue
        host, offset, flip = rehost(f.id, f.wall, f.offset_mm, f.w_mm, False)
        side = _other_side(f.side) if flip else f.side
        fixtures.append(f.model_copy(update={"wall": host.id, "offset_mm": offset, "side": side}))
    rooms = [
        r.model_copy(update={"boundary": [node_id[i] for i in graph.boundaries[r.id]]})
        for r in change.rooms
    ]
    return floor.model_copy(
        update={
            "nodes": nodes,
            "walls": walls,
            "rooms": rooms,
            "openings": openings,
            "fixtures": fixtures,
        }
    )


def _other_side(side: WallSide) -> WallSide:
    return WallSide.RIGHT if side == WallSide.LEFT else WallSide.LEFT


def _other_hinge(hinge: HingeSide) -> HingeSide:
    return HingeSide.B_SIDE if hinge == HingeSide.A_SIDE else HingeSide.A_SIDE


def _floor_of(plan: HousePlan, room: str) -> int:
    for fi, floor in enumerate(plan.floors):
        if any(r.id == room for r in floor.rooms):
            return fi
    raise LookupError(room)


def _with_floor(plan: HousePlan, fi: int, floor: Floor) -> HousePlan:
    floors = list(plan.floors)
    floors[fi] = floor
    return plan.model_copy(update={"floors": floors})


def _overlaps(rects: dict[str, Rect]) -> tuple[str, str] | None:
    keys = list(rects)
    for i, a in enumerate(keys):
        for b in keys[i + 1 :]:
            if rects[a].overlap_area(rects[b]) > 0:
                return a, b
    return None


# ---------- MOVE_EDGE ----------


def move_edge(
    plan: HousePlan, room: str, side: RoomSide, delta: int, ruleset: RulesetContent
) -> HousePlan:
    """Moves one side of a room by `delta` (along +x for LEFT and RIGHT, +y for FRONT and
    BACK), and with it only what must move to keep every room a rectangle: the rooms on either
    side of that line whose extent along it overlaps the moving span, repeated until no more
    join. The rest of the line stays, so it jogs where the span ends. Rejects a room that would
    collapse (WALL_WOULD_COLLAPSE) or overlap another (ROOMS_WOULD_OVERLAP)."""
    if delta == 0:
        raise GraphEditRejected("zero movement", PlanOpRejection.NO_MOVEMENT)
    fi = _floor_of(plan, room)
    floor = plan.floors[fi]
    rects = room_rects(floor)
    r = rects[room]
    across_x = side in (RoomSide.LEFT, RoomSide.RIGHT)  # the line is x = line
    line = {RoomSide.LEFT: r.x0, RoomSide.RIGHT: r.x1, RoomSide.FRONT: r.y0, RoomSide.BACK: r.y1}[
        side
    ]
    lo, hi = (r.y0, r.y1) if across_x else (r.x0, r.x1)

    def extent(q: Rect) -> tuple[int, int]:
        return (q.y0, q.y1) if across_x else (q.x0, q.x1)

    def on_line(q: Rect) -> str | None:  # which end of q lies on the line
        q0, q1 = (q.x0, q.x1) if across_x else (q.y0, q.y1)
        return "high" if q1 == line else "low" if q0 == line else None

    members: dict[str, str] = {}
    grew = True
    while grew:
        grew = False
        for key, q in rects.items():
            end = on_line(q)
            q_lo, q_hi = extent(q)
            if key not in members and end and q_lo < hi and q_hi > lo:
                members[key] = end
                lo, hi = min(lo, q_lo), max(hi, q_hi)
                grew = True

    new_rects = dict(rects)
    for key, end in members.items():
        q = rects[key]
        dx0 = dx1 = dy0 = dy1 = 0
        if across_x:
            dx0, dx1 = (0, delta) if end == "high" else (delta, 0)
        else:
            dy0, dy1 = (0, delta) if end == "high" else (delta, 0)
        moved = rect_or_none(q.x0 + dx0, q.y0 + dy0, q.x1 + dx1, q.y1 + dy1)
        if moved is None:
            raise GraphEditRejected(
                f"{key} would collapse", PlanOpRejection.WALL_WOULD_COLLAPSE, key
            )
        new_rects[key] = moved
    clash = _overlaps(new_rects)
    if clash:
        raise GraphEditRejected(
            f"{clash[0]} would overlap {clash[1]}", PlanOpRejection.ROOMS_WOULD_OVERLAP, *clash
        )

    def moved_point(p: Pt) -> Pt | None:
        on, along = (p[0], p[1]) if across_x else (p[1], p[0])
        if on != line or not lo <= along <= hi:
            return None
        return (p[0] + delta, p[1]) if across_x else (p[0], p[1] + delta)

    def shift(s: Seg) -> int:
        parallel = s.axis == ("y" if across_x else "x")
        return (
            line + delta if parallel and s.coord == line and lo <= s.lo and s.hi <= hi else s.coord
        )

    change = Change(rects=new_rects, rooms=list(floor.rooms), moved=moved_point, shift=shift)
    return _with_floor(plan, fi, _rebuild(floor, rects, change, ruleset))


# ---------- ADD_ROOM ----------


def _start(
    length: int, width: int, taken: list[tuple[int, int]], jamb: int, step: int
) -> int | None:
    """Where an opening of `width` goes on a wall: centred if free, else the first free grid step
    from node a; `jamb` clear of both ends and of other openings (as the generator places)."""
    lo, hi = jamb, length - jamb - width
    if hi < lo:
        return None

    def free(s: int) -> bool:
        return all(s + width + jamb <= t0 or s >= t1 + jamb for t0, t1 in taken)

    middle = (length - width) // 2
    if lo <= middle <= hi and free(middle):
        return middle
    s = lo
    while s <= hi:
        if free(s):
            return s
        s += step
    return None


def _unique(base: str, used: set[str]) -> str:
    candidate, n = base, 2
    while candidate in used:
        candidate, n = f"{base}_{n}", n + 1
    return candidate


def add_room(
    plan: HousePlan,
    host_room: str,
    room_type: RoomType,
    side: RoomSide,
    depth: int,
    ruleset: RulesetContent,
) -> HousePlan:
    """Splits a slice `depth` deep off the `side` of the host, across its full width, as a new
    room of `room_type`. One door joins it to the host (ruleset size, centred on the longest
    shared wall); a window goes on its longest outside wall when the room type needs one and the
    slice did not take one of the host's. The new room is recorded as the owner's addition to
    the programme (`programme.room_added`)."""
    rule = ruleset.rooms.get(room_type)
    if rule is None or not rule.enclosed:
        raise GraphEditRejected(
            f"{room_type.value} cannot be added here", PlanOpRejection.ROOM_TYPE_NOT_ALLOWED
        )
    fi = _floor_of(plan, host_room)
    floor = plan.floors[fi]
    rects = room_rects(floor)
    host = next(r for r in floor.rooms if r.id == host_room)
    h = rects[host_room]
    extent = h.w if side in (RoomSide.LEFT, RoomSide.RIGHT) else h.h
    if not host.enclosed or depth >= extent:
        raise GraphEditRejected(
            f"a {depth} mm slice does not fit inside {host_room}",
            PlanOpRejection.NOT_A_SLICE,
            host_room,
        )
    if side == RoomSide.LEFT:
        piece, rest = Rect(h.x0, h.y0, h.x0 + depth, h.y1), Rect(h.x0 + depth, h.y0, h.x1, h.y1)
    elif side == RoomSide.RIGHT:
        piece, rest = Rect(h.x1 - depth, h.y0, h.x1, h.y1), Rect(h.x0, h.y0, h.x1 - depth, h.y1)
    elif side == RoomSide.FRONT:
        piece, rest = Rect(h.x0, h.y0, h.x1, h.y0 + depth), Rect(h.x0, h.y0 + depth, h.x1, h.y1)
    else:
        piece, rest = Rect(h.x0, h.y1 - depth, h.x1, h.y1), Rect(h.x0, h.y0, h.x1, h.y1 - depth)

    room_ids = {r.id for f in plan.floors for r in f.rooms}
    key = room_type.value.lower()
    same = [r for f in plan.floors for r in f.rooms if r.type == room_type]
    new_id = _unique(f"{key}_{len(same) + 1}", room_ids)
    room = Room(
        id=new_id,
        type=room_type,
        name=room_name(new_id, room_type) if same else ROOM_NAMES[room_type],
        boundary=["pending"] * 4,
        zone=rule.zone,
        enclosed=True,
        required=False,
        size_spec=SizeSpec(
            min_short_mm=rule.min_short_mm,
            min_area_mm2=rule.min_area_mm2,
            pref_area_mm2=rule.pref_area_mm2,
            max_area_mm2=rule.max_area_mm2,
        ),
        origin=ADDED_ROOM_ORIGIN,
    )
    new_rects = {**rects, host_room: rest, new_id: piece}
    change = Change(rects=new_rects, rooms=[*floor.rooms, room], window_alias={host_room: new_id})
    edited = _rebuild(floor, rects, change, ruleset)

    points = {n.id: (n.x, n.y) for n in edited.nodes}
    segs = {w.id: _seg_of(points[w.a], points[w.b])[0] for w in edited.walls}
    o_rules, used = ruleset.openings, {o.id for f in plan.floors for o in f.openings}
    taken: dict[str, list[tuple[int, int]]] = {}
    for o in edited.openings:
        taken.setdefault(o.wall, []).append((o.offset_mm, o.offset_mm + o.width_mm))

    def length(w: Wall) -> int:
        return segs[w.id].hi - segs[w.id].lo

    shared = sorted(
        (w for w in edited.walls if set(_beside(new_rects, segs[w.id])) == {host_room, new_id}),
        key=lambda w: (-length(w), w.id),
    )
    door = None
    for wall in shared:
        start = _start(
            length(wall),
            o_rules.door_width_mm,
            taken.get(wall.id, []),
            o_rules.jamb_clearance_mm,
            ruleset.grid_mm,
        )
        if start is not None:
            left, _ = _beside(new_rects, segs[wall.id])
            door = Opening(
                id=_unique(f"door_{new_id}", used),
                kind=OpeningKind.DOOR,
                wall=wall.id,
                offset_mm=start,
                width_mm=o_rules.door_width_mm,
                height_mm=o_rules.door_height_mm,
                sill_mm=0,
                door=DoorSpec(
                    leaf=DoorLeaf.SINGLE,
                    hinge=HingeSide.A_SIDE,
                    opens_to=WallSide.LEFT if left == new_id else WallSide.RIGHT,
                ),
            )
            break
    if door is None:
        raise GraphEditRejected(
            f"there is no room for a door between {host_room} and the new room",
            PlanOpRejection.DOOR_DOES_NOT_FIT,
            host_room,
        )
    openings = [*edited.openings, door]
    used.add(door.id)

    def beside_new(o: Opening) -> bool:
        s = segs[o.wall]
        span = Seg(s.axis, s.coord, s.lo + o.offset_mm, s.lo + o.offset_mm + o.width_mm)
        return new_id in _beside(new_rects, span)

    has_window = any(o.kind == OpeningKind.WINDOW and beside_new(o) for o in openings)
    if rule.needs_window and not has_window:
        outside = sorted(
            (
                w
                for w in edited.walls
                if w.kind == WallKind.EXTERIOR and new_id in _beside(new_rects, segs[w.id])
            ),
            key=lambda w: (-length(w), w.id),
        )
        for wall in outside:
            start = _start(
                length(wall),
                o_rules.window_width_mm,
                taken.get(wall.id, []),
                o_rules.jamb_clearance_mm,
                ruleset.grid_mm,
            )
            if start is not None:
                openings.append(
                    Opening(
                        id=_unique(f"window_{new_id}", used),
                        kind=OpeningKind.WINDOW,
                        wall=wall.id,
                        offset_mm=start,
                        width_mm=o_rules.window_width_mm,
                        height_mm=o_rules.window_height_mm,
                        sill_mm=o_rules.window_sill_mm,
                    )
                )
                break  # none fits: the validator reports the missing window
    edited = edited.model_copy(update={"openings": openings})
    return programme.room_added(_with_floor(plan, fi, edited), room)


# ---------- DELETE_ROOM ----------


def delete_room(plan: HousePlan, room: str, merge_into: str, ruleset: RulesetContent) -> HousePlan:
    """Removes `room` and gives its floor area to `merge_into`, which must share one whole side
    with it so the two make a rectangle. The doors and openings between the two go with the
    wall between them; the removed room's fixtures go with it; its other openings now belong to
    `merge_into`. Recorded as the owner's removal (`programme.room_removed`)."""
    fi = _floor_of(plan, room)
    floor = plan.floors[fi]
    rects = room_rects(floor)
    if merge_into not in rects:
        raise LookupError(merge_into)
    if merge_into == room:
        raise GraphEditRejected(
            "a room cannot merge into itself", PlanOpRejection.ROOMS_NOT_MERGEABLE, room
        )
    gone = next(r for r in floor.rooms if r.id == room)
    keep = next(r for r in floor.rooms if r.id == merge_into)
    a, b = rects[room], rects[merge_into]
    union = None
    if (a.y0, a.y1) == (b.y0, b.y1) and (a.x1 == b.x0 or b.x1 == a.x0):
        union = Rect(min(a.x0, b.x0), a.y0, max(a.x1, b.x1), a.y1)
    elif (a.x0, a.x1) == (b.x0, b.x1) and (a.y1 == b.y0 or b.y1 == a.y0):
        union = Rect(a.x0, min(a.y0, b.y0), a.x1, max(a.y1, b.y1))
    if union is None or gone.enclosed != keep.enclosed:
        raise GraphEditRejected(
            f"{room} and {merge_into} do not make one rectangle together",
            PlanOpRejection.ROOMS_NOT_MERGEABLE,
            room,
            merge_into,
        )
    nodes = {n.id: (n.x, n.y) for n in floor.nodes}
    walls = {w.id: w for w in floor.walls}

    def between(wall: str, offset: int, width: int) -> bool:
        w = walls[wall]
        seg, reversed_ = _seg_of(nodes[w.a], nodes[w.b])
        start = seg.hi - offset - width if reversed_ else seg.lo + offset
        return set(_beside(rects, Seg(seg.axis, seg.coord, start, start + width))) == {
            room,
            merge_into,
        }

    new_rects = {k: (union if k == merge_into else r) for k, r in rects.items() if k != room}
    change = Change(
        rects=new_rects,
        rooms=[r for r in floor.rooms if r.id != room],
        alias={room: merge_into},
        drop_openings={o.id for o in floor.openings if between(o.wall, o.offset_mm, o.width_mm)},
        drop_fixtures={f.id for f in floor.fixtures if f.room == room},
    )
    edited = _rebuild(floor, rects, change, ruleset)
    return programme.room_removed(_with_floor(plan, fi, edited), gone)
