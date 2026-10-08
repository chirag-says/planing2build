"""ZonedLocalSearchSolver (Checkpoint 2; topology selection and two-phase search in Checkpoint 2.1):
the production solver. Pure Python, no dependency.

For a LayoutProblem it

1. selects topologies (`zoning.select`): every applicable family's candidate trees, with a
   verdict per family saying why it does or does not apply;
2. compiles each into a sizing problem (`compile.ZonedProblem`) and keeps, per family, the
   `objective.family_pool` best starting points (stable: ties keep enumeration order);
3. sizes that pool coarsely: cyclic coordinate search with steps of 1200 and 600 mm,
   accepting a move only if it strictly lowers (hard shortfall, sizing objective), so it
   terminates. Moves: one cut line ±step; two consecutive cut lines of one split together (a
   room or a group shifts, keeping its size);
4. ranks the coarse results by (shortfall, full Scorer total) and finishes, at 300 and 150 mm and
   the grid, the best `objective.candidate_limit`, with an equal share reserved per family so
   every applicable family is compared at full precision;
   a finished layout still short of a hard constraint by a little (at most 400 mm in total) gets a
   bounded escape: pairs of cut lines moved together;
5. re-checks every finished layout with exact wall insets and ranks the feasible ones by the full
   Scorer total (ties: enumeration order), the infeasible ones by total shortfall.

No randomness and integer arithmetic only: the same problem gives the same ranking on every
machine. The seed is accepted for the interface and unused. The solver never decides validity:
the pipeline builds each ranked layout into a HousePlan and the validator judges it."""

from dataclasses import dataclass

from p2b.core.vocabulary import InfeasibleReason, RoomType, SolverKind, TopologyFamily
from p2b.houseplans.engine.compile import Shortfall, Values, ZonedProblem
from p2b.houseplans.engine.fit import FitRule
from p2b.houseplans.engine.objective import QualityScore
from p2b.houseplans.engine.ruleset import RulesetContent
from p2b.houseplans.engine.solver import Infeasible, InfeasibleDetail, LayoutProblem, SolveOutcome
from p2b.houseplans.engine.zoning import Verdict, select, zoning_inputs

COARSE_STEPS = (1200, 600)
FINE_STEPS = (300, 150)
MAX_EVALUATIONS = 6_000  # per candidate and phase; a bound, never reached on the corpus
ESCAPE_BUDGET = 1_500  # per finished candidate left with a small shortfall
ESCAPE_TOTAL = 6_000  # per search
ESCAPE_MAX_SHORTFALL = 400  # mm: larger shortfalls are a topology misfit, not a stuck search


@dataclass(frozen=True)
class CandidateLayout:
    zp: ZonedProblem
    values: Values
    violation: int  # total hard shortfall (0 = every compiled hard constraint met)
    shortfalls: tuple[Shortfall, ...]
    quality: QualityScore | None  # full Scorer result, for feasible layouts
    index: int  # enumeration order, the deterministic tie-break

    @property
    def name(self) -> str:
        return self.zp.name

    @property
    def family(self) -> TopologyFamily:
        return self.zp.family


@dataclass(frozen=True)
class ZonedSearch:
    feasible: tuple[CandidateLayout, ...]  # best first
    closest: CandidateLayout | None  # the least-short infeasible layout, for explanations
    enumerated: int
    sized: int
    evaluations: int
    verdicts: tuple[Verdict, ...] = ()


def _steps(steps: tuple[int, ...], grid: int, finish: bool) -> tuple[int, ...]:
    out = [s for s in steps if s > grid and s % grid == 0]
    return (*out, grid) if finish else tuple(out)


Move = tuple[bool, tuple[tuple[int, int], ...]]  # (slab?, (variable, step) pairs)


def _deltas(zp: ZonedProblem, step: int) -> list[Move]:
    """The move set at one step size, in a fixed order: each cut line ±step; each pair of
    consecutive cut lines of one split ±step together (whatever lies between shifts, keeping
    its size); and each slab move: every cut line along the same axis at or beyond a cut's
    current position moves ±step together, so the parts crossing that line shrink or grow and
    everything beyond it shifts (a whole band of the house moves towards an open yard)."""
    out: list[Move] = []
    n = len(zp.var_names)
    for d in (step, -step):
        out.extend((False, ((i, d),)) for i in range(n))
        out.extend((False, ((i, d), (j, d))) for i, j in zp.prog.siblings)
        out.extend((True, ((i, d),)) for i in range(n))
    return out


def _apply(zp: ZonedProblem, v: Values, move: Move) -> tuple[int, ...]:
    slab, pairs = move
    cand = list(v)
    if slab:
        (i, d), axis = pairs[0], zp.prog.var_axis[pairs[0][0]]
        line = v[i]
        for j, a in enumerate(zp.prog.var_axis):
            if a == axis and v[j] >= line:
                cand[j] += d
    else:
        for var, d in pairs:
            cand[var] += d
    return tuple(cand)


def size(
    zp: ZonedProblem,
    start: Values | None = None,
    steps: tuple[int, ...] = (*COARSE_STEPS, *FINE_STEPS),
    budget: int = MAX_EVALUATIONS,
) -> tuple[Values, tuple[int, int], int] | None:
    """Cyclic coordinate search: moves are tried in a fixed cycle; an improving move is applied and
    tried again at once; a step size ends after one full cycle without improvement. Returns the
    sizing, its (violation, objective) and the evaluations used, or None if the start is
    degenerate."""
    v = start if start is not None else zp.initial()
    best = zp.evaluate(v)
    used = 1
    if best is None:
        return None
    # results by sizing, for this call only: the cycle revisits sizings (a move and its undo, a
    # slab move that moves a single cut), and the memo is freed with the call
    seen: dict[Values, tuple[int, int] | None] = {v: best}
    for step in steps:
        deltas = _deltas(zp, step)
        if not deltas:
            break
        i, idle = 0, 0
        while idle < len(deltas) and used < budget:
            cand = _apply(zp, v, deltas[i])
            if cand in seen:
                result = seen[cand]
            else:
                result = seen[cand] = zp.evaluate(cand)
            used += 1
            if result is not None and result < best:
                v, best, idle = cand, result, 0
                continue  # the same move again
            i = (i + 1) % len(deltas)
            idle += 1
    return v, best, used


def escape(
    zp: ZonedProblem, v: Values, best: tuple[int, int], budget: int
) -> tuple[Values, tuple[int, int], int]:
    """For a sizing left with a hard shortfall: every pair of cut lines moved together (each
    ±150 mm or ±1 grid step), the best improving pair applied, until none improves. Bounded by
    `budget` evaluations. A shortfall that needs two cuts in different splits to move at once (a
    room grows only if its neighbour moves first) is out of reach of single moves."""
    used = 0
    n = len(zp.var_names)
    steps = [s for s in (150, zp.g) if s % zp.g == 0]
    while best[0] > 0 and used < budget:
        found: tuple[tuple[int, int], Values] | None = None
        for step in steps:
            for i in range(n):
                for j in range(i + 1, n):
                    for di in (step, -step):
                        for dj in (step, -step):
                            cand = list(v)
                            cand[i] += di
                            cand[j] += dj
                            result = zp.evaluate(tuple(cand))
                            used += 1
                            if result is not None and result < (found[0] if found else best):
                                found = (result, tuple(cand))
            if found is not None or used >= budget:
                break
        if found is None:
            break
        best, v = found
        sized = size(zp, v, (zp.g,), budget)
        if sized is not None:
            v, best, extra = sized
            used += extra
    return v, best, used


def search(
    problem: LayoutProblem,
    ruleset: RulesetContent,
    fit: dict[RoomType, FitRule],
    families: frozenset[TopologyFamily] | None = None,
) -> ZonedSearch:
    """The ranked layouts for a problem; `families` restricts the topology families tried (the
    benchmark and tests compare families one at a time; production tries all)."""
    obj = ruleset.objective
    if obj is None:
        return ZonedSearch((), None, 0, 0, 0)
    inputs = zoning_inputs(problem)
    selection = select(problem, ruleset, fit)
    topologies = [t for t in selection.topologies if families is None or t.family in families]
    compiled = [ZonedProblem(problem, ruleset, t, fit, inputs) for t in topologies]
    evaluations = len(compiled)

    # Phase 1: per family, the best starting points, sized coarsely.
    pools: dict[TopologyFamily, list[tuple[tuple[int, int], int, ZonedProblem, Values]]] = {}
    for i, zp in enumerate(compiled):
        start = zp.initial()
        first = zp.evaluate(start)
        if first is not None:
            pools.setdefault(zp.family, []).append((first, i, zp, start))
    coarse: list[tuple[tuple[int, int, int], int, ZonedProblem, Values]] = []
    for family in pools:
        pool = sorted(pools[family], key=lambda t: (t[0], t[1]))[: obj.family_pool]
        for _, i, zp, start in pool:
            sized = size(zp, start, _steps(COARSE_STEPS, zp.g, finish=False))
            if sized is None:
                continue
            values, (violation, _), used = sized
            evaluations += used
            key = (violation, zp.full_score(values).total, i)
            coarse.append((key, i, zp, values))
    coarse.sort(key=lambda t: t[0])

    # Phase 2: an equal share per family, then the best of the rest, finished at full precision.
    present = list(dict.fromkeys(t[2].family for t in coarse))
    quota = max(1, obj.candidate_limit // max(1, len(present)))
    chosen: list[tuple[tuple[int, int, int], int, ZonedProblem, Values]] = []
    for family in present:
        chosen += [t for t in coarse if t[2].family == family][:quota]
    taken = {t[1] for t in chosen}
    chosen += [t for t in coarse if t[1] not in taken][: max(0, obj.candidate_limit - len(chosen))]
    chosen.sort(key=lambda t: t[1])

    feasible: list[CandidateLayout] = []
    infeasible: list[CandidateLayout] = []
    escape_left = ESCAPE_TOTAL
    for _, index, zp, start in chosen:
        sized = size(zp, start, _steps(FINE_STEPS, zp.g, finish=True))
        if sized is None:
            continue
        values, result, used = sized
        evaluations += used
        if 0 < result[0] <= ESCAPE_MAX_SHORTFALL and escape_left > 0:
            values, result, used = escape(zp, values, result, min(ESCAPE_BUDGET, escape_left))
            evaluations += used
            escape_left -= used
        rects = zp.rects(values)
        if rects is None:
            continue
        if not zp.exact(rects):
            # The wall pattern changed while sizing; size again with the final pattern, once.
            zp.reset_insets(rects)
            again = size(zp, values)
            if again is None:
                continue
            values, _, used = again
            evaluations += used
            rects = zp.rects(values)
            if rects is None or not zp.exact(rects):
                continue
        shortfalls = tuple(zp.shortfalls(values))
        violation = sum(s.amount for s in shortfalls)
        if violation == 0:
            feasible.append(CandidateLayout(zp, values, 0, (), zp.full_score(values), index))
        else:
            ordered = tuple(sorted(shortfalls, key=lambda s: (-s.amount, s.room, s.code)))
            infeasible.append(CandidateLayout(zp, values, violation, ordered, None, index))
    feasible.sort(key=lambda c: (c.quality.total if c.quality else 0, c.index))
    closest = min(infeasible, key=lambda c: (c.violation, c.index)) if infeasible else None
    return ZonedSearch(
        tuple(feasible), closest, len(compiled), len(chosen), evaluations, selection.verdicts
    )


class ZonedLocalSearchSolver:
    """The LayoutSolver face of the search: the best-ranked layout. The pipeline uses `search`
    directly so it can fall back to the next layout when one does not build or validate."""

    kind = SolverKind.ZONED_LOCAL_SEARCH
    version = "1.1.0"

    def __init__(self, ruleset: RulesetContent, fit: dict[RoomType, FitRule]):
        self.ruleset, self.fit = ruleset, fit

    def solve(self, problem: LayoutProblem, *, seed: int) -> SolveOutcome:
        found = search(problem, self.ruleset, self.fit)
        if found.feasible:
            best = found.feasible[0]
            return best.zp.placed(best.values)
        reason = InfeasibleDetail(
            InfeasibleReason.DEPTH_EXCEEDED, {"candidates_tried": found.sized}
        )
        return Infeasible((reason,))
