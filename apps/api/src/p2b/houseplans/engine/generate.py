"""The generation pipeline:

    intent + ruleset → LayoutProblem → LayoutSolver → rectangles + access topology
      → planar wall graph → openings and fixtures → HousePlan
      → validate → deterministic repair → VALID plan, or INFEASIBLE with reasons, or INVALID

INVALID means the engine produced a plan its own validator rejects: an engine defect. The caller
records it as FAILED and never shows the plan. Every solver goes through this one path, so no
solver can bypass the HousePlan or the validator."""

from dataclasses import dataclass, field
from typing import Literal

from p2b.core.vocabulary import (
    ConstraintKind,
    ConstraintOutcome,
    ConstraintStrength,
    InfeasibleReason,
    OpeningKind,
    OriginKind,
    PlanSource,
    PlotEdgeKind,
    RelationKind,
    RoomType,
    SetbackSide,
)
from p2b.houseplans.engine.canonical import sha256_of
from p2b.houseplans.engine.derive import WallInfo, analyse, half
from p2b.houseplans.engine.geom import Rect, rect_or_none
from p2b.houseplans.engine.graph import Graph, build_graph
from p2b.houseplans.engine.intent import ArchitecturalIntent
from p2b.houseplans.engine.model import (
    SCHEMA_VERSION,
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
from p2b.houseplans.engine.place import PlacementFailure, place_fixtures, place_openings
from p2b.houseplans.engine.repair import AppliedRepair, repair
from p2b.houseplans.engine.ruleset import RulesetContent
from p2b.houseplans.engine.solver import (
    Infeasible,
    InfeasibleDetail,
    LayoutProblem,
    LayoutSolver,
    ParkingDemand,
    Placed,
    RelationDemand,
    RoomDemand,
)
from p2b.houseplans.engine.validate import ENGINE_VERSION, ValidationReport, validate

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


@dataclass
class GenerationResult:
    outcome: Literal["VALID", "INFEASIBLE", "INVALID"]
    plan: HousePlan | None = None
    report: ValidationReport | None = None
    reasons: tuple[InfeasibleDetail, ...] = ()
    repairs: list[AppliedRepair] = field(default_factory=list)
    topology: str | None = None


def _plot_rect(intent: ArchitecturalIntent) -> Rect:
    return Rect(0, 0, intent.site.frontage_mm, intent.site.depth_mm)


def compile_problem(
    intent: ArchitecturalIntent, ruleset: RulesetContent
) -> LayoutProblem | Infeasible:
    missing = sorted(
        {p.room_type.value for p in intent.programme if p.room_type not in ruleset.rooms}
        | (
            {ruleset.zoning.circulation_room.value}
            if ruleset.zoning.circulation_room not in ruleset.rooms
            else set()
        )
    )
    if intent.parking is not None and intent.parking.kind not in ruleset.parking:
        missing.append(f"parking.{intent.parking.kind.value}")
    for items in ruleset.templates.values():
        missing.extend(
            f"fixtures.{i.fixture.value}" for i in items if i.fixture not in ruleset.fixtures
        )
    if missing:
        return Infeasible(
            (
                InfeasibleDetail(
                    InfeasibleReason.RULESET_INCOMPLETE, {"missing": ", ".join(missing)}
                ),
            )
        )
    s = intent.site.setbacks_mm
    envelope = _plot_rect(intent).inset(
        s[SetbackSide.LEFT], s[SetbackSide.FRONT], s[SetbackSide.RIGHT], s[SetbackSide.BACK]
    )
    t = half(ruleset.walls.exterior_mm)
    region = envelope.inset(t, t, t, t) if envelope is not None else None
    if region is None:
        return Infeasible((InfeasibleDetail(InfeasibleReason.ENVELOPE_EMPTY, {}),))
    rooms = []
    for item in intent.programme:
        rule = ruleset.rooms[item.room_type]
        rooms.append(
            RoomDemand(
                key=item.key,
                room_type=item.room_type,
                enclosed=rule.enclosed,
                min_short_mm=rule.min_short_mm,
                min_area_mm2=rule.min_area_mm2,
                target_area_mm2=rule.pref_area_mm2 or rule.min_area_mm2,
            )
        )
    parking = None
    if intent.parking is not None:
        key = next(p.key for p in intent.programme if p.room_type == RoomType.PARKING)
        space = ruleset.parking[intent.parking.kind]
        parking = ParkingDemand(
            key=key,
            clear_w_mm=intent.parking.spaces * space.space_w_mm,
            clear_d_mm=space.space_d_mm,
        )
    o = ruleset.openings
    return LayoutProblem(
        region=region,
        grid_mm=ruleset.grid_mm,
        wall_allowance_mm=max(ruleset.walls.exterior_mm, ruleset.walls.interior_mm),
        rooms=tuple(rooms),
        relations=tuple(
            RelationDemand(
                room=r.room,
                host=r.host,
                access=OpeningKind.DOOR
                if r.kind == RelationKind.ADJACENT_WITH_DOOR
                else OpeningKind.VOID,
            )
            for r in intent.relations
        ),
        parking=parking,
        zoning=ruleset.zoning,
        passage_key="passage",
        passage_clear_mm=ruleset.passage_min_width_mm,
        door_span_mm=o.door_width_mm + 2 * o.jamb_clearance_mm,
        void_span_mm=o.void_width_mm + 2 * o.jamb_clearance_mm,
    )


def _room_name(key: str, room_type: RoomType) -> str:
    base = ROOM_NAMES[room_type]
    suffix = key.rsplit("_", 1)[-1]
    return f"{base} {suffix}" if suffix.isdigit() else base


def _site(intent: ArchitecturalIntent) -> Site:
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
    parking = None
    return Site(
        plot=Plot(vertices=vertices, edges=edges),
        north_angle_deg=intent.site.north_angle_deg,
        facing=intent.site.facing,
        entry_edge="edge_front",
        setbacks=setbacks,
        parking=parking,
    )


def _constraints(intent: ArchitecturalIntent, outcome: ConstraintOutcome) -> list[Constraint]:
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


def _walls_from_graph(graph: Graph) -> dict[str, WallInfo]:
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


def generate(
    intent: ArchitecturalIntent,
    ruleset: RulesetContent,
    *,
    ruleset_version: int,
    ruleset_sha256: str,
    solver: LayoutSolver,
    seed: int,
) -> GenerationResult:
    problem = compile_problem(intent, ruleset)
    if isinstance(problem, Infeasible):
        return GenerationResult("INFEASIBLE", reasons=problem.reasons)
    solved = solver.solve(problem, seed=seed)
    if isinstance(solved, Infeasible):
        return GenerationResult("INFEASIBLE", reasons=solved.reasons)
    if not isinstance(solved, Placed):
        raise TypeError(f"solver returned {type(solved).__name__}")

    types = {p.key: p.room_type for p in intent.programme} | solved.added_rooms
    origins = {p.key: p.origin for p in intent.programme}
    keys = [p.key for p in intent.programme] + sorted(solved.added_rooms)
    enclosed = {k: ruleset.rooms[types[k]].enclosed for k in keys}
    graph = build_graph(
        {k: solved.rects[k] for k in keys},
        enclosed,
        exterior_mm=ruleset.walls.exterior_mm,
        interior_mm=ruleset.walls.interior_mm,
    )
    walls = _walls_from_graph(graph)
    room_types = {k: types[k] for k in keys}
    try:
        openings = place_openings(solved.access, solved.entry_room, walls, room_types, ruleset)
        # Clear rectangles for fixtures come from the same derivation the validator uses.
        draft = _assemble(
            intent,
            ruleset,
            graph,
            keys,
            types,
            origins,
            openings,
            [],
            ruleset_version,
            ruleset_sha256,
            solver,
            seed,
            ConstraintOutcome.NOT_EVALUATED,
        )
        clear = analyse(draft).clear_rects
        fixtures = place_fixtures(room_types, walls, clear, openings, ruleset)
    except PlacementFailure as failure:
        return GenerationResult("INFEASIBLE", reasons=(failure.detail,), topology=solved.topology)

    plan = _assemble(
        intent,
        ruleset,
        graph,
        keys,
        types,
        origins,
        openings,
        fixtures,
        ruleset_version,
        ruleset_sha256,
        solver,
        seed,
        ConstraintOutcome.NOT_EVALUATED,
    )
    fixed = repair(
        plan, ruleset, intent=intent, ruleset_version=ruleset_version, ruleset_sha256=ruleset_sha256
    )
    if not fixed.report.valid:
        return GenerationResult(
            "INVALID",
            plan=fixed.plan,
            report=fixed.report,
            repairs=fixed.applied,
            topology=solved.topology,
        )
    final = fixed.plan.model_copy(
        update={"constraints": _constraints(intent, ConstraintOutcome.MET)}
    )
    report = validate(
        final,
        ruleset,
        intent=intent,
        ruleset_version=ruleset_version,
        ruleset_sha256=ruleset_sha256,
    )
    final = final.model_copy(
        update={"meta": final.meta.model_copy(update={"body_sha256": sha256_of(final.body())})}
    )
    return GenerationResult(
        "VALID" if report.valid else "INVALID",
        plan=final,
        report=report,
        repairs=fixed.applied,
        topology=solved.topology,
    )


def _assemble(
    intent: ArchitecturalIntent,
    ruleset: RulesetContent,
    graph: Graph,
    keys: list[str],
    types: dict[str, RoomType],
    origins: dict[str, Origin],
    openings: list[Opening],
    fixtures: list[Fixture],
    ruleset_version: int,
    ruleset_sha256: str,
    solver: LayoutSolver,
    seed: int,
    outcome: ConstraintOutcome,
) -> HousePlan:
    site = _site(intent)
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
                name=_room_name(k, types[k]),
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
        schema_version=SCHEMA_VERSION,
        source=PlanSource.GENERATED,
        generator=GeneratorInfo(
            engine="p2b-houseplans",
            engine_version=ENGINE_VERSION,
            solver=solver.kind,
            solver_version=solver.version,
            seed=seed,
            ruleset_version=ruleset_version,
            ruleset_sha256=ruleset_sha256,
            intent_sha256=sha256_of(intent),
        ),
    )
    return HousePlan(
        meta=meta,
        site=site,
        floors=[floor],
        constraints=_constraints(intent, outcome),
        compromises=[],
    )


__all__ = ["GenerationResult", "compile_problem", "generate", "rect_or_none"]
