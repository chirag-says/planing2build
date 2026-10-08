# Plan2Build: AI design engine, Checkpoint 2.2.1 report (parking and space allocation)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_2_2_1_REPORT.md` |
| Date | 2026-10-07 |
| Basis | `AI_DESIGN_ENGINE_CHECKPOINT_2_2_REPORT.md` (limitation L-1), `AI_DESIGN_ENGINE_CHECKPOINT_2_1_REPORT.md`, Chirag's Checkpoint 2.2.1 brief of 2026-10-07 |
| Branch | `houseplans-checkpoint-1`. Checkpoint 1 is `22628ab` (tag `houseplans-cp1`, unchanged). Checkpoints 2, 2.1, 2.2 and 2.2.1 are in the working tree, **not committed, not tagged** |
| Scope | Parking and spare-space allocation only. No editor, Gemini, LLM, 3D, VPS, deployment or OR-Tools work |
| Review | **Accepted by Chirag on 2026-10-07** (stated in the Checkpoint 3 brief) |
| Ruleset | All values are the **SYNTHETIC / TEST ONLY** ruleset. No new rule value was added. Production parking standards stay open (AD-05, CP2-U1) |
| Assets | `AI_DESIGN_ENGINE_CHECKPOINT_2_2_1_ASSETS/`: `svg/` (every VALID plan), `montage_cp2_2_vs_cp2_2_1.html`, `benchmark_local.json`. CP2.2 evidence stays in `AI_DESIGN_ENGINE_CHECKPOINT_2_2_ASSETS/` |

---

## A. CP2.2 baseline

CP2.2 plans and the CP2.2 benchmark were saved before any change. The Scorer did not change in this checkpoint, so CP2.2 and CP2.2.1 totals compare directly.

| Measure (52 VALID plans with parking) | CP2.2 |
|---|---|
| Parking clear area ÷ required area (spaces × space size), mean | 2.57 |
| Median | 1.64 |
| Worst | 13.5 (a 1 × 2 m two-wheeler in a 4.15 × 6.5 m cell) |
| Plans over 1.25 / 1.6 / 2 × | 45 / 29 / 18 |
| 3bhk_50x60 two cars | 8.20 × 8.55 m clear for two cars needing 5 × 5 m |

## B. Parking root cause

Audit of how parking enters the engine (brief Part 1):

| Question | Finding |
|---|---|
| Minimum dimensions | `LayoutProblem.parking.clear_w_mm × clear_d_mm` = spaces × ruleset space size (synthetic: car 2.5 × 5.0 m, two-wheeler 1.0 × 2.0 m). The compiler's only parking constraint is clear ≥ that size |
| Initial dimensions | Since CP2.2 the parking starts at its least size (start weight 0) |
| Surplus allocation | Parking is a leaf of the layout tree, so it takes a whole cell: a share of the front band beside the living room, the head of a stepped side column, the head of a wing or of the courtyard's service column, or the full-depth end of the linear row. The cell's size is set by its neighbours (the rooms behind it, the band depth, the column width), not by the car |
| Open-space splits | Parking was never part of an open split; open areas were separate leaves |
| Effect on rooms behind | A room behind or beside the parking got only an interior wall where the parking covered its side |
| Treated differently from open space | Yes, and badly: parking is not an enclosed room, so no Scorer term reads its size. Any surplus in its cell cost the search nothing, so it stayed there |

Root cause: **the car space and its layout cell were the same rectangle.** Whatever geometry the neighbours left in the cell became "parking". In 50x60 the parking column had to match the 10.55 m depth of living, dining and kitchen beside it, while the only room behind the car was a 1.95 m bath, so the car got 8.6 m of depth.

## C. Geometry change

One mechanism, in one place (`compile.ZonedProblem.boxes` and `bay`), used by the sizing evaluator, the readable shortfalls, the Scorer's facts and the placement:

**The parking bay.** The parking cell stays in the tree; the parking room is the bay inside it. Along each axis:

1. if the cell is longer than the required clear size plus at most an interior wall either side (on the grid) by **at least `zoning.open_space_min_mm`**, the parking keeps exactly that size and the rest of the cell is left unbuilt, an open court, side yard or forecourt;
2. otherwise the parking keeps the whole cell extent: a remainder narrower than one usable open strip stays as apron instead of becoming a sliver.

The bay keeps the road edge (front) and the house side: in a cell at a side boundary of the plot it moves away from that boundary, so the open strip runs along the plot edge; in an inner cell it moves towards the plot's centre line.

What this means:

| Brief requirement | How it is met |
|---|---|
| Starts at the required envelope | Unchanged start (least size); the bay is the required envelope whenever surplus exists |
| Controlled extra space only when useful | Extra space below one open strip (synthetic 1.5 m) stays as apron; larger surplus never goes to the car |
| No arbitrary absorption | The car's rectangle is bounded at required + walls + less than one strip |
| Remainder becomes open space | The remainder is unbuilt; rooms facing it get exterior walls, exactly as for any open area |
| No invented rooms | The remainder is not a room; programme equals the request (test) |
| No forced construction | Built area does not grow; it shrinks by the parking surplus |
| Existing contracts | HousePlan schema unchanged; validator unchanged; parking room still at least the required size; the open remainder is absence of rooms, as every open area already is |
| No new rule value | The threshold is the existing `zoning.open_space_min_mm`. Rulesets without it keep the old behaviour |

Because the bay can turn a neighbour's interior wall (against parking) into an exterior wall (against the open remainder), the existing exact-inset check re-sizes a candidate when the wall pattern changed; nothing new was needed there. A trial of an extra pair-move escape after that re-size changed no case and was removed.

**Scoring (brief Part 5).** No parking term was added. Geometry alone bounds the parking (section D), so a score would only duplicate it. No weight changed.

## D. Before and after parking dimensions

Clear dimensions in the built plans (m, from `derive.analyse`; quality from the benchmark):

| Case | Parking | CP2.2 clear | CP2.2.1 clear | Quality CP2.2 → CP2.2.1 |
|---|---|---|---|---|
| 3bhk_50x60_wide_two_cars | 2 cars | 8.20 × 8.55 | 5.05 × 5.10 | 2,762 → 2,758 |
| 2bhk_40x80_west_two_cars | 2 cars | 6.55 × 5.00 | 5.05 × 5.00 | 1,586 → 1,586 |
| 3bhk_45x70_two_cars_puja | 2 cars | 7.05 × 5.00 | 5.05 × 5.00 | 4,081 → 4,081 |
| 4bhk_50x80_large_two_cars | 2 cars | 8.70 × 5.00 | 5.05 × 5.00 | 2,926 → 2,926 |
| q06 4BHK 60x90 | 2 cars | 6.35 × 8.35 | 6.35 × 5.10 (width is apron) | 3,288 → 3,278 |
| c05 4BHK 60x100 | 2 cars | 6.84 × 8.65 | 6.54 × 5.10 (width is apron) | 2,925 → 2,951 |
| 3bhk_30x60_single_car_vastu | 1 car | 3.22 × 6.70 | 3.22 × 5.10 | 1,953 → 1,943 |
| prop_wide_60x35 | 1 car | 6.11 × 5.00 | 2.55 × 5.00 | 9,341 → 10,963 |
| prop_very_wide_80x28 | 1 car | 2.51 × 5.90 | 2.51 × 5.90 (apron) | 2,700 → 2,700 |
| 2bhk_30x50_north_twowheeler_open | 1 two-wheeler | 4.15 × 6.50 | 1.05 × 2.10 | 885 → 921 |
| 2bhk_30x55_west_twowheeler | 1 two-wheeler | 3.57 × 5.50 | 1.05 × 2.10 | 669 → 665 |
| c14 2BHK 30x45 open plan | 1 two-wheeler | 4.15 × 5.00 | 1.05 × 2.10 | 897 → 930 |
| c12 2BHK 45x45 | 1 two-wheeler | 2.85 × 2.15 | 1.05 × 2.05 | 3,371 → 3,394 |
| q15 2BHK 50x30 | 1 two-wheeler | 2.95 × 2.30 | 1.05 × 2.30 | 2,145 → 2,108 |

Whole corpus, 52 VALID plans with parking:

| Measure | CP2.2 | CP2.2.1 |
|---|---|---|
| Parking clear area ÷ required, mean | 2.57 | 1.30 |
| Median | 1.64 | 1.22 |
| Worst | 13.5 | 2.05 |
| Over 1.25 / 1.6 / 2 × | 45 / 29 / 18 | 24 / 9 / 1 |

The 9 plans still over 1.6 × are all apron cases: on one axis the remainder was under 1.5 m (for example a car cell 3.94 m wide, 1.44 m more than the car; a two-wheeler cell 1.95 m wide). For a 1 m two-wheeler an apron under 1.5 m is a large ratio; it is a small area.

Every parking type and topology the brief lists was checked on each family's best layout (`tests/test_houseplan_cp2_2_1.py`, matrix): one car, two cars, one, two and three two-wheelers; beside the living room (front band), beside the service zone (stepped column with the kitchen behind, courtyard service column), stepped fronts, wings, courtyard, side wing, spine and linear. In every case the parking is at least the required size, less than required + walls + one open strip on each axis, on the road edge, and touching the house.

## E. Before and after architectural quality

All 75 corpus cases, scored by the same Scorer:

| Measure (55 cases VALID in both) | CP2.2 | CP2.2.1 |
|---|---|---|
| Feasibility | 55 VALID | 55 VALID, **no outcome changed** |
| Sum of quality totals | 210,860 | 212,560 (+0.8%) |
| Cases better / same / worse | | 12 / 34 / 10 |
| Rooms over 2.5 × preferred | 4 | 4 |
| Rooms over 1.6 × preferred | 66 | 67 |
| Rooms over aspect limit | 62 | 59 |
| Sum of aspect excess | 9,152 | 9,383 |
| Rooms over aspect limit by > 10% | 15 | 16 |
| Sum of WET_CLUSTER | 23,211 | 23,878 (+2.9%) |
| Mean circulation share | 11.7% | 11.7% |
| Plans byte-identical | | 45 of 75 (every plan without parking, every INFEASIBLE case, and plans whose cell had no surplus) |

Quality is maintained, not improved: the Scorer never saw parking size, so removing parking surplus cannot show in it. The small costs come from honest geometry: a room side that now faces the open remainder needs an exterior wall (50 mm thicker inset than the interior wall against parking), so a few rooms lose 50 mm of clear size.

The ten worse cases: nine move 0.0 to 4.1% (`2bhk_30x50_north_twowheeler_open` +4.1%, `c14` +3.7%, `c25` +3.6%, the rest under 2%). `prop_wide_60x35` moves +17%: its CP2.2 winner put a bedroom behind the parking, where it needed only an interior wall; with the bay that side faces the forecourt, the bedroom ends 20 mm short of its 2.8 m minimum, and the engine picks the next layout. Both versions of that plan have the same flaw (a living room about 10 to 11 m wide across a wide, shallow plot; CP2.2 limitation); the reviewed geometry is not a better or worse house in any other respect.

Runtime and memory (development machine, same corpus and command as CP2.2, idle machine):

| Measure | CP2.2 | CP2.2.1 | Gate |
|---|---|---|---|
| Normal p95 | 700 ms | 719 ms | ≤ 1000: met |
| Difficult p99 | 1,779 ms | 1,846 ms | ≤ 3000: met |
| Infeasible search p95 | 909 ms | 888 ms | ≤ 1500: met |
| Median per-case ratio (normal / difficult) | | 1.04 / 1.04 | |
| Validation p95 / repair p95 | 2.8 / 7.4 ms | 2.6 / 7.2 ms | met |
| RSS peak / traced one generation | 63.7 / 2.0 MB | 64.3 / 2.1 MB | met |
| Threads 1 / 2 / 4, p95 | 742 / 1,527 / 2,966 ms | 754 / 1,612 / 3,204 ms | |
| Determinism; fresh-process hashes | 75/75; equal | 75/75; equal | met |

A first CP2.2.1 run measured infeasible-search p95 at 1,433 ms; re-timing the slow cases alone gave CP2.2 speeds, and the re-run on an idle machine (above) confirmed it was machine load (Docker Desktop had just started).

## F. Regression results

| Check | Result |
|---|---|
| CP1 goldens (3) | Byte-identical |
| CP1 baseline record (50 plans) | Unchanged (test passes) |
| Validator authority, 39 codes, negative corpus | Unchanged; tests pass |
| HousePlan schema | Unchanged; contracts unchanged |
| Determinism | 75/75; fresh process reproduces every hash |
| 11/11 original feasible VALID; 25x40 VALID | Yes |
| Labels | Unchanged; every FEASIBLE label VALID, every INFEASIBLE label INFEASIBLE, 0 invalid attempts |
| CP2.2 tests (stepped fronts, carport courts, courtyard, wet-aware order, slab moves, ROOM_SIZE_OUTLIER, fit, no invented rooms) | All pass unchanged |
| Zoned goldens | 4 regenerated (the parking cases 30x50, 40x80, 50x80, 25x40); 4 unchanged |
| Static checks | ruff, ruff format, mypy strict (318 files), import-linter 5/5 |
| Full API suite | 755 passed, 0 failed, 1 skipped (`test_r2_cors`: needs the local storage container, unrelated), 25 min, with the local database |

New tests (`tests/test_houseplan_cp2_2_1.py`, 19): the bay rule at the left and right boundaries and inside, depth behind the car, apron below one open strip, no rule without `open_space_min_mm`; the 50x60 regression; a two-wheeler bay instead of a column; no room added; and the family × parking-type matrix in section D.

## G. Visual comparison

`AI_DESIGN_ENGINE_CHECKPOINT_2_2_1_ASSETS/montage_cp2_2_vs_cp2_2_1.html` (CP2.2 left, CP2.2.1 right), reviewed in the browser:

| Case | Finding |
|---|---|
| 50x60 3BHK, 2 cars | Fixed. The 8.2 × 8.6 m parking rectangle is gone: a 5 × 5 m carport against the living room, and an L-shaped open court along the plot side and behind the car, up to the common bath. Rooms unchanged |
| 40x80 2BHK, 2 cars | Carport 6.55 → 5.05 m wide; an open strip along the plot edge beside it. Rooms unchanged |
| 45x70 3BHK, 2 cars | Carport 7.05 → 5.05 m wide; open strip at the plot edge, joining the court beside bedroom 3. Rooms unchanged |
| 50x80 4BHK, 2 cars | Carport 8.70 → 5.05 m wide; open strip at the plot edge. Rooms unchanged |
| 60x90 4BHK | Carport 8.35 → 5.10 m deep; the open court now runs from the car to the kitchen. Width is apron (6.35 m) |
| 60x100 4BHK | Same as 60x90: a larger court behind a 5.1 m deep carport |
| 80x28 wide | Unchanged: the car's full-depth cell has only 0.9 m spare, kept as apron |
| 30x50 two-wheeler | Fixed. The 4.15 × 6.5 m "parking" column is now a 1.05 × 2.1 m bay against the living room with an open forecourt; bedroom 1 now has an outside wall onto it |
| 45x45 two-wheeler | Small bay at the front corner, open forecourt beside it |
| 60x35 wide | Parking 6.1 → 2.55 m wide with open space beside it; the engine moved to the next layout (section E). The 11 m living room is present in both versions |

In every reviewed plan the parking now reads as a car space, and surplus reads as open court or forecourt. No reviewed plan got worse as a house; 60x35 scores worse for the reason in section E.

## H. Remaining limitations

| ID | Limitation | Note |
|---|---|---|
| L-1 | Apron: a remainder under one open strip (synthetic 1.5 m) stays with the parking, so 9 plans keep 1.6 to 2.05 × the required area | By design: a sliver of open space is worse than a wider apron. AD-05 may set a different strip width or an explicit apron rule |
| L-2 | The open remainder is not drawn or labelled in the plan (open areas are absence of rooms, as since CP2.1) | A forecourt or court label for the 2D view is a presentation decision for the next checkpoint |
| L-3 | Rooms beside the remainder take an exterior wall; a few lose 50 mm and one layout (60x35) became infeasible by 20 mm | Honest geometry. A bay anchored to keep a room's side covered was not added: it would favour walls over open space |
| L-4 | Parking is still inside the footprint and on the road edge only by the topologies' construction; the validator does not check road access | CP2-U1 (front-setback parking) remains open |
| L-5 | CP2.2 limitations L-2 to L-10 are unchanged (60x90 long wing, linear corridor, row-depth baths and puja, 22x60, wide-shallow and deep-narrow plots with cars, latency vs CP2.1) | Out of scope here |

## I. Verdict

**CP2.2.1 ACCEPTED** (recommendation; Chirag's explicit approval decides; nothing is committed or tagged).

| Brief Part 8 condition | Met? | Evidence |
|---|---|---|
| 50x60 parking regression fixed | Yes | 8.20 × 8.55 → 5.05 × 5.10 m clear for two 2.5 × 5 m cars; open court instead |
| No feasible case becomes infeasible | Yes | 0 outcome changes across 75 cases |
| No previously good major layout regresses | Yes | The reviewed large and two-car plans keep their rooms; quality equal or within 1%. The one +17% case (60x35) was already a poor layout in CP2.2 |
| Architectural quality maintained or improved | Maintained | Quality +0.8%, rooms over 2.5 × unchanged, aspect count 62 → 59, circulation unchanged |
| Parking stops absorbing arbitrary surplus | Yes | Mean 2.57 → 1.30 × required, worst 13.5 → 2.05, over 2 × 18 → 1; the remainder is apron below one open strip |
| Deterministic hashes stable | Yes | 75/75 deterministic, fresh-process equal; every plan without parking byte-identical to CP2.2 |
| Full tests pass | Yes | 755 passed |
| Visual inspection confirms | Yes | Section G |

Stop here as instructed. The next checkpoint is planned separately.
