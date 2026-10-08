# Plan2Build: AI design engine, Checkpoint 2.2 report (architectural quality refinement)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_2_2_REPORT.md` |
| Date | 2026-10-07 |
| Basis | `AI_DESIGN_ENGINE_CHECKPOINT_2_1_REPORT.md` (CP2.1 NOT ACCEPTED, VPS gate deferred), Chirag's Checkpoint 2.2 brief of 2026-10-07 |
| Branch | `houseplans-checkpoint-1`. Checkpoint 1 is `22628ab` (tag `houseplans-cp1`, unchanged). Checkpoints 2, 2.1 and 2.2 are in the working tree, **not committed, not tagged** |
| Scope | Plan quality only. No VPS, deployment, LLM, Gemini, image generation, 2D editor, 3D or OR-Tools work |
| Verdict | **CP2.2 ACCEPTED** as a recommendation (section L); Chirag's approval decides. Not committed, not tagged |
| Followed by | `AI_DESIGN_ENGINE_CHECKPOINT_2_2_1_REPORT.md` (2026-10-07): the parking bay removes limitation L-1; this report records the Checkpoint 2.2 state |
| Ruleset | Every rule value, preference and weight is the **SYNTHETIC / TEST ONLY** ruleset (CP1-06, CP2-U7). Production stays blocked (AD-05) |
| Assets | `AI_DESIGN_ENGINE_CHECKPOINT_2_2_ASSETS/`: `svg/` (every VALID CP2.2 plan), `svg_cp2_1/` (the CP2.1 renders of the reviewed cases), `montage_cp2_1_vs_cp2_2.html`, `benchmark_local.json` (CP2.2 run), `cp2_1_rescored.json` (CP2.1 plans scored by the CP2.2 Scorer) |

---

## A. CP2.1 baseline

CP2.1 plans were saved before any CP2.2 change (75 cases, `.sakha/tmp/cp21_before/`). All before/after numbers below score both sets with the **same** CP2.2 Scorer, so a change in the Scorer cannot pass for a change in the plans.

| Measure (53 cases VALID in both) | CP2.1 |
|---|---|
| Sum of quality totals | 353,747 |
| Rooms over their aspect limit | 60 (bedrooms 15, dining 10, living 9, baths 14, kitchen 6, puja 3, utility 3) |
| Sum of aspect excess (ratio over limit) | 11.5 |
| Rooms over 1.6 × preferred area | 111 |
| Rooms over 2.5 × preferred area | 36 |
| Sum of WET_CLUSTER scores | 26,928 |
| Large plans with bedrooms opening straight off living or dining | most wings layouts (circulation share 0%) |

Part 1 audit of the representative plans (CP2.1):

| Plot | What was wrong |
|---|---|
| 25x40 1BHK | Acceptable for the plot: three bands, no corridor. Bedroom 4.15 × 2.96 m slightly long |
| 30x50 2BHK | Acceptable: spine with a stepped front. Two-wheeler "parking" is a 4.15 × 6.5 m cell (the stepped column) |
| 40x65 3BHK | Dining 3.9 × 6.9 m (2.6 × preferred); attached bath beside the kitchen, not its bedroom; bedrooms entered from dining |
| 40x80 2BHK, 2 cars | Dining 6.8 × 4.6 m (3.4 ×), living 4.4 × 6.6 m: the rooms behind a 6.6 m wide carport took its whole width. Baths apart |
| 45x70 3BHK, 2 cars | Kitchen 6.5 × 2.7 m and dining 6.5 × 3.35 m (the carport width again); 5 rooms over aspect limit; baths scattered |
| 50x60 3BHK, 2 cars | Wings layout; bedrooms and baths entered from living and dining; wet rooms in three places |
| 50x80 4BHK, 2 cars | Living 4.5 × 13.15 m (3.9 ×), dining 4.5 × 6.8 m (3.4 ×): the centre of the wings layout had to match the deepest wing (CP2.1 L3) |
| 60x90 4BHK | Living 4.8 ×, dining 6.5 × preferred, attached bath 3.7 ×. Spare depth went into the public rooms |
| 80x28 wide | One row of rooms, every room as deep as the car beside it (4.55 m): 6 rooms over aspect limit, baths 2.5 × preferred |
| 22x60 narrow | One column beside a 1.05 m passage: every room is 3.94 m across, so kitchen, bath and dining are long across the plot |

## B. Problems selected for improvement

| ID | Problem | Why it was chosen |
|---|---|---|
| P1 | Spare space becomes oversized public rooms (40x65, 50x80, 60x90, 45x70) | The brief's first example ("an absurd 13 m long living room") and the largest share of the quality total |
| P2 | Rooms behind a wide carport take its width (40x80, 45x70) | A structural cause, found in every two-car plan |
| P3 | Bedrooms opening straight off living or dining in large plans | Public-to-private progression (Part 3) |
| P4 | Wet rooms scattered, attached baths not back to back | Part 4, the weakest topology term in CP2.1 |
| P5 | Wide-shallow rows as deep as the car | Part 8 |
| P6 | A mean area term that lets one absurd room hide among right-sized ones | Part 9: the Scorer could not see P1 clearly |
| P7 | Search unable to move a whole band of the house, or rooms either side of a corridor, together | Found while fixing P1: the better layouts existed but were out of reach of single-cut moves |

Not selected, with reasons in section I: the 22x60 single column (window rule and corridor width), two-wheeler cells, wide-shallow plots with cars that remain NO_SUPPORTED_LAYOUT.

## C. Architectural reasoning model

The engine reasons in four zones and one open category, written into the topologies (candidate generation), not hidden in the score:

| Zone | Rooms | Where the topologies put it |
|---|---|---|
| Public | Entrance, living | At the road edge. The entrance is on the living room's front wall (binding rule since CP2.1) |
| Semi-public | Dining, kitchen, kitchen chain (utility, store) | Directly behind or beside living. In a stepped front: dining behind living, kitchen behind the parking. In the courtyard layout: dining on the court, kitchen between dining and a service yard |
| Private | Bedrooms, their attached baths | In a rear row or a side wing, reached through a passage or gallery, not through the public rooms |
| Service | Common bath, utility | Common bath on the passage; utility behind the kitchen |
| Open | Rear yard, side court, centre court, service yard | A leaf of the layout tree like any room. Spare area goes here, not into rooms. No room is ever invented to use space (test: the programme of every reviewed large plan equals the requested programme) |

Relationships and how each is produced:

| Relationship | Mechanism |
|---|---|
| Living ↔ entrance | Entry room is the living room, entrance centred on its front wall |
| Living ↔ dining | Dining directly behind living (stepped fronts, courtyard centre) with a VOID or door per the programme |
| Dining ↔ kitchen | Kitchen chain adjacent to dining in every family (CP2.1 test kept) |
| Kitchen ↔ utility | The kitchen chain stacks utility behind the kitchen; reached through it |
| Bedroom ↔ attached bath | A pair cell; the wet-aware row order turns pairs so attached baths sit back to back |
| Bedrooms ↔ private zone | Rear row or wing, entered from a passage or gallery |
| Common bath ↔ circulation | Common bath entered from the passage, placed between suites in the wet-aware order |

## D. Geometry and topology changes

| Change | File | What it does | Problem |
|---|---|---|---|
| Stepped front with a carport court | `zoning.py` (`Context.stepped`, `carport_court`), FRONT_PUBLIC_REAR_PRIVATE and L_CIRCULATION `stepped` / `stepped_court` tops | The parking keeps its own depth with the kitchen behind it; living keeps its own depth with dining behind it. When the carport is wider than an open strip plus the narrowest room, an open court takes the outer part behind it, so the kitchen stays at kitchen width | P1, P2 |
| Courtyard wings layout | `zoning._courtyard` (replaces the CP2.1 court variant, whose dining room had no window and whose utility blocked the kitchen) | Service column: parking, then kitchen chain (optionally with a side court), then a service yard. Centre: living, dining, centre court; the dining room looks onto the court. Bedroom suites along a gallery on the other side | P1, P3 |
| Wet-aware row orders | `Context.row_orders` | Besides programme order and its mirror: first suite with its bath on the right, wet singles, second suite mirrored, so attached baths meet and the common bath sits between them | P4 |
| Wings `wet` design | wings family | A wing variant that keeps wet rooms on one side of the wing | P4 |
| Linear yard | `linear_family` (`_yard`) | The row and its corridor keep their own depth with a yard behind them; the car beside them is no longer the row's depth | P5 |
| Same-axis splits flattened | `layout_tree._split` | A flexible split along the same axis is spliced into its parent (the same rectangles), so cuts that were in separate splits become siblings | P7 |
| Siblings across fixed parts | `layout_tree.compile_tree` | A fixed corridor no longer breaks the sibling chain: the rooms either side of a corridor shift together | P7 |
| Slab moves | `zoned_ls._deltas` / `_apply` | Every cut along one axis at or beyond a cut line moves with it: a whole band of the house moves towards an open yard | P7 |
| Parking and passages start at their least size | `compile.ZonedProblem.initial` | They take no share of the spare area at the start; spare area goes to rooms and open areas | P1 |
| Search phases | `zoned_ls` | Coarse steps 1200 and 600 for the family pool, finishing at 300, 150 and the grid; `family_pool` 12 → 20 (ruleset data). The 50x80 winner was outside a pool of 12 | P1 |
| Door-position-complete fixture fit | `fit._fits` | The bound tests a room with its hall on any side and the door at both ends of its wall, at both positions a plan produces (a jamb from the wall's end node, or half a crossing wall further in at a T-junction) | Regression R3, section H |
| Speed, results unchanged | `objective.py`, `compile.py`, `zoned_ls.py` | `room_terms` cached (bounded, 32,768 entries); `SizeRule` a NamedTuple; accumulator sums instead of lists; open-area boxes computed once per evaluation; a memo of sizings scoped to one `size()` call. All 75 plan hashes and ranking hashes identical before and after | Latency |

No validator rule, binding rule or threshold changed. The validator has the same authority and the same 39 codes.

## E. Scoring changes

| Term | Status | Geometric meaning | Implementation | Tests |
|---|---|---|---|---|
| ROOM_SIZE_OUTLIER | New, weight 2 [SYNTHETIC] | The single worst room's deviation from its preferred clear area, in thousandths: `max over enclosed rooms of abs(clear area − preferred) × 1000 // preferred`. Subjects: the room(s) at that maximum | `SizingAccumulator.worst_area_dev`; `score()` adds the term; the compiled evaluator uses the same accumulator, so solver and stored plan agree | `test_room_size_outlier_is_the_worst_room_area_deviation`, `test_room_size_outlier_names_the_room_furthest_from_its_preference`, `test_the_plan_score_is_the_solver_score_for_a_plan_with_an_open_area` (CP2.1), golden scores |

Why it exists: AREA_DEVIATION is a mean, so a 13 m living room among eight right-sized rooms moves it little. The outlier term makes the worst room visible on its own.

What it did **not** do: added alone (before the topology changes) it only moved oversize between rooms (rooms over aspect limit 60 → 80 in the trial run). That run was discarded. The improvement in section F comes from the topologies in section D, which give spare area somewhere to go. No weight was raised to make a case pass and no threshold was lowered. Every other term is unchanged from CP2.1.

The CP1 baseline record (`benchmark_baseline_cp1.json`) was rescored with the new term: all 50 CP1 plan bodies are byte-identical; the 17 VALID ones have new totals. It was also extended to the CP2.2 corpus.

## F. Benchmark, before and after

Corpora: CP2 (`benchmark_cp2.json`), CP2.1 quality (`benchmark_cp2_1_quality.json`) unchanged, plus the new **CP2.2 corpus** `benchmark_cp2_2_quality.json`: 25 cases, labels fixed on 2026-10-07 before any engine version ran on it. 15 FEASIBLE, 4 INFEASIBLE, 6 MEASURE, each tagged with what it exercises (adjacency, wet clustering, bedroom grouping, entrance, circulation, large, narrow, wide-shallow, open space, oversize).

### F.1 Outcomes and quality by corpus (CP2.1 plans rescored by the CP2.2 Scorer)

| Corpus | Cases | VALID CP2.1 | VALID CP2.2 | Shared VALID | Mean quality CP2.1 → CP2.2 | Rooms over aspect limit | Cases scoring worse |
|---|---|---|---|---|---|---|---|
| original | 14 | 11 | 11 | 11 | 5,645 → 3,142 | 15 → 11 | 0 |
| cp2_new | 12 | 9 | 9 | 9 | 5,707 → 3,993 | 9 → 9 | 0 |
| proportion | 8 | 5 | 5 | 5 | 7,237 → 3,681 | 11 → 3 | 0 |
| quality | 16 | 9 | 9 | 9 | 7,213 → 3,392 | 9 → 8 | 0 |
| cp2_2 | 25 | 19 | 21 | 19 | 7,325 → 3,955 | 16 → 27 | 0 |
| **All** | **75** | **53** | **55** | **53** | **6,674 → 3,671 (0.55)** | **60 → 58** | **0** |

Every label holds: 11/11 original FEASIBLE VALID, 15/15 CP2.2 FEASIBLE VALID, every INFEASIBLE label INFEASIBLE, no INFEASIBLE label VALID, 0 invalid attempts returned. Two cases CP2.1 could not plan are now VALID: `c14_2bhk_30x45_open_plan_twowheeler` (FEASIBLE label, which CP2.1 failed) and `c11_3bhk_70x35_wide_car` (MEASURE). No case lost feasibility.

### F.2 Architectural-quality measures (53 shared VALID cases)

| Measure | CP2.1 | CP2.2 |
|---|---|---|
| Sum of quality totals | 353,747 | 194,600 (−45%) |
| Rooms over 2.5 × preferred area | 36 | 3 |
| Rooms over 1.6 × preferred area | 111 | 65 |
| Rooms over aspect limit by more than 10% | 22 | 14 |
| Sum of aspect excess | 11.5 | 7.4 |
| Rooms over aspect limit | 60 | 58 |
| Of which bedrooms / dining / kitchen | 15 / 10 / 6 | 7 / 6 / 2 |
| Of which baths / puja | 14 / 3 | 22 / 11 |
| Sum of WET_CLUSTER | 26,928 | 22,211 (−18%) |
| Parking area / need, mean (50 shared plans with parking) | 2.43 | 2.06 |
| Parking over 1.6 × need | 30 | 19 |

The aspect count fell only by 2, and it moved from habitable rooms to small service rooms (section I, L-4). On the CP2.2 corpus it rose 16 → 27 for that reason.

### F.3 CP2.2 corpus, per case

| Case | Label | CP2.1 | CP2.2 | CP2.2 topology |
|---|---|---|---|---|
| c01 3BHK 40x70, 2 attached | FEASIBLE | 6,829 | 4,907 | L_CIRCULATION stepped, wet order |
| c02 2BHK 35x60 utility | FEASIBLE | 5,111 | 4,926 | SPINE stepped |
| c03 3BHK 45x80 2 cars puja | FEASIBLE | 11,406 | 4,121 | L_CIRCULATION stepped court |
| c04 4BHK 55x90 2 cars | FEASIBLE | 13,985 | 2,731 | Courtyard |
| c05 4BHK 60x100 2 cars puja utility | FEASIBLE | 20,469 | 2,925 | Courtyard with side court |
| c06 3BHK 50x70 car | FEASIBLE | 5,135 | 1,557 | Courtyard |
| c07 2BHK 30x60 two-wheeler attached | FEASIBLE | 2,524 | 2,169 | SPINE |
| c08 2BHK 25x65 no car | FEASIBLE | 4,125 | 4,102 | FRONT_PUBLIC_REAR_PRIVATE |
| c09 3BHK 30x80 car | FEASIBLE | 2,076 | 1,910 | SPINE stepped |
| c10 2BHK 60x30 two-wheeler | FEASIBLE | 8,422 | 7,574 | Wings gallery |
| c11 3BHK 70x35 car | MEASURE | NO_SUPPORTED_LAYOUT | 15,363 | FRONT_LIVING_REAR_BEDROOM 2-band |
| c12 2BHK 45x45 puja | FEASIBLE | 4,853 | 3,371 | Wings gallery |
| c13 1BHK 30x45 car | FEASIBLE | 1,012 | 682 | SPINE stepped |
| c14 2BHK 30x45 open plan | FEASIBLE | NO_SUPPORTED_LAYOUT | 897 | SPINE |
| c15 3BHK 40x60 all attached | MEASURE | 6,811 | 4,963 | L_CIRCULATION stepped |
| c16 4BHK 45x80 utility | FEASIBLE | 10,845 | 1,945 | Courtyard |
| c17 3BHK 35x60 puja | MEASURE | 5,964 | 5,735 | SPINE stepped |
| c18 2BHK 40x40 car | MEASURE | 3,991 | 3,897 | Wings |
| c19 to c22 | INFEASIBLE | PROVEN | PROVEN | none |
| c23 4BHK 50x90 2 cars puja | MEASURE | 10,941 | 3,959 | L_CIRCULATION stepped court |
| c24 3BHK 60x45 utility | MEASURE | 10,776 | 10,031 | Wings gallery |
| c25 2BHK 35x70 puja | FEASIBLE | 3,900 | 3,656 | SPINE |

Winning families across the 55 VALID plans: SPINE 18, CENTRAL_LIVING_BEDROOM_WINGS 17 (7 of them courtyard layouts), L_CIRCULATION 12, FRONT_PUBLIC_REAR_PRIVATE 3, FRONT_LIVING_REAR_BEDROOM 3, FRONT_EXTENSION 1, LINEAR_REAR_CORRIDOR 1. Stepped carport courts win 8 cases.

### F.4 Performance (development machine, 12 logical CPUs, Python 3.13; not the VPS)

| Measure | CP2.1 | CP2.2 | Gate |
|---|---|---|---|
| Normal p95 (all corpora) | 433 ms | 700 ms | ≤ 1000: met |
| Difficult p99 | 1,159 ms | 1,779 ms | ≤ 3000: met |
| Infeasible pre-check p95 | 0.6 ms | 0.9 ms | met |
| Infeasible search p95 | 702 ms | 909 ms | ≤ 1500: met |
| Same 50 cases, median ratio CP2.2 / CP2.1 | | normal 1.5, difficult 1.34 | |
| Validation p95 / repair p95 | 2.3 / 6.2 ms | 2.8 / 7.4 ms | met |
| Fixture-fit build, once per worker per ruleset | 81 ms | 559 ms | |
| RSS peak (whole benchmark) | 42 MB | 64 MB | met |
| Peak traced memory, one generation | 1.1 MB | 2.0 MB | |
| Threads 1 / 2 / 4, p95 | 437 / 899 / 1,892 ms | 742 / 1,527 / 2,966 ms | |
| Throughput per process | | 2.4 plans/s, 0.97 cores at any thread count | |

The first full run measured normal p95 at 1,267 ms (gate missed). The cause was evaluation cost (more terms, more moves per cycle). The speed changes in section D cut it by about 30% with identical results (75/75 hashes). CP2.2 is still 1.3 to 1.5 times slower than CP2.1 on the same cases. Threads do not add throughput (the GIL): the worker's `asyncio.to_thread` concurrency serialises engine work. The VPS gate remains unmeasured (deferred by Chirag).

## G. Visual comparison

`AI_DESIGN_ENGINE_CHECKPOINT_2_2_ASSETS/montage_cp2_1_vs_cp2_2.html`: CP2.1 left, CP2.2 right, captions scored by the same Scorer. Reviewed by eye in the browser, case by case, with the brief's ten questions: (1) entrance, (2) living as the public heart, (3) dining connected, (4) kitchen placed, (5) bedrooms grouped, (6) bathrooms sensible, (7) circulation purposeful, (8) proportions believable, (9) leftover space used, (10) looks designed rather than packed. Y yes, P partly, N no.

| Plot | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Change from CP2.1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 25x40 1BHK | Y | Y | Y | Y | Y | P | Y | P | Y | P | Same topology, mirrored. Bath not beside the kitchen; bedroom 4.25 × 2.96 m |
| 30x50 2BHK | Y | Y | Y | Y | Y | Y | Y | Y | P | Y | Identical layout. The two-wheeler cell is 4.15 × 6.5 m (front forecourt in effect) |
| 40x65 3BHK | Y | P | Y | Y | P | Y | P | P | Y | P | Better: dining 3.9 × 6.9 m → about 4.0 × 4.2 m, common bath beside the kitchen, larger rear yard. Still: living 4.05 × 6.85 m (over aspect), bedroom 1 at the front beside living, bedrooms entered from living and dining |
| 40x80 2BHK, 2 cars | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Clearly better: stepped front, kitchen 2.7 m wide behind the carport with a 3.9 m open court beside it, dining behind living, attached and common baths back to back on the passage, compact house with a rear yard |
| 45x70 3BHK, 2 cars | Y | Y | Y | Y | Y | Y | Y | P | Y | Y | Clearly better: kitchen 6.5 × 2.7 → 3.4 × 2.45 m, dining 6.5 × 3.35 → 3.4 × 3.1 m, aspect violations 5 → 1, attached baths back to back. Puja 1.6 × 2.95 m long |
| 50x60 3BHK, 2 cars | Y | Y | Y | Y | Y | Y | Y | P | **N** | P | Rooms better (no stretched living or dining; baths paired; bedrooms on a passage, not off the dining room). **Regression: the carport is 8.25 × 8.6 m for two cars that need 5 × 5 m** (CP2.1: about 5 × 5 m). The open court beside the common bath is only 1.95 m deep |
| 50x80 4BHK, 2 cars | Y | Y | Y | Y | Y | Y | Y | P | P | Y | Clearly better: the 4.5 × 13.15 m living room is gone; L circulation with service column, bedroom row with paired baths; quality 14,118 → 2,926. Parking 1.63 × need |
| 60x90 4BHK | Y | Y | Y | Y | Y | Y | P | Y | P | P | Rooms much better (living 4.8 ×, dining 6.5 × preferred are gone). Courtyard layout, but every bedroom suite is in one wing along a gallery about 22 m long, and the house reads as a thin L around a large court |
| 80x28 wide | Y | Y | Y | Y | Y | Y | P | Y | Y | P | Better: rooms 3.15 m deep instead of 4.55 m, aspect violations 6 → 0, yard behind the corridor. Still one row with a 19.8 m rear corridor (26.5% circulation) |
| 22x60 narrow | Y | P | Y | P | Y | P | P | N | Y | N | Unchanged (structural, section I) |
| 50x30 wide | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Unchanged layout, slightly different sizes; dining 4.3 × 2.86 m now just over aspect |

Summary: four of eleven reviewed plans are clearly better (40x65, 40x80, 45x70, 50x80), three are better with a visible flaw (50x60 carport, 60x90 long wing, 80x28 corridor), four are essentially unchanged (25x40, 30x50, 22x60, 50x30). The audit flaws P1 and P2 are fixed in every reviewed plan. None of the reviewed plans got worse overall. 50x60 got worse in one respect: the carport.

## H. Regression results

| Check | Result |
|---|---|
| CP1 goldens (3) | Byte-identical |
| CP1 baseline plans (50) | Bodies byte-identical; scores rescored for ROOM_SIZE_OUTLIER |
| Validator authority, 39 codes, negative corpus | Unchanged; tests pass |
| Determinism | 75/75 cases deterministic; ranking hashes stable; a fresh process reproduces every hash |
| Speed changes | 75/75 plan and ranking hashes identical before and after |
| Solver score = stored plan score | Holds (CP2.1 tests kept) |
| INVALID returned as VALID | 0 invalid attempts; no INFEASIBLE label VALID |
| 11/11 original feasible VALID | Yes |
| 25x40 VALID | Yes |
| Zoned goldens (8) | Regenerated: the plans changed by design |
| Contracts | Regenerated (ROOM_SIZE_OUTLIER) |
| Static checks | ruff, ruff format, mypy strict (317 files), import-linter 5/5; web lint, typecheck, 30 tests, build |
| Full API suite | 737 passed, 0 failed (one existing SQLAlchemy deprecation warning), 25 min, with the local database |

Regressions found and fixed during the checkpoint, each with a test (`tests/test_houseplan_cp2_2.py`, 17 tests):

| ID | Regression | Fix | Test |
|---|---|---|---|
| R1 | Same-axis nesting from `with_open` kept the yard cut apart from the layout's cuts | Flatten same-axis flexible splits | `test_a_flexible_split_along_the_same_axis_is_spliced_in` |
| R2 | A fixed corridor reset the sibling chain | Siblings span fixed parts | `test_sibling_cuts_span_a_fixed_corridor` |
| R3 | `3bhk_50x60_wide_two_cars` (FEASIBLE) turned INFEASIBLE: the common bath passed the fit bound but its door sat half an exterior wall further in at a T-junction | Fit bound tests every door position and hall side | `test_fixture_fit_covers_the_door_beside_a_crossing_exterior_wall`, `test_the_50x60_two_car_plot_is_valid` |
| R4 | The courtyard's parking was stretched to 20 m | Parking starts at its least size | `test_parking_starts_at_its_least_size` |
| R5 | Kitchen took the full carport width | Stepped carport court | `test_a_wide_carport_leaves_an_open_court_beside_the_rooms_behind_it` |
| R6 | 80x28 rows as deep as the car | Linear yard | `test_the_linear_row_keeps_its_own_depth_with_a_yard_behind` |
| R7 | Latency gate missed after the topology work | Exact speed changes | Covered by the hash identity check and the golden tests |

Other CP2.2 tests: slab move geometry, courtyard relationships (dining on the court, kitchen beside dining and the service yard), wet-aware order (attached baths share a wall), the outlier term, the bounded cache, and, for 50x80, 55x90 and 60x90, that the room programme equals the requested one (no invented rooms) and no room exceeds 2.5 × its preferred area.

Changed CP2 and CP2.1 tests, with the reason in the test: the soft-constraint count 13 → 14 (ROOM_SIZE_OUTLIER); the bath long-wall fit point 2750 → 2800 mm (R3).

## I. Remaining limitations

| ID | Limitation | Evidence | Cause | Next step |
|---|---|---|---|---|
| L-1 | Spare front space goes to the parking. 50x60 carport 8.25 × 8.6 m (2.6 × need); two-wheeler cells 2.5 to 10 × need in most two-wheeler plans | Section F.2 parking rows; `svg/3bhk_50x60_wide_two_cars.svg` | Parking is not an enclosed room, so no Scorer term sees its size; the cut between the parking and the rooms behind it has no reason to move | Either an open forecourt leaf in front of or beside the parking in stepped fronts, or a parking-excess term (needs a decision: is a paved forecourt "parking" or "open space" in the product?) |
| L-2 | 60x90 courtyard: one wing of every suite along a 22 m gallery | Montage, q06 | `_courtyard` stacks all far groups in one column | Split the far groups across both sides of the court, or a rear bedroom row with the court in front |
| L-3 | Long corridors in linear and some L plans: 80x28 19.8 m, 26.5% circulation | F, G | One row along the road needs a corridor its whole length | A two-row linear variant with a central hall for plots deeper than about 9 m |
| L-4 | Baths and puja rooms in a bedroom row take the row's full depth (puja 1.6 × 3.0 m, attached bath 1.75 × 3.1 m): rooms over aspect limit 14 → 22 baths, 3 → 11 puja | F.2 | A row cell spans the row; nothing may fill the rest of a bath's depth without inventing a room | Let a pair be bath over wardrobe or bath over the bedroom's alcove (an L bedroom), which needs non-rectangular rooms; or accept and relax the synthetic aspect limits for baths (AD-05) |
| L-5 | 22x60 unchanged: every room 3.94 m across one column | G | Window rule (every habitable room and bath needs an outside wall, CP2-U3), 1.05 m passage, one column. A second room across the column would have no outside wall | AD-05 decisions on bath ventilation (a duct instead of a window) and corridor width |
| L-6 | Wide-shallow plots with cars still NO_SUPPORTED_LAYOUT: 45x35, 60x40 two cars, 70x30 | Benchmark rows | The 5 m car depth leaves too little behind it (CP2.1 L5) | CP2-U1 (parking in the front setback) |
| L-7 | Deep narrow plots with a car: 25x90 and 22x100 NO_SUPPORTED_LAYOUT | Closest: parking 2.40 m where 2.50 m is needed, living 2.99 m where 3.00 m | With 3 ft side setbacks the buildable widths are 5.79 m and 4.88 m. A car (2.5 m) beside the living room (3.0 m) needs 5.5 m clear plus about 0.5 m of walls; every family puts the car beside the entry room at the front | A variant with the car in front of the living room, or CP2-U1 |
| L-8 | 40x65 living 4.05 × 6.85 m, bedroom 1 at the front | Montage | Wings centre depth follows the deeper wing | Same remedy as L-2 |
| L-9 | Slower than CP2.1 (1.3 to 1.5 × on the same cases); fit build 559 ms per worker start; no parallel throughput from threads | F.4 | More topologies, larger pool, more moves; the GIL | Process-based workers for the engine queue; VPS measurement (deferred) |
| L-10 | Orientation not evaluated | ORIENTATION NOT_EVALUATED | AD-13 | Unchanged |

## J. Synthetic-rule dependencies

Every value below is synthetic test data (`ruleset_synthetic_test_only.json`) and needs AD-05 approval before production:

| Value | Used for |
|---|---|
| `objective.weights.ROOM_SIZE_OUTLIER` = 2 (new) | Weight of the new term |
| `objective.family_pool` = 20 (was 12) | Search breadth; a performance and quality setting, not an architectural rule |
| `zoning.open_space_min_mm` = 1500 | Narrowest open court or yard; decides when a carport court, a linear yard or a rear yard exists |
| Room preferred areas, short/long preferences, aspect limits | Every size term, including ROOM_SIZE_OUTLIER and the aspect counts in this report |
| Window rule for baths (CP2-U3) | Drives L-4 and L-5 |
| Parking inside the footprint (CP2-U1) | Drives L-1, L-6, L-7 |
| Corridor width, wall thicknesses, door and window widths, jamb clearance | Fixture fit, passages, window walls |

No new hard rule was introduced. The zone model in section C uses the existing `zoning.depth_order` data and the programme's relations.

## K. Recommendation for the next checkpoint

1. Decide whether a paved forecourt counts as parking or open space (product question), then fix L-1 structurally. This is the most visible flaw left.
2. Courtyard and wings: split suites across two sides or a rear row (L-2, L-8).
3. A two-row linear variant for wide plots deeper than about 9 m (L-3).
4. AD-05 items that block narrow plots: bath ventilation by duct, corridor width (L-5); CP2-U1 front-setback parking (L-6, L-7).
5. Engine workers as processes, then the deferred VPS gate with the CP2.2 corpus included (`vps_benchmark.sh` already runs `--corpus all`; its environment record should also hash `benchmark_cp2_2_quality.json`).
6. Only then the 2D editor or visualisation work.

## L. Verdict

**CP2.2 ACCEPTED** (recommendation; Chirag's explicit approval decides, and nothing is committed or tagged until then).

| Brief Part 13 item | Met? | Evidence |
|---|---|---|
| Deterministic correctness intact | Yes | 75/75 deterministic, fresh-process hashes equal, CP1 goldens and baseline bodies byte-identical, 737 tests pass |
| Feasibility does not regress materially | Yes | Every label holds; +2 VALID (c11, c14); the 50x60 regression found mid-checkpoint was fixed |
| Architectural-quality metrics improve | Yes | Quality −45% on 53 shared cases, 0 cases worse |
| Oversized rooms reduced | Yes | Over 2.5 × preferred 36 → 3; over 1.6 × 111 → 65 |
| Wet clustering improves where applicable | Yes | −18%; attached baths back to back in the row layouts |
| Circulation more purposeful | Mostly | Large plans: bedrooms off passages instead of off living and dining. Still long: 80x28 corridor, 60x90 gallery (L-2, L-3) |
| Large plots improve | Yes | 50x80, 55x90, 60x90, 60x100, 45x80: quality down 79 to 86% |
| Narrow and wide where structurally possible | Partly | 80x28 rows no longer car-deep, 70x35 now VALID; 22x60 and narrow plots with cars blocked by rules (L-5, L-7) |
| Visual inspection shows clear improvement | Yes, with one regression | 7 of 11 better, 4 unchanged, none worse overall; the 50x60 carport is worse (L-1) |
| No score gaming | Yes | One new term with a geometric meaning; no threshold or weight lowered; CP2.1 plans rescored by the same Scorer. The 50x60 carport shows a Scorer blind spot (parking size), recorded as L-1, not hidden |
| Limitations documented | Yes | Section I |

What would change this verdict: if Chirag judges the 50x60 carport, or bathrooms and puja rooms becoming the rooms over aspect limit (L-4), unacceptable for the POC. Both are recorded with a proposed fix.
