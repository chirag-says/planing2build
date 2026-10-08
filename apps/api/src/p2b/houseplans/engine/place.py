"""Rule-based placement of openings and fixtures on a solved layout. Positions are hosted (wall +
offset), sizes come from the ruleset, and every candidate is checked with the same derived
geometry the validator uses. A required element that does not fit is reported, never forced."""

from dataclasses import dataclass

from p2b.core.vocabulary import (
    DoorLeaf,
    FixtureType,
    HingeSide,
    InfeasibleReason,
    OpeningKind,
    OriginKind,
    RoomType,
    WallKind,
    WallSide,
)
from p2b.houseplans.engine.derive import WallInfo, fixture_info, opening_info
from p2b.houseplans.engine.geom import Rect
from p2b.houseplans.engine.model import DoorSpec, Fixture, Opening, Origin
from p2b.houseplans.engine.ruleset import RulesetContent
from p2b.houseplans.engine.solver import Access, InfeasibleDetail


@dataclass(frozen=True)
class PlacementFailure(Exception):
    detail: InfeasibleDetail


def _fail(code: InfeasibleReason, **params: int | str) -> PlacementFailure:
    return PlacementFailure(InfeasibleDetail(code, dict(params)))


def _side_of(wall: WallInfo, room: str) -> WallSide:
    return WallSide.LEFT if room in wall.left_rooms else WallSide.RIGHT


def _walls_between(walls: dict[str, WallInfo], a: str, b: str) -> list[WallInfo]:
    out = [
        w
        for w in walls.values()
        if (a in w.left_rooms and b in w.right_rooms) or (b in w.left_rooms and a in w.right_rooms)
    ]
    return sorted(out, key=lambda w: (-w.length, w.id))


def _free_start(
    wall: WallInfo, width: int, taken: list[tuple[int, int]], jamb: int, *, centred: bool, step: int
) -> int | None:
    """A start offset for an opening of `width` on the wall, keeping `jamb` clear at both ends and
    between openings; the centred position first when asked, else the first from node a."""
    lo, hi = jamb, wall.length - jamb - width
    if hi < lo:
        return None

    def free(s: int) -> bool:
        return all(s + width + jamb <= t0 or s >= t1 + jamb for t0, t1 in taken)

    if centred:
        middle = (wall.length - width) // 2
        if lo <= middle <= hi and free(middle):
            return middle
    s = lo
    while s <= hi:
        if free(s):
            return s
        s += step
    return None


def place_openings(
    access: tuple[Access, ...],
    entry_room: str,
    walls: dict[str, WallInfo],
    room_types: dict[str, RoomType],
    ruleset: RulesetContent,
) -> list[Opening]:
    o_rules, g = ruleset.openings, ruleset.grid_mm
    taken: dict[str, list[tuple[int, int]]] = {}
    openings: list[Opening] = []
    used_ids: set[str] = set()

    def new_id(base: str) -> str:
        candidate, n = base, 2
        while candidate in used_ids:
            candidate, n = f"{base}_{n}", n + 1
        used_ids.add(candidate)
        return candidate

    def put(
        kind: OpeningKind,
        wall: WallInfo,
        start: int,
        width: int,
        height: int,
        sill: int,
        enter: str | None,
        ident: str,
    ) -> None:
        door = None
        if kind in (OpeningKind.DOOR, OpeningKind.MAIN_ENTRANCE):
            if enter is None:
                raise ValueError("a door needs the room it opens into")
            door = DoorSpec(
                leaf=DoorLeaf.SINGLE, hinge=HingeSide.A_SIDE, opens_to=_side_of(wall, enter)
            )
        openings.append(
            Opening(
                id=new_id(ident),
                kind=kind,
                wall=wall.id,
                offset_mm=start,
                width_mm=width,
                height_mm=height,
                sill_mm=sill,
                door=door,
            )
        )
        taken.setdefault(wall.id, []).append((start, start + width))

    # Main entrance: the entry room's exterior wall on the road edge.
    front = [
        w
        for w in walls.values()
        if w.kind == WallKind.EXTERIOR
        and entry_room in (w.left_rooms + w.right_rooms)
        and w.direction == (1, 0)
        and _side_of(w, entry_room) == WallSide.LEFT
    ]
    front.sort(key=lambda w: (w.a[1], -w.length, w.id))
    if not front:
        raise _fail(InfeasibleReason.OPENING_FIT, room=entry_room, opening="MAIN_ENTRANCE")
    wall = front[0]
    start = _free_start(
        wall, o_rules.main_entrance_width_mm, [], o_rules.jamb_clearance_mm, centred=True, step=g
    )
    if start is None:
        raise _fail(InfeasibleReason.OPENING_FIT, room=entry_room, opening="MAIN_ENTRANCE")
    put(
        OpeningKind.MAIN_ENTRANCE,
        wall,
        start,
        o_rules.main_entrance_width_mm,
        o_rules.door_height_mm,
        0,
        entry_room,
        "main_entrance",
    )

    # Doors and open connections from the solver's access topology.
    for acc in access:
        width = o_rules.door_width_mm if acc.kind == OpeningKind.DOOR else o_rules.void_width_mm
        placed = False
        for wall in _walls_between(walls, acc.room, acc.via):
            start = _free_start(
                wall,
                width,
                taken.get(wall.id, []),
                o_rules.jamb_clearance_mm,
                centred=acc.kind == OpeningKind.VOID,
                step=g,
            )
            if start is not None:
                prefix = "door" if acc.kind == OpeningKind.DOOR else "void"
                put(
                    acc.kind,
                    wall,
                    start,
                    width,
                    o_rules.door_height_mm,
                    0,
                    acc.room if acc.kind == OpeningKind.DOOR else None,
                    f"{prefix}_{acc.room}",
                )
                placed = True
                break
        if not placed:
            raise _fail(InfeasibleReason.OPENING_FIT, room=acc.room, opening=acc.kind.value)

    # Windows: one per room whose rule needs one, on its longest exterior wall with room.
    for room, room_type in room_types.items():
        rule = ruleset.rooms.get(room_type)
        if rule is None or not rule.needs_window:
            continue
        candidates = sorted(
            (
                w
                for w in walls.values()
                if w.kind == WallKind.EXTERIOR and room in (w.left_rooms + w.right_rooms)
            ),
            key=lambda w: (-w.length, w.id),
        )
        for wall in candidates:
            start = _free_start(
                wall,
                o_rules.window_width_mm,
                taken.get(wall.id, []),
                o_rules.jamb_clearance_mm,
                centred=True,
                step=g,
            )
            if start is not None:
                put(
                    OpeningKind.WINDOW,
                    wall,
                    start,
                    o_rules.window_width_mm,
                    o_rules.window_height_mm,
                    o_rules.window_sill_mm,
                    None,
                    f"window_{room}",
                )
                break
        else:
            raise _fail(InfeasibleReason.OPENING_FIT, room=room, opening="WINDOW")
    return openings


def place_fixtures(
    room_types: dict[str, RoomType],
    walls: dict[str, WallInfo],
    clear_rects: dict[str, Rect | None],
    openings: list[Opening],
    ruleset: RulesetContent,
) -> list[Fixture]:
    zones_by_room: dict[str, list[Rect]] = {}
    for o in openings:
        info = opening_info(o, walls.get(o.wall))
        if info is None:
            continue
        for zone in info.zones:
            for room in info.wall.left_rooms + info.wall.right_rooms:
                zones_by_room.setdefault(room, []).append(zone)
    fixtures: list[Fixture] = []
    for room, room_type in room_types.items():
        template = ruleset.templates.get(room_type, [])
        clear = clear_rects.get(room)
        if not template:
            continue
        if clear is None:
            raise _fail(InfeasibleReason.FIXTURE_FIT, room=room)
        hosts = sorted(
            (w for w in walls.values() if room in (w.left_rooms + w.right_rooms)),
            key=lambda w: (-w.length, w.id),
        )
        footprints: list[Rect] = []
        clearances: list[Rect] = []
        for item in template:
            rule = ruleset.fixtures[item.fixture]
            for n in range(1, item.count + 1):
                fixture = _fit(
                    room,
                    item.fixture,
                    rule.w_mm,
                    rule.d_mm,
                    rule.clear_front_mm,
                    n,
                    hosts,
                    clear,
                    zones_by_room.get(room, []),
                    footprints,
                    clearances,
                    ruleset.grid_mm,
                )
                if fixture is None:
                    raise _fail(InfeasibleReason.FIXTURE_FIT, room=room, fixture=item.fixture.value)
                fixtures.append(fixture)
    return fixtures


def _fit(
    room: str,
    fixture_type: FixtureType,
    w: int,
    d: int,
    clear_front: int,
    n: int,
    hosts: list[WallInfo],
    clear: Rect,
    zones: list[Rect],
    footprints: list[Rect],
    clearances: list[Rect],
    step: int,
) -> Fixture | None:
    ident = f"{fixture_type.value.lower()}_{room}" + (f"_{n}" if n > 1 else "")
    origin = Origin(kind=OriginKind.RULESET, ref=f"ruleset:templates.{fixture_type.value}")
    for wall in hosts:
        side = _side_of(wall, room)
        offset = 0
        while offset + w <= wall.length:
            candidate = Fixture(
                id=ident,
                type=fixture_type,
                room=room,
                wall=wall.id,
                offset_mm=offset,
                side=side,
                w_mm=w,
                d_mm=d,
                origin=origin,
            )
            info = fixture_info(candidate, wall, clear_front)
            fp, cl = info.footprint, info.clearance
            if (
                fp is not None
                and clear.contains(fp)
                and (cl is None or clear.contains(cl))
                and all(fp.overlap_area(z) == 0 for z in zones)
                and all(fp.overlap_area(o) == 0 for o in footprints + clearances)
                and (cl is None or all(cl.overlap_area(o) == 0 for o in footprints))
            ):
                footprints.append(fp)
                if cl is not None:
                    clearances.append(cl)
                return candidate
            offset += step
    return None
