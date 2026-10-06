"""CP-SAT benchmark shaped like the Checkpoint 2 layout problem (spike only; not application code).

Twelve rooms on a 75 mm grid in a 7.6 m x 16.5 m region: containment, no overlap, minimum sides
and areas, six adjacencies with a shared edge long enough for a door, total area equal to the
region (no gaps), and a weighted objective toward preferred areas. One search worker, a fixed seed
and a deterministic time limit, as ADR-025 requires. Prints one JSON line per run and a summary.

Sizes here are benchmark inputs, not architectural rules.
"""

import argparse
import hashlib
import json
import resource
import statistics
import sys
import time

T_IMPORT = time.perf_counter()
RSS_BEFORE_KB = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
from ortools.sat.python import cp_model  # noqa: E402

IMPORT_S = time.perf_counter() - T_IMPORT
RSS_AFTER_IMPORT_KB = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

G = 75
W, D = 7600 // G, 16500 // G  # the 40 x 65 ft prototype's wall-centreline region, rounded
SPAN = 1100 // G + 1  # door plus jambs, in cells
# name, min short side (cells), min area (cells), preferred area (cells)
ROOMS = [
    ("living", 40, 2140, 2670), ("kitchen", 27, 1070, 1200), ("dining", 33, 1340, 1500),
    ("bed1", 37, 1600, 1870), ("bed2", 37, 1600, 1870), ("bed3", 37, 1600, 1870),
    ("bath_a", 20, 540, 600), ("bath_c", 20, 540, 600), ("puja", 20, 450, 500),
    ("passage", 14, 180, 400), ("parking", 34, 2230, 2300), ("utility", 16, 360, 400),
]  # fmt: skip
ADJACENT = [("kitchen", "dining"), ("dining", "living"), ("bath_a", "bed1"), ("passage", "living"),
            ("passage", "bed2"), ("passage", "bed3")]  # fmt: skip


def build() -> tuple[cp_model.CpModel, dict[str, tuple[cp_model.IntVar, ...]]]:
    m = cp_model.CpModel()
    v: dict[str, tuple[cp_model.IntVar, ...]] = {}
    xi, yi, areas, penalties = [], [], [], []
    for name, short, min_area, pref in ROOMS:
        x, y = m.new_int_var(0, W, f"x_{name}"), m.new_int_var(0, D, f"y_{name}")
        w, h = m.new_int_var(short, W, f"w_{name}"), m.new_int_var(short, D, f"h_{name}")
        a = m.new_int_var(min_area, W * D, f"a_{name}")
        m.add_multiplication_equality(a, [w, h])
        xe, ye = m.new_int_var(0, W, f"xe_{name}"), m.new_int_var(0, D, f"ye_{name}")
        m.add(xe == x + w)
        m.add(ye == y + h)
        xi.append(m.new_interval_var(x, w, xe, f"ix_{name}"))
        yi.append(m.new_interval_var(y, h, ye, f"iy_{name}"))
        dev = m.new_int_var(0, W * D, f"dev_{name}")
        m.add_abs_equality(dev, a - pref)
        penalties.append(dev)
        areas.append(a)
        v[name] = (x, y, w, h, a)
    m.add_no_overlap_2d(xi, yi)
    m.add(sum(areas) == W * D)  # the rooms tile the region: nothing left unassigned
    for p, q in ADJACENT:
        xp, yp, wp, hp, _ = v[p]
        xq, yq, wq, hq, _ = v[q]
        sides = [m.new_bool_var(f"{p}_{q}_{s}") for s in ("l", "r", "b", "t")]
        m.add_exactly_one(sides)
        for flag, touch, lo_a, hi_a, lo_b, hi_b in (
            (sides[0], xp + wp == xq, yp, yp + hp, yq, yq + hq),
            (sides[1], xq + wq == xp, yp, yp + hp, yq, yq + hq),
            (sides[2], yp + hp == yq, xp, xp + wp, xq, xq + wq),
            (sides[3], yq + hq == yp, xp, xp + wp, xq, xq + wq),
        ):
            m.add(touch).only_enforce_if(flag)
            lo, hi = m.new_int_var(0, max(W, D), ""), m.new_int_var(0, max(W, D), "")
            m.add_max_equality(lo, [lo_a, lo_b])
            m.add_min_equality(hi, [hi_a, hi_b])
            m.add(hi - lo >= SPAN).only_enforce_if(flag)
    m.minimize(sum(penalties))
    return m, v


# Zoned shape (ADR-025: zoning first, CP-SAT sizes within it): a front band (parking | living), a
# centre passage of fixed width, and two columns of stacked rooms. CP-SAT chooses the band depth,
# the parking and column widths and every room depth; rooms tile the region exactly.
PASSAGE = 1200 // G
LEFT = ["bed1", "bath_a", "bed2", "puja"]
RIGHT = ["dining", "kitchen", "utility", "bath_c", "bed3"]


def build_zoned() -> tuple[cp_model.CpModel, dict[str, tuple[cp_model.IntVar, ...]]]:
    m = cp_model.CpModel()
    spec = {name: (short, min_area, pref) for name, short, min_area, pref in ROOMS}
    v: dict[str, tuple[cp_model.IntVar, ...]] = {}
    penalties = []
    front = m.new_int_var(1, D, "front")
    park_w = m.new_int_var(spec["parking"][0], W, "park_w")
    left_w = m.new_int_var(1, W, "left_w")
    right_w = m.new_int_var(1, W, "right_w")
    m.add(left_w + PASSAGE + right_w == W)

    def room(name: str, width: cp_model.LinearExprT, depth: cp_model.IntVar) -> None:
        short, min_area, pref = spec[name]
        w = m.new_int_var(short, W, f"w_{name}")
        m.add(w == width)
        m.add(depth >= short)
        a = m.new_int_var(min_area, W * D, f"a_{name}")
        m.add_multiplication_equality(a, [w, depth])
        dev = m.new_int_var(0, W * D, f"dev_{name}")
        m.add_abs_equality(dev, a - pref)
        penalties.append(dev)
        v[name] = (w, depth, a)

    room("parking", park_w, front)
    room("living", W - park_w, front)
    for column, width in ((LEFT, left_w), (RIGHT, right_w)):
        depths = []
        for name in column:
            d = m.new_int_var(1, D, f"d_{name}")
            room(name, width, d)
            depths.append(d)
        m.add(sum(depths) + front == D)
    m.minimize(sum(penalties))
    return m, v


def solve(seed: int, budget: float, mode: str) -> dict[str, object]:
    model, v = build_zoned() if mode == "zoned" else build()
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.max_deterministic_time = budget
    solver.parameters.max_time_in_seconds = 60
    start = time.perf_counter()
    status = solver.solve(model)
    wall = time.perf_counter() - start
    solution = None
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        solution = {k: [solver.value(x) for x in xs] for k, xs in sorted(v.items())}
    digest = (
        hashlib.sha256(json.dumps(solution, sort_keys=True).encode()).hexdigest()
        if solution
        else None
    )
    return {"status": solver.status_name(status), "wall_s": round(wall, 3), "objective": solver.objective_value
            if solution else None, "solution_sha256": digest}  # fmt: skip


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--budget", type=float, default=5.0, help="deterministic time units")
    parser.add_argument("--mode", choices=("zoned", "free"), default="zoned")
    args = parser.parse_args()
    runs = [solve(args.seed, args.budget, args.mode) for _ in range(args.runs)]
    for r in runs:
        print(json.dumps(r))
    walls = sorted(r["wall_s"] for r in runs)  # type: ignore[type-var]
    summary = {
        "mode": args.mode,
        "python": sys.version.split()[0],
        "import_s": round(IMPORT_S, 3),
        "rss_before_import_mb": round(RSS_BEFORE_KB / 1024, 1),
        "rss_after_import_mb": round(RSS_AFTER_IMPORT_KB / 1024, 1),
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
        "runs": len(runs),
        "statuses": sorted({str(r["status"]) for r in runs}),
        "wall_p50_s": statistics.median(walls),
        "wall_p95_s": walls[max(0, round(0.95 * len(walls)) - 1)],
        "distinct_solutions": len({r["solution_sha256"] for r in runs}),
        "solution_sha256": runs[0]["solution_sha256"],
    }
    print("SUMMARY " + json.dumps(summary))


if __name__ == "__main__":
    main()
