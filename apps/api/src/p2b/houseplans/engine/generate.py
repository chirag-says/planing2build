"""The generation pipeline:

    intent + ruleset → compile → feasibility pre-check (PROVEN?) → LayoutSolver
      → ranked layouts → for each, best first, up to `objective.build_attempts`:
           build (walls, openings, fixtures) → validate → deterministic repair → VALID?
      → VALID plan with hard and scored soft constraints, or INFEASIBLE with a classification

INFEASIBLE is PROVEN only when the pre-check's arithmetic shows no arrangement can work; otherwise
NO_SUPPORTED_LAYOUT (CP2-U4). A layout that builds but fails validation after repair is an engine
defect: it is recorded in `attempts` and the next layout is tried; it is never returned as VALID.

The Checkpoint 1 solver (DETERMINISTIC_MVP, the fallback) keeps its exact path: one layout, schema
1.0.0, hard constraints only, so its documents stay byte-identical. INVALID is returned only by that
path, as in Checkpoint 1."""

from dataclasses import dataclass, field
from typing import Literal

from p2b.core.vocabulary import (
    ConstraintOutcome,
    ConstraintStrength,
    FeasibilityClass,
    InfeasibleReason,
    OpeningKind,
    OriginKind,
    RelationKind,
    RoomType,
    SetbackSide,
    SolverKind,
    TopologyFamily,
)
from p2b.houseplans.engine.build import BuildContext, build_plan, hard_constraints
from p2b.houseplans.engine.canonical import sha256_of
from p2b.houseplans.engine.derive import half
from p2b.houseplans.engine.feasibility import FeasibilityReport, no_supported_layout, precheck
from p2b.houseplans.engine.fit import fixture_fit
from p2b.houseplans.engine.geom import Rect, rect_or_none
from p2b.houseplans.engine.intent import ArchitecturalIntent
from p2b.houseplans.engine.model import (
    SCHEMA_VERSION,
    SCHEMA_VERSION_1_0,
    Constraint,
    HousePlan,
    Origin,
)
from p2b.houseplans.engine.objective import QualityScore, score_plan
from p2b.houseplans.engine.place import PlacementFailure
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
from p2b.houseplans.engine.solver.zoned_ls import search
from p2b.houseplans.engine.validate import ValidationReport, validate
from p2b.houseplans.engine.zoning import Verdict


@dataclass(frozen=True)
class Attempt:
    """One ranked layout the pipeline tried: VALID, PLACEMENT (an opening or fixture template did
    not fit) or INVALID (validator errors after repair, listed)."""

    topology: str
    result: Literal["VALID", "PLACEMENT", "INVALID"]
    codes: tuple[str, ...] = ()


@dataclass
class GenerationResult:
    outcome: Literal["VALID", "INFEASIBLE", "INVALID"]
    plan: HousePlan | None = None
    report: ValidationReport | None = None
    reasons: tuple[InfeasibleDetail, ...] = ()
    repairs: list[AppliedRepair] = field(default_factory=list)
    topology: str | None = None
    feasibility: FeasibilityReport | None = None
    quality: QualityScore | None = None
    attempts: list[Attempt] = field(default_factory=list)
    candidates_enumerated: int = 0
    candidates_sized: int = 0
    feasible_layouts: int = 0
    evaluations: int = 0
    family: TopologyFamily | None = None  # the chosen layout's topology family (zoned solver)
    verdicts: tuple[Verdict, ...] = ()  # which families applied, and why not where they did not


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


def soft_constraints(quality: QualityScore, first_id: int) -> list[Constraint]:
    """The Scorer's terms as SOFT constraints: weight and origin from the ruleset's objective,
    the measured score, and MET / PARTIAL / UNMET / NOT_EVALUATED."""
    out = []
    for i, term in enumerate(quality.terms):
        out.append(
            Constraint(
                id=f"c{first_id + i}",
                kind=term.kind,
                strength=ConstraintStrength.SOFT,
                weight=term.weight,
                subjects=list(term.subjects),
                params={},
                origin=Origin(
                    kind=OriginKind.RULESET, ref=f"ruleset:objective.weights.{term.kind.value}"
                ),
                outcome=term.outcome,
                score_milli=term.score_milli,
            )
        )
    return out


def _finish(plan: HousePlan, ctx: BuildContext, *, scored: bool) -> GenerationResult:
    """Repair, then the final document: hard constraints MET (plus the scored soft terms),
    validated again, body hash stamped."""
    intent, ruleset = ctx.intent, ctx.ruleset
    fixed = repair(
        plan,
        ruleset,
        intent=intent,
        ruleset_version=ctx.ruleset_version,
        ruleset_sha256=ctx.ruleset_sha256,
    )
    if not fixed.report.valid:
        return GenerationResult(
            "INVALID", plan=fixed.plan, report=fixed.report, repairs=fixed.applied
        )
    constraints = hard_constraints(intent, ConstraintOutcome.MET)
    quality = score_plan(fixed.plan, ruleset) if scored else None
    if quality is not None:
        constraints += soft_constraints(quality, len(constraints) + 1)
    final = fixed.plan.model_copy(update={"constraints": constraints})
    report = validate(
        final,
        ruleset,
        intent=intent,
        ruleset_version=ctx.ruleset_version,
        ruleset_sha256=ctx.ruleset_sha256,
    )
    meta = final.meta.model_copy(update={"body_sha256": sha256_of(final.body())})
    final = final.model_copy(update={"meta": meta})
    return GenerationResult(
        "VALID" if report.valid else "INVALID",
        plan=final,
        report=report,
        repairs=fixed.applied,
        quality=quality,
    )


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
    if (
        isinstance(problem, Infeasible)
        and problem.reasons[0].code == InfeasibleReason.RULESET_INCOMPLETE
    ):
        return GenerationResult("INFEASIBLE", reasons=problem.reasons)  # a configuration fault
    proven = precheck(intent, ruleset)
    if proven is not None:
        detail = InfeasibleDetail(proven.code, dict(proven.params))
        return GenerationResult("INFEASIBLE", reasons=(detail,), feasibility=proven)
    if isinstance(problem, Infeasible):  # unreachable: the pre-check decides an empty envelope
        return GenerationResult("INFEASIBLE", reasons=problem.reasons)
    zoned = solver.kind == SolverKind.ZONED_LOCAL_SEARCH
    ctx = BuildContext(
        intent,
        ruleset,
        ruleset_version,
        ruleset_sha256,
        solver,
        seed,
        SCHEMA_VERSION if zoned else SCHEMA_VERSION_1_0,
    )
    return _generate_zoned(problem, ctx) if zoned else _generate_single(problem, ctx)


def _generate_single(problem: LayoutProblem, ctx: BuildContext) -> GenerationResult:
    """The Checkpoint 1 path, unchanged in behaviour; INFEASIBLE now carries a classification."""
    solved = ctx.solver.solve(problem, seed=ctx.seed)
    if isinstance(solved, Infeasible):
        report = no_supported_layout(ctx.intent, [], 1, None)
        return GenerationResult("INFEASIBLE", reasons=solved.reasons, feasibility=report)
    if not isinstance(solved, Placed):
        raise TypeError(f"solver returned {type(solved).__name__}")
    try:
        plan = build_plan(solved, ctx)
    except PlacementFailure as failure:
        report = no_supported_layout(ctx.intent, [], 1, solved.topology)
        return GenerationResult(
            "INFEASIBLE", reasons=(failure.detail,), topology=solved.topology, feasibility=report
        )
    result = _finish(plan, ctx, scored=False)
    result.topology = solved.topology
    return result


def _generate_zoned(problem: LayoutProblem, ctx: BuildContext) -> GenerationResult:
    obj = ctx.ruleset.objective
    if obj is None:
        missing = InfeasibleDetail(InfeasibleReason.RULESET_INCOMPLETE, {"missing": "objective"})
        return GenerationResult("INFEASIBLE", reasons=(missing,))
    found = search(problem, ctx.ruleset, fixture_fit(ctx.ruleset))
    attempts: list[Attempt] = []
    placement: list[InfeasibleDetail] = []
    result: GenerationResult | None = None
    for layout in found.feasible[: obj.build_attempts]:
        try:
            plan = build_plan(layout.zp.placed(layout.values), ctx)
        except PlacementFailure as failure:
            attempts.append(Attempt(layout.name, "PLACEMENT", (failure.detail.code.value,)))
            placement.append(failure.detail)
            continue
        finished = _finish(plan, ctx, scored=True)
        if finished.outcome == "VALID":
            attempts.append(Attempt(layout.name, "VALID"))
            finished.topology = layout.name
            finished.family = layout.family
            result = finished
            break
        codes = sorted({i.code.value for i in finished.report.errors} if finished.report else set())
        attempts.append(Attempt(layout.name, "INVALID", tuple(codes)))
    if result is None:
        if found.feasible:
            report = _placement_report(ctx.intent, found.sized, attempts, placement)
        else:
            closest = found.closest
            gaps = (
                [(s.code, s.room, s.amount, s.needed, s.actual) for s in closest.shortfalls]
                if closest
                else []
            )
            report = no_supported_layout(
                ctx.intent, gaps, found.sized, closest.name if closest else None
            )
        detail = InfeasibleDetail(report.code, dict(report.params))
        result = GenerationResult("INFEASIBLE", reasons=(detail,), feasibility=report)
    result.attempts = attempts
    result.candidates_enumerated, result.candidates_sized = found.enumerated, found.sized
    result.feasible_layouts, result.evaluations = len(found.feasible), found.evaluations
    result.verdicts = found.verdicts
    return result


def _placement_report(
    intent: ArchitecturalIntent,
    tried: int,
    attempts: list[Attempt],
    placement: list[InfeasibleDetail],
) -> FeasibilityReport:
    """Sized layouts existed but none built into a valid plan: name what failed first."""
    base = no_supported_layout(intent, [], tried, attempts[0].topology if attempts else None)
    if placement:
        first = placement[0]
        room = str(first.params.get("room", "one room")).replace("_", " ")
        what = "the fittings" if first.code == InfeasibleReason.FIXTURE_FIT else "a door or window"
        code = first.code
    else:
        room, what, code = "one room", "a valid arrangement", InfeasibleReason.OPENING_FIT
    explanation = (
        f"None of the {tried} layouts this version of the engine can produce fits this "
        f"programme on the plot. In the closest one, {what} for {room} could not be placed. "
        "This does not mean the home is impossible to design."
    )
    params = {**base.params, "attempts": len(attempts)}
    return FeasibilityReport(
        FeasibilityClass.NO_SUPPORTED_LAYOUT, code, explanation, params, base.constraints
    )


__all__ = [
    "Attempt",
    "GenerationResult",
    "compile_problem",
    "generate",
    "rect_or_none",
    "soft_constraints",
]
