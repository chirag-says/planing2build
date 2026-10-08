"""Experiment only, not production (Checkpoint 2 report, aspect criterion): what if ASPECT_EXCESS
charged a fixed 1000 per violating room on top of the approved magnitude? Re-solves the shared
VALID cases with that term, then scores the result with the APPROVED Scorer, and compares rooms
over aspect limit and quality with Checkpoint 1. Needs a prior local benchmark JSON:

    cd apps/api && uv run python scripts/benchmark_houseplans.py --json ../../SYSTEM_BLUEPRINT/\
02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_2_ASSETS/benchmark_local.json
    uv run python ../../tools/spikes/cp2_layout/aspect_count_experiment.py"""

import json
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
API = REPO / "apps" / "api"
sys.path[:0] = [str(API / "scripts"), str(API / "src")]
import p2b.houseplans.engine.objective as obj  # noqa: E402
from benchmark_houseplans import intent_of, load, run  # noqa: E402
from p2b.houseplans.engine import ZonedLocalSearchSolver, fixture_fit, score_plan  # noqa: E402

corpus, rules, cp1 = load(API / "tests" / "fixtures" / "houseplans")
ASSETS = REPO / "SYSTEM_BLUEPRINT" / "02_IMPLEMENTATION" / "AI_DESIGN_ENGINE_CHECKPOINT_2_ASSETS"
base = json.loads((ASSETS / "benchmark_local.json").read_text("utf-8"))
shared = [r for r in base["rows"] if r["outcome"] == "VALID" and r.get("cp1", {}).get("outcome") == "VALID"]
original = {r["case"] for r in base["rows"] if r["group"] == "original"}

orig_terms = obj.room_terms


def counted(rule, w, h):
    t = orig_terms(rule, w, h)
    return replace(t, aspect_excess=t.aspect_excess + 1000) if t.over_aspect else t


obj.room_terms = counted
zoned = ZonedLocalSearchSolver(rules, fixture_fit(rules))
tot = {"all": [0, 0, 0, 0, 0, 0], "orig": [0, 0, 0, 0, 0, 0]}
valid_orig = 0
for r in base["rows"]:
    if r["group"] == "original" and r["expect"] == "FEASIBLE":
        res = run(intent_of(corpus[r["case"]], rules), rules, zoned)
        valid_orig += res.outcome == "VALID"
for r in shared:
    res = run(intent_of(corpus[r["case"]], rules), rules, zoned)
    obj.room_terms = orig_terms  # report with the approved Scorer
    q = score_plan(res.plan, rules)
    obj.room_terms = counted
    row = [r["cp1"]["aspect_violations"], r["aspect_violations"], q.aspect_violations,
           r["cp1"]["quality"], r["quality"], q.total]
    print(f"{r['case']:34s} asp cp1={row[0]} cp2={row[1]} exp={row[2]}  q cp1={row[3]} cp2={row[4]} exp={row[5]}")
    for k in ("all",) + (("orig",) if r["case"] in original else ()):
        tot[k] = [a + b for a, b in zip(tot[k], row)]
for k, v in tot.items():
    print(k, "aspect cp1/cp2/exp", v[:3], "ratio cp2", round(v[1] / v[0], 3), "exp", round(v[2] / v[0], 3),
          "| quality ratio cp2", round(v[4] / v[3], 3), "exp", round(v[5] / v[3], 3))
print("original feasible VALID with experiment:", valid_orig, "/ 11")
