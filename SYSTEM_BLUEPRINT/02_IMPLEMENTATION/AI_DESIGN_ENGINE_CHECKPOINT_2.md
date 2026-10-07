# Plan2Build: AI design engine, Checkpoint 2 readiness (layout quality and optimisation)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_2.md` |
| Version | 1.0 (2026-10-06) |
| Status | APPROVED with changes (Chirag, 2026-10-06); section 0 governs where it differs. Evidence research code: `tools/spikes/cp2_layout/` (not imported by the application). **Checkpoint 2.1 (2026-10-07) extends sections C, D and E: see section S and `AI_DESIGN_ENGINE_CHECKPOINT_2_1_REPORT.md`** |
| Basis | `AI_DESIGN_ENGINE_HAIRLINE_READINESS.md` v1.1 (section 0), `AI_DESIGN_ENGINE_CHECKPOINT_1.md` and its report, ADR-025, ADR-026, PD-28, the Checkpoint 1 code and tests, the three golden renders |
| Branch | `houseplans-checkpoint-1`. Checkpoint 1 committed as `22628ab`, tag `houseplans-cp1` (CP2-U6) |
| Markers | **[MEASURED]** from a run recorded here. **[REC]** Sakha's recommendation. **[OPEN]** needs Chirag. **[SYNTHETIC]** test or benchmark value, never a rule |

## 0. Approval and decisions (Chirag, 2026-10-06)

| ID | Decision |
|---|---|
| CP2-U1 | Not decided. Parking stays INSIDE_FOOTPRINT until AD-05 gives architect-approved placement rules. No Raipur parking or setback rule is invented |
| CP2-U2 | YES. Bedrooms and dining may sit in the front band beside the living room where the topology permits (family F); privacy is a soft objective, never a prohibition |
| CP2-U3 | Not decided. The bathroom exterior-window rule stays until an AD-05 ruleset says whether a shaft or duct is allowed |
| CP2-U4 | APPROVED. Homeowner message for NO_SUPPORTED_LAYOUT: "We could not fit this home on your plot with the layouts we can generate today. A Plan2Build architect can still design it." Physical impossibility is claimed only for PROVEN |
| CP2-U5 | A VPS benchmark run is mandatory for acceptance; development-machine numbers are never presented as production performance |
| CP2-U6 | YES. Checkpoint 1 committed and tagged before any Checkpoint 2 production commit |
| CP2-U7 | Objective weights and preferred proportions are ruleset data; synthetic values only for local development, tests, benchmarks and research until AD-05 |
| CP2-U8 | Vastu stays NOT_EVALUATED until AD-13; no Vastu rule is invented |

Changes to the plan below:

- **Acceptance criterion N.3 (VALID count) is replaced:** for the committed synthetic benchmark corpus, at least **90%** of cases labelled expected-feasible must produce a VALID plan (10 of the original 11). Every case Checkpoint 1 solved stays VALID; no INVALID output; PROVEN stays PROVEN; NO_SUPPORTED_LAYOUT is used honestly. Labels are never changed to improve the metric.
- Production solver: `ZonedLocalSearchSolver`. MVP solver kept as fallback and reference. CP-SAT research only; OR-Tools absent from the API lockfile, the API image, the normal worker image and production CI.
- Fixture fit is considered before the final candidate is chosen: candidate → fixture-fit bound → solve → build → validate → rank → next candidate.

### Summary

Checkpoint 1's weaknesses are mostly in **zoning** (which rooms go where), not in the optimiser. A deterministic pure-Python sizer over a better zoned structure, run through the unchanged Checkpoint 1 plan builder and validator, cut the quality penalty on the five shared cases by 1.6 to 9.5 times, solved two plots Checkpoint 1 called infeasible (and lost one to a fixture-fit gap that the design below closes), at 25 to 460 ms per plan. CP-SAT on the identical structure and objective was **not better** and was up to 16 times slower on the hardest case [MEASURED]. Recommendation: **BUILD WITH CHANGES**, with no OR-Tools in Checkpoint 2.

---

## A. Checkpoint 1 audit

### A.1 Implementation map

| Area | File | What it does now | Checkpoint 2 action |
|---|---|---|---|
| Schema | `engine/model.py` | HousePlan 1.0.0, integer mm, planar graph, hosted openings and fixtures | **Keep.** One backward-compatible addition (schema 1.1.0): optional `score_milli` on `Constraint` so soft preferences carry a measured score |
| Canonical hash | `engine/canonical.py` | sha256 of the body | Keep |
| Intent | `engine/intent.py` | Programme, HARD relations, orientation mode recorded only | **Extend:** soft preferences with weight and origin (section E); requirement semantics unchanged |
| Ruleset | `engine/ruleset.py` | Room minimums, openings, fixtures, templates, parking, zoning roles | **Extend** to content 1.1.0 (section I); loader accepts 1.0 and 1.1 |
| Solver contract | `engine/solver/__init__.py` | `LayoutProblem`, `LayoutSolver`, `Placed`, `Infeasible` | **Keep the interface**; add a structured `ZonedProblem` and ranked `CandidateLayout` output (section D) |
| MVP solver | `engine/solver/mvp.py` | Band and spine, centred spine, greedy column split, slack to the largest room | **Keep unchanged** as fallback and reference, with its own goldens |
| Graph, placement | `engine/graph.py`, `engine/place.py` | Rectangles to walls; doors, windows, fixtures by rule | Keep; add a fixture-fit lower bound used by the compiler (section J) |
| Pipeline | `engine/generate.py` | compile → solve → build → validate → repair | **Restructure** into the stages of section D; candidate fallback |
| Derivation | `engine/derive.py` | `PlanGeometry` and analysis | Keep; the new Scorer reads it |
| Validator | `engine/validate.py` | 39 codes, independent of the generator | **Keep unchanged.** Soft scoring is a separate Scorer, never a validation error |
| Operations | `engine/ops.py` | Typed operations with inverses | Keep; MOVE_WALL stays deferred |
| Repair | `engine/repair.py` | Two repairers, ≤ 3 passes, strict improvement | **Extend** with reason codes and three repairers (section K) |
| Service, API, job | `houseplans/*.py` | Request, job, reads, ops reads | Small: detail response gains a derived `quality` block; solver selection by setting |
| Tests | 7 files, 105 tests + 5 schema cases | Engine, negative corpus (21), golden (3), API | Keep all; add sections M and H |

### A.2 What Checkpoint 1 got right (keep)

HousePlan as the only truth; hosted elements; one coordinate frame; an independent validator that caught every defect in the corpus; typed operations; byte-identical determinism; INFEASIBLE instead of bad plans; no model in the path.

---

## B. Solver weaknesses

### B.1 Measured baseline [MEASURED]

Corpus of 14 cases (`tools/spikes/cp2_layout/corpus.py`; synthetic ruleset). Quality is measured on the final VALID plan's `PlanGeometry` (clear dimensions). Aspect limits and preferred areas are synthetic benchmark values.

| Measure (Checkpoint 1 solver) | Value |
|---|---|
| VALID / expected feasible | 5 of 11 |
| INVALID returned | 0 |
| Rooms over their aspect limit (all VALID cases) | 35 |
| Mean worst aspect per plan | 3.66 |
| Worst single room | 5.51 (a 8.8 × 1.6 m bathroom in the two-car plan) |
| Mean circulation share | 9.1% |
| Generation latency | under 10 ms per plan |

### B.2 Causes, from the code and the renders

| # | Weakness | Effect seen |
|---|---|---|
| W1 | Leftover column depth goes to one room | Bedroom 3.1 × 7.55 m (aspect 2.4) in the 2-bedroom plan; Checkpoint 1's own change only moved the problem |
| W2 | Spine always centred | When parking pushes the entry room off-centre, the solver falls to one column: every room becomes a full-width strip (aspect up to 5.5) |
| W3 | Column split is one greedy area balance | 6 of 11 ordinary plots reported INFEASIBLE although a different split fits (35 × 55 confirmed) |
| W4 | Living room takes the full front width | Living 6.4 × 3.05 m (aspect 2.1) |
| W5 | Spine runs the full depth | Passage up to 16.4 m; no rear room spanning the width |
| W6 | Zoning lives inside the solver | Topology, sizing and access are one function; nothing reusable by a second solver |
| W7 | No objective | Nothing measures proportions, adjacency, wet grouping, exposure or orientation; constraint outcomes are all MET |
| W8 | Fixture fit is checked only after solving | The spike's best-scoring plan for 30 × 50 failed FIXTURE_FIT; Checkpoint 1 has the same latent risk |
| W9 | Infeasibility reasons are codes and numbers | No human-readable explanation; no distinction between "physically impossible" and "no layout this engine can make" |
| W10 | Parking only inside the footprint, in the front band | A car takes 5.2 m of front depth; most remaining infeasible cases come from this |
| W11 | Orientation recorded, never used | Vastu preference has no effect (AD-13 pending) |
| W12 | No wet-area grouping | Baths land on opposite sides of the spine |

---

## C. Zoning architecture

Zoning becomes its own deterministic stage that produces **candidate zone plans**; solvers only size them.

### C.1 Zones

| Zone | Rooms (from ruleset data, not code) | Placement rule |
|---|---|---|
| OUTDOOR / PARKING | PARKING | Front band, at the side the candidate chooses; placement options from the ruleset (W10, CP2-U1) |
| ENTRY / PUBLIC | LIVING (entry room), FOYER | Front band, on the road edge; holds the main entrance |
| SEMI_PUBLIC | DINING, PUJA | Directly behind or beside the entry room |
| SERVICE / WET | KITCHEN, UTILITY, BATH_COMMON, WC | Near the semi-public zone; wet rooms grouped (soft) |
| PRIVATE | BEDROOM, BATH_ATTACHED | Furthest from the road; attached bath beside its bedroom |
| CIRCULATION | PASSAGE | Generated by the topology, never requested |

The zone of each room type and the front-to-back privacy order are ruleset data (`zoning.zones`, `zoning.depth_order`), so a later programme changes data, not code.

### C.2 Topology families (Checkpoint 2)

| Family | Shape | Choices enumerated |
|---|---|---|
| S (spine) | Front band; a passage spine at a **variable** x; one or two columns; optional rear band spanning the width | Parking side (2); spine position (variable); one or two columns; rear room or none; column assignment (all splits ranked by a depth bound, best K kept) |
| F (front-band extension) | As S, but the front band also holds one semi-public or private room beside the entry room when the frontage allows | Which room joins the front band (bounded by zone rules); parking side |

Deferred to a later checkpoint, with benchmark evidence first: H (horizontal hall for wide, shallow plots), paired cells (a no-window room between a window room and the spine), courtyards.

### C.3 Enumeration is bounded and deterministic

Candidates are generated in a fixed order and pruned by a cheap lower bound (minimum depth per column at nominal width, including fixture-fit minimums). The spike kept the best 4 splits per family and side: at most a few dozen candidates for a 4-bedroom programme [MEASURED: ≤ 0.46 s total in pure Python on the development machine].

---

## D. Layout problem model

```text
ArchitecturalIntent
  → FeasibilityPrecheck          (section J; may stop with INFEASIBLE + explanation)
  → ZoningEngine                 → ZoneCandidate[]      (structure only, no sizes)
  → ConstraintCompiler           → ZonedProblem per candidate
  → LayoutSolver.solve           → CandidateLayout[]    (ranked, with objective breakdown)
  → PlanBuilder                  (existing graph + place + assemble)
  → Validator                    (unchanged, independent)
  → Repair                       (typed operations)
  → Scorer                       (objective recomputed from the built HousePlan)
  → first VALID candidate in rank order, else INFEASIBLE / FAILED
```

### D.1 Data types (new, in `engine/`)

| Type | Holds |
|---|---|
| `ZoneCandidate` | Family, parking side, ordered room groups per column, front-band members, rear member, access topology (who is entered from whom), a stable name |
| `Variable` | Name, bounds (mm), grid step; e.g. `front_depth`, `spine_x`, `rear_depth`, one cut per stacked room |
| `HardConstraint` | Id, kind, the variables it touches, origin (requirement, input, ruleset or topology) |
| `SoftTerm` | Id, kind, weight, origin, a pure scoring function over rectangles |
| `ZonedProblem` | Candidate, region, variables, hard constraints, soft terms, ruleset reference |
| `CandidateLayout` | Rectangles, access topology, candidate name, objective total and per-term breakdown, solver kind and version |

`LayoutSolver` keeps its signature for the MVP solver. A second method `solve_zoned(problems) -> list[CandidateLayout]` serves optimising solvers; nothing in the domain model mentions CP-SAT.

### D.2 Solvers

| Solver | Role in Checkpoint 2 |
|---|---|
| `DeterministicMVPLayoutSolver` | Unchanged fallback and reference; selectable by setting |
| `ZonedLocalSearchSolver` (new, pure Python) | **Default.** Coordinate descent over the problem's variables, steps 1,200 → 50 mm, strict improvement of (hard violation, objective), fixed variable order, integer arithmetic |
| `CPSATLayoutSolver` (new) | Same `ZonedProblem` and objective; imported only where `ortools` exists; **not deployed** (section F); used by the benchmark to measure the local search's optimality gap |

---

## E. Objective function

All terms are integer, deterministic, and computed by one `Scorer` from rectangles (solver side) and from `PlanGeometry` (after building). Weights and preferences are **ruleset data**; the values below are [SYNTHETIC] until AD-05.

### E.1 Hard (constraints, never traded)

Zero overlap; inside the envelope; required rooms and counts; minimum short side and area per type (clear); fixture-fit minimum per templated room; parking clear size; entrance on the entry edge; access spans (spine to entry room, anchored room to entry room, every door wall ≥ door width + jambs); attached bath reached only from its bedroom; exterior exposure for rooms whose rule needs a window.

### E.2 Soft (scored; each with weight, origin, measured score, result state)

| Term | Measure | Origin |
|---|---|---|
| AREA_DEVIATION | `|A − A_pref| / A_pref` per room | Ruleset preferred area |
| WIDTH_DEPTH_DEVIATION | `|w − w_pref| / w_pref + |d − d_pref| / d_pref` where preferred dimensions exist | Ruleset (new fields) |
| ASPECT_EXCESS | `max(0, long / short − limit)` per room | Ruleset aspect limit per type (new) |
| CIRCULATION_SHARE | Passage clear area / total clear area | Ruleset target share |
| OVERSIZE | `max(0, A − A_max) / A_max` | Ruleset maximum area |
| ADJACENCY | Soft relations (kitchen–dining, dining–living, bedrooms grouped): shared wall length ≥ door span → met | Ruleset relation table and intent |
| WET_CLUSTER | Wet rooms sharing a wall or stacked in one column, over all wet rooms | Ruleset |
| EXTERIOR_EXPOSURE | Exterior wall length per habitable room above the window minimum | Ruleset |
| PRIVACY | Bedrooms not sharing a wall with the entry room; private zone behind semi-public | Ruleset zone order |
| PARKING_CONVENIENCE | Parking shares a wall with the entry room | Ruleset |
| ORIENTATION | Room centre in its preferred compass sector (north angle from the facing) | Ruleset orientation table; **inactive (NOT_EVALUATED) until AD-13**; never reported as compliance |

Result states per soft term: MET, PARTIAL (score between thresholds), UNMET, NOT_EVALUATED. They are written to the plan's `constraints` (strength SOFT, weight, origin, outcome, `score_milli`) as generation provenance; the Scorer recomputes them on read for the API's `quality` block.

### E.3 Combination

`objective = Σ weight_t × score_t`, integer (×1000). Lexicographic order inside the solver: (hard violation, objective). Ties break by candidate order, then variable order. The spike used AREA ×1, ASPECT ×2, CIRCULATION ×1 [SYNTHETIC].

---

## F. CP-SAT architecture options

### F.1 Measurements [MEASURED, development machine, Docker `--cpus=1`, not the VPS]

Same 14 cases, same zoned structure, same objective, built and validated by the Checkpoint 1 engine:

| Solver | VALID | INVALID | Mean quality score (lower better) | Rooms over aspect | Mean worst aspect | Latency p50 (all cases) | Worst case | Deterministic |
|---|---|---|---|---|---|---|---|---|
| Checkpoint 1 MVP | 5 | 0 | 16.93 (on its 5) | 35 | 3.66 | < 1 ms (infeasible fast) to 9.6 ms | 9.6 ms | Yes |
| Zoned local search, greedy split | 6 | 0 | 5.48 | 21 | 2.56 | 67 ms in container | 0.28 s | Yes |
| Zoned local search, enumerated splits | 6 (one new feasible, one lost to FIXTURE_FIT, W8) | 0 | 4.94 | 15 | 2.58 | 129 ms (Windows host) | 0.46 s | Yes |
| CP-SAT, same structure, budget 2 | 6 | 0 | 5.70 | 21 | 2.63 | 18.5 ms | **4.8 s** | Yes |

Per case (Checkpoint 1 → zoned local search, enumerated):

| Case | Score | Worst aspect | Rooms over aspect |
|---|---|---|---|
| 2BHK 30 × 50 north | 5.83 → 0.79 (greedy split; enumerated hit W8) | 2.44 → 1.90 | 5 → 0 |
| 3BHK 40 × 65 east | 8.22 → 1.91 | 2.77 → 1.78 | 7 → 2 |
| 2BHK 40 × 80 west, two cars | 29.56 → 3.12 | 5.51 → 2.33 | 6 → 2 |
| 4BHK 50 × 80, two cars | 25.06 → 15.89 | 4.27 → 4.58 | 10 → 5 |
| 3BHK 45 × 70, two cars | 15.95 → 7.64 | 3.31 → 3.16 | 7 → 6 |
| 3BHK 30 × 60 | INFEASIBLE → 0.40 | → 1.73 | → 0 |
| 2BHK 35 × 55 | INFEASIBLE → 0.68 | → 1.91 | → 0 |

Earlier OR-Tools spike (Checkpoint 1 report, section 13): +236 MB in the API image, +62 MB worker memory, unguided free placement found no solution, zoned shape p95 3.37 s at budget 2.

Separate worker images [MEASURED]:

| Image | Size | Cold start (container start to engine imported) | Memory after import | Peak memory over the corpus |
|---|---|---|---|---|
| Engine only (Python 3.12 slim + Pydantic) | 211 MB | about 1.1 s | 35 MB | 36.5 MB |
| Engine + OR-Tools | 521 MB (OR-Tools layer 247 MB) | about 1.7 s | 97 MB | not measured |
| Current API image, for reference | 925 MB | | 155 MB worker import | |

### F.2 Options

| Option | Assessment against the measurements |
|---|---|
| A. Separate engine worker with OR-Tools | Isolates the API image, but adds a container, a queue route and a deploy unit for no measured quality gain today |
| B. Deterministic production solver; CP-SAT only in an isolated worker | Sound shape **if** CP-SAT is ever needed; not needed by Checkpoint 2's families |
| C. Optimise the model so CP-SAT can come later | Done by design: the `ZonedProblem` is solver-neutral |
| D. Hybrid: zoning + deterministic sizing; CP-SAT only for hard sub-problems | **Adopted in its pure form for Checkpoint 2**: zoning + deterministic local search covers every family; no sub-problem in Checkpoint 2 needs CP-SAT |

---

## G. Separate worker architecture evaluation

| Question | Finding |
|---|---|
| Is a separate worker needed now? | No [MEASURED]: the pure-Python solver adds no dependency and runs in the existing worker on the `engine` queue, one plan at a time |
| If CP-SAT is needed later (multi-floor, irregular plots, topology search beyond enumeration) | Option B: an `engine-cpsat` worker image consuming its own queue, chosen by the plan's solver setting; the API image never carries OR-Tools |
| Cost of that worker on the VPS | Image 521 MB on disk (base layers shared with the API image), about 100 MB resident while idle with OR-Tools imported, one more Compose service |
| What must be measured on the VPS before either worker is trusted | Corpus latency p50/p95/p99, peak memory, cold start, and the same determinism hashes as CI; script and command in section L |
| Production suitability claim | **None yet.** Every number here is from the development machine with `--cpus=1`. The VPS run is an acceptance criterion (N.11) |

---

## H. Benchmark design

### H.1 Corpus (synthetic ruleset; labelled non-production)

At least 24 cases in `tests/fixtures/houseplans/requirements.json`, each with expected outcome. Feasible set includes: 30 × 50 2BHK north; 40 × 65 3BHK east with puja; 40 × 80 2BHK west with two cars; 25 × 40 1BHK; 22 × 60 narrow and deep; 50 × 80 4BHK with two cars, puja and utility; 30 × 60 3BHK, Vastu MUST_FOLLOW; 35 × 55 2BHK with utility, Vastu off; 45 × 70 3BHK, two attached baths; asymmetric setbacks; common bath only; two-wheeler only; open kitchen with dining in living. Infeasible set includes: programme over area budget; parking too wide for frontage; programme over depth; a fixture template that cannot fit the minimum bath.

### H.2 Proportion corpus (Part 11)

Each case is built so that Checkpoint 1 produces the named defect; the test asserts Checkpoint 2 does not:

| Defect | Engineered by | Metric asserted |
|---|---|---|
| Very deep bedroom | Short column programme on a deep plot | Bedroom aspect ≤ ruleset limit, or reported PARTIAL with score |
| Very narrow bedroom | Narrow plot, two columns forced | Short side ≥ minimum; aspect term reported |
| Very wide bathroom | One-column fallback case | Bath aspect ≤ limit |
| Huge leftover living | Wide plot, small programme | OVERSIZE term ≤ threshold |
| Oversized passage | Deep plot | CIRCULATION_SHARE ≤ Checkpoint 1's value for the same case |
| Tiny kitchen | Tight programme | Kitchen area ≥ preferred × factor or reported |
| Long narrow utility | Wide column | Utility aspect ≤ limit |
| Parking consuming the band | Two cars on 40 ft | Parking share of envelope reported; entry room aspect ≤ limit |
| Awkward leftovers | Odd dimensions not on the grid | Remainders absorbed by rooms whose OVERSIZE stays under threshold |

### H.3 Metrics and targets (relative to Checkpoint 1, so no architectural values are invented)

| Metric | Target for Checkpoint 2 |
|---|---|
| INVALID results | 0 |
| VALID among expected-feasible cases | ≥ Checkpoint 1's count, and every case Checkpoint 1 solved still solved |
| Rooms over aspect limit (shared VALID cases) | ≤ 50% of Checkpoint 1's |
| Mean quality score (shared VALID cases) | ≤ 50% of Checkpoint 1's; no single case worse |
| Circulation share | No case worse than Checkpoint 1 |
| Determinism | 100% identical hashes across repeats, processes and machines |
| Local search optimality gap vs CP-SAT | Reported per case (research only) |

Debug renders of every VALID case are regenerated for review, each with its score breakdown.

---

## I. Ruleset requirements

Content schema 1.1.0, backward compatible (1.0.0 files load with defaults):

| Addition | Purpose |
|---|---|
| `effective_from`, `effective_to` (dates) | Versioning in time; the table already carries approval columns |
| `approval` block (approver role, review note reference) | Mirrors the row's approval for exported content |
| Room rules: `pref_w_mm`, `pref_d_mm`, `aspect_limit_x10`, `max_area_mm2` | Section E terms |
| `circulation`: passage minimum, target share | CIRCULATION_SHARE |
| `zoning.zones`, `zoning.depth_order`, `zoning.front_band_extension` | Section C data |
| `relations_soft`: room-type pairs with weights | ADJACENCY |
| `parking.placements` allowed (INSIDE_FOOTPRINT now; others pending CP2-U1) | W10 |
| `setbacks`: table by plot size and road width (structure only) | For "Not sure" setbacks once AD-03 and AD-05 allow; unused until then |
| `orientation`: room type → preferred sectors and weight | Inactive until AD-13 |
| `objective.weights` | Section E.3, versioned with the rules |
| `fixture_fit`: minimum clear dimensions per templated room, derived and checked at load | W8 |

Production values stay blocked by AD-05. The synthetic ruleset becomes 1.1.0 with clearly synthetic values, used only by local development, tests, benchmarks and solver research. Nothing in this checkpoint approves or publishes a ruleset.

---

## J. Feasibility pre-check

Runs before zoning; cheap; deterministic; never relaxes anything.

| Check | Arithmetic | Classification |
|---|---|---|
| Envelope | Plot minus setbacks is non-empty | PROVEN |
| Area budget | Σ (minimum clear area + wall allowance) + circulation minimum ≤ envelope area | PROVEN |
| Width | Widest required short side + walls ≤ envelope width; parking width + entry minimum ≤ frontage | PROVEN |
| Fixture fit | Each templated room's minimum ≥ its template's fit minimum | PROVEN (ruleset or programme conflict) |
| Depth by family | Front band minimum + best column split lower bound + rear minimum ≤ envelope depth, per family | NO_SUPPORTED_LAYOUT if every family fails |

The explanation is generated from structured reasons, in metres, naming the hard constraints involved (constraint ids and their origins), for example:

> Available buildable depth after setbacks is 9.45 m. The front band needs 5.40 m for parking for one car beside the living room, and the deepest column needs at least 6.10 m for two bedrooms, one bathroom and the kitchen at their minimum sizes: 11.50 m in total. Constraints involved: parking for 1 car (requirement), 3 bedrooms (requirement), setbacks front 1.83 m and back 1.22 m (requirement).

**PROVEN** means no rectangle arrangement can fit. **NO_SUPPORTED_LAYOUT** means none of the layouts this engine version can produce fits; the message says so plainly and does not claim the programme is impossible. This replaces Checkpoint 1's single code-plus-numbers form (W9).

---

## K. Repair integration

| Change | Detail |
|---|---|
| Reason codes | `AppliedRepair` gains `reason: RepairReason` (VALIDATION_ERROR, OBJECTIVE); every repair records the issue code or the term it improved |
| New repairers | OPENING_OVERLAP (slide the later opening), FIXTURE_BLOCKS_OPENING and FIXTURE_CLEARANCE_BLOCKED (nearest clear slot on the same or the next wall of the room) |
| Candidate fallback | If building or validating the best candidate fails (for example FIXTURE_FIT, W8), the next-ranked candidate is built; at most K (ruleset, [SYNTHETIC] 5); reasons recorded |
| Not in Checkpoint 2 | Resizing rooms through MOVE_WALL (needs graph editing; the editing checkpoint); any language-model repair |

Repair never removes or adds a room, changes a type or a count, or relaxes a hard constraint. It stays bounded (three passes) and deterministic, and each pass must reduce validation errors or improve a measured objective term without adding an error.

---

## L. Performance budget

### L.1 Measured today [development machine]

| Item | Measured |
|---|---|
| Checkpoint 1 generation | ≤ 9.6 ms per plan |
| Zoned local search generation | 25 to 456 ms per plan (corpus p50 67 to 129 ms) |
| CP-SAT generation (same structure) | up to 4.8 s per plan at budget 2 |
| Validation | 0.9 to 2.9 ms per plan |
| Infeasible result | < 1 ms (bound) to 320 ms (search exhausted) |
| Worker memory | Engine-only process 36.5 MB peak over the corpus; peak traced allocation 0.5 MB per plan |

### L.2 Proposed budgets (to be confirmed on the VPS before acceptance)

| Item | Budget, one VPS core |
|---|---|
| Normal generation | p95 ≤ 1.0 s |
| Difficult generation (4BHK, two cars, many candidates) | p99 ≤ 3.0 s |
| Infeasible result | p95 ≤ 0.5 s when the pre-check decides; ≤ 1.5 s when search decides |
| Validation | p95 ≤ 20 ms |
| Repair | p95 ≤ 100 ms |
| Memory increase in the worker | ≤ 50 MB |
| Determinism | 100% |

Measurement script: `apps/api/scripts/benchmark_houseplans.py` (new) prints p50/p95/p99, peak memory and hashes; run in the worker container on the VPS staging stack with `docker compose exec worker python scripts/benchmark_houseplans.py`.

---

## M. Tests

| Suite | Content |
|---|---|
| Existing | All 105 Checkpoint 1 tests, the 21-case negative corpus and the 39 codes unchanged and green; the MVP solver's three goldens unchanged |
| Zoning | Candidate enumeration order and count; bounds; zone assignment from ruleset data; no candidate puts a room outside its zone order |
| Compiler | Each hard constraint and soft term present with origin; fixture-fit minimums |
| Local search | Determinism (repeat, fresh process); strict-improvement property; never returns a hard violation as feasible |
| Objective and Scorer | Hand-computed scores for a small fixture; solver-side and plan-side scores agree within the clear-dimension allowance |
| Feasibility | PROVEN vs NO_SUPPORTED_LAYOUT cases; explanation text snapshot; constraint ids listed |
| Candidate fallback | A case where the best candidate fails FIXTURE_FIT and the next one is VALID |
| Repair | New repairers; reason codes; never changes a requirement |
| Benchmark | Section H targets as assertions against committed Checkpoint 1 baseline numbers |
| Golden | At least 24 cases, both solvers where applicable; byte-identical; renders regenerated |
| CP-SAT (optional, marked) | Runs only where `ortools` is importable (the research image); never in the API's CI |
| API | `quality` block present and derived; solver setting respected; feature flag behaviour unchanged |

---

## N. Acceptance criteria

1. The MVP solver works unchanged; its goldens and every Checkpoint 1 test pass.
2. `ZoningEngine`, `ConstraintCompiler`, `ZonedProblem`, `Scorer` and `ZonedLocalSearchSolver` exist behind the unchanged `LayoutSolver` interface.
3. On the shared VALID cases, rooms over aspect limit and mean quality score are each ≤ 50% of Checkpoint 1's, and no case scores worse.
4. Every hard constraint holds in every VALID plan (the validator is the judge).
5. Every soft preference in a plan carries weight, origin, measured score and result state.
6. Every INFEASIBLE result carries a PROVEN or NO_SUPPORTED_LAYOUT classification, a human-readable explanation in metres and the constraint ids involved.
7. No INVALID plan is ever stored or returned as VALID.
8. All 39 validation codes and the 21-case negative corpus pass unchanged.
9. All goldens are byte-identical across repeats, a fresh process and CI.
10. The benchmark covers at least 24 cases, VALID and INFEASIBLE, plus the proportion corpus.
11. The latency and memory budgets of L.2 are measured **on the VPS** and recorded; if they fail there, the checkpoint is not accepted.
12. OR-Tools is not added to the API image or lockfile.
13. Production ruleset values stay blocked (AD-05); only the synthetic ruleset is used.
14. No language model, no 2D editor, no 3D viewer, no AI visualisation.
15. No claim of structural, statutory, permit, construction or Vastu compliance anywhere in code, API or documents.

---

## O. Files expected to change

### O.1 Create (engine is pure, as now)

| Path | Purpose |
|---|---|
| `apps/api/src/p2b/houseplans/engine/zoning.py` | `ZoningEngine`, `ZoneCandidate`, families S and F, bounded enumeration |
| `apps/api/src/p2b/houseplans/engine/compile.py` | `ConstraintCompiler`, `ZonedProblem`, `Variable`, `HardConstraint`, `SoftTerm` |
| `apps/api/src/p2b/houseplans/engine/objective.py` | Term definitions and the `Scorer` (rectangles and `PlanGeometry`) |
| `apps/api/src/p2b/houseplans/engine/feasibility.py` | Pre-check, classification, explanation builder |
| `apps/api/src/p2b/houseplans/engine/solver/zoned_ls.py` | `ZonedLocalSearchSolver` |
| `apps/api/src/p2b/houseplans/engine/solver/cpsat.py` | `CPSATLayoutSolver` (research; imports `ortools` lazily; excluded from the API's coverage and CI) |
| `apps/api/scripts/benchmark_houseplans.py` | Section L measurement |
| `apps/api/tests/test_houseplan_zoning.py`, `_objective.py`, `_feasibility.py`, `_benchmark.py` | Tests |
| `apps/api/tests/fixtures/houseplans/golden/*.json` (more), `benchmark_baseline_cp1.json` | Goldens and the recorded Checkpoint 1 baseline |
| `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_2_REPORT.md` | Report |

### O.2 Modify

| Path | Change |
|---|---|
| `engine/generate.py` | Pipeline of section D; candidate fallback; solver chosen by argument |
| `engine/solver/__init__.py` | `CandidateLayout`, `solve_zoned` |
| `engine/ruleset.py` | Content 1.1.0 |
| `engine/intent.py` | Soft preferences in the intent (from ruleset data and inputs) |
| `engine/model.py` | Schema 1.1.0: optional `Constraint.score_milli` |
| `engine/repair.py` | Reason codes; three repairers |
| `engine/__init__.py` | Exports |
| `core/vocabulary.py` | Enums: soft term kinds, `RepairReason`, `FeasibilityClass`, topology family, solver kind `ZONED_LOCAL_SEARCH` |
| `core/config.py` | `houseplans_solver` setting (ZONED_LOCAL_SEARCH default, DETERMINISTIC_MVP fallback); production refuses CP_SAT |
| `houseplans/service.py`, `schemas.py`, `router.py` | Solver setting; derived `quality` block; infeasibility explanation fields |
| `tests/fixtures/houseplans/ruleset_synthetic_test_only.json`, `requirements.json` | 1.1.0 and the larger corpus |
| `packages/contracts/*` | Regenerated |

No web source file changes.

---

## P. Migrations

**None.** Ruleset content is JSON (schema change inside content); soft scores live in the HousePlan document; the quality block is derived on read; infeasibility explanations fit the existing `house_plans.infeasibility` JSONB. Solver kind values are strings already stored in `house_plans.solver` (no CHECK on it).

---

## Q. Risks

| ID | Risk | Mitigation |
|---|---|---|
| R1 | Benchmark numbers come from the development machine, not the VPS | N.11 makes the VPS run an acceptance gate; needs access (CP2-U5) |
| R2 | Synthetic weights and preferences shape what "better" means | Targets are relative to Checkpoint 1; all values are ruleset data replaced under AD-05 |
| R3 | Local search can stall in a local optimum | Measured against CP-SAT on the corpus; CP-SAT found nothing better on any case in the spike |
| R4 | Candidate enumeration grows with programme size | Bounded by K and a depth bound; measured worst 0.46 s for 4BHK; budget enforced by the existing solve timeout |
| R5 | Parking inside the footprint keeps many ordinary plots infeasible | CP2-U1; until decided, INFEASIBLE says NO_SUPPORTED_LAYOUT honestly |
| R6 | Bath windows required on exterior walls constrain every topology | CP2-U3; ruleset data, not code |
| R7 | Golden churn: the new default solver changes every hash | MVP goldens stay; new goldens per solver; regeneration is a reviewed script run |
| R8 | Scope pull toward a full CAD engine | Families limited to S and F; H, paired cells and courtyards need benchmark evidence first |
| R9 | Thread-based timeout cannot stop a long search | Local search is bounded by steps and candidates; CP-SAT has deterministic limits |
| R10 | Uncommitted Checkpoint 1 code under Checkpoint 2 changes | CP2-U6: commit Checkpoint 1 first |

---

## R. Recommendation

**BUILD WITH CHANGES.**

- Build zoning, the constraint compiler, the objective and Scorer, the feasibility pre-check and a pure-Python `ZonedLocalSearchSolver` as the default, with the MVP solver kept as fallback.
- Do **not** add OR-Tools anywhere in production in Checkpoint 2. On the measured corpus CP-SAT was not better than the deterministic local search on the same structure and was up to 16 times slower. Keep `CPSATLayoutSolver` as research code behind the same interface for measuring optimality gaps, and revisit Option B (isolated worker) only when a family appears that enumeration plus local search cannot handle.
- The quality ceiling is set by zoning: the remaining infeasible and poorly proportioned cases come from topology (front-band parking, single front band, fixed families) and from rules still pending (parking placement, bath ventilation). Those decisions matter more than the choice of solver.
- Acceptance requires the VPS measurement.

### Unresolved business decisions

| ID | Question | Recommendation |
|---|---|---|
| CP2-U1 | May a car park in the open front setback (common practice) instead of only inside the house footprint? Depends on Raipur development rules (AD-05) | Ask the architect reviewing AD-05; until then keep INSIDE_FOOTPRINT and report NO_SUPPORTED_LAYOUT honestly |
| CP2-U2 | May a bedroom or the dining room face the road in the front band beside the living room? | Yes as an option (family F), scored down by PRIVACY rather than forbidden |
| CP2-U3 | Must every bathroom have a window on an exterior wall, or may it ventilate through a shaft or duct? | Architect input under AD-05; keep the current rule until then |
| CP2-U4 | Homeowner wording when no supported layout fits (not proven impossible) | Draft: "We could not fit this home on your plot with the layouts we can generate today. A Plan2Build architect can still design it." Chirag to approve (like AD-16) |
| CP2-U5 | Access to the staging VPS (or someone to run one command there) for the performance gate | Needed before acceptance |
| CP2-U6 | Commit the Checkpoint 1 implementation before Checkpoint 2 starts | Yes |
| CP2-U7 | Who approves objective weights and preferred proportions | Part of the AD-05 ruleset approval |
| CP2-U8 | Vastu orientation table | AD-13; the term stays NOT_EVALUATED until then |

~Sakha

---

## S. Checkpoint 2.1 update (2026-10-07)

Checkpoint 2 was not accepted (aspect criterion missed, VPS gate not run, `1bhk_25x40` unsolved). Checkpoint 2.1 changed the following parts of this plan. The rest stands. Details and measurements: `AI_DESIGN_ENGINE_CHECKPOINT_2_1_REPORT.md`.

| Section | Change |
|---|---|
| C.2 Topology families | Six more families: SIDE_WING, FRONT_LIVING_REAR_BEDROOM, FRONT_PUBLIC_REAR_PRIVATE, L_CIRCULATION, CENTRAL_LIVING_BEDROOM_WINGS, LINEAR_REAR_CORRIDOR. Optional open (unbuilt) areas: a rear yard, a central court. Every family is written as a slicing tree (`engine/layout_tree.py`) |
| C.3 Enumeration | Topology selection (`zoning.select`) checks each family against sound lower bounds and records a verdict with a reason; identical trees from two families are kept once |
| D.1 Data types | `Topology` (tree, access rules with alternative entry rooms, passages, open areas), `Verdict`, `Selection`; `ZonedProblem` compiles any tree |
| D.2 Solvers | Two-phase search: a coarse pool per family, then the best `candidate_limit` finished with a reserved share per family; a bounded pair-move escape for layouts within 400 mm of feasible. Solver version 1.1.0 |
| E.1 Hard (in the compiler) | Added as necessary conditions: a window wall for every room that needs a window (the entry room's front wall holds the centred entrance and a window), passage width and length, open-area width. Fixture fit depends on which wall holds the door |
| E.2 Soft | Added ZONE_ORDER (the ruleset's front-to-back zone order) and BEDROOM_GROUPING (bedrooms entered from one shared space). EXTERIOR_EXPOSURE now measures the longest stretch of outside wall, including walls facing an open area. ASPECT_EXCESS is unchanged |
| I. Ruleset | Content 1.1.0 gains `zoning.open_space_min_mm` and `objective.family_pool` (both synthetic in the test ruleset; AD-05) |
| Ruleset hash | Fields new in 1.1.0 are omitted from serialisation at their default, so a 1.0.0 ruleset still hashes as in Checkpoint 1 |

## T. Checkpoint 2.2 update (2026-10-07)

The VPS gate is deferred (CP2.1 stays NOT ACCEPTED). Checkpoint 2.2 refined plan quality and changed the following. Details and measurements: `AI_DESIGN_ENGINE_CHECKPOINT_2_2_REPORT.md`.

| Section | Change |
|---|---|
| C.2 Topology families | Stepped fronts with an open carport court (FRONT_PUBLIC_REAR_PRIVATE, L_CIRCULATION); a courtyard layout replaces the wings family's court variant; wet-aware row orders; a wet wing design; a yard behind the linear row. No new family |
| D.2 Solvers | Same-axis splits flattened, sibling cuts across fixed corridors, slab moves; coarse steps 1200 and 600, finishing at 300, 150 and the grid; parking and passages start at their least size; a sizing memo per `size()` call. Results deterministic as before |
| E.1 Hard (in the compiler) | Fixture fit tests every door position and hall side a plan can produce |
| E.2 Soft | Added ROOM_SIZE_OUTLIER (the worst room's area deviation). Every other term unchanged |
| I. Ruleset | Synthetic test ruleset: ROOM_SIZE_OUTLIER weight 2, `family_pool` 20 (AD-05) |

## U. Checkpoint 2.2.1 update (2026-10-07)

Parking and spare-space allocation. Details: `AI_DESIGN_ENGINE_CHECKPOINT_2_2_1_REPORT.md`.

| Section | Change |
|---|---|
| D.1 Data types | `ZonedProblem.bay`: the parking room is a bay inside its layout cell. Along each axis it keeps its required clear size (plus at most an interior wall either side) when the rest of the cell is at least `zoning.open_space_min_mm`; that rest stays unbuilt. A smaller rest stays with the parking as apron. No schema, validator or ruleset change |
