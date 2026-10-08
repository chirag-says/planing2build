"""Deterministic sizer (research spike): coordinate descent over the candidate's cut positions,
step sizes 1200 → 50 mm, accepting only strict improvements of (violation, objective). No
randomness, integer arithmetic only, fixed variable order: same input, same output."""

from __future__ import annotations

from dataclasses import dataclass

from p2b.core.vocabulary import InfeasibleReason, SolverKind
from p2b.houseplans.engine.geom import ceil_div, ceil_to
from p2b.houseplans.engine.solver import Infeasible, InfeasibleDetail, LayoutProblem, SolveOutcome

from common import Candidate, Layout, Spec, candidates, pref_area

STEPS = (1200, 600, 300, 150, 50)


def initial(spec: Spec) -> Layout:
    p, a, g, reg = spec.p, spec.a, spec.g, spec.reg
    ew = spec.entry_x[1] - spec.entry_x[0] - a
    e_depth = max(spec.entry.min_short_mm, ceil_div(pref_area(spec.entry), max(1, ew))) + a
    f = ceil_to(max(spec.park_d, e_depth), g)
    s = ceil_to(reg.x0 + (reg.w - spec.spine_w) // 2, g)
    if spec.c.two_columns:  # keep the spine over the entry room
        e0, e1 = spec.entry_x
        s = min(max(s, e0), e1 - spec.spine_w)
    r = 0
    if spec.c.rear:
        rr = spec.c.rear.rooms[0]
        r = ceil_to(max(rr.min_short_mm, ceil_div(pref_area(rr), max(1, reg.w - a))) + a, g)
    lay = Layout(f=f, s=s, r=r)
    length = reg.h - f - r
    for (x0, x1), groups in zip(spec.column_x(lay), spec.c.columns, strict=True):
        rooms = [rm for gr in groups for rm in gr.rooms]
        weights = [pref_area(rm) for rm in rooms]
        total = sum(weights)
        depths = [ceil_to(length * w // total, g) for w in weights]
        lay.cuts.append(depths[:-1])
    return lay


def _moves(lay: Layout, spec: Spec, step: int) -> list[Layout]:
    out = []

    def clone() -> Layout:
        return Layout(lay.f, lay.s, lay.r, [list(c) for c in lay.cuts])

    for d in (step, -step):
        x = clone(); x.f += d; out.append(x)  # noqa: E702
        if spec.c.two_columns:
            x = clone(); x.s += d; out.append(x)  # noqa: E702
        if spec.c.rear:
            x = clone(); x.r += d; out.append(x)  # noqa: E702
        for ci, cuts in enumerate(lay.cuts):
            for i in range(len(cuts)):
                x = clone(); x.cuts[ci][i] += d; out.append(x)  # noqa: E702
                if i + 1 < len(cuts):  # move a cut line: one room grows, its neighbour shrinks
                    x = clone(); x.cuts[ci][i] += d; x.cuts[ci][i + 1] -= d; out.append(x)  # noqa: E702
    return out


def size(spec: Spec) -> tuple[Layout, tuple[int, int]] | None:
    lay = initial(spec)
    best = spec.evaluate(lay)
    if best is None:
        return None
    for step in STEPS:
        improved = True
        while improved:
            improved = False
            for cand in _moves(lay, spec, step):
                score = spec.evaluate(cand)
                if score is not None and score < best:
                    lay, best, improved = cand, score, True
    return lay, best


@dataclass
class SpikeResult:
    candidate: Candidate
    layout: Layout
    violation: int
    objective: int


class LocalSearchZonedSolver:
    kind = SolverKind.DETERMINISTIC_MVP  # spike only: no vocabulary change for research code
    version = "spike-cp2-ls-0"

    def __init__(self) -> None:
        self.last: list[SpikeResult] = []

    def solve(self, problem: LayoutProblem, *, seed: int) -> SolveOutcome:  # noqa: ARG002
        self.last = []
        for cand in candidates(problem):
            spec = Spec(problem, cand)
            out = size(spec)
            if out is not None:
                lay, (viol, obj) = out
                self.last.append(SpikeResult(cand, lay, viol, obj))
        feasible = [r for r in self.last if r.violation == 0]
        if not feasible:
            return Infeasible((InfeasibleDetail(InfeasibleReason.DEPTH_EXCEEDED, {"spike": "no feasible candidate"}),))
        best = min(feasible, key=lambda r: (r.objective, self.last.index(r)))
        return Spec(problem, best.candidate).placed(best.layout)
