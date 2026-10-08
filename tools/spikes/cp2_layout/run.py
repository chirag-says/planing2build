"""Run the corpus through the real engine with each sizer and print quality and latency.

    cd tools/spikes/cp2_layout && ../../../apps/api/.venv/Scripts/python run.py [--solver mvp|ls|cpsat]

Quality is measured on the final VALID HousePlan's PlanGeometry (clear dimensions), not on the
solver's own estimate, so every solver is judged the same way."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

HERE = Path(__file__).resolve().parent
API = Path(__import__("os").environ.get("P2B_API_DIR", HERE.parents[2] / "apps" / "api"))
sys.path[:0] = [str(HERE), str(API / "src"), str(API)]

from common import ASPECT_LIMIT_X10, PREF_AREA_FACTOR_X100  # noqa: E402
from corpus import CORPUS  # noqa: E402

from p2b.core.vocabulary import RoomType  # noqa: E402
from p2b.houseplans.engine import (  # noqa: E402
    DesignInputs, DeterministicMVPLayoutSolver, Normalised, generate, normalise, plan_geometry, sha256_of, validate,
)
from p2b.houseplans.engine import RulesetContent  # noqa: E402

RULES = RulesetContent.model_validate(json.loads(
    (API / "tests" / "fixtures" / "houseplans" / "ruleset_synthetic_test_only.json").read_text("utf-8")))
SHA = sha256_of(RULES)


def intent_of(name: str):  # type: ignore[no-untyped-def]
    answers, inputs = CORPUS[name]
    out = normalise(answers, DesignInputs.model_validate(inputs), RULES, question_set_version=1,
                    requirement_version=1, ruleset_version=1, ruleset_sha256=SHA)  # fmt: skip
    assert isinstance(out, Normalised), (name, out)
    return out.intent


def metrics(plan) -> dict[str, float]:  # type: ignore[no-untyped-def]
    geo = plan_geometry(plan, RULES).floors[0]
    aspects, devs, over, excess = [], [], 0, 0.0
    passage = total = 0
    for room in geo.rooms:
        w, d = room.clear_w_mm or 0, room.clear_d_mm or 0
        if not w or not d or room.type == RoomType.PARKING:
            continue
        area = w * d
        total += area
        if room.type == RoomType.PASSAGE:
            passage += area
            continue
        aspect = max(w, d) / min(w, d)
        aspects.append(aspect)
        rule = RULES.rooms[room.type]
        pref = rule.pref_area_mm2 or rule.min_area_mm2 * PREF_AREA_FACTOR_X100 // 100
        devs.append(abs(area - pref) / pref)
        limit = ASPECT_LIMIT_X10.get(room.type, 99) / 10
        if aspect > limit:
            over += 1
            excess += aspect - limit
    return {
        "max_aspect": round(max(aspects), 2),
        "mean_aspect": round(statistics.mean(aspects), 2),
        "rooms_over_aspect": over,
        "mean_area_dev": round(statistics.mean(devs), 3),
        "circulation_pct": round(100 * passage / total, 1),
        "aspect_excess_sum": round(excess, 2),
        "score": round(statistics.mean(devs) + 2 * excess + passage / total, 3),
    }


def make_solver(kind: str):  # type: ignore[no-untyped-def]
    if kind == "mvp":
        return DeterministicMVPLayoutSolver()
    if kind == "ls":
        from local_search import LocalSearchZonedSolver

        return LocalSearchZonedSolver()
    from cpsat_sizer import CPSATZonedSolver

    return CPSATZonedSolver()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solver", default="ls", choices=("mvp", "ls", "cpsat"))
    ap.add_argument("--repeat", type=int, default=5)
    args = ap.parse_args()
    solver = make_solver(args.solver)
    rows = []
    for name in CORPUS:
        intent = intent_of(name)
        times, hashes = [], set()
        result = None
        for _ in range(args.repeat):
            t = time.perf_counter()
            result = generate(intent, RULES, ruleset_version=1, ruleset_sha256=SHA, solver=solver, seed=7)
            times.append(time.perf_counter() - t)
            hashes.add(result.plan.meta.body_sha256 if result.plan else result.outcome)
        assert result is not None
        row = {"case": name, "solver": args.solver, "outcome": result.outcome, "topology": result.topology,
               "gen_ms_p50": round(1000 * statistics.median(times), 1), "gen_ms_max": round(1000 * max(times), 1),
               "deterministic": len(hashes) == 1}  # fmt: skip
        if result.outcome == "VALID" and result.plan is not None:
            row |= metrics(result.plan)
            t = time.perf_counter()
            for _ in range(20):
                validate(result.plan, RULES, intent=intent)
            row["validate_ms"] = round(1000 * (time.perf_counter() - t) / 20, 1)
        elif result.outcome == "INVALID" and result.report is not None:
            row["errors"] = sorted({e.code.value for e in result.report.errors})
        else:
            row["reason"] = result.reasons[0].code.value if result.reasons else None
        rows.append(row)
        print(json.dumps(row))
    tracemalloc.start()
    generate(intent_of("4bhk_50x80_large_two_cars"), RULES, ruleset_version=1, ruleset_sha256=SHA, solver=solver, seed=7)
    peak = tracemalloc.get_traced_memory()[1]
    valid = [r for r in rows if r["outcome"] == "VALID"]
    print("SUMMARY " + json.dumps({
        "solver": args.solver, "cases": len(rows), "valid": len(valid),
        "infeasible": sum(r["outcome"] == "INFEASIBLE" for r in rows),
        "invalid": sum(r["outcome"] == "INVALID" for r in rows),
        "deterministic": all(r["deterministic"] for r in rows),
        "mean_score": round(statistics.mean(r["score"] for r in valid), 3) if valid else None,
        "mean_max_aspect": round(statistics.mean(r["max_aspect"] for r in valid), 2) if valid else None,
        "rooms_over_aspect": sum(r["rooms_over_aspect"] for r in valid),
        "mean_circulation_pct": round(statistics.mean(r["circulation_pct"] for r in valid), 1) if valid else None,
        "gen_ms_p50_all": round(statistics.median(r["gen_ms_p50"] for r in rows), 1),
        "gen_ms_max_all": max(r["gen_ms_max"] for r in rows),
        "peak_alloc_mb_large_case": round(peak / 1e6, 1),
    }))  # fmt: skip


if __name__ == "__main__":
    main()
