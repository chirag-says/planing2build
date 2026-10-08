"""Checkpoint 3.1 visual review and editing timings on real plans.

For each web fixture plan (real engine output, synthetic test ruleset), applies the first edit of
each kind the engine accepts and the validator passes, in a fixed search order: a local side move
(MOVE_EDGE), the same side moved as a whole line (MOVE_WALL), a new room (ADD_ROOM), a removed
room (DELETE_ROOM), a room type change and a door or window resize. Writes each step's document
summary and PlanGeometry for the web montage, the outcome counts of every attempt (accepted,
refused with its code, or rejected by the validator), and timings of the engine calls the API
makes (edit = apply + re-measure + validate; revert = replay from version 1 through the log).

    cd apps/api && uv run python scripts/review_houseplan_edits.py OUT_DIR
"""

import json
import statistics
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterator
from functools import partial
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT / "scripts"))

from benchmark_houseplans import intent_of, load  # noqa: E402

from p2b.core.vocabulary import OpeningKind, RoomSide, RoomType, WallKind  # noqa: E402
from p2b.houseplans.engine import HousePlan, plan_geometry, sha256_of  # noqa: E402
from p2b.houseplans.engine.edit import BatchRejected, EditResult, apply_edit, edit  # noqa: E402
from p2b.houseplans.engine.graph_edit import room_rects  # noqa: E402
from p2b.houseplans.engine.intent import ArchitecturalIntent  # noqa: E402
from p2b.houseplans.engine.model import dump  # noqa: E402
from p2b.houseplans.engine.ops import (  # noqa: E402
    AddRoom,
    DeleteRoom,
    MoveEdge,
    MoveOpening,
    MoveWall,
    PlanOp,
    SetOpening,
    SetRoomType,
)
from p2b.houseplans.engine.ruleset import RulesetContent  # noqa: E402

FIXTURES = API_ROOT.parent / "web" / "tests" / "fixtures" / "houseplans"
CASES = (
    "1bhk_25x40_south_small",
    "2bhk_30x50_north_twowheeler_open",
    "2bhk_40x80_west_two_cars",
    "3bhk_45x70_two_cars_puja",
    "3bhk_50x60_wide_two_cars",
    "q06_4bhk_60x90_large_two_cars_puja_utility",
    "prop_very_wide_80x28",
    "1bhk_30x40_no_parking",
)


def ms(fn: Callable[[], Any], runs: int = 5) -> float:
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000)
    return statistics.median(samples)


class Review:
    def __init__(self, plan: HousePlan, rules: RulesetContent, intent: ArchitecturalIntent):
        self.plan, self.rules, self.intent = plan, rules, intent
        self.outcomes: dict[str, Counter[str]] = {}

    def run(self, ops: list[PlanOp], plan: HousePlan | None = None) -> EditResult:
        return edit(
            plan or self.plan,
            ops,
            self.rules,
            intent=self.intent,
            ruleset_version=None,
            ruleset_sha256=None,
        )

    def first(self, kind: str, attempts: Iterator[PlanOp]) -> tuple[PlanOp, EditResult] | None:
        counts = self.outcomes.setdefault(kind, Counter())
        found = None
        for op in attempts:
            try:
                result = self.run([op])
            except BatchRejected as rejected:
                counts[rejected.rejected.code.value] += 1
                continue
            if result.report.valid:
                counts["VALID"] += 1
                found = found or (op, result)
            else:
                counts["INVALID"] += 1
        return found


def attempts(plan: HousePlan, rules: RulesetContent) -> dict[str, Callable[[], Iterator[PlanOp]]]:
    floor = plan.floors[0]
    rooms = floor.rooms
    types = [t for t, r in rules.rooms.items() if r.enclosed]

    def edges() -> Iterator[PlanOp]:
        for r in rooms:
            for side in RoomSide:
                for d in (300, -300):
                    yield MoveEdge(room=r.id, side=side, delta_mm=d)

    def lines() -> Iterator[PlanOp]:
        for w in floor.walls:
            if w.kind == WallKind.INTERIOR:
                for d in (300, -300):
                    yield MoveWall(wall=w.id, delta_mm=d)

    def adds() -> Iterator[PlanOp]:
        for r in rooms:
            for side in RoomSide:
                for t in (RoomType.UTILITY, RoomType.WC, RoomType.BEDROOM):
                    depth = rules.rooms[t].min_short_mm + rules.walls.interior_mm
                    yield AddRoom(host_room=r.id, type=t, side=side, depth_mm=depth)

    def deletes() -> Iterator[PlanOp]:
        for a in rooms:
            for b in rooms:
                if a.id != b.id:
                    yield DeleteRoom(room=a.id, merge_into=b.id)

    def retypes() -> Iterator[PlanOp]:
        for r in rooms:
            for t in types:
                if t != r.type:
                    yield SetRoomType(room=r.id, type=t)

    def resizes() -> Iterator[PlanOp]:
        for o in floor.openings:
            if o.kind == OpeningKind.WINDOW:
                yield SetOpening(
                    opening=o.id,
                    width_mm=o.width_mm + 300,
                    height_mm=o.height_mm,
                    sill_mm=o.sill_mm,
                )

    return {
        "MOVE_EDGE": edges,
        "MOVE_WALL": lines,
        "ADD_ROOM": adds,
        "DELETE_ROOM": deletes,
        "SET_ROOM_TYPE": retypes,
        "SET_OPENING": resizes,
    }


def summary(plan: HousePlan) -> dict[str, Any]:
    rects = room_rects(plan.floors[0])
    return {
        "rooms": {
            r.id: [rects[r.id].x0, rects[r.id].y0, rects[r.id].x1, rects[r.id].y1]
            for r in plan.floors[0].rooms
        },
        "compromises": [dump(c) for c in plan.compromises],
    }


def review_case(
    name: str,
    plan: HousePlan,
    rules: RulesetContent,
    intent: ArchitecturalIntent,
    timings: dict[str, list[float]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    review = Review(plan, rules, intent)
    before = summary(plan)["rooms"]
    steps: list[dict[str, Any]] = [
        {"label": "generated", "op": None, "geometry": dump(plan_geometry(plan, rules))}
    ]
    for kind, make in attempts(plan, rules).items():
        hit = review.first(kind, make())
        if hit is None:
            steps.append({"label": kind, "op": None, "geometry": None})
            continue
        op, result = hit
        timings.setdefault(kind, []).append(ms(partial(review.run, [op])))
        after = summary(result.plan)
        steps.append(
            {
                "label": kind,
                "op": dump(op),
                "geometry": dump(plan_geometry(result.plan, rules)),
                "summary": after,
                "changed_rooms": sorted(k for k, v in after["rooms"].items() if before.get(k) != v),
            }
        )

    # history: up to ten accepted edge moves in a row, then the replay a revert does
    chain: list[PlanOp] = []
    state = plan
    for op in attempts(plan, rules)["MOVE_EDGE"]():
        try:
            result = review.run([op], state)
        except BatchRejected:
            continue
        if result.report.valid:
            chain.append(op)
            state = result.plan
        if len(chain) == 10:
            break

    def replay() -> HousePlan:
        current = plan
        for op in chain:
            current, _ = apply_edit(current, [op], rules)
        return current

    if chain:
        timings.setdefault("revert_replay_per_revision", []).append(ms(replay, 3) / len(chain))
        if sha256_of(replay().body()) != sha256_of(state.body()):
            raise SystemExit(f"{name}: the replay does not reproduce the chain")
    # an edit that changes nothing: the fixed cost of apply, re-measure and validate
    same = plan.floors[0].openings[0]
    noop = MoveOpening(opening=same.id, offset_mm=same.offset_mm)
    timings.setdefault("edit_fixed_cost", []).append(ms(lambda: review.run([noop])))
    timings.setdefault("derive_geometry", []).append(ms(lambda: plan_geometry(plan, rules)))
    return steps, {kind: dict(c) for kind, c in review.outcomes.items()}


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    corpus, rules, _ = load(API_ROOT / "tests" / "fixtures" / "houseplans")
    timings: dict[str, list[float]] = {}
    report: dict[str, Any] = {}
    for name in CASES:
        data = json.loads((FIXTURES / f"{name}.json").read_text("utf-8"))
        plan = HousePlan.model_validate(data["document"])
        steps, outcomes = review_case(name, plan, rules, intent_of(corpus[name], rules), timings)
        report[name] = outcomes
        (out / f"{name}.json").write_text(
            json.dumps({"case": name, "steps": steps}, separators=(",", ":")), "utf-8"
        )
        print(name, {k: v.get("VALID", 0) for k, v in outcomes.items()})
    stats = {
        k: {"median_ms": round(statistics.median(v), 1), "max_ms": round(max(v), 1)}
        for k, v in timings.items()
    }
    (out / "summary.json").write_text(
        json.dumps({"outcomes": report, "timings": stats}, indent=2), "utf-8"
    )
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
