"""Checkpoint 2 benchmark for concept floor plan generation (AI_DESIGN_ENGINE_CHECKPOINT_2).

Runs the benchmark corpus through the production solver (ZONED_LOCAL_SEARCH) and, as the baseline,
the Checkpoint 1 solver with the frozen Checkpoint 1 ruleset. Both are scored by the same Scorer and
weights. Reports per case: input, expected class, solver, outcome (VALID / INFEASIBLE with its
classification), quality score, aspect violations, circulation share, latency and body hash; then
latency percentiles per class, validation and repair latency, memory, determinism and the
Checkpoint 2 acceptance figures. Optionally writes debug SVGs of every VALID plan.

Self-contained: it needs the engine (`src`) and the fixture directory only, so it runs inside the
production worker image with the script and fixtures mounted read-only:

    docker run --rm --cpus 2 -v "$PWD/apps/api/scripts:/app/scripts:ro" \\
      -v "$PWD/apps/api/tests/fixtures/houseplans:/app/fixtures:ro" <api-image> \\
      python scripts/benchmark_houseplans.py --fixtures /app/fixtures --label vps

Locally: cd apps/api && uv run python scripts/benchmark_houseplans.py --svg-dir OUT --json OUT.json

Timings are wall-clock on the machine it runs on. A laptop run is not evidence for the VPS gate
(CP2-U5)."""

import argparse
import gc
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from p2b.houseplans.engine import (  # noqa: E402
    DesignInputs,
    DeterministicMVPLayoutSolver,
    GenerationResult,
    HousePlan,
    LayoutSolver,
    Normalised,
    RulesetContent,
    ZonedLocalSearchSolver,
    fixture_fit,
    generate,
    normalise,
    plan_geometry,
    repair,
    score_plan,
    sha256_of,
    validate,
)
from p2b.houseplans.engine.derive import analyse  # noqa: E402
from p2b.houseplans.engine.generate import compile_problem  # noqa: E402
from p2b.houseplans.engine.intent import ArchitecturalIntent  # noqa: E402
from p2b.houseplans.engine.solver import LayoutProblem  # noqa: E402
from p2b.houseplans.engine.solver.zoned_ls import search  # noqa: E402

TARGETS_MS = {  # CP2 VPS gate (section 0 of AI_DESIGN_ENGINE_CHECKPOINT_2)
    "normal_p95": 1000,
    "difficult_p99": 3000,
    "infeasible_precheck_p95": 500,
    "infeasible_search_p95": 1500,
    "validation_p95": 20,
    "repair_p95": 100,
}
MEMORY_TARGET_MB = 50
SEED = 7


# ---------- measurement helpers ----------


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile; 0.0 for no values."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered) / 100))
    return ordered[min(rank, len(ordered)) - 1]


def rss_mb() -> tuple[float, float]:
    """(current, peak) resident set in MB: /proc on Linux, the process counters on Windows."""
    status = Path("/proc/self/status")
    if status.exists():
        fields = dict(line.split(":", 1) for line in status.read_text().splitlines() if ":" in line)
        return int(fields["VmRSS"].split()[0]) / 1024, int(fields["VmHWM"].split()[0]) / 1024
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        c = Counters()
        c.cb = ctypes.sizeof(c)
        kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return c.WorkingSetSize / 2**20, c.PeakWorkingSetSize / 2**20
    return 0.0, 0.0


# ---------- the corpus ----------


CORPORA: dict[str, tuple[str, ...]] = {
    "cp2": ("benchmark_cp2.json",),
    "quality": ("benchmark_cp2_1_quality.json",),
    "cp2_2": ("benchmark_cp2_2_quality.json",),
}
CORPORA["all"] = CORPORA["cp2"] + CORPORA["quality"] + CORPORA["cp2_2"]


def load(
    fixtures: Path, corpus_name: str = "all"
) -> tuple[dict[str, Any], RulesetContent, RulesetContent]:
    corpus: dict[str, Any] = {}
    for file in CORPORA[corpus_name]:
        corpus |= json.loads((fixtures / file).read_text("utf-8"))["cases"]
    rules = RulesetContent.model_validate(
        json.loads((fixtures / "ruleset_synthetic_test_only.json").read_text("utf-8"))
    )
    cp1 = RulesetContent.model_validate(
        json.loads((fixtures / "ruleset_synthetic_cp1_test_only.json").read_text("utf-8"))
    )
    return corpus, rules, cp1


def intent_of(case: dict[str, Any], rules: RulesetContent) -> ArchitecturalIntent:
    outcome = normalise(
        case["answers"],
        DesignInputs.model_validate(case["design_inputs"]),
        rules,
        question_set_version=1,
        requirement_version=1,
        ruleset_version=1,
        ruleset_sha256=sha256_of(rules),
    )
    if not isinstance(outcome, Normalised):
        raise SystemExit(f"case does not normalise: {outcome}")
    return outcome.intent


def run(
    intent: ArchitecturalIntent, rules: RulesetContent, solver: LayoutSolver
) -> GenerationResult:
    return generate(
        intent,
        rules,
        ruleset_version=1,
        ruleset_sha256=sha256_of(rules),
        solver=solver,
        seed=SEED,
    )


def summary_of(case: dict[str, Any]) -> str:
    a, d = case["answers"], case["design_inputs"]
    s = a["setbacks"]
    parking = f"{d.get('parking_spaces', 0)} {d.get('parking_kind', '').lower()}".strip()
    return (
        f"{a['plot_width_ft']}x{a['plot_depth_ft']} ft {a['facing']}, setbacks F{s['FRONT']} "
        f"B{s['BACK']} L{s['LEFT']} R{s['RIGHT']}; {a['bedrooms']} bed, {a['bathrooms']} bath "
        f"({d['attached_bathrooms']} attached); pooja {a['pooja_room']}; parking "
        f"{parking if a['car_parking'] else 'none'}"
    )


def perturbed(plan: HousePlan) -> HousePlan | None:
    """The plan with its first door slid off its wall (OPENING_OUTSIDE_HOST): an AUTO repair."""
    an = analyse(plan)
    data = plan.model_dump(mode="json", by_alias=True)
    for o in sorted(data["floors"][0]["openings"], key=lambda o: o["id"]):
        if o["kind"] == "DOOR":
            o["offset_mm"] = an.walls[o["wall"]].length - o["width_mm"] // 2
            return HousePlan.model_validate(data)
    return None


# ---------- the benchmark ----------


def benchmark(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    corpus, rules, cp1 = load(Path(args.fixtures), args.corpus)
    if args.cases:
        corpus = {k: v for k, v in corpus.items() if k in set(args.cases.split(","))}
    rss_start, _ = rss_mb()
    fit_t = time.perf_counter()
    fit = fixture_fit(rules)
    fit_ms = (time.perf_counter() - fit_t) * 1000
    zoned = ZonedLocalSearchSolver(rules, fit)
    rows: list[dict[str, Any]] = []
    cold_ms: dict[str, float] = {}
    for name, case in corpus.items():
        intent = intent_of(case, rules)
        timings, hashes, rankings = [], [], []
        result: GenerationResult | None = None
        for i in range(args.repeats + 1):
            gc.collect()
            t = time.perf_counter()
            result = run(intent, rules, zoned)
            ms = (time.perf_counter() - t) * 1000
            if i == 0:
                cold_ms[name] = ms  # first run of this case: caches warm from other cases only
            else:
                timings.append(ms)
            hashes.append(result.plan.meta.body_sha256 if result.plan else "INFEASIBLE")
        problem = compile_problem(intent, rules)
        families_feasible: list[str] = []
        for _ in range(2):
            if not isinstance(problem, LayoutProblem):
                break
            found = search(problem, rules, fit)
            ranking = [(c.name, c.quality.total if c.quality else -1) for c in found.feasible]
            rankings.append(hashlib.sha256(json.dumps(ranking).encode()).hexdigest()[:16])
            families_feasible = sorted({c.family.value for c in found.feasible})
        if result is None:
            raise SystemExit("no run")
        feasibility = result.feasibility
        row: dict[str, Any] = {
            "case": name,
            "group": case["group"],
            "expect": case["expect"],
            "latency_class": case["latency_class"],
            "input": summary_of(case),
            "solver": zoned.kind.value,
            "outcome": result.outcome,
            "classification": feasibility.classification.value if feasibility else None,
            "code": feasibility.code.value if feasibility else None,
            "explanation": feasibility.explanation if feasibility else None,
            "topology": result.topology,
            "family": result.family.value if result.family else None,
            "families_applicable": sorted(v.family.value for v in result.verdicts if v.applicable),
            "families_feasible": families_feasible,
            "exercises": case.get("exercises", []),
            "candidates_enumerated": result.candidates_enumerated,
            "candidates_sized": result.candidates_sized,
            "feasible_layouts": result.feasible_layouts,
            "attempts": [f"{a.topology}:{a.result}" for a in result.attempts],
            "latency_ms_p50": round(percentile(timings, 50), 1),
            "latency_ms_max": round(max(timings), 1) if timings else 0.0,
            "latency_ms_runs": [round(t, 1) for t in timings],
            "body_sha256": hashes[-1],
            "deterministic": len(set(hashes)) == 1 and len(set(rankings)) <= 1,
            "ranking_sha": rankings[0] if rankings else None,
        }
        q = score_plan(result.plan, rules) if result.plan is not None else None
        if result.plan is not None and q is not None:
            row |= {
                "quality": q.total,
                "aspect_violations": q.aspect_violations,
                "circulation_share_milli": q.circulation_share_milli,
                "terms": {t.kind.value: t.score_milli for t in q.terms},
            }
            if args.svg_dir:
                write_svg(Path(args.svg_dir), name, case, result.plan, rules, row)
            if args.plans_dir:  # the plan itself, so a later Scorer can rescore it
                target = Path(args.plans_dir)
                target.mkdir(parents=True, exist_ok=True)
                (target / f"{name}.json").write_text(
                    json.dumps(result.plan.model_dump(mode="json", by_alias=True)), "utf-8"
                )
            row |= time_validation_and_repair(result.plan, rules, intent, args.repeats)
        if not args.no_baseline:
            row["cp1"] = baseline(case, cp1, rules)
        rows.append(row)
        if not args.quiet:
            print(line_of(row), flush=True)
    rss_end, rss_peak = rss_mb()
    tracemalloc.start()
    sample = next(iter(corpus.values()))
    run(intent_of(sample, rules), rules, zoned)
    _, traced_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "label": args.label,
        "machine": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpus": os.cpu_count(),
        },
        "repeats": args.repeats,
        "fixture_fit_ms": round(fit_ms, 1),
        "cold_ms": {k: round(v, 1) for k, v in cold_ms.items()},
        "rows": rows,
        "memory_mb": {
            "rss_start": round(rss_start, 1),
            "rss_end": round(rss_end, 1),
            "rss_peak": round(rss_peak, 1),
            "increase_peak_over_start": round(rss_peak - rss_start, 1),
            "traced_peak_one_generation": round(traced_peak / 2**20, 1),
        },
        "wall_seconds": round(time.perf_counter() - started, 1),
    }


def time_validation_and_repair(
    plan: HousePlan, rules: RulesetContent, intent: ArchitecturalIntent, repeats: int
) -> dict[str, Any]:
    v_ms, r_ms = [], []
    broken = perturbed(plan)
    repaired_ok = None
    for _ in range(max(1, repeats)):
        t = time.perf_counter()
        validate(plan, rules, intent=intent)
        v_ms.append((time.perf_counter() - t) * 1000)
        if broken is not None:
            t = time.perf_counter()
            fixed = repair(broken, rules, intent=intent)
            r_ms.append((time.perf_counter() - t) * 1000)
            repaired_ok = fixed.report.valid
    return {"validation_ms": v_ms, "repair_ms": r_ms, "repair_restored_valid": repaired_ok}


def baseline(case: dict[str, Any], cp1: RulesetContent, rules: RulesetContent) -> dict[str, Any]:
    """The Checkpoint 1 solver on the frozen Checkpoint 1 ruleset, scored with the CP2 weights."""
    result = run(intent_of(case, cp1), cp1, DeterministicMVPLayoutSolver())
    out: dict[str, Any] = {"outcome": result.outcome}
    q = score_plan(result.plan, rules) if result.plan is not None else None
    if result.plan is not None and q is not None:
        out |= {
            "quality": q.total,
            "aspect_violations": q.aspect_violations,
            "circulation_share_milli": q.circulation_share_milli,
            "body_sha256": result.plan.meta.body_sha256,
        }
    return out


def write_svg(
    target: Path,
    name: str,
    case: dict[str, Any],
    plan: HousePlan,
    rules: RulesetContent,
    row: dict[str, Any],
) -> None:
    from render_houseplan_debug import render

    target.mkdir(parents=True, exist_ok=True)
    terms = ", ".join(f"{k.lower()} {v}" for k, v in row["terms"].items() if v)
    notes = (
        summary_of(case),
        f"topology {row['topology']}; quality {row['quality']} (lower is better); "
        f"rooms over aspect limit {row['aspect_violations']}; "
        f"circulation {row['circulation_share_milli'] / 10:.1f}%",
        f"terms (milli): {terms or 'all met'}",
        f"body sha256 {row['body_sha256'][:16]}; synthetic test ruleset; not a drawing",
    )
    title = (
        f"{name}: debug render, {row.get('family') or 'no family'}, "
        f"{plan.meta.generator.solver.value} {plan.meta.generator.solver_version}"
    )
    svg = render(plan_geometry(plan, rules), title, notes)
    (target / f"{name}.svg").write_text(svg, "utf-8")


def line_of(row: dict[str, Any]) -> str:
    q = row.get("quality", "")
    cls = row["classification"] or ""
    cp1 = row.get("cp1", {})
    return (
        f"{row['case']:42s} {row['expect']:10s} {row['outcome']:10s} {cls:19s} q={q!s:6s} "
        f"asp={row.get('aspect_violations', '')!s:2s} p50={row['latency_ms_p50']:7.1f}ms "
        f"{row['family'] or '':28s} feasible={len(row['families_feasible'])} "
        f"cp1={cp1.get('outcome', '')}/{cp1.get('quality', '')}"
    )


# ---------- summary ----------


def summarise(report: dict[str, Any]) -> dict[str, Any]:
    rows = report["rows"]
    by_class: dict[str, list[float]] = {"normal": [], "difficult": []}
    infeasible: dict[str, list[float]] = {"PROVEN": [], "NO_SUPPORTED_LAYOUT": []}
    validation, repair_ms = [], []
    for r in rows:
        if r["outcome"] == "INFEASIBLE" and r["classification"]:
            infeasible[r["classification"]].extend(r["latency_ms_runs"])
        elif r["latency_class"] in by_class:
            by_class[r["latency_class"]].extend(r["latency_ms_runs"])
        validation.extend(r.get("validation_ms", []))
        repair_ms.extend(r.get("repair_ms", []))
    latency: dict[str, dict[int, float]] = {
        "normal": {q: round(percentile(by_class["normal"], q), 1) for q in (50, 95, 99)},
        "difficult": {q: round(percentile(by_class["difficult"], q), 1) for q in (50, 95, 99)},
        "infeasible_precheck": {
            q: round(percentile(infeasible["PROVEN"], q), 1) for q in (50, 95, 99)
        },
        "infeasible_search": {
            q: round(percentile(infeasible["NO_SUPPORTED_LAYOUT"], q), 1) for q in (50, 95, 99)
        },
        "validation": {q: round(percentile(validation, q), 2) for q in (50, 95, 99)},
        "repair": {q: round(percentile(repair_ms, q), 2) for q in (50, 95, 99)},
    }
    samples = {
        "normal": by_class["normal"],
        "difficult": by_class["difficult"],
        "infeasible_precheck": infeasible["PROVEN"],
        "infeasible_search": infeasible["NO_SUPPORTED_LAYOUT"],
        "validation": validation,
        "repair": repair_ms,
    }

    def gate(kind: str, q: int, target: str) -> bool | None:
        """None when the run had no sample of this kind: not measured is not a pass."""
        return latency[kind][q] <= TARGETS_MS[target] if samples[kind] else None

    gates = {
        "normal_p95": gate("normal", 95, "normal_p95"),
        "difficult_p99": gate("difficult", 99, "difficult_p99"),
        "infeasible_precheck_p95": gate("infeasible_precheck", 95, "infeasible_precheck_p95"),
        "infeasible_search_p95": gate("infeasible_search", 95, "infeasible_search_p95"),
        "validation_p95": gate("validation", 95, "validation_p95"),
        "repair_p95": gate("repair", 95, "repair_p95"),
        "memory": report["memory_mb"]["increase_peak_over_start"] <= MEMORY_TARGET_MB,
        "determinism": all(r["deterministic"] for r in rows),
    }
    original = [r for r in rows if r["group"] == "original" and r["expect"] == "FEASIBLE"]
    shared = [
        r for r in rows if r["outcome"] == "VALID" and r.get("cp1", {}).get("outcome") == "VALID"
    ]
    acceptance = {
        "original_expected_feasible": len(original),
        "original_valid": sum(r["outcome"] == "VALID" for r in original),
        "cp1_valid_cases_still_valid": all(
            r["outcome"] == "VALID" for r in rows if r.get("cp1", {}).get("outcome") == "VALID"
        ),
        # Section 0 / item 3: on the shared VALID cases, rooms over aspect limit and mean quality
        # score each <= 50% of Checkpoint 1's, and no case scores worse. Reported for the original
        # spike corpus (the doc's basis) and for the whole benchmark.
        "shared_original": versus_cp1([r for r in shared if r["group"] == "original"]),
        "shared_all": versus_cp1(shared),
        "invalid_attempts": sum(a.endswith(":INVALID") for r in rows for a in r["attempts"]),
        "expected_infeasible_but_valid": [
            r["case"] for r in rows if r["expect"] == "INFEASIBLE" and r["outcome"] == "VALID"
        ],
    }
    counts = {k: len(v) for k, v in samples.items()}
    return {"latency_ms": latency, "samples": counts, "gates": gates, "acceptance": acceptance}


def versus_cp1(both: list[dict[str, Any]]) -> dict[str, Any]:
    cp1_q = sum(r["cp1"]["quality"] for r in both)
    cp2_q = sum(r["quality"] for r in both)
    cp1_a = sum(r["cp1"]["aspect_violations"] for r in both)
    cp2_a = sum(r["aspect_violations"] for r in both)
    return {
        "cases": len(both),
        "mean_quality_cp1": round(cp1_q / len(both), 1) if both else None,
        "mean_quality_cp2": round(cp2_q / len(both), 1) if both else None,
        "quality_ratio": round(cp2_q / cp1_q, 3) if cp1_q else None,
        "aspect_violations_cp1": cp1_a,
        "aspect_violations_cp2": cp2_a,
        "aspect_ratio": round(cp2_a / cp1_a, 3) if cp1_a else None,
        "cases_scoring_worse": [r["case"] for r in both if r["quality"] > r["cp1"]["quality"]],
        "cases_with_more_aspect_violations": [
            r["case"] for r in both if r["aspect_violations"] > r["cp1"]["aspect_violations"]
        ],
    }


def quality_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Architectural quality of the VALID plans per corpus group: mean score, rooms over aspect,
    mean of every term (milli), winning families, and how many families had a feasible layout."""
    out: dict[str, Any] = {}
    for group in sorted({r["group"] for r in rows}):
        valid = [r for r in rows if r["group"] == group and r["outcome"] == "VALID"]
        if not valid:
            continue
        terms: dict[str, list[int]] = {}
        for r in valid:
            for kind, value in r["terms"].items():
                if value is not None:
                    terms.setdefault(kind, []).append(value)
        won: dict[str, int] = {}
        for r in valid:
            won[r["family"]] = won.get(r["family"], 0) + 1
        out[group] = {
            "valid": len(valid),
            "cases": sum(1 for r in rows if r["group"] == group),
            "mean_quality": round(sum(r["quality"] for r in valid) / len(valid), 1),
            "aspect_violations": sum(r["aspect_violations"] for r in valid),
            "mean_circulation_share_milli": round(
                sum(r["circulation_share_milli"] for r in valid) / len(valid), 1
            ),
            "term_means_milli": {k: round(sum(v) / len(v), 1) for k, v in sorted(terms.items())},
            "families_won": dict(sorted(won.items())),
            "distinct_families_won": len(won),
            "mean_families_feasible": round(
                sum(len(r["families_feasible"]) for r in valid) / len(valid), 2
            ),
        }
    return out


def concurrency_check(args: argparse.Namespace, threads: int) -> dict[str, Any]:
    """Normal-class generations run `threads` at a time in one process, on threads, as the
    worker runs engine jobs (`asyncio.to_thread`): per-generation latency under contention."""
    from concurrent.futures import ThreadPoolExecutor

    corpus, rules, _ = load(Path(args.fixtures), args.corpus)
    zoned = ZonedLocalSearchSolver(rules, fixture_fit(rules))
    intents = [intent_of(c, rules) for c in corpus.values() if c["latency_class"] == "normal"]

    def timed(intent: ArchitecturalIntent) -> float:
        t = time.perf_counter()
        run(intent, rules, zoned)
        return (time.perf_counter() - t) * 1000

    rss_before, _ = rss_mb()
    wall, cpu = time.perf_counter(), time.process_time()
    with ThreadPoolExecutor(max_workers=threads) as pool:
        times = list(pool.map(timed, intents * max(1, args.repeats)))
    wall, cpu = time.perf_counter() - wall, time.process_time() - cpu
    rss_after, rss_peak = rss_mb()
    return {
        "threads": threads,
        "samples": len(times),
        "p50": round(percentile(times, 50), 1),
        "p95": round(percentile(times, 95), 1),
        "p99": round(percentile(times, 99), 1),
        "wall_s": round(wall, 2),
        "throughput_per_s": round(len(times) / wall, 2) if wall else None,
        # process CPU seconds per wall second: about 1.0 means one core busy (the GIL bound)
        "cpu_cores_used": round(cpu / wall, 2) if wall else None,
        "rss_mb": {
            "before": round(rss_before, 1),
            "after": round(rss_after, 1),
            "peak": round(rss_peak, 1),
        },
    }


def fresh_process_hashes(args: argparse.Namespace) -> list[str]:
    code = [
        sys.executable,
        __file__,
        "--fixtures",
        args.fixtures,
        "--corpus",
        args.corpus,
        "--hashes-only",
    ]
    if args.cases:
        code += ["--cases", args.cases]
    out = subprocess.run(code, capture_output=True, text=True, check=True, timeout=1800)  # noqa: S603
    return out.stdout.strip().split(",")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--fixtures", default=str(ROOT / "tests" / "fixtures" / "houseplans"))
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--cases", default="")
    parser.add_argument("--svg-dir", default="")
    parser.add_argument("--json", default="")
    parser.add_argument("--plans-dir", default="", help="write each VALID plan's JSON here")
    parser.add_argument("--label", default="local")
    parser.add_argument("--no-baseline", action="store_true")
    parser.add_argument(
        "--fresh-process", action="store_true", help="recheck hashes in a new process"
    )
    parser.add_argument("--hashes-only", action="store_true")
    parser.add_argument("--corpus", choices=sorted(CORPORA), default="all")
    parser.add_argument(
        "--concurrency", default="", help="comma list of thread counts, e.g. 2,4 (normal cases)"
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    if args.hashes_only:
        corpus, rules, _ = load(Path(args.fixtures), args.corpus)
        names = args.cases.split(",") if args.cases else list(corpus)
        zoned = ZonedLocalSearchSolver(rules, fixture_fit(rules))
        hashes: list[str] = []
        for name in names:
            r = run(intent_of(corpus[name], rules), rules, zoned)
            hashes.append((r.plan.meta.body_sha256 or "") if r.plan else "INFEASIBLE")
        print(",".join(hashes))
        return
    report = benchmark(args)
    report["summary"] = summarise(report)
    report["summary"]["quality"] = quality_summary(report["rows"])
    if args.concurrency:
        report["summary"]["concurrency"] = [
            concurrency_check(args, int(n)) for n in args.concurrency.split(",")
        ]
    if args.fresh_process:
        here = [r["body_sha256"] for r in report["rows"]]
        same = fresh_process_hashes(args) == here
        report["summary"]["gates"]["fresh_process_hashes_equal"] = same
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1) + "\n", "utf-8")
    print(
        json.dumps(
            {
                "label": args.label,
                **report["summary"],
                "memory_mb": report["memory_mb"],
                "fixture_fit_ms": report["fixture_fit_ms"],
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
