"""Checkpoint 3.2 review: rooms added in open space on real plans.

For each web fixture plan (real engine output, synthetic test ruleset), derives the insertion
slots and tries, in every slot, each enclosed room type at its smallest size (clear minimums
plus the walls, on the grid) and at the slot's full size. Counts the outcomes (accepted, refused
with its code, rejected by the validator), checks every accepted result (no overlap, canonical
graph, one door from the host, deterministic body, open area reduced by the room's footprint)
and keeps the first accepted room of up to four types for the montage. Times slot derivation
and the edits.

    cd apps/api && uv run python scripts/review_houseplan_insertions.py OUT_DIR
"""

import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT / "scripts"))

from benchmark_houseplans import intent_of, load  # noqa: E402

from p2b.core.vocabulary import OpeningKind  # noqa: E402
from p2b.houseplans.engine import HousePlan, plan_geometry, sha256_of  # noqa: E402
from p2b.houseplans.engine.derive import analyse  # noqa: E402
from p2b.houseplans.engine.edit import BatchRejected, apply_edit, edit  # noqa: E402
from p2b.houseplans.engine.graph_edit import Change, _rebuild, room_rects  # noqa: E402
from p2b.houseplans.engine.insertion import InsertionSlot, insertion_slots  # noqa: E402
from p2b.houseplans.engine.model import dump  # noqa: E402
from p2b.houseplans.engine.ops import AddRoomOutside  # noqa: E402
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


def sizes(slot: InsertionSlot, rules: RulesetContent, room_type: Any) -> list[tuple[int, int]]:
    rule = rules.rooms[room_type]
    step = rules.grid_mm

    def up(v: int) -> int:
        return -(-v // step) * step

    depth = up(rule.min_short_mm + slot.depth_allowance_mm)
    length = up(
        max(
            rule.min_short_mm,
            -(-rule.min_area_mm2 // max(1, depth - slot.depth_allowance_mm)),
        )
        + slot.length_allowance_mm
    )
    full = (slot.max_depth_mm - slot.max_depth_mm % step, slot.length_mm - slot.length_mm % step)
    out = [(depth, length)] if depth <= slot.max_depth_mm and length <= slot.length_mm else []
    return [*out, full] if full not in out else out


def require(ok: bool, what: str) -> None:
    if not ok:
        raise SystemExit(f"integrity check failed: {what}")


def checked(plan: HousePlan, edited: HousePlan, op: AddRoomOutside, rules: RulesetContent) -> None:
    before, after = room_rects(plan.floors[0]), room_rects(edited.floors[0])
    new = next(k for k in after if k not in before)
    require({k: v for k, v in after.items() if k != new} == before, "rooms moved")
    keys = list(after)
    require(
        all(
            after[a].overlap_area(after[b]) == 0 for i, a in enumerate(keys) for b in keys[i + 1 :]
        ),
        "overlap",
    )
    floor = edited.floors[0]
    rebuilt = _rebuild(floor, after, Change(rects=after, rooms=list(floor.rooms)), rules)
    require(dump(rebuilt) == dump(floor), "graph not canonical")
    doors = [
        o
        for k, o in analyse(edited).openings.items()
        if set(o.connects) == {op.host_room, new} and o.opening.kind == OpeningKind.DOOR
    ]
    require(len(doors) == 1, "door")
    again, _ = apply_edit(plan, [op], rules)
    require(sha256_of(again.body()) == sha256_of(edited.body()), "not deterministic")
    open_before = sum(a.area_mm2 for a in plan_geometry(plan, rules).floors[0].open_areas)
    open_after = sum(a.area_mm2 for a in plan_geometry(edited, rules).floors[0].open_areas)
    require(open_before - open_after == after[new].area, "open area")


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    corpus, rules, _ = load(API_ROOT / "tests" / "fixtures" / "houseplans")
    types = [t for t, r in rules.rooms.items() if r.enclosed]
    timings: dict[str, list[float]] = {"slots": [], "insert": []}
    report: dict[str, Any] = {}
    for name in CASES:
        plan = HousePlan.model_validate(
            json.loads((FIXTURES / f"{name}.json").read_text("utf-8"))["document"]
        )
        intent = intent_of(corpus[name], rules)
        start = time.perf_counter()
        slots = insertion_slots(plan, rules)
        timings["slots"].append((time.perf_counter() - start) * 1000)
        outcomes: Counter[str] = Counter()
        invalid: Counter[str] = Counter()
        steps: list[dict[str, Any]] = [
            {"label": "generated", "op": None, "geometry": dump(plan_geometry(plan, rules))}
        ]
        shown: set[str] = set()
        for slot in slots:
            for room_type in types:
                for depth, length in sizes(slot, rules, room_type):
                    op = AddRoomOutside(
                        host_room=slot.host_room,
                        type=room_type,
                        side=slot.side,
                        offset_mm=slot.offset_mm,
                        length_mm=length,
                        depth_mm=depth,
                    )
                    start = time.perf_counter()
                    try:
                        result = edit(
                            plan,
                            [op],
                            rules,
                            intent=intent,
                            ruleset_version=None,
                            ruleset_sha256=None,
                        )
                    except BatchRejected as rejected:
                        outcomes[rejected.rejected.code.value] += 1
                        continue
                    finally:
                        timings["insert"].append((time.perf_counter() - start) * 1000)
                    if not result.report.valid:
                        outcomes["INVALID"] += 1
                        for code in sorted({e.code.value for e in result.report.errors}):
                            invalid[code] += 1
                        continue
                    outcomes["VALID"] += 1
                    checked(plan, result.plan, op, rules)
                    if room_type.value not in shown and len(shown) < 4:
                        shown.add(room_type.value)
                        new = sorted(
                            set(room_rects(result.plan.floors[0])) - set(room_rects(plan.floors[0]))
                        )
                        steps.append(
                            {
                                "label": f"ADD_ROOM_OUTSIDE {room_type.value}",
                                "op": dump(op),
                                "geometry": dump(plan_geometry(result.plan, rules)),
                                "changed_rooms": new,
                            }
                        )
        report[name] = {
            "slots": len(slots),
            "outcomes": dict(outcomes),
            "validator_codes": dict(invalid),
        }
        (out / f"{name}.json").write_text(
            json.dumps({"case": name, "steps": steps}, separators=(",", ":")), "utf-8"
        )
        print(name, len(slots), dict(outcomes))
    stats = {
        k: {
            "median_ms": round(statistics.median(v), 2),
            "max_ms": round(max(v), 2),
            "count": len(v),
        }
        for k, v in timings.items()
        if v
    }
    (out / "summary.json").write_text(
        json.dumps({"cases": report, "timings": stats}, indent=2), "utf-8"
    )
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
