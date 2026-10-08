"""The PlanBuilder: solver rectangles and access topology become a HousePlan (walls, openings,
fixtures, site, hard constraints, metadata). Every solver's output goes through this one builder,
so no solver can produce geometry that bypasses the HousePlan or the validator.

Moved unchanged from Checkpoint 1's generate.py; the only addition is the schema version to emit,
so the Checkpoint 1 solver keeps producing byte-identical 1.0.0 documents."""

from dataclasses import dataclass

from p2b.core.vocabulary import (
    ConstraintKind,
    ConstraintOutcome,
    ConstraintStrength,
    OriginKind,
    PlanSource,
    PlotEdgeKind,
    RoomType,
    SetbackSide,
)
from p2b.houseplans.engine.canonical import sha256_of
from p2b.houseplans.engine.derive import WallInfo, analyse
from p2b.houseplans.engine.graph import Graph, build_graph
from p2b.houseplans.engine.intent import ArchitecturalIntent
from p2b.houseplans.engine.model import (
    Constraint,
    Fixture,
    Floor,
    GeneratorInfo,
    HousePlan,
    Meta,
    Node,
    Opening,
    Origin,
    ParamValue,
    Parking,
    Plot,
    PlotEdge,
    Point,
    Room,
    Setback,
    Site,
    SizeSpec,
    Wall,
)
from p2b.houseplans.engine.place import place_fixtures, place_openings
from p2b.houseplans.engine.ruleset import RulesetContent
from p2b.houseplans.engine.solver import LayoutSolver, Placed
from p2b.houseplans.engine.validate import ENGINE_VERSION

ROOM_NAMES = {
    RoomType.LIVING: "Living room",
    RoomType.DINING: "Dining",
    RoomType.KITCHEN: "Kitchen",
    RoomType.BEDROOM: "Bedroom",
    RoomType.BATH_ATTACHED: "Attached bathroom",
    RoomType.BATH_COMMON: "Common bathroom",
    RoomType.WC: "WC",
    RoomType.PUJA: "Puja room",
    RoomType.UTILITY: "Utility",
    RoomType.STORE: "Store",
    RoomType.PASSAGE: "Passage",
    RoomType.FOYER: "Foyer",
    RoomType.STAIR_HALL: "Stair hall",
    RoomType.PARKING: "Parking",
}
SOLVER_ORIGIN = Origin(kind=OriginKind.SOLVER, ref="solver:circulation")


@dataclass(frozen=True)
class BuildContext:
    intent: ArchitecturalIntent
    ruleset: RulesetContent
    ruleset_version: int
    ruleset_sha256: str
    solver: LayoutSolver
    seed: int
    schema_version: str


def room_name(key: str, room_type: RoomType) -> str:
    base = ROOM_NAMES[room_type]
    suffix = key.rsplit("_", 1)[-1]
    return f"{base} {suffix}" if suffix.isdigit() else base


def site_of(intent: ArchitecturalIntent) -> Site:
    w, d = intent.site.frontage_mm, intent.site.depth_mm
    vertices = [Point(x=0, y=0), Point(x=w, y=0), Point(x=w, y=d), Point(x=0, y=d)]
    edges = [
        PlotEdge(id="edge_front", start=0, end=1, kind=PlotEdgeKind.ROAD, side=SetbackSide.FRONT),
        PlotEdge(
            id="edge_right", start=1, end=2, kind=PlotEdgeKind.NEIGHBOUR, side=SetbackSide.RIGHT
        ),
        PlotEdge(
            id="edge_back", start=2, end=3, kind=PlotEdgeKind.NEIGHBOUR, side=SetbackSide.BACK
        ),
        PlotEdge(
            id="edge_left", start=3, end=0, kind=PlotEdgeKind.NEIGHBOUR, side=SetbackSide.LEFT
        ),
    ]
    edge_of = {e.side: e.id for e in edges}
    setbacks = [
        Setback(
            edge=edge_of[side],
            distance_mm=intent.site.setbacks_mm[side],
            source=intent.site.setback_sources[side],
        )
        for side in SetbackSide
    ]
    return Site(
        plot=Plot(vertices=vertices, edges=edges),
        north_angle_deg=intent.site.north_angle_deg,
        facing=intent.site.facing,
        entry_edge="edge_front",
        setbacks=setbacks,
        parking=None,
    )


def hard_constraints(intent: ArchitecturalIntent, outcome: ConstraintOutcome) -> list[Constraint]:
    out: list[Constraint] = []

    def add(
        kind: ConstraintKind, subjects: list[str], params: dict[str, ParamValue], origin: Origin
    ) -> None:
        out.append(
            Constraint(
                id=f"c{len(out) + 1}",
                kind=kind,
                strength=ConstraintStrength.HARD,
                weight=0,
                subjects=subjects,
                params=params,
                origin=origin,
                outcome=outcome,
            )
        )

    counts: dict[RoomType, list[Origin]] = {}
    for item in intent.programme:
        counts.setdefault(item.room_type, []).append(item.origin)
    for room_type, origins in counts.items():
        add(ConstraintKind.ROOM_PRESENT, [room_type.value], {"count": len(origins)}, origins[0])
    for rel in intent.relations:
        add(ConstraintKind.RELATION, [rel.room, rel.host], {"kind": rel.kind.value}, rel.origin)
    add(
        ConstraintKind.INSIDE_ENVELOPE,
        ["envelope"],
        {},
        Origin(kind=OriginKind.REQUIREMENT, ref="requirement:setbacks"),
    )
    add(ConstraintKind.ENTRANCE_ON_EDGE, ["edge_front"], {}, intent.site.facing_origin)
    if intent.parking is not None:
        add(
            ConstraintKind.PARKING_PROVIDED,
            ["parking"],
            {"spaces": intent.parking.spaces, "kind": intent.parking.kind.value},
            intent.parking.origin,
        )
    return out


def wall_infos(graph: Graph) -> dict[str, WallInfo]:
    """WallInfo for placement, straight from the graph (rooms known by construction)."""
    out = {}
    for w in graph.walls:
        a, b = graph.nodes[w.a], graph.nodes[w.b]
        direction = (1, 0) if a[1] == b[1] else (0, 1)
        out[w.id] = WallInfo(
            id=w.id,
            a=a,
            b=b,
            kind=w.kind,
            thickness=w.thickness_mm,
            length=abs(b[0] - a[0]) + abs(b[1] - a[1]),
            direction=direction,
            left_rooms=(w.left_room,) if w.left_room else (),
            right_rooms=(w.right_room,) if w.right_room else (),
        )
    return out


def build_plan(placed: Placed, ctx: BuildContext) -> HousePlan:
    """The HousePlan for a solver's layout. Raises PlacementFailure when an opening or a fixture
    template does not fit; never forces one in."""
    intent, ruleset = ctx.intent, ctx.ruleset
    types = {p.key: p.room_type for p in intent.programme} | placed.added_rooms
    origins = {p.key: p.origin for p in intent.programme}
    keys = [p.key for p in intent.programme] + sorted(placed.added_rooms)
    enclosed = {k: ruleset.rooms[types[k]].enclosed for k in keys}
    graph = build_graph(
        {k: placed.rects[k] for k in keys},
        enclosed,
        exterior_mm=ruleset.walls.exterior_mm,
        interior_mm=ruleset.walls.interior_mm,
    )
    walls = wall_infos(graph)
    room_types = {k: types[k] for k in keys}
    openings = place_openings(placed.access, placed.entry_room, walls, room_types, ruleset)
    # Clear rectangles for fixtures come from the same derivation the validator uses.
    draft = assemble(ctx, graph, keys, types, origins, openings, [])
    clear = analyse(draft).clear_rects
    fixtures = place_fixtures(room_types, walls, clear, openings, ruleset)
    return assemble(ctx, graph, keys, types, origins, openings, fixtures)


def assemble(
    ctx: BuildContext,
    graph: Graph,
    keys: list[str],
    types: dict[str, RoomType],
    origins: dict[str, Origin],
    openings: list[Opening],
    fixtures: list[Fixture],
) -> HousePlan:
    intent, ruleset = ctx.intent, ctx.ruleset
    site = site_of(intent)
    if intent.parking is not None:
        space = ruleset.parking[intent.parking.kind]
        site = site.model_copy(
            update={
                "parking": Parking(
                    spaces=intent.parking.spaces,
                    kind=intent.parking.kind,
                    space_w_mm=space.space_w_mm,
                    space_d_mm=space.space_d_mm,
                    placement=intent.parking.placement,
                    origin=intent.parking.origin,
                )
            }
        )
    rooms = []
    for k in keys:
        rule = ruleset.rooms[types[k]]
        rooms.append(
            Room(
                id=k,
                type=types[k],
                name=room_name(k, types[k]),
                boundary=graph.boundaries[k],
                zone=rule.zone,
                enclosed=rule.enclosed,
                required=True,
                size_spec=SizeSpec(
                    min_short_mm=rule.min_short_mm,
                    min_area_mm2=rule.min_area_mm2,
                    pref_area_mm2=rule.pref_area_mm2,
                    max_area_mm2=rule.max_area_mm2,
                ),
                origin=origins.get(k, SOLVER_ORIGIN),
            )
        )
    lv = ruleset.levels
    floor = Floor(
        id="floor_0",
        level=0,
        name="Ground floor",
        ffl_mm=0,
        floor_to_floor_mm=lv.floor_to_floor_mm,
        clear_height_mm=lv.clear_height_mm,
        slab_mm=lv.slab_mm,
        plinth_mm=lv.plinth_mm,
        nodes=[Node(id=i, x=p[0], y=p[1]) for i, p in graph.nodes.items()],
        walls=[
            Wall(id=w.id, a=w.a, b=w.b, thickness_mm=w.thickness_mm, kind=w.kind)
            for w in graph.walls
        ],
        rooms=rooms,
        openings=openings,
        stairs=[],
        fixtures=fixtures,
    )
    meta = Meta(
        schema_version=ctx.schema_version,
        source=PlanSource.GENERATED,
        generator=GeneratorInfo(
            engine="p2b-houseplans",
            engine_version=ENGINE_VERSION,
            solver=ctx.solver.kind,
            solver_version=ctx.solver.version,
            seed=ctx.seed,
            ruleset_version=ctx.ruleset_version,
            ruleset_sha256=ctx.ruleset_sha256,
            intent_sha256=sha256_of(intent),
        ),
    )
    return HousePlan(
        meta=meta,
        site=site,
        floors=[floor],
        constraints=hard_constraints(intent, ConstraintOutcome.NOT_EVALUATED),
        compromises=[],
    )
