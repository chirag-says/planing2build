# Plan2Build: AI design engine, Checkpoint 2 implementation report

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_2_REPORT.md` |
| Date | 2026-10-06 |
| Plan | `AI_DESIGN_ENGINE_CHECKPOINT_2.md` with Chirag's approval and decisions CP2-U1 to CP2-U8 (its section 0 governs) |
| Branch | `houseplans-checkpoint-1`. Checkpoint 1 is committed as `22628ab` (annotated tag `houseplans-cp1`, CP2-U6). The Checkpoint 2 implementation is in the working tree, **not committed**, awaiting review |
| Superseded by | `AI_DESIGN_ENGINE_CHECKPOINT_2_1_REPORT.md` (2026-10-07): Checkpoint 2.1 reworked the topologies and re-measured everything below; this report records the Checkpoint 2 state |
| Status | **CHECKPOINT 2 IMPLEMENTED, NOT YET ACCEPTED.** One acceptance criterion missed (rooms over aspect limit, section 8). The VPS gate (CP2-U5) has **not run**: this machine has no access to the VPS (section 9). Checkpoint 3 not started |
| Ruleset | All rule values, preferences and weights are the **SYNTHETIC / TEST ONLY** ruleset (CP1-06, CP2-U7). Production stays blocked (AD-05) |

---

## 1. Files created

| Path | Purpose |
|---|---|
| `apps/api/src/p2b/houseplans/engine/zoning.py` | Zone candidates: families SPINE and FRONT_EXTENSION, variants, ranked column splits, isomorphic splits dropped |
| `apps/api/src/p2b/houseplans/engine/compile.py` | Constraint compiler: `ZonedProblem` (variables, geometry, hard shortfalls, access topology) and its compiled sizing evaluator |
| `apps/api/src/p2b/houseplans/engine/objective.py` | The Scorer: eleven soft terms, `score`, `score_plan`, the shared size-term helpers |
| `apps/api/src/p2b/houseplans/engine/footprint.py` | Exact clear rectangles from room rectangles (the walls the builder will create) |
| `apps/api/src/p2b/houseplans/engine/feasibility.py` | Pre-check (PROVEN), NO_SUPPORTED_LAYOUT explanations, homeowner messages |
| `apps/api/src/p2b/houseplans/engine/fit.py` | Fixture-fit minimums derived from the ruleset and the real placement routine |
| `apps/api/src/p2b/houseplans/engine/build.py` | The plan builder, moved out of `generate.py` unchanged, plus the schema version to emit |
| `apps/api/src/p2b/houseplans/engine/solver/zoned_ls.py` | `ZonedLocalSearchSolver` and `search` (ranked layouts, closest infeasible layout) |
| `apps/api/scripts/benchmark_houseplans.py` | Benchmark: per-case record, latency per class, validation and repair latency, memory, determinism, acceptance, SVGs |
| `apps/api/tests/test_houseplan_cp2.py` | Zoning, compiler, Scorer agreement, pipeline, fallback, feasibility, repair (27 tests) |
| `apps/api/tests/test_houseplan_benchmark.py` | Acceptance on the benchmark corpus (6 tests and 1 strict expected failure, section 8) |
| `apps/api/tests/fixtures/houseplans/benchmark_cp2.json` | Benchmark corpus: 26 cases plus 8 proportion cases, labels fixed before the first run |
| `apps/api/tests/fixtures/houseplans/benchmark_baseline_cp1.json` | Recorded Checkpoint 1 baseline on the same corpus |
| `apps/api/tests/fixtures/houseplans/ruleset_synthetic_cp1_test_only.json` | The Checkpoint 1 ruleset, frozen, for the Checkpoint 1 goldens |
| `apps/api/tests/fixtures/houseplans/golden/zoned/*.json` | Six zoned-solver goldens: every variant, both families |
| `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_2_ASSETS/*.svg` | Debug renders of all 22 VALID benchmark plans, with score breakdowns |
| `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_2_ASSETS/benchmark_local.json` | Full benchmark record, laptop |
| `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_2_ASSETS/benchmark_local_docker_2cpu.json` | Full benchmark record, production image limited to 2 CPUs on the laptop |
| `tools/spikes/cp2_layout/aspect_count_experiment.py` | Research only: the aspect-term experiment behind decision CP2-D1 |

## 2. Files modified

| Path | Change |
|---|---|
| `apps/api/src/p2b/core/vocabulary.py` | Soft term kinds, `ConstraintOutcome.PARTIAL`, `SolverKind.ZONED_LOCAL_SEARCH`, `TopologyFamily`, `FeasibilityClass`, `RepairReason` |
| `apps/api/src/p2b/core/config.py` | `houseplans_solver` (ZONED_LOCAL_SEARCH default, DETERMINISTIC_MVP); CP-SAT is not a selectable value |
| `apps/api/src/p2b/houseplans/engine/model.py` | Schema 1.1.0: optional `Constraint.score_milli`, omitted when absent so 1.0.0 hashes do not move |
| `apps/api/src/p2b/houseplans/engine/ruleset.py` | Content 1.1.0 (preferences, aspect limits, circulation target, soft relations, zoning options, objective, structure-only setback, parking-placement and orientation tables). Fields new in 1.1.0 are omitted from serialisation at their default, so a 1.0.0 ruleset hashes exactly as in Checkpoint 1 |
| `apps/api/src/p2b/houseplans/engine/generate.py` | Pipeline: compile, pre-check, solve, ranked fallback, build, validate, repair, scored soft constraints. The Checkpoint 1 path is kept and emits 1.0.0 |
| `apps/api/src/p2b/houseplans/engine/repair.py` | Reason codes; OPENING_OVERLAP, FIXTURE_BLOCKS_OPENING and FIXTURE_CLEARANCE_BLOCKED repairers; one move per element per pass |
| `apps/api/src/p2b/houseplans/engine/validate.py` | Those three codes now carry repair hint AUTO |
| `apps/api/src/p2b/houseplans/engine/upgrade.py` | Docstring: 1.1.0 is additive, no upgrader needed |
| `apps/api/src/p2b/houseplans/engine/__init__.py` | Exports |
| `apps/api/src/p2b/houseplans/service.py` | `solver_for` (configured solver, Checkpoint 1 solver for a ruleset without an objective); the job uses the solver stored on the plan; classified infeasibility JSON |
| `apps/api/src/p2b/houseplans/schemas.py`, `router.py` | `InfeasibilityOut` gains classification, message, explanation, constraints; derived `quality` block on the plan detail |
| `apps/api/tests/fixtures/houseplans/ruleset_synthetic_test_only.json` | Synthetic content 1.1.0 |
| `apps/api/tests/houseplans_support.py`, `test_houseplan_golden.py`, `test_houseplans_api.py` | Checkpoint 1 goldens on the frozen ruleset; zoned goldens; API assertions for 1.1.0, soft terms, quality and PROVEN |
| `apps/api/scripts/update_houseplan_golden.py`, `render_houseplan_debug.py` | Zoned goldens; renderer reusable by the benchmark |
| `apps/api/pyproject.toml` | mypy path includes `scripts` (CI type-checks scripts and the benchmark test imports one) |
| `packages/contracts/*` | Regenerated |

No migration (as planned, section P). No web source change. No new dependency.

**Deviations from the plan's file list (section O), each deliberate:**

| Planned | Done instead | Why |
|---|---|---|
| `engine/solver/cpsat.py` (research, lazy `ortools` import) | Kept in `tools/spikes/cp2_layout/cpsat_sizer.py` | Section 0 says CP-SAT stays research code only. The engine purity contract (import-linter, external packages included) rejects an `ortools` import anywhere in the engine, lazy or not |
| `CandidateLayout`, `solve_zoned` in `solver/__init__.py` | `CandidateLayout`, `search` in `solver/zoned_ls.py` | Keeps the solver interface module free of one solver's types |
| Soft preferences in `intent.py` | Not changed | No requirement answer or design input expresses a soft preference yet; all preferences come from ruleset data |
| Tests split as `_zoning`, `_objective`, `_feasibility` | One `test_houseplan_cp2.py` | Same coverage; one fixture setup |
| Larger corpus in `requirements.json` | `benchmark_cp2.json` | Keeps the Checkpoint 1 fixture and its goldens untouched |

## 3. Checkpoint 1 commit

| Item | Value |
|---|---|
| Commit | `22628ab` "AI design engine Checkpoint 1: houseplans module, migration 0019, validator" |
| Tag | `houseplans-cp1` (annotated, object `3927b68`) |
| Later commit | `dd42c6f` Checkpoint 2 readiness and the layout spike |

## 4. Solver architecture

```
answers + design inputs ─ normalise ─▶ ArchitecturalIntent
  ─ compile_problem ─▶ LayoutProblem (or RULESET_INCOMPLETE)
  ─ FeasibilityPrecheck ─▶ PROVEN infeasible (stop) | undecided
  ─ zoning.candidates ─▶ zone candidates (families S, F; bounded, deterministic)
  ─ compile.ZonedProblem per candidate ─▶ variables, hard shortfalls, access topology
  ─ rank by starting point, keep objective.candidate_limit
  ─ size each: cyclic coordinate search, lexicographic (hard shortfall, Scorer size terms)
  ─ re-check exact wall insets; rank feasible layouts by the full Scorer
  ─ for the best objective.build_attempts layouts:
        build (walls, openings, fixtures) ─ validate ─ repair ─ VALID? stop : next
  ─ VALID HousePlan 1.1.0 with HARD (MET) and SOFT (scored) constraints
  ─ or INFEASIBLE / NO_SUPPORTED_LAYOUT with the closest layout's shortfalls
```

| Part | Detail |
|---|---|
| Production solver | `ZonedLocalSearchSolver`, pure Python, no dependency, `SolverKind.ZONED_LOCAL_SEARCH`, version 1.0.0 |
| Fallback and reference | `DeterministicMVPLayoutSolver` (Checkpoint 1), selected by setting or automatically for a ruleset without an objective. Its documents stay schema 1.0.0 and byte-identical |
| Search | Moves: one variable ± step; a cut line between two stacked rooms; the front band with each column's first room compensating. Steps 1200, 600, 300, 150 mm, then the 50 mm grid. A move is accepted only on strict improvement, so the search terminates; a budget of 6000 evaluations per candidate is a safety bound never reached on the corpus |
| Compiled evaluator | Integer tuples instead of rectangle objects, per-candidate constants, the Scorer's own size helpers. A test holds it equal to the shortfall list plus the Scorer on 300+ sizings |
| Hard constraints in the compiler | Clear minimum short side and area (exact wall insets), fixture-fit minimums, parking clear size, passage length, and one generic access rule: every (room, entered-from) pair shares a wall at least as long as its opening plus jambs |
| Validity | Decided only by the validator. The compiler's hard constraints are necessary conditions used to search; nothing is VALID until the existing validator accepts the built plan |
| Fallback | A layout that fails placement or validation after repair is recorded in `attempts` and the next is built. On the corpus: 0 INVALID attempts |
| No cheating | The solver chooses sizes only. Rooms, counts, types, minimums, setbacks, plot and road side come from the intent and ruleset and are never changed |

## 5. Topology families

| Family | Variants | Description |
|---|---|---|
| SPINE (S) | `two`, `stepped`, `one` | Front band: parking at one side, the entry room on the road edge. A passage spine runs back from the entry room. Other rooms stack in one or two columns in groups (a host and the rooms reached only through it). `two`: spine anywhere over the entry room. `stepped`: the parking side of the front band may be deeper; the outer column starts under it. `one`: single column. Optional rear band: one room across the full width behind the spine |
| FRONT_EXTENSION (F) | same | As S with one more room beside the entry room in the front band: a bedroom or the dining room (CP2-U2). Privacy is a scored term, never a prohibition |

Enumeration per case: extension (none, or the last single-room group of each permitted type) × rear (none or a bedroom) × parking side × (two and stepped × the best `split_limit` distinct column splits, plus one). Splits are ranked by a depth lower bound, then imbalance, then bit mask; splits that only exchange rooms of the same type are dropped. Cases on the corpus enumerate 25 to 54 candidates; 32 (`candidate_limit`) are sized. No courtyard, H, paired-cell or other topology was added.

## 6. Objective and scoring

The Scorer (`engine/objective.py`) is the one definition of quality. The solver ranks with it and the API scores the stored plan with it; a test asserts the solver's predicted score equals the built plan's score term by term, and that the solver's clear rectangles equal the validator's.

`total = Σ weight × score_milli` over evaluated terms. Lower is better. Terms never decide validity.

| Term | Measure (milli, 0 = met) | Synthetic weight |
|---|---|---|
| AREA_DEVIATION | Mean over rooms of \|clear area − preferred\| / preferred | 2 |
| DIMENSION_DEVIATION | Mean of short and long side deviations from preferred | 1 |
| ASPECT_EXCESS | Σ (long/short − limit) over rooms above their limit (doc section E definition) | 3 |
| OVERSIZE | Σ (area − max) / max over rooms above their maximum | 2 |
| CIRCULATION_SHARE | max(0, passage clear area / enclosed clear area − target) | 2 |
| ADJACENCY | Share of soft relation rules unmet (kitchen and dining, dining and living sharing a door-width wall) | 1 |
| WET_CLUSTER | Share of wet rooms sharing no wall with another wet room | 1 |
| EXTERIOR_EXPOSURE | Share of window-needing rooms with less exterior wall than `exposure_min_mm` | 1 |
| PRIVACY | Share of bedrooms in the front band or touching the entry room | 1 |
| PARKING_CONVENIENCE | Parking does not touch the entry room | 1 |
| ORIENTATION | Always NOT_EVALUATED until AD-13 (CP2-U8); no Vastu rule invented | 1 |

Outcome per term: MET (0), PARTIAL (< 1000), UNMET (≥ 1000), NOT_EVALUATED (no rule data). In the document every term is a SOFT constraint with its weight, `score_milli`, outcome, the rooms that cost score, and origin `RULESET` / `ruleset:objective.weights.<KIND>`. The plan detail adds a derived `quality` block (total, terms, per-room clear size and aspect).

## 7. Benchmark results

Corpus `benchmark_cp2.json`: the 14 spike cases with their labels unchanged, 12 new cases labelled before the first run, and 8 proportion cases (one 2-bedroom, one-car programme across plot shapes, expectation MEASURE). Latency class rule fixed in advance: 4+ bedrooms or 2+ parking spaces is "difficult". Five timed runs per case after one untimed run.

Laptop: Windows 11, Python 3.13.9. Container: the production API image (Python 3.12.15, Linux) limited to 2 CPUs on the same laptop.

| Case | Group | Expected | Class | Result | Topology | Quality | Rooms over aspect | Circulation | p50 laptop | p50 2-CPU container | Body hash |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2bhk_30x50_north_twowheeler_open | original | FEASIBLE | normal | VALID | SPINE_stepped_pL_s3 | 918 | 1 | 15.8% | 116 ms | 144 ms | `3f8a4baed51e` |
| 3bhk_40x65_east_puja | original | FEASIBLE | normal | VALID | SPINE_stepped_pL_s2 | 7866 | 5 | 10.0% | 278 ms | 330 ms | `a96bd3ab877e` |
| 2bhk_40x80_west_two_cars | original | FEASIBLE | difficult | VALID | SPINE_stepped_pR_s3 | 6564 | 2 | 11.8% | 307 ms | 396 ms | `0744363bd303` |
| 1bhk_25x40_south_small | original | FEASIBLE | normal | NO_SUPPORTED_LAYOUT |  |  |  |  | 66 ms | 79 ms | `INFEASIBLE` |
| 2bhk_22x60_narrow_deep | original | FEASIBLE | normal | VALID | SPINE_one_pL | 3133 | 5 | 17.9% | 118 ms | 141 ms | `f9708e4e4388` |
| 4bhk_50x80_large_two_cars | original | FEASIBLE | difficult | VALID | SPINE_stepped_pL_s2 | 28656 | 8 | 8.6% | 560 ms | 667 ms | `474cbab7bf2e` |
| 3bhk_30x60_single_car_vastu | original | FEASIBLE | normal | VALID | SPINE_stepped_pL_s2 | 909 | 0 | 13.3% | 223 ms | 267 ms | `16590b4c5279` |
| 2bhk_35x55_utility_no_vastu | original | FEASIBLE | normal | VALID | SPINE_stepped_pL_s1 | 2669 | 2 | 11.8% | 229 ms | 272 ms | `27bb49d57fb4` |
| 3bhk_45x70_two_cars_puja | original | FEASIBLE | difficult | VALID | SPINE_stepped_pL_s3 | 18312 | 7 | 9.0% | 369 ms | 446 ms | `cb28f01c195d` |
| 3bhk_40x60_asymmetric_setbacks | original | FEASIBLE | normal | VALID | FRONT_EXTENSION_stepped_pL_x_bedroom_3_s1 | 11218 | 4 | 8.9% | 297 ms | 354 ms | `dd75a8d110f4` |
| 2bhk_30x45_common_bath_only | original | FEASIBLE | normal | VALID | SPINE_stepped_pL_s0 | 334 | 0 | 11.9% | 127 ms | 150 ms | `f3d4411ba8c5` |
| 3bhk_20x30_too_small | original | INFEASIBLE | infeasible | PROVEN |  |  |  |  | 0 ms | 0 ms | `INFEASIBLE` |
| 2bhk_30x60_two_cars_too_wide | original | INFEASIBLE | infeasible | NO_SUPPORTED_LAYOUT |  |  |  |  | 186 ms | 226 ms | `INFEASIBLE` |
| 4bhk_30x40_overfull | original | INFEASIBLE | infeasible | PROVEN |  |  |  |  | 0 ms | 0 ms | `INFEASIBLE` |
| 3bhk_40x60_north_one_car | cp2_new | FEASIBLE | normal | VALID | SPINE_stepped_pL_s2 | 9482 | 8 | 10.0% | 304 ms | 357 ms | `a4e7f36e53ec` |
| 2bhk_35x50_south_car | cp2_new | FEASIBLE | normal | VALID | SPINE_stepped_pL_s1 | 1925 | 0 | 11.1% | 166 ms | 210 ms | `128edf5b7c4a` |
| 2bhk_30x55_west_twowheeler | cp2_new | FEASIBLE | normal | VALID | SPINE_stepped_pL_s3 | 483 | 0 | 16.7% | 116 ms | 134 ms | `0efd8b7edaad` |
| 3bhk_35x70_east_car | cp2_new | FEASIBLE | normal | VALID | SPINE_stepped_pL_s2 | 2378 | 1 | 10.5% | 270 ms | 308 ms | `17235ba0c797` |
| 1bhk_30x40_no_parking | cp2_new | FEASIBLE | normal | VALID | SPINE_two_pL_s0 | 2493 | 1 | 7.5% | 22 ms | 26 ms | `c626c00302e6` |
| 4bhk_45x75_two_cars_puja | cp2_new | FEASIBLE | difficult | VALID | SPINE_stepped_pR_s3 | 16782 | 10 | 9.6% | 463 ms | 552 ms | `ed16d6790c8d` |
| 3bhk_50x60_wide_two_cars | cp2_new | FEASIBLE | difficult | VALID | FRONT_EXTENSION_stepped_pL_x_bedroom_3_s3 | 14796 | 3 | 8.2% | 280 ms | 352 ms | `51f7e4eb4e6f` |
| 4bhk_40x90_deep_car_utility | cp2_new | FEASIBLE | difficult | VALID | SPINE_two_pL_s3 | 6901 | 2 | 9.3% | 499 ms | 617 ms | `7a180b3a51b2` |
| 2bhk_25x50_narrow_open_plan | cp2_new | MEASURE | normal | VALID | SPINE_stepped_pL_rear_bedroom_2_s2 | 3610 | 1 | 10.9% | 84 ms | 103 ms | `87213a9da709` |
| 4bhk_25x40_overfull | cp2_new | INFEASIBLE | infeasible | PROVEN |  |  |  |  | 0 ms | 1 ms | `INFEASIBLE` |
| 2bhk_12x40_too_narrow | cp2_new | INFEASIBLE | infeasible | PROVEN |  |  |  |  | 0 ms | 0 ms | `INFEASIBLE` |
| 3bhk_25x30_setbacks_eat_plot | cp2_new | INFEASIBLE | infeasible | PROVEN |  |  |  |  | 0 ms | 0 ms | `INFEASIBLE` |
| prop_square_45x45 | proportion | MEASURE | normal | VALID | FRONT_EXTENSION_stepped_pL_x_bedroom_2_s1 | 12337 | 4 | 7.1% | 200 ms | 229 ms | `4525e6a36d99` |
| prop_mid_40x55 | proportion | MEASURE | normal | VALID | SPINE_stepped_pL_s1 | 4369 | 6 | 9.8% | 180 ms | 215 ms | `615355619cf3` |
| prop_wide_60x35 | proportion | MEASURE | normal | NO_SUPPORTED_LAYOUT |  |  |  |  | 167 ms | 194 ms | `INFEASIBLE` |
| prop_wide_70x30 | proportion | MEASURE | normal | NO_SUPPORTED_LAYOUT |  |  |  |  | 173 ms | 204 ms | `INFEASIBLE` |
| prop_very_wide_80x28 | proportion | MEASURE | normal | NO_SUPPORTED_LAYOUT |  |  |  |  | 135 ms | 161 ms | `INFEASIBLE` |
| prop_deep_30x70 | proportion | MEASURE | normal | VALID | SPINE_stepped_pR_s3 | 1112 | 0 | 15.6% | 220 ms | 269 ms | `671af16dcc07` |
| prop_deep_25x90 | proportion | MEASURE | normal | NO_SUPPORTED_LAYOUT |  |  |  |  | 205 ms | 247 ms | `INFEASIBLE` |
| prop_very_deep_22x100 | proportion | MEASURE | normal | NO_SUPPORTED_LAYOUT |  |  |  |  | 284 ms | 337 ms | `INFEASIBLE` |

Feasibility on the original corpus: **10 of 11 expected-feasible cases VALID** (target ≥ 10). The miss is `1bhk_25x40_south_small` (NO_SUPPORTED_LAYOUT; the closest layout leaves bedroom 1 at 2.40 m where 2.80 m is needed). The three expected-infeasible cases are INFEASIBLE. New cases: all 8 labelled FEASIBLE are VALID; all 3 labelled INFEASIBLE are PROVEN.

Proportion corpus: square and moderately deep plots work (45x45, 40x55, 30x70). Wide shallow plots (60x35, 70x30, 80x28) and very narrow deep plots with a car (25x90, 22x100) return NO_SUPPORTED_LAYOUT (section 13, W1 and W2).

## 8. Comparison against Checkpoint 1

Baseline: the Checkpoint 1 solver on the frozen Checkpoint 1 ruleset, each VALID plan scored by the same Scorer and weights (`benchmark_baseline_cp1.json`; a test checks the live baseline still equals it).

| Case | CP1 result | CP1 quality | CP2 quality | CP1 rooms over aspect | CP2 rooms over aspect | CP1 circulation | CP2 circulation |
|---|---|---|---|---|---|---|---|
| 2bhk_30x50_north_twowheeler_open | VALID | 9812 | 918 | 5 | 1 | 11.7% | 15.8% |
| 3bhk_40x65_east_puja | VALID | 15170 | 7866 | 7 | 5 | 8.5% | 10.0% |
| 2bhk_40x80_west_two_cars | VALID | 53540 | 6564 | 6 | 2 | 9.4% | 11.8% |
| 2bhk_22x60_narrow_deep | INFEASIBLE | | 3133 | | 5 | | 17.9% |
| 4bhk_50x80_large_two_cars | VALID | 44168 | 28656 | 10 | 8 | 7.6% | 8.6% |
| 3bhk_30x60_single_car_vastu | INFEASIBLE | | 909 | | 0 | | 13.3% |
| 2bhk_35x55_utility_no_vastu | INFEASIBLE | | 2669 | | 2 | | 11.8% |
| 3bhk_45x70_two_cars_puja | VALID | 29140 | 18312 | 7 | 7 | 8.1% | 9.0% |
| 3bhk_40x60_asymmetric_setbacks | INFEASIBLE | | 11218 | | 4 | | 8.9% |
| 2bhk_30x45_common_bath_only | INFEASIBLE | | 334 | | 0 | | 11.9% |
| 3bhk_40x60_north_one_car | INFEASIBLE | | 9482 | | 8 | | 10.0% |
| 2bhk_35x50_south_car | INFEASIBLE | | 1925 | | 0 | | 11.1% |
| 2bhk_30x55_west_twowheeler | VALID | 10965 | 483 | 4 | 0 | 12.1% | 16.7% |
| 3bhk_35x70_east_car | VALID | 8749 | 2378 | 4 | 1 | 10.5% | 10.5% |
| 1bhk_30x40_no_parking | VALID | 6035 | 2493 | 3 | 1 | 10.2% | 7.5% |
| 4bhk_45x75_two_cars_puja | INFEASIBLE | | 16782 | | 10 | | 9.6% |
| 3bhk_50x60_wide_two_cars | VALID | 30084 | 14796 | 8 | 3 | 7.0% | 8.2% |
| 4bhk_40x90_deep_car_utility | VALID | 23395 | 6901 | 10 | 2 | 9.4% | 9.3% |
| 2bhk_25x50_narrow_open_plan | INFEASIBLE | | 3610 | | 1 | | 10.9% |
| prop_square_45x45 | INFEASIBLE | | 12337 | | 4 | | 7.1% |
| prop_mid_40x55 | VALID | 10832 | 4369 | 4 | 6 | 7.9% | 9.8% |
| prop_deep_30x70 | INFEASIBLE | | 1112 | | 0 | | 15.6% |

| Acceptance criterion (section 0) | Result | Verdict |
|---|---|---|
| ≥ 90% of expected-feasible VALID (10 of the original 11) | 10 of 11 | **Met** |
| All Checkpoint 1 VALID cases remain VALID | 11 of 11 | **Met** |
| No INVALID returned as VALID | 0 INVALID results, 0 INVALID attempts; every VALID plan passes the validator | **Met** |
| PROVEN stays PROVEN; NO_SUPPORTED_LAYOUT used honestly | PROVEN only on cases labelled INFEASIBLE; every NO_SUPPORTED_LAYOUT explanation says it is not impossible | **Met** |
| Labels not manipulated | Original 14 unchanged; new labels fixed before the first run | **Met** |
| Mean quality score ≤ 50% of Checkpoint 1's (shared VALID cases) | 41.0% (original corpus, 5 cases); 38.8% (whole benchmark, 11 cases) | **Met** |
| No case scores worse | None on either corpus | **Met** |
| Rooms over aspect limit ≤ 50% of Checkpoint 1's | 23 of 35 = 65.7% (original); 36 of 68 = 52.9% (whole benchmark). One case has more violations than Checkpoint 1 (`prop_mid_40x55`, 6 against 4) while scoring 4369 against 10832 | **Missed** |
| Golden hashes deterministic; candidate ordering deterministic | Section 11 | **Met** |
| All Checkpoint 1 tests and all 39 validation codes green | Section 11 | **Met** |

**Why the aspect criterion is missed.** The approved term measures how far a room is over its limit (section E: `max(0, long/short − limit)`). The optimiser therefore accepts marginal excesses when they buy larger gains elsewhere: in `prop_mid_40x55` the kitchen is 1.805 against 1.8 and the living room 1.52 against 1.5. Total aspect excess there is 67 milli against Checkpoint 1's 2317, but the criterion counts rooms. A smaller part is structural: on the widest plots each column is 4.4 to 6.7 m wide and every stacked room spans it.

**Measured alternative (not applied).** `tools/spikes/cp2_layout/aspect_count_experiment.py` adds a fixed 1000 milli per violating room to the term and re-solves the shared cases, then scores them with the approved Scorer:

| Variant | Rooms over aspect, original | Rooms over aspect, whole benchmark | Quality vs CP1, original | Quality vs CP1, whole benchmark | Original feasible VALID |
|---|---|---|---|---|---|
| Approved term (built) | 65.7% | 52.9% | 41.0% | 38.8% | 10 / 11 |
| Term + 1000 per violating room | 22.9% | 16.2% | 43.8% | 41.2% | 10 / 11 |

The change meets every criterion on both corpora. It changes the approved definition of a term, so it is decision CP2-D1 (section 14), not something this checkpoint applied. A strict expected-failure test records the miss and will fail loudly when the criterion starts passing.

## 9. VPS performance results

**Not measured. The VPS gate has not run.** This machine has no SSH key or other access to the Hostinger KVM 2. No production-suitability claim is made from the figures below (CP2-U5).

Command for the VPS, from the repository checkout, with the stack idle:

```bash
docker build -t p2b-api:cp2 apps/api
docker run --rm --cpus 2 --user root \
  -v "$PWD/apps/api/scripts:/app/scripts:ro" \
  -v "$PWD/apps/api/tests/fixtures/houseplans:/app/fixtures:ro" \
  -v "$PWD:/out" p2b-api:cp2 \
  python scripts/benchmark_houseplans.py --fixtures /app/fixtures --repeats 5 \
  --fresh-process --json /out/benchmark_vps.json --label vps-kvm2
```

`--user root` is only so the throwaway container can write the result file into the mounted directory; the service image and its user are unchanged.

Rehearsal on the laptop (not evidence for the gate):

| Measure | Target (VPS) | Laptop | Production image, 2 CPUs | Samples |
|---|---|---|---|---|
| Normal generation p95 | ≤ 1000 ms | 301 ms | 357 ms | 80 |
| Difficult generation p99 | ≤ 3000 ms | 566 ms | 704 ms | 30 |
| Infeasible, decided by pre-check, p95 | ≤ 500 ms | 0.5 ms | 0.8 ms | 25 |
| Infeasible, decided by search, p95 | ≤ 1500 ms | 285 ms | 341 ms | 35 |
| Validation p95 | ≤ 20 ms | 2.2 ms | 3.5 ms | 110 |
| Repair p95 (one door slid off its wall, repaired) | ≤ 100 ms | 6.0 ms | 9.3 ms | 110 |
| Slowest first (cold) generation of a case | none | 561 ms | 666 ms | 34 |
| Fixture-fit table, once per ruleset | none | 32 ms | 42 ms | 1 |

Bottleneck if the VPS is slower: sizing evaluations (5000 to 16000 per case, about 30 to 35 µs each). Candidate optimisations, in order: size only the best half of candidates at the 150 mm and 50 mm steps; lower `candidate_limit` (ruleset data); cache sizings across identical sub-problems. Each changes rankings, so each would need the goldens re-approved.

Optimisations already applied while building (all deterministic, measured on the 4-bedroom case): compiled evaluator (3.1 s to 1.3 s), cyclic coordinate search and isomorphic-split removal (1.3 s to 0.56 s).

## 10. Memory results

| Measure | Target | Laptop | Production image, 2 CPUs |
|---|---|---|---|
| Resident memory after engine import | none | 36.2 MB | 38.4 MB |
| Peak during the whole benchmark | none | 38.0 MB | 40.0 MB |
| Increase over the run | ≤ 50 MB | 1.9 MB | 1.6 MB |
| Python allocations, one generation (tracemalloc peak) | none | 0.4 MB | 0.4 MB |

No dependency was added; the API image is unchanged apart from source files (925 MB as built locally, all of it pre-existing).

## 11. Deterministic hash results

| Check | Result |
|---|---|
| Checkpoint 1 goldens (MVP solver, frozen ruleset) | Byte-identical: `bc430b40…` (3bhk_40x65_east), `97f446ba…` (2bhk_30x50_north), `1ba2ffbc…` (2bhk_40x80_west_two_cars) |
| Checkpoint 1 ruleset hash | `f04a2b9f…`, unchanged (the 1.1.0 fields are omitted at their default) |
| Zoned goldens | `3f8a4bae…`, `a96bd3ab…`, `0744363b…`, `f9708e4e…`, `dd75a8d1…`, `474cbab7…` (six cases, every variant and both families), byte-for-byte in-process and in a fresh process |
| Repeated runs, whole benchmark | 34 of 34 cases identical across 6 runs each; candidate ranking hash identical across runs |
| Fresh process, whole benchmark | Identical |
| Across platforms | All 34 body hashes identical between Windows / Python 3.13.9 and the Linux production image / Python 3.12.15 |
| Test suite | 682 passed, 1 skipped, 1 strict expected failure (the aspect criterion, section 8); coverage 91% overall and 89% on services (gates 70% and 85%). Includes all Checkpoint 1 tests, the 39 validation codes and the 21-case negative corpus. A first run that overlapped other test processes on the same database hit Postgres deadlocks in 8 build-plan tests; they pass alone and in the clean full run |
| Static checks | ruff format and lint, mypy strict (`src tests scripts`), import-linter (5 contracts kept, engine purity included), contract regeneration, web lint and type check: all pass |

## 12. Infeasibility classification examples

Homeowner message for NO_SUPPORTED_LAYOUT (CP2-U4, approved): "We could not fit this home on your plot with the layouts we can generate today. A Plan2Build architect can still design it."

PROVEN is claimed only from arithmetic that holds for any arrangement: an empty envelope; a room or the parking that cannot fit in the envelope in either orientation (minimum clear size plus the thinnest walls); or the rooms' least footprints exceeding the envelope's area. It is measured against the envelope, not the engine's wall-centreline region, so it cannot depend on how this engine places walls. Fixture-fit minimums are not used for PROVEN because they assume a door position.

- 1bhk_25x40_south_small [NO_SUPPORTED_LAYOUT, DEPTH_EXCEEDED]: None of the 26 layouts this version of the engine can produce fits this programme on the plot. In the closest one, bedroom 1 would be 2.40 m across; the rules need 2.80 m; dining would be 2.30 m across; the rules need 2.50 m. This does not mean the home is impossible to design.
- 3bhk_20x30_too_small [PROVEN, AREA_BUDGET]: The buildable area after setbacks is 4.88 m by 6.71 m (32.70 m²). The requested rooms need at least 75.30 m² at their minimum sizes with walls, before any passage, so they cannot fit in any arrangement.
- 2bhk_30x60_two_cars_too_wide [NO_SUPPORTED_LAYOUT, PARKING_TOO_WIDE]: None of the 32 layouts this version of the engine can produce fits this programme on the plot. In the closest one, the parking would be 3.95 m where 5.00 m is needed; passage would share only 1.10 m of wall with the room it opens from; a door needs 1.20 m; dining would be 2.47 m across; the rules need 2.50 m. This does not mean the home is impossible to design.
- 4bhk_30x40_overfull [PROVEN, AREA_BUDGET]: The buildable area after setbacks is 7.92 m by 9.75 m (77.29 m²). The requested rooms need at least 88.27 m² at their minimum sizes with walls, before any passage, so they cannot fit in any arrangement.
- 4bhk_25x40_overfull [PROVEN, AREA_BUDGET]: The buildable area after setbacks is 6.40 m by 10.06 m (64.38 m²). The requested rooms need at least 88.27 m² at their minimum sizes with walls, before any passage, so they cannot fit in any arrangement.
- 2bhk_12x40_too_narrow [PROVEN, WIDTH_TOO_NARROW]: The buildable area is 2.44 m wide and 10.06 m deep after setbacks. The living needs at least 3.10 m in both directions including its walls.
- 3bhk_25x30_setbacks_eat_plot [PROVEN, PARKING_TOO_WIDE]: Parking for 1 needs 2.50 m by 5.00 m. The buildable area after setbacks is 4.57 m by 4.27 m.
- prop_wide_60x35 [NO_SUPPORTED_LAYOUT, PARKING_TOO_WIDE]: None of the 32 layouts this version of the engine can produce fits this programme on the plot. In the closest one, the parking would be 3.60 m where 5.00 m is needed; living would be 2.20 m across; the rules need 3.00 m; dining would be 1.85 m across; the rules need 2.50 m. This does not mean the home is impossible to design.
- prop_wide_70x30 [NO_SUPPORTED_LAYOUT, DEPTH_EXCEEDED]: None of the 32 layouts this version of the engine can produce fits this programme on the plot. In the closest one, living would be 1.15 m across; the rules need 3.00 m; bedroom 1 would be 1.00 m across; the rules need 2.80 m; dining would be 0.80 m across; the rules need 2.50 m. This does not mean the home is impossible to design.
- prop_very_wide_80x28 [NO_SUPPORTED_LAYOUT, DEPTH_EXCEEDED]: None of the 25 layouts this version of the engine can produce fits this programme on the plot. In the closest one, living would be 0.95 m across; the rules need 3.00 m; bedroom 1 would be 1.00 m across; the rules need 2.80 m; dining would be 0.70 m across; the rules need 2.50 m. This does not mean the home is impossible to design.
- prop_deep_25x90 [NO_SUPPORTED_LAYOUT, PARKING_TOO_WIDE]: None of the 32 layouts this version of the engine can produce fits this programme on the plot. In the closest one, the parking would be 2.40 m where 2.50 m is needed; living would be 2.99 m across; the rules need 3.00 m. This does not mean the home is impossible to design.
- prop_very_deep_22x100 [NO_SUPPORTED_LAYOUT, PARKING_TOO_WIDE]: None of the 32 layouts this version of the engine can produce fits this programme on the plot. In the closest one, the parking would be 1.50 m where 2.50 m is needed; living would be 2.98 m across; the rules need 3.00 m. This does not mean the home is impossible to design.

## 13. Remaining weaknesses

| ID | Weakness | Evidence | Direction |
|---|---|---|---|
| W1 | Wide shallow plots are unsupported | 60x35, 70x30, 80x28 return NO_SUPPORTED_LAYOUT: S and F stack rooms in depth behind a full-width front band | A family with rooms side by side across the width (a new topology, needs approval) |
| W2 | Narrow deep plots with a car | 25x90 and 22x100 miss by 0.01 to 1 m: parking and the entry room must sit side by side in the front band | Parking ahead of the entry room inside the footprint (a variant) or front-setback parking (CP2-U1, not decided) |
| W3 | Aspect count criterion missed | Section 8 | Decision CP2-D1 |
| W4 | Column-width rooms on wide plots | 4-bedroom 50x80: baths 6.7 × 2.2 m; 5 rooms stay over aspect even with the CP2-D1 change | Paired cells (bath beside its bedroom), excluded from this checkpoint without evidence; this is the evidence |
| W5 | Circulation share rises in some plans | 2bhk_30x50: 11.7% to 15.8%; within the term's weight it is cheaper than poor proportions | Synthetic weights; real weights come with AD-05 |
| W6 | Large plots fill the whole envelope | Rooms grow past their maximum (OVERSIZE) because the layout tiles the envelope; no open space is left | Open space or a smaller footprint is a topology and product question |
| W7 | One original case unsolved | 1bhk_25x40: no S/F layout fits the bedroom and dining at once | Accepted under the 90% criterion; reported honestly |
| W8 | No OBJECTIVE repair | No current term depends on where an opening or fitting sits; resizing needs wall moves (editing checkpoint) | As planned |
| W9 | PROVEN homeowner message is draft | Only the NO_SUPPORTED_LAYOUT wording is approved | Decision CP2-D3 |
| W10 | VPS gate not run | Section 9 | Run the command |

## 14. Remaining business decisions

| ID | Decision | Recommendation |
|---|---|---|
| CP2-D1 | Change ASPECT_EXCESS to charge a fixed cost per violating room in addition to the excess (section 8), or revise the criterion to aspect excess | Change the term: it meets every criterion on both corpora and matches how a homeowner sees a badly proportioned room |
| CP2-D2 | Run the VPS gate (needs someone with VPS access, or access for me) | Run it before Checkpoint 3 |
| CP2-D3 | Homeowner wording when infeasibility is PROVEN. Draft: "This home cannot fit on your plot under the current planning rules. A Plan2Build architect can review the requirement with you." | Approve or replace |
| CP2-D4 | Whether wide shallow plots (W1) and paired cells (W4) enter Checkpoint 3 as new topology families | Yes for W1 if wide plots are common in Raipur listings; W4 after CP2-D1 |
| Carried | AD-05 (real ruleset values and weights), AD-06 (allowance), AD-13 (orientation and Vastu), AD-16, CP2-U1 (front-setback parking), CP2-U3 (bath exterior window) | Unchanged; production stays blocked |

## 15. Recommendation

**BUILD WITH CHANGES.**

The zoned solver does what Checkpoint 2 set out to do: 10 of 11 expected-feasible cases VALID (Checkpoint 1: 5), every Checkpoint 1 VALID case still VALID, no invalid plan, honest PROVEN and NO_SUPPORTED_LAYOUT classes, quality at 39 to 41% of Checkpoint 1's with no case worse, deterministic across processes and platforms, and comfortable margins on every latency and memory target in the 2-CPU rehearsal. The changes before acceptance: decide CP2-D1 (one-line term change, goldens re-approved), run the VPS gate (CP2-D2), and approve the PROVEN wording (CP2-D3).

Waiting for approval. Checkpoint 3 not started.
