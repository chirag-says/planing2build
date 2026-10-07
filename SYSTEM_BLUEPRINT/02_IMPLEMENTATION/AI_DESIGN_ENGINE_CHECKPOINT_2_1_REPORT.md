# Plan2Build: AI design engine, Checkpoint 2.1 report (architectural topology quality)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_2_1_REPORT.md` |
| Date | 2026-10-07 |
| Basis | `AI_DESIGN_ENGINE_CHECKPOINT_2.md` (approved with changes; its section S records what this checkpoint changed), `AI_DESIGN_ENGINE_CHECKPOINT_2_REPORT.md`, Chirag's Checkpoint 2.1 brief of 2026-10-07 |
| Branch | `houseplans-checkpoint-1`. Checkpoint 1 is `22628ab` (tag `houseplans-cp1`, unchanged). Checkpoint 2 and 2.1 are in the working tree, **not committed** |
| Verdict | **CP2.1 NOT ACCEPTED** (final gate attempted 2026-10-07). Every acceptance item is met on the development machine except items 9 and 10: the benchmark has not run on the VPS. No Plan2Build VPS deployment is defined yet, and this machine has no access to any VPS (section 12.1). Not committed, not tagged |
| Followed by | `AI_DESIGN_ENGINE_CHECKPOINT_2_2_REPORT.md` (2026-10-07): the VPS gate was deferred and Checkpoint 2.2 refined plan quality; this report records the Checkpoint 2.1 state |
| Ruleset | All rule values, preferences and weights are the **SYNTHETIC / TEST ONLY** ruleset (CP1-06, CP2-U7). Production stays blocked (AD-05) |

---

## 1. Objective

Move the deterministic engine from valid rectangle packing toward constraint-valid, architecturally coherent concept layouts: several genuinely different residential topologies, chosen per plot and programme; better proportions through better layouts, not a re-weighted metric; the `1bhk_25x40` case solved or formally explained; and the VPS performance gate run.

## 2. Starting Checkpoint 2 state

| Measure | Checkpoint 2 |
|---|---|
| Original expected-feasible cases VALID | 10 of 11 (`1bhk_25x40_south_small` NO_SUPPORTED_LAYOUT) |
| Topology families | SPINE and FRONT_EXTENSION (a front band, a passage spine, one or two full-depth columns) |
| Rooms over aspect limit vs Checkpoint 1 (shared VALID cases) | 65.7% original corpus, 52.9% whole benchmark: **missed** (target ≤ 50%) |
| Mean quality vs Checkpoint 1 | 41.0% and 38.8%: met |
| VPS gate | not run |

## 3. Architectural problems identified

| ID | Problem | Seen in |
|---|---|---|
| P1 | Every layout was one shape: front band, spine, columns | All 22 Checkpoint 2 renders |
| P2 | Rooms stretched to fill the envelope: the last room of each column took all leftover depth; on wide plots every stacked room took the full column width | 4BHK 50x80: baths 6.7 × 2.2 m, bedrooms 6.7 × 3.4 m (8 rooms over aspect) |
| P3 | Private rooms scattered along the spine among public and service rooms | 3BHK 40x65, 2BHK 40x80 |
| P4 | Small plots unsolved | 1BHK 25x40 |
| P5 | Wide, shallow plots unsolved | 60x35, 70x30, 80x28 (proportion corpus) |
| P6 | Bathrooms sized for a door on the long wall, then entered through the short wall: fixture placement failed after sizing | Found while building 2.1 (2BHK 30x50) |
| P7 | The living room's front wall could not hold both the centred entrance and a window when it had no other outside wall | Found while building 2.1 (wings layouts) |

## 4. Root-cause analysis

- **P1 and P2 were structural, not a weighting problem.** The geometry code hard-wrote one topology. A column of rooms beside a spine gives every room the column's width; the column must reach the rear setback, so its last room absorbs the leftover. The aspect term was already penalising this, but no sizing of that topology could fix it. Raising the aspect weight would only have traded aspect for oversize.
- **P3:** column assignment ranked splits by depth balance only, ignoring zones.
- **P4:** the plot is 6.2 m wide inside the walls. A spine with two columns leaves 2.3 m per column, under the 2.8 m bedroom minimum. A single column has to stack dining, kitchen, bedroom and bath, which needs more depth than the plot has. Every Checkpoint 2 topology needs a corridor, and the corridor is what does not fit. Section 9 has the full working.
- **P5:** every family stacked bands in depth; the car's 5 m depth plus anything behind it exceeds a 7 to 8 m deep plot.
- **P6:** the fixture-fit bound assumed one door wall.
- **P7:** the compiler checked "a 1.4 m outside wall" but not what else that wall holds.

## 5. New topology families

All families are now slicing trees (`engine/layout_tree.py`): a rectangle split along x or y into parts, recursively, down to rooms, passages and open (unbuilt) areas. Variables are absolute cut positions, so the same compiler, search and Scorer serve every family. The Checkpoint 2 families were re-expressed in the same engine.

| Family | Shape | Where it fits |
|---|---|---|
| SPINE | Front band (parking, living), passage spine from the living room, one or two columns; optional rear room | Narrow and medium plots |
| FRONT_EXTENSION | SPINE with a bedroom or dining room beside the living room (CP2-U2) | Wider fronts |
| SIDE_WING | SPINE with public and service rooms in one column and private rooms in the other | Deep plots with a clear private side |
| FRONT_LIVING_REAR_BEDROOM | No corridor. Two bands (everything behind the living room in one row, each room with a rear window) or three (dining and kitchen, then up to two private rooms entered from the dining room) | Small plots; wide, shallow plots |
| FRONT_PUBLIC_REAR_PRIVATE | Public band, dining and kitchen, a cross corridor entered from the dining room, the private rooms side by side behind it (attached baths beside their bedrooms) | Medium-width deep plots |
| L_CIRCULATION | A spine beside the dining and service rooms that turns into a rear cross corridor serving the private band | Deep plots, 3 to 4 bedrooms |
| CENTRAL_LIVING_BEDROOM_WINGS | Living and dining in the middle, a wing of rooms either side, kitchen at the rear of a wing beside the dining room, parking at the front of a wing. Variants: a gallery corridor along the deep wing; a court behind living, dining and kitchen | Wide and square plots, large programmes |
| LINEAR_REAR_CORRIDOR | One row of rooms along the road, each with a front window, a corridor behind them, parking full depth at one end | Very wide, shallow plots |

Every family may also leave an open rear yard (ruleset `zoning.open_space_min_mm`, synthetic 1.5 m), so leftover depth becomes open space instead of a stretched room.

## 6. Topology-selection logic

`zoning.select` runs every family generator. Each one:

- checks sound lower bounds: minimum clear sizes plus the thinnest walls, fixture fit, parking clear size, passage width;
- rejects itself early with a plain reason if those bounds exceed the plot. Example: "two wings and the centre need 8.10 m of width";
- generates its variants: parking side, mirror orders, kitchen side, wing splits ranked by depth balance, open yard;
- returns a verdict with the candidate count.

Identical trees produced by two families are kept once. Applicability, circulation, adjacency, wet clustering, privacy, exposure, parking and proportions are then judged by the compiler (hard) and the Scorer (soft) on sized layouts, not guessed in advance.

## 7. Candidate-generation improvements

| Change | Why |
|---|---|
| Slicing trees with absolute cuts | One engine for all families; a single move shifts one cut line and resizes only the two parts beside it |
| Start from minimum extents | Each part first gets its least size (minimums, fixture fit, typical walls), then shares the rest by preferred area. Dimensions start inside their valid range (brief Part 5) instead of proportional shares that left a bathroom 0.9 m deep |
| Two-phase search | Per family, the best starting points are sized coarsely (`family_pool`, synthetic 12); the best `candidate_limit` (32) are finished, with an equal share reserved per family so every applicable family is compared at full precision |
| Pair-move escape | A layout within 400 mm of feasible gets bounded pair moves (two cut lines together); a tight row cannot be fixed one cut at a time |
| Door-aware fixture fit | `fit.FitRule`: a staircase of minimal (along the door wall, across) sizes from the real placement routine; the compiler reads which wall holds the door from the access plan |
| Window walls in the compiler | Every room needing a window must have a 1.4 m stretch of outside wall (boundary or open area); the living room's front wall must hold the centred entrance and a window (3.8 m) or it needs a side wall |
| Alternative entry rooms | An access rule may list several rooms (wing rooms: living or dining); the one with the longest shared wall is used |
| Exact insets with open areas | A side partly facing an open area takes the exterior wall's inset, as `derive.analyse` measures it |
| Speed | Allocation-free size terms and inlined checks: about 35 µs per sizing evaluation |

Determinism is unchanged: integer arithmetic, fixed enumeration order, fixed move order, ties by enumeration index.

## 8. Objective and scoring changes

The Scorer stays the single definition of quality; solver and stored plan agree term by term on every VALID case (test). Weights are ruleset data, synthetic, pending AD-05.

| Term | Status | Why it exists |
|---|---|---|
| AREA_DEVIATION, DIMENSION_DEVIATION, ASPECT_EXCESS, OVERSIZE, CIRCULATION_SHARE | Unchanged | Room size and proportion against the ruleset's preferences; corridor share |
| ADJACENCY, WET_CLUSTER, PRIVACY, PARKING_CONVENIENCE | Unchanged | Soft relations (kitchen and dining, dining and living), wet rooms sharing walls, bedrooms away from the entry room, parking beside the entry room |
| EXTERIOR_EXPOSURE | Measure changed | Now the longest single stretch of outside wall (one window needs one wall), including walls facing an open area; Checkpoint 2 summed boundary length |
| ZONE_ORDER | New, weight 1 [SYNTHETIC] | The ruleset's front-to-back zone order (`zoning.depth_order`, already ruleset data): a pair breaks it when the more private room lies wholly in front of the other. Pairs joined by a relation (an attached bath behind its bedroom) are not compared |
| BEDROOM_GROUPING | New, weight 1 [SYNTHETIC] | Bedrooms should open off one shared space rather than be scattered: (distinct rooms bedrooms open off − 1) / (bedrooms − 1) |
| ORIENTATION | Unchanged, NOT_EVALUATED | AD-13 |

Not added: a "topology suitability" term. It would score the family label, not the layout, and would double-count what the terms above already measure.

**The aspect term is the Checkpoint 2 definition, unchanged.** The improvement in section 10 comes from the layouts.

## 9. The 25x40 investigation

| Item | Value |
|---|---|
| Plot | 25 x 40 ft, setbacks front 4, back 3, left 2, right 2 ft: buildable 6.40 × 10.06 m, wall-centreline region 6.20 × 9.86 m |
| Programme | Living, dining, kitchen (closed), 1 bedroom, 1 common bath, two-wheeler parking (1.0 × 2.0 m) |
| Cause of the Checkpoint 2 failure | Missing topology. Two columns beside a 1.2 m spine leave 2.3 m clear per column (bedroom minimum 2.8 m); one column needs about 12.3 m of depth for dining, kitchen, bath and bedroom in a stack. Every Checkpoint 2 topology needs a corridor. Not the setbacks, not the feasibility bounds (the pre-check correctly did not claim PROVEN), not parking |
| Fix | FRONT_LIVING_REAR_BEDROOM, three bands, no corridor: living and the two-wheeler at the front; dining and kitchen side by side; bedroom and bath at the rear, both entered from the dining room |
| Result | **VALID**, validated by the unchanged validator. Quality 1447, 1 room over aspect limit, no passage. Golden `golden/zoned/1bhk_25x40_south_small.json`; regression test `test_the_small_25x40_plot_is_valid_without_a_corridor` |

## 10. Benchmark results, before and after

Corpora:

- **Checkpoint 2 corpus** (`benchmark_cp2.json`, unchanged): 14 original cases, 12 Checkpoint 2 additions, 8 proportion cases.
- **New architectural-quality corpus** (`benchmark_cp2_1_quality.json`): 16 cases, each tagged with what it stresses. Labels were fixed on 2026-10-07 before its first run; all are MEASURE.

The baseline is the Checkpoint 1 solver on the frozen Checkpoint 1 ruleset. Every quality figure uses the current Scorer and the synthetic weights. Rooms over aspect limit is a geometric count, so it compares directly across all three checkpoints. Checkpoint 2 quality scores were recorded under the Checkpoint 2 Scorer and are not repeated here. The six Checkpoint 2 golden plans were rescored under the current Scorer in the second table below.

| Case | Group | Expected | Checkpoint 1 | Checkpoint 2 | Checkpoint 2.1 | Family (2.1) | Rooms over aspect: CP1 / CP2 / CP2.1 | Quality: CP1 / CP2.1 | p50 laptop / container |
|---|---|---|---|---|---|---|---|---|---|
| 2bhk_30x50_north_twowheeler_open | original | FEASIBLE | VALID | VALID | VALID | SPINE | 5 / 1 / 0 | 9812 / 603 | 187 / 184 ms |
| 3bhk_40x65_east_puja | original | FEASIBLE | VALID | VALID | VALID | CENTRAL_LIVING_BEDROOM_WINGS | 7 / 5 / 0 | 15291 / 3029 | 427 / 416 ms |
| 2bhk_40x80_west_two_cars | original | FEASIBLE | VALID | VALID | VALID | FRONT_PUBLIC_REAR_PRIVATE | 6 / 2 / 1 | 53540 / 3040 | 360 / 353 ms |
| 1bhk_25x40_south_small | original | FEASIBLE | INFEASIBLE | NO_SUPPORTED_LAYOUT | VALID | FRONT_LIVING_REAR_BEDROOM | – / – / 1 | – / 1447 | 107 / 115 ms |
| 2bhk_22x60_narrow_deep | original | FEASIBLE | INFEASIBLE | VALID | VALID | SPINE | – / 5 / 5 | – / 3100 | 121 / 119 ms |
| 4bhk_50x80_large_two_cars | original | FEASIBLE | VALID | VALID | VALID | CENTRAL_LIVING_BEDROOM_WINGS | 10 / 8 / 3 | 44297 / 8228 | 904 / 890 ms |
| 3bhk_30x60_single_car_vastu | original | FEASIBLE | INFEASIBLE | VALID | VALID | SPINE | – / 0 / 0 | – / 941 | 396 / 360 ms |
| 2bhk_35x55_utility_no_vastu | original | FEASIBLE | INFEASIBLE | VALID | VALID | SPINE | – / 2 / 0 | – / 2556 | 402 / 397 ms |
| 3bhk_45x70_two_cars_puja | original | FEASIBLE | VALID | VALID | VALID | L_CIRCULATION | 7 / 7 / 5 | 29268 / 8890 | 756 / 741 ms |
| 3bhk_40x60_asymmetric_setbacks | original | FEASIBLE | INFEASIBLE | VALID | VALID | CENTRAL_LIVING_BEDROOM_WINGS | – / 4 / 0 | – / 2843 | 430 / 419 ms |
| 2bhk_30x45_common_bath_only | original | FEASIBLE | INFEASIBLE | VALID | VALID | SPINE | – / 0 / 0 | – / 324 | 109 / 108 ms |
| 3bhk_20x30_too_small | original | INFEASIBLE | INFEASIBLE | PROVEN | PROVEN | – | – / – / – | – / – | 0 / 0 ms |
| 2bhk_30x60_two_cars_too_wide | original | INFEASIBLE | INFEASIBLE | NO_SUPPORTED_LAYOUT | NO_SUPPORTED_LAYOUT | – | – / – / – | – / – | 225 / 217 ms |
| 4bhk_30x40_overfull | original | INFEASIBLE | INFEASIBLE | PROVEN | PROVEN | – | – / – / – | – / – | 0 / 0 ms |
| 3bhk_40x60_north_one_car | cp2_new | FEASIBLE | INFEASIBLE | VALID | VALID | CENTRAL_LIVING_BEDROOM_WINGS | – / 8 / 0 | – / 3051 | 384 / 372 ms |
| 2bhk_35x50_south_car | cp2_new | FEASIBLE | INFEASIBLE | VALID | VALID | SPINE | – / 0 / 0 | – / 1904 | 230 / 225 ms |
| 2bhk_30x55_west_twowheeler | cp2_new | FEASIBLE | VALID | VALID | VALID | SPINE | 4 / 0 / 0 | 10965 / 310 | 326 / 327 ms |
| 3bhk_35x70_east_car | cp2_new | FEASIBLE | VALID | VALID | VALID | SPINE | 4 / 1 / 1 | 8749 / 2051 | 354 / 355 ms |
| 1bhk_30x40_no_parking | cp2_new | FEASIBLE | VALID | VALID | VALID | SPINE | 3 / 1 / 1 | 6035 / 3160 | 68 / 66 ms |
| 4bhk_45x75_two_cars_puja | cp2_new | FEASIBLE | INFEASIBLE | VALID | VALID | L_CIRCULATION | – / 10 / 4 | – / 7639 | 902 / 868 ms |
| 3bhk_50x60_wide_two_cars | cp2_new | FEASIBLE | VALID | VALID | VALID | CENTRAL_LIVING_BEDROOM_WINGS | 8 / 3 / 1 | 30115 / 4044 | 453 / 451 ms |
| 4bhk_40x90_deep_car_utility | cp2_new | FEASIBLE | VALID | VALID | VALID | L_CIRCULATION | 10 / 2 / 2 | 23438 / 6017 | 785 / 776 ms |
| 2bhk_25x50_narrow_open_plan | cp2_new | MEASURE | INFEASIBLE | VALID | VALID | L_CIRCULATION | – / 1 / 0 | – / 1301 | 119 / 118 ms |
| 4bhk_25x40_overfull | cp2_new | INFEASIBLE | INFEASIBLE | PROVEN | PROVEN | – | – / – / – | – / – | 0 / 0 ms |
| 2bhk_12x40_too_narrow | cp2_new | INFEASIBLE | INFEASIBLE | PROVEN | PROVEN | – | – / – / – | – / – | 0 / 0 ms |
| 3bhk_25x30_setbacks_eat_plot | cp2_new | INFEASIBLE | INFEASIBLE | PROVEN | PROVEN | – | – / – / – | – / – | 1 / 0 ms |
| prop_square_45x45 | proportion | MEASURE | INFEASIBLE | VALID | VALID | CENTRAL_LIVING_BEDROOM_WINGS | – / 4 / 0 | – / 1930 | 338 / 338 ms |
| prop_mid_40x55 | proportion | MEASURE | VALID | VALID | VALID | FRONT_PUBLIC_REAR_PRIVATE | 4 / 6 / 2 | 10832 / 2519 | 278 / 273 ms |
| prop_wide_60x35 | proportion | MEASURE | INFEASIBLE | NO_SUPPORTED_LAYOUT | VALID | FRONT_LIVING_REAR_BEDROOM | – / – / 1 | – / 5202 | 205 / 199 ms |
| prop_wide_70x30 | proportion | MEASURE | INFEASIBLE | NO_SUPPORTED_LAYOUT | NO_SUPPORTED_LAYOUT | – | – / – / – | – / – | 159 / 156 ms |
| prop_very_wide_80x28 | proportion | MEASURE | INFEASIBLE | NO_SUPPORTED_LAYOUT | VALID | LINEAR_REAR_CORRIDOR | – / – / 6 | – / 9298 | 164 / 167 ms |
| prop_deep_30x70 | proportion | MEASURE | INFEASIBLE | VALID | VALID | SPINE | – / 0 / 2 | – / 1710 | 233 / 230 ms |
| prop_deep_25x90 | proportion | MEASURE | INFEASIBLE | NO_SUPPORTED_LAYOUT | NO_SUPPORTED_LAYOUT | – | – / – / – | – / – | 218 / 208 ms |
| prop_very_deep_22x100 | proportion | MEASURE | INFEASIBLE | NO_SUPPORTED_LAYOUT | NO_SUPPORTED_LAYOUT | – | – / – / – | – / – | 177 / 174 ms |
| q01_2bhk_45x35_wide_shallow_car | quality | MEASURE | INFEASIBLE | not run | NO_SUPPORTED_LAYOUT | – | – / not run / – | – / – | 144 / 136 ms |
| q02_3bhk_60x40_wide_two_cars | quality | MEASURE | INFEASIBLE | not run | NO_SUPPORTED_LAYOUT | – | – / not run / – | – / – | 199 / 203 ms |
| q03_1bhk_20x45_narrow_no_car | quality | MEASURE | INFEASIBLE | not run | NO_SUPPORTED_LAYOUT | – | – / not run / – | – / – | 37 / 37 ms |
| q04_2bhk_25x60_narrow_twowheeler | quality | MEASURE | INFEASIBLE | not run | VALID | SPINE | – / not run / 1 | – / 3190 | 162 / 161 ms |
| q05_3bhk_30x75_deep_car | quality | MEASURE | VALID | not run | VALID | SPINE | 4 / not run / 0 | 11184 / 924 | 314 / 306 ms |
| q06_4bhk_60x90_large_two_cars_puja_utility | quality | MEASURE | VALID | not run | VALID | CENTRAL_LIVING_BEDROOM_WINGS | 11 / not run / 1 | 77327 / 7724 | 1139 / 1113 ms |
| q07_3bhk_50x50_square_car_utility | quality | MEASURE | INFEASIBLE | not run | VALID | CENTRAL_LIVING_BEDROOM_WINGS | – / not run / 0 | – / 3108 | 455 / 444 ms |
| q08_2bhk_35x40_compact_open_plan | quality | MEASURE | VALID | not run | VALID | FRONT_EXTENSION | 3 / not run / 0 | 9353 / 2783 | 77 / 77 ms |
| q09_2bhk_30x40_compact_car | quality | MEASURE | INFEASIBLE | not run | NO_SUPPORTED_LAYOUT | – | – / not run / – | – / – | 101 / 99 ms |
| q10_3bhk_40x70_all_attached | quality | MEASURE | VALID | not run | VALID | CENTRAL_LIVING_BEDROOM_WINGS | 8 / not run / 2 | 15386 / 3887 | 346 / 343 ms |
| q11_2bhk_40x50_twowheeler_utility_puja | quality | MEASURE | VALID | not run | VALID | CENTRAL_LIVING_BEDROOM_WINGS | 8 / not run / 1 | 22689 / 3266 | 404 / 394 ms |
| q12_4bhk_50x100_very_large_two_cars | quality | MEASURE | VALID | not run | VALID | CENTRAL_LIVING_BEDROOM_WINGS | 10 / not run / 4 | 42478 / 6892 | 931 / 910 ms |
| q13_3bhk_35x45_tight_car | quality | MEASURE | INFEASIBLE | not run | NO_SUPPORTED_LAYOUT | – | – / not run / – | – / – | 262 / 256 ms |
| q14_1bhk_25x30_tiny_no_car | quality | MEASURE | INFEASIBLE | not run | NO_SUPPORTED_LAYOUT | – | – / not run / – | – / – | 19 / 20 ms |
| q15_2bhk_50x30_wide_shallow_twowheeler | quality | MEASURE | INFEASIBLE | not run | VALID | CENTRAL_LIVING_BEDROOM_WINGS | – / not run / 0 | – / 1395 | 170 / 170 ms |
| q16_3bhk_45x60_puja_two_cars_utility | quality | MEASURE | INFEASIBLE | not run | NO_SUPPORTED_LAYOUT | – | – / not run / – | – / – | 702 / 697 ms |

**Acceptance figures** (Checkpoint 2 corpus; the shared cases are those VALID under both Checkpoint 1 and 2.1):

| Criterion | Checkpoint 2 | Checkpoint 2.1 | Target |
|---|---|---|---|
| Original expected-feasible VALID | 10 of 11 | **11 of 11** | ≥ 10 |
| Checkpoint 1 VALID cases still VALID | all | all (17 of 17) | all |
| INVALID results or INVALID build attempts | 0 | 0 | 0 |
| PROVEN only where expected infeasible | yes | yes | yes |
| Rooms over aspect limit vs Checkpoint 1, original corpus | 65.7% | **25.7%** (9 of 35) | ≤ 50% |
| Rooms over aspect limit vs Checkpoint 1, all shared cases | 52.9% | **21.4%** (24 of 112) | ≤ 50% |
| Mean quality vs Checkpoint 1, original corpus | 41.0% | **15.6%** | ≤ 50% |
| Mean quality vs Checkpoint 1, all shared cases | 38.8% | **16.0%** | ≤ 50% |
| Cases scoring worse than Checkpoint 1 | none | none | none |
| VALID cases, whole benchmark (50 cases, both corpora) | not measured (quality corpus is new) | 34 | measured |

**Checkpoint 2 plans rescored with the current Scorer** (the six Checkpoint 2 goldens, one comparison on equal terms):

| Case | Checkpoint 2 | Checkpoint 2.1 |
|---|---|---|
| 2bhk_30x50_north_twowheeler_open | 918, 1 over aspect | 603, 0 over aspect (SPINE) |
| 3bhk_40x65_east_puja | 7926, 5 | 3029, 0 (CENTRAL_LIVING_BEDROOM_WINGS) |
| 2bhk_40x80_west_two_cars | 6564, 2 | 3040, 1 (FRONT_PUBLIC_REAR_PRIVATE, rear yard) |
| 3bhk_40x60_asymmetric_setbacks | 11869, 4 | 2843, 0 (CENTRAL_LIVING_BEDROOM_WINGS, rear yard) |
| 2bhk_22x60_narrow_deep | 3133, 5 | 3100, 5 (SPINE) |
| 4bhk_50x80_large_two_cars | 28748, 8 | 8228, 3 (CENTRAL_LIVING_BEDROOM_WINGS) |

**Architectural quality** (VALID plans, Checkpoint 2.1, mean of each term in milli; 0 is best):

| Corpus group | VALID | Mean quality | Over aspect | ZONE_ORDER | BEDROOM_GROUPING | WET_CLUSTER | ADJACENCY | EXTERIOR_EXPOSURE | PARKING_CONVENIENCE | Circulation share | Families that won |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cp2_new | 9 of 12 | 3275 | 9 | 72 | 208 | 696 | 0 | 0 | 0 | 9.7% | wings 2, L circulation 3, spine 4 |
| original | 11 of 14 | 3182 | 15 | 90 | 183 | 423 | 0 | 0 | 0 | 8.2% | wings 3, front living rear bedroom 1, front public rear private 1, L circulation 1, spine 5 |
| proportion | 5 of 8 | 4132 | 11 | 38 | 200 | 400 | 0 | 0 | 0 | 10.6% | wings 1, front living rear bedroom 1, front public rear private 1, linear 1, spine 1 |
| quality | 9 of 16 | 3685 | 9 | 171 | 296 | 398 | 0 | 0 | 0 | 4.8% | wings 6, front extension 1, spine 2 |

**Topology diversity.** A family scores where it produced a VALID plan for the case (lower is better); a dash means it produced none. Solvable cases: 34 of 50. Mean VALID families per solvable case: 2.8. Seven of the eight families win at least one case outright; SIDE_WING produces VALID plans but never wins.

| Case | S | F | SW | HUB | PUB-PRIV | L | WINGS | LINEAR | VALID families |
|---|---|---|---|---|---|---|---|---|---|
| 2bhk_30x50_north_twowheeler_open | 603 | 4543 | – | – | 11896 | 4070 | – | – | 4 |
| 3bhk_40x65_east_puja | 7535 | 10493 | – | – | – | 4415 | 3029 | – | 4 |
| 2bhk_40x80_west_two_cars | 5928 | – | – | – | 3040 | 9682 | – | – | 3 |
| 1bhk_25x40_south_small | – | – | – | 1447 | – | – | – | – | 1 |
| 2bhk_22x60_narrow_deep | 3100 | – | – | – | – | – | – | – | 1 |
| 4bhk_50x80_large_two_cars | 28768 | 34190 | – | – | – | 12091 | 8228 | – | 4 |
| 3bhk_30x60_single_car_vastu | 941 | – | – | – | – | 2748 | – | – | 2 |
| 2bhk_35x55_utility_no_vastu | 2556 | – | – | – | 6134 | – | – | – | 2 |
| 3bhk_45x70_two_cars_puja | 18419 | – | – | – | – | 7914 | – | – | 2 |
| 3bhk_40x60_asymmetric_setbacks | – | 11809 | – | – | – | – | 2843 | – | 2 |
| 2bhk_30x45_common_bath_only | 324 | – | – | – | – | – | – | – | 1 |
| 3bhk_40x60_north_one_car | 9544 | 11147 | – | – | – | 5046 | 3051 | – | 4 |
| 2bhk_35x50_south_car | 1904 | – | – | – | 6442 | – | – | – | 2 |
| 2bhk_30x55_west_twowheeler | 310 | 19196 | – | – | 2360 | 4525 | – | – | 4 |
| 3bhk_35x70_east_car | 2051 | – | – | – | – | 2584 | – | – | 2 |
| 1bhk_30x40_no_parking | 3160 | 4504 | – | 4915 | 12928 | – | – | – | 4 |
| 4bhk_45x75_two_cars_puja | 16983 | – | – | – | – | 7639 | – | – | 2 |
| 3bhk_50x60_wide_two_cars | 16516 | 15212 | – | – | 6255 | 14380 | 4044 | – | 5 |
| 4bhk_40x90_deep_car_utility | 6639 | 12828 | 10083 | – | – | 6017 | 6509 | – | 5 |
| 2bhk_25x50_narrow_open_plan | 3032 | – | – | – | – | 1301 | – | – | 2 |
| prop_square_45x45 | – | 13312 | – | – | – | – | 1930 | – | 2 |
| prop_mid_40x55 | 4524 | 9506 | – | – | 2519 | 9467 | 3592 | – | 5 |
| prop_wide_60x35 | – | – | – | 5202 | – | – | – | – | 1 |
| prop_very_wide_80x28 | – | – | – | – | – | – | – | 9298 | 1 |
| prop_deep_30x70 | 1710 | – | – | – | – | 3447 | – | – | 2 |
| q04_2bhk_25x60_narrow_twowheeler | 3190 | – | – | – | – | 5240 | – | – | 2 |
| q05_3bhk_30x75_deep_car | 924 | – | – | – | – | 2846 | – | – | 2 |
| q06_4bhk_60x90_large_two_cars_puja_utility | 57563 | 51374 | – | – | – | 27671 | 7724 | – | 4 |
| q07_3bhk_50x50_square_car_utility | – | – | – | – | – | – | 3108 | – | 1 |
| q08_2bhk_35x40_compact_open_plan | 5799 | 2783 | – | – | 12411 | 8387 | – | – | 4 |
| q10_3bhk_40x70_all_attached | 6447 | – | – | – | – | 3973 | 3887 | – | 3 |
| q11_2bhk_40x50_twowheeler_utility_puja | 10603 | 12194 | – | – | 4863 | – | 3266 | – | 4 |
| q12_4bhk_50x100_very_large_two_cars | 20608 | 25854 | 30315 | – | – | 7048 | 6892 | – | 5 |
| q15_2bhk_50x30_wide_shallow_twowheeler | – | – | – | 6249 | – | – | 1395 | – | 2 |
| Cases with a VALID plan | 27 | 15 | 2 | 4 | 10 | 21 | 14 | 1 | |

Column key: S spine, F front extension, SW side wing, HUB front living rear bedroom, PUB-PRIV front public rear private, L L circulation, WINGS central living bedroom wings, LINEAR linear rear corridor.

## 11. SVG visual comparison

The renders and the montage are in `AI_DESIGN_ENGINE_CHECKPOINT_2_1_ASSETS/`:

- `svg/` has every VALID plan, each with its family, score breakdown and body hash.
- `montage_cp2_vs_cp2_1.html` sets Checkpoint 2 (left) against Checkpoint 2.1 (right) for the six requested cases, with the drawings inlined.

| Case | Checkpoint 2 | Checkpoint 2.1 |
|---|---|---|
| 2BHK 30x50 north | Spine, stepped front; bath and utility strips across the column | Same family, tighter: no room over aspect, circulation 15.8% to 12.4% |
| 3BHK 40x65 east, puja | Spine with five long rooms in two columns | Living and dining in the centre (each 3.95 × 5.9 m, larger than preferred), bedroom wings either side, kitchen beside dining: 0 rooms over aspect |
| 2BHK 40x80 west, two cars | Spine; parking 5.2 × 15.2 m; bedrooms mixed with kitchen and baths along the spine | Public front (parking, living), dining and kitchen, a cross corridor, bedrooms with baths side by side at the rear, an open rear yard |
| 1BHK 25x40 south | No plan | Living at the front, dining and kitchen, bedroom and bath behind, no corridor |
| 2BHK 22x60 narrow, deep | Single column beside a spine | Unchanged family and nearly unchanged plan; the plot's 5.3 m width forces it (section 16) |
| 4BHK 50x80, two cars | Spine; 6.7 m-wide columns; baths 6.7 × 2.2 m | Wings: two bedroom suites, the common bath, puja, kitchen and utility in one 2.8 m wing; parking and two bedrooms in the other; 3 rooms over aspect. The living room is 4.5 × 13.2 m and the dining room 4.5 × 6.8 m (section 16, L3) |

## 12. VPS benchmark

**Not run.** This machine has no SSH key, agent or credentials for the Hostinger KVM 2. The only trace is two Hostinger IP addresses in `~/.ssh/known_hosts`, and I did not try to connect to them. Acceptance items 9 and 10 therefore remain open. No production claim is made from the figures in section 13 (CP2-U5).

Command for the VPS, from the repository checkout at the commit under test, with the stack idle:

```bash
docker build -t p2b-api:cp2-1 apps/api
docker run --rm --cpus 2 --user root \
  -v "$PWD/apps/api/scripts:/app/scripts:ro" \
  -v "$PWD/apps/api/tests/fixtures/houseplans:/app/fixtures:ro" \
  -v "$PWD:/out" p2b-api:cp2-1 \
  python scripts/benchmark_houseplans.py --fixtures /app/fixtures --corpus all \
  --repeats 5 --fresh-process --concurrency 1,2,4 \
  --json /out/benchmark_vps.json --label vps-kvm2
```

Record with the result: `nproc`, `free -m`, `docker version`, `python --version` inside the image, and `git rev-parse HEAD`. The JSON records the corpus, labels and per-case results. `--user root` only lets the throwaway container write the result file into the mounted directory; the service image and its user are unchanged.

### 12.1 Final acceptance gate attempt (2026-10-07)

The gate was attempted and could not run. What was checked:

| Check | Finding |
|---|---|
| A Plan2Build staging or production environment | None is defined in the repository. `.github/workflows/ci.yml` has no deploy job: "Deploy jobs (GHCR push, staging, production) are added once the repository owner and the deploy approver are decided (baseline D-13, AQ-29)". `infra/` holds only the local stack and the R2 CORS files |
| Access from this machine | No SSH key or agent, no SSH config, no remote Docker context (only Docker Desktop), no PuTTY session, no GitHub CLI login. `~/.ssh/known_hosts` lists two Hostinger IP addresses; it is not recorded which project they serve, there are no credentials for them, and no connection was attempted |
| Substitutes | None used. Laptop, Docker Desktop and WSL runs are rehearsals only (CP2-U5); they are not reported as VPS results |

To make the run one step for whoever has access, `apps/api/scripts/vps_benchmark.sh` was added. It changes nothing in the engine:

- It records the provider (DMI vendor and product), CPU count and model, RAM, kernel, OS, Docker client and server versions, and the commit. It also records whether the working tree is clean, the corpus and ruleset sha256, the image's Python version and the load before and after.
- It builds the production API image (the worker runs the same image).
- It runs the documented command above unchanged.
- It times one cold start: a fresh container importing the engine and generating one plan.

The concurrency check in `benchmark_houseplans.py` now also records throughput, process CPU (cores used) and resident memory for each concurrency level (Task 3).

```bash
bash apps/api/scripts/vps_benchmark.sh
```

Its output directory holds `environment.txt` and `benchmark_vps.json`. Every acceptance number comes from that file; the gates are in `summary.gates`.

**Worker deployment, pending the VPS numbers.** The local check of the extended concurrency measurement is a tooling check, not VPS evidence:

| At once | p95 | Throughput | CPU used |
|---|---|---|---|
| 1 | 424 ms | 3.92 plans/s | 1.00 core |
| 2 | 833 ms | 4.01 plans/s | 0.99 core |

Two generations in one process share one core: throughput does not rise and latency doubles. One engine worker process per assigned core, concurrency 1 each, is the model these numbers support. On a 2 vCPU KVM 2 that also hosts the API, web, ClamAV and staging, that is one engine worker if a core must stay free for the rest, two if engine traffic justifies it. The VPS run decides: its `cpu_count`, memory and concurrency results are the inputs. No queue redesign, OR-Tools or extra infrastructure is indicated.

## 13. Memory and performance (development machine; not the VPS)

| Measure | Target (VPS) | Laptop, Windows, Python 3.13.9 | Production image, `--cpus 2`, Linux, Python 3.12.15 | Samples |
|---|---|---|---|---|
| Normal generation p95 | ≤ 1000 ms | 433 ms | 425 ms | 130 |
| Difficult generation p99 | ≤ 3000 ms | 1159 ms | 1129 ms | 40 |
| Infeasible, decided by the pre-check, p95 | ≤ 500 ms | 0.6 ms | 0.5 ms | 25 |
| Infeasible, decided by search, p95 | ≤ 1500 ms | 702 ms | 697 ms | 55 |
| Validation p95 | ≤ 20 ms | 2.3 ms | 2.6 ms | 170 |
| Repair p95 (a door slid off its wall, repaired) | ≤ 100 ms | 6.2 ms | 7.0 ms | 170 |
| Memory increase over the whole run | ≤ 50 MB | 4.2 MB | 4.1 MB | 1 |
| Slowest first (cold) generation of a case | none | 1137 ms | 1106 ms | 50 |
| Fixture-fit table, once per ruleset | none | 81 ms | 97 ms | 1 |

**Concurrency** (normal cases run 1, 2 or 4 at a time on threads in one process, as the worker runs engine jobs through `asyncio.to_thread`):

| At once | Laptop p95 | Container p95 | Container p99 |
|---|---|---|---|
| 1 | 437 ms | 434 ms | 468 ms |
| 2 | 899 ms | 885 ms | 952 ms |
| 4 | 1892 ms | 2018 ms | 2183 ms |

The engine is CPU-bound Python, so generations in one worker process share one core and latency grows almost linearly with how many run at once. The worker's default concurrency is 8 (`worker_concurrency`). The current contract (CP1-07) serialises generations per project, not across projects. With more than about two generations at once on one process, normal-case latency passes 1 s. The settings already allow a remedy without code: a dedicated engine worker per vCPU (`P2B_WORKER_QUEUES=engine`, `P2B_WORKER_CONCURRENCY=1`), so further generations wait in the queue instead of slowing each other. That is decision CP2.1-D2.

## 14. Test results

| Check | Result |
|---|---|
| Full API suite with coverage | 719 passed, 1 skipped, 1 failed. The failure was the new benchmark test's fixture omitting the quality summary (a test defect). Fixed, and that file re-run: 8 passed. Coverage 91% overall, 89% on services (gates 70% and 85%) |
| Engine test modules | All pass, including the Checkpoint 1 goldens, the 39 validation codes and the 21-case negative corpus |
| Static checks | ruff format and lint, mypy strict (`src tests scripts`), import-linter (5 contracts kept, engine purity included), contract regeneration, web lint and type check |

New and changed tests:

- **`test_houseplan_cp2_1.py`:**
  - selection verdicts and reasons;
  - each of the eight families building a VALID plan;
  - five or more winning families across plot shapes;
  - small, narrow-deep, wide-shallow and large plots;
  - two-car parking;
  - kitchen and dining connected in every family;
  - BEDROOM_GROUPING, ZONE_ORDER, WET_CLUSTER and open-area exposure;
  - regressions for P6 and P7, the fixed-last-part split, minimum-extent starts, open-area insets and duplicate topologies;
  - validator independence on a wings plan;
  - reproducibility;
  - score agreement on a plan with an open yard;
  - no circulation through bedrooms.
- **`test_houseplan_cp2.py`:** moved to the topology API; the fixture-repair test no longer assumes a particular layout.
- **`test_houseplan_benchmark.py`:**
  - 11 of 11 original cases VALID;
  - the aspect criterion is now a normal assertion and passes, where it was a strict expected failure;
  - five or more winning families;
  - both corpora;
  - the live Checkpoint 1 baseline equals the recorded one.
- **Validator:** all 39 codes and the 21-case negative corpus are unchanged and pass.

## 15. Deterministic repeatability

| Check | Result |
|---|---|
| Checkpoint 1 goldens (MVP solver, frozen ruleset) | Byte-identical: `bc430b40…`, `97f446ba…`, `1ba2ffbc…` |
| Checkpoint 1 ruleset hash | `f04a2b9f…`, unchanged (1.1.0 fields omitted at their default) |
| Zoned goldens | Eight plans from six families, byte-for-byte in-process and in a fresh process |
| Repeated runs | 50 of 50 cases identical over 6 runs; candidate rankings identical |
| Fresh process, whole benchmark | Identical |
| Across platforms | All 50 body hashes identical: Windows / Python 3.13.9 and the Linux production image / Python 3.12.15 |

## 16. Remaining limitations

| ID | Limitation | Evidence | Next step |
|---|---|---|---|
| L1 | **VPS gate not run** | Section 12 | Run the command; needs VPS access |
| L2 | Concurrent generations share one core per worker process | Section 13 | CP2.1-D2 |
| L3 | 4BHK 50x80 with two cars: the wings layout's living room is 4.5 × 13.2 m. The centre must match the deepest wing; the gallery and court variants that release it need 3.8 m of living-room front plus a 1.2 m gallery, which the 12.6 m width with a 5.15 m two-car wing does not have | Render, `svg/4bhk_50x80_large_two_cars.svg` | A wing corridor that also serves the parking wing, or parking in the front setback (CP2-U1) |
| L4 | Narrow, deep plots with a car (25x90, 22x100): the living room and parking must both touch the road edge (the entrance rule; parking inside the footprint, CP2-U1), and together they need more than the 5.6 m width | NO_SUPPORTED_LAYOUT | CP2-U1 decision; not a topology gap |
| L5 | Wide, shallow plots with car parking (45x35 and 60x40 with cars, 70x30): the car's 5 m depth leaves too little behind it; every family is over by 0.02 to 0.8 m on these synthetic minimums | NO_SUPPORTED_LAYOUT with the closest shortfalls | A parking-courtyard or L-around-parking family, or front-setback parking (CP2-U1) |
| L6 | Very small plots (25x30 1BHK, 20x45 1BHK, 30x40 2BHK with car, 35x45 3BHK with car) | NO_SUPPORTED_LAYOUT; some likely physically impossible under these synthetic minimums but not provable by the pre-check's arithmetic | Real minimums (AD-05) decide |
| L7 | 2BHK 22x60: 5 rooms over aspect limit; a 5.3 m-wide plot makes every room full width beside the spine | Unchanged from Checkpoint 2 | Synthetic aspect limits; a narrower passage or open-plan dining would need rules (AD-05) |
| L8 | SIDE_WING and LINEAR_REAR_CORRIDOR win rarely (SIDE_WING never as the overall winner) | Family table | Kept: they are the best family on some plots and cheap to evaluate |
| L9 | Wet clustering is the weakest term (mean 0.4 to 0.7 of its scale): bathrooms follow their bedrooms rather than the kitchen | Quality table | A family variant grouping wet rooms, if the ruleset weights it higher (AD-05) |
| L10 | The pre-check's PROVEN homeowner wording is still draft (CP2-D3) | Checkpoint 2 report | Approve or replace |
| L11 | All quality judgements rest on synthetic preferences, aspect limits and weights | Ruleset note | AD-05 |

## 17. Can Checkpoint 2 now be accepted?

**Not yet.** On this machine:

- every Checkpoint 2 criterion is met: feasibility (11 of 11), aspect (25.7% and 21.4%), quality (15.6% and 16.0%), no INVALID, honest classes, determinism, the Checkpoint 1 contracts, and the full test suite;
- every Checkpoint 2.1 gate item except 9 and 10 is met.

The remaining condition for both checkpoints is the same: the benchmark on the target VPS. The 2-CPU container rehearsal suggests wide margins on every latency target, but under CP2-U5 a rehearsal is not acceptance.

## 18. Next checkpoint recommendation

1. **Run the VPS benchmark** (L1), record it here, and accept or reject Checkpoint 2 and 2.1 on it. Commit and tag only then.
2. **Decide CP2.1-D2:** a dedicated engine worker per vCPU with concurrency 1, measured on the VPS with `--concurrency`.
3. **Then Checkpoint 3 (the 2D editor)** on this engine, unchanged in its contracts: HousePlan as the source of truth, typed operations, the same validator. No change to the engine is needed for it.
4. Carry L3 to L7 as topology work alongside AD-05 (real minimums) and CP2-U1 (front-setback parking): they are mostly rule questions, not search questions.

Decisions for Chirag:

| ID | Decision | Recommendation |
|---|---|---|
| CP2.1-D1 | A Plan2Build VPS environment to benchmark on (D-13, AQ-29), and access to it, or someone with access runs `apps/api/scripts/vps_benchmark.sh` and returns its output directory | Required before acceptance |
| CP2.1-D2 | Engine concurrency in production: a dedicated engine worker per vCPU, concurrency 1 | Yes; measure on the VPS |
| CP2.1-D3 | Keep the two new soft terms (ZONE_ORDER, BEDROOM_GROUPING) and the changed EXTERIOR_EXPOSURE measure | Yes |
| CP2-D1 (Checkpoint 2) | The per-violation aspect term | No longer needed: the criterion is met with the approved term |
| CP2-D3 (Checkpoint 2) | PROVEN homeowner wording | Approve or replace |
| Carried | AD-05, AD-06, AD-13, AD-16, CP2-U1, CP2-U3 | Unchanged; production stays blocked |
