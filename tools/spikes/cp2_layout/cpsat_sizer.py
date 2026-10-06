"""CP-SAT sizer for the same zoned structure and the same objective as local_search.py (research
spike; needs `ortools`, so it runs only in the separate worker image). One search worker, a fixed
seed and a deterministic time limit, per ADR-025."""

from __future__ import annotations

import math
import os

from ortools.sat.python import cp_model

from common import ASPECT_LIMIT_X10, W_AREA, W_ASPECT, W_CORRIDOR, Candidate, Layout, Spec, candidates, pref_area, scored
from p2b.core.vocabulary import InfeasibleReason, SolverKind
from p2b.houseplans.engine.solver import Infeasible, InfeasibleDetail, LayoutProblem, SolveOutcome

BUDGET = float(os.environ.get("CPSAT_BUDGET", "2.0"))  # deterministic time units per candidate
SCALE = 10**6


def solve_candidate(spec: Spec) -> tuple[Layout, str] | None:
    c, p, reg, g, a = spec.c, spec.p, spec.reg, spec.g, spec.a
    m = cp_model.CpModel()
    H = reg.h
    f = m.new_int_var(0, H // g, "f")
    r = m.new_int_var(0, H // g, "r") if c.rear else None
    s = m.new_int_var(0, reg.w // g, "s") if c.two_columns else None
    terms = []

    def room_terms(room, w_expr, d_expr, w_max, d_max) -> None:  # type: ignore[no-untyped-def]
        cw = m.new_int_var(0, w_max, f"cw_{room.key}")
        cd = m.new_int_var(0, d_max, f"cd_{room.key}")
        m.add(cw == w_expr - a)
        m.add(cd == d_expr - a)
        if spec.park_room is not None and room.key == spec.park_room.key:
            m.add(cw >= p.parking.clear_w_mm)
            m.add(cd >= p.parking.clear_d_mm)
            return
        m.add(cw >= room.min_short_mm)
        m.add(cd >= room.min_short_mm)
        area = m.new_int_var(0, w_max * d_max, f"a_{room.key}")
        m.add_multiplication_equality(area, [cw, cd])
        m.add(area >= room.min_area_mm2)
        if not scored(room):
            return
        pa = pref_area(room)
        dev = m.new_int_var(0, w_max * d_max, f"dev_{room.key}")
        m.add_abs_equality(dev, area - pa)
        terms.append((W_AREA * SCALE // pa, dev))
        lim = ASPECT_LIMIT_X10[room.room_type]
        ex1 = m.new_int_var(0, 10 * max(w_max, d_max), f"exw_{room.key}")
        ex2 = m.new_int_var(0, 10 * max(w_max, d_max), f"exd_{room.key}")
        m.add(ex1 >= 10 * cw - lim * cd)
        m.add(ex2 >= 10 * cd - lim * cw)
        coef = W_ASPECT * SCALE // (10 * math.isqrt(pa))
        terms.append((coef, ex1))
        terms.append((coef, ex2))

    f_mm = g * f
    rear_mm = g * r if r is not None else 0
    length = H - f_mm - rear_mm
    m.add(length >= g)
    # front band
    if spec.park_room is not None:
        room_terms(spec.park_room, spec.park_x[1] - spec.park_x[0], f_mm, reg.w, H)
    room_terms(spec.entry, spec.entry_x[1] - spec.entry_x[0], f_mm, reg.w, H)
    # spine and columns
    if c.two_columns:
        s_mm = g * s
        cols = [(reg.x0, s_mm + reg.x0), (s_mm + reg.x0 + spec.spine_w, reg.x1)]
        e0, e1 = spec.entry_x
        m.add(s_mm + reg.x0 + spec.spine_w - e0 >= p.void_span_mm)
        m.add(e1 - (s_mm + reg.x0) >= p.void_span_mm)
        m.add(s_mm + reg.x0 >= reg.x0 + g)
        m.add(s_mm + reg.x0 + spec.spine_w <= reg.x1 - g)
        if c.anchored is not None:
            if c.entry_column == 1:
                m.add(e1 - (s_mm + reg.x0 + spec.spine_w) >= p.door_span_mm)
            else:
                m.add((s_mm + reg.x0) - e0 >= p.door_span_mm)
    else:
        s0, s1 = spec.spine_x(Layout(0, 0, 0))
        cols = spec.column_x(Layout(0, 0, 0))
        e0, e1 = spec.entry_x
        if min(s1, e1) - max(s0, e0) < p.void_span_mm:
            return None
    terms.append((W_CORRIDOR * SCALE * spec.spine_w // (reg.w * reg.h), length))
    depth_vars: list[list[cp_model.IntVar]] = []
    for (x0, x1), groups in zip(cols, c.columns, strict=True):
        rooms = [rm for gr in groups for rm in gr.rooms]
        ks = [m.new_int_var(1, H // g, f"k_{rm.key}") for rm in rooms[:-1]]
        depth_vars.append(ks)
        used = sum(g * k for k in ks)
        last_d = length - used
        m.add(last_d >= g)
        heads = {gr.rooms[0].key for gr in groups if not (c.anchored is not None and gr is c.anchored)}
        for i, rm in enumerate(rooms):
            d_expr = g * ks[i] if i < len(ks) else last_d
            room_terms(rm, x1 - x0, d_expr, reg.w, H)
            if rm.key in heads:
                m.add(d_expr >= p.door_span_mm)
    if c.rear:
        room_terms(c.rear.rooms[0], reg.w, rear_mm, reg.w, H)
    m.minimize(sum(coef * v for coef, v in terms))
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 7
    solver.parameters.max_deterministic_time = BUDGET
    status = solver.solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    lay = Layout(f=g * solver.value(f), s=(reg.x0 + g * solver.value(s)) if s is not None else 0,
                 r=g * solver.value(r) if r is not None else 0,
                 cuts=[[g * solver.value(k) for k in ks] for ks in depth_vars])  # fmt: skip
    return lay, solver.status_name(status)


class CPSATZonedSolver:
    kind = SolverKind.CP_SAT
    version = "spike-cp2-cpsat-0"

    def __init__(self) -> None:
        self.last: list[tuple[Candidate, Layout, str, tuple[int, int] | None]] = []

    def solve(self, problem: LayoutProblem, *, seed: int) -> SolveOutcome:  # noqa: ARG002
        self.last = []
        for cand in candidates(problem):
            spec = Spec(problem, cand)
            out = solve_candidate(spec)
            if out is not None:
                lay, status = out
                self.last.append((cand, lay, status, spec.evaluate(lay)))
        feasible = [x for x in self.last if x[3] is not None and x[3][0] == 0]
        if not feasible:
            return Infeasible((InfeasibleDetail(InfeasibleReason.DEPTH_EXCEEDED, {"spike": "no feasible candidate"}),))
        best = min(feasible, key=lambda x: (x[3][1], self.last.index(x)))  # type: ignore[index]
        return Spec(problem, best[0]).placed(best[1])
