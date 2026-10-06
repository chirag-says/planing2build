# Plan2Build: AI design engine, Checkpoint 1 implementation report

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_1_REPORT.md` |
| Date | 2026-10-06 |
| Plan | `AI_DESIGN_ENGINE_CHECKPOINT_1.md` v1.0 with Chirag's approval and final CP1 answers (its "Approval and final answers" table governs) |
| Branch | `houseplans-checkpoint-1` (from `main`). Commits: Slice 3.7 baseline (CP1-08), then the decision records. The Checkpoint 1 implementation is in the working tree, **not committed**, awaiting review |
| Status | **CHECKPOINT 1 IMPLEMENTED.** OR-Tools **not adopted**: the image-growth threshold failed (section 13). Checkpoint 2 not started |

---

## 1. Files created

| Path | Purpose |
|---|---|
| `apps/api/src/p2b/houseplans/__init__.py` | Module docstring (never authoritative) |
| `apps/api/src/p2b/houseplans/interface.py` | Empty public interface until reference marking |
| `apps/api/src/p2b/houseplans/models.py` | `LayoutRuleset`, `HousePlanRecord`, `HousePlanVersion`, guard lists |
| `apps/api/src/p2b/houseplans/schemas.py` | API request and response models |
| `apps/api/src/p2b/houseplans/router.py` | Homeowner routes |
| `apps/api/src/p2b/houseplans/ops_router.py` | Operations read-only routes |
| `apps/api/src/p2b/houseplans/service.py` | Request path, job path, reads, stale expiry, transition table |
| `apps/api/src/p2b/houseplans/rulesets.py` | Ruleset loader (PUBLISHED, or DRAFT/APPROVED/synthetic only where settings allow) |
| `apps/api/src/p2b/houseplans/handlers.py` | Outbox subscription → job with `queueing_lock` and a shared `lock` |
| `apps/api/src/p2b/houseplans/jobs.py` | `generate_plan` on queue `engine` |
| `apps/api/src/p2b/houseplans/engine/__init__.py` | Public engine API |
| `apps/api/src/p2b/houseplans/engine/units.py` | Feet to millimetres (Decimal, half-even) |
| `apps/api/src/p2b/houseplans/engine/model.py` | HousePlan schema 1.0.0 |
| `apps/api/src/p2b/houseplans/engine/canonical.py` | Canonical JSON and sha256 |
| `apps/api/src/p2b/houseplans/engine/upgrade.py` | Schema version gate |
| `apps/api/src/p2b/houseplans/engine/ruleset.py` | Ruleset content model and citation check |
| `apps/api/src/p2b/houseplans/engine/intent.py` | Provisional `DesignInputs`, `ArchitecturalIntent`, `normalise` |
| `apps/api/src/p2b/houseplans/engine/geom.py` | Integer geometry |
| `apps/api/src/p2b/houseplans/engine/graph.py` | Rectangles → nodes, walls, room boundary cycles |
| `apps/api/src/p2b/houseplans/engine/solver/__init__.py` | `LayoutSolver` interface and solver data types |
| `apps/api/src/p2b/houseplans/engine/solver/mvp.py` | `DeterministicMVPLayoutSolver` |
| `apps/api/src/p2b/houseplans/engine/place.py` | Openings and fixtures placement |
| `apps/api/src/p2b/houseplans/engine/generate.py` | The pipeline and plan assembly |
| `apps/api/src/p2b/houseplans/engine/derive.py` | Analysis and `PlanGeometry` |
| `apps/api/src/p2b/houseplans/engine/validate.py` | Validator, check registry, report |
| `apps/api/src/p2b/houseplans/engine/ops.py` | Typed operations with exact inverses |
| `apps/api/src/p2b/houseplans/engine/repair.py` | Deterministic repair loop |
| `apps/api/migrations/versions/0019_houseplans.py` | Migration |
| `apps/api/scripts/update_houseplan_golden.py` | Regenerates golden files (deliberate, reviewed) |
| `apps/api/scripts/render_houseplan_debug.py` | Development-only SVG of `PlanGeometry` |
| `apps/api/tests/houseplans_support.py` | Fixtures loader, ruleset install, negative corpus |
| `apps/api/tests/fixtures/houseplans/ruleset_synthetic_test_only.json` | Synthetic test ruleset |
| `apps/api/tests/fixtures/houseplans/requirements.json` | Five requirement cases |
| `apps/api/tests/fixtures/houseplans/golden/*.json` | Three golden plans |
| `apps/api/tests/test_houseplan_geom.py`, `_normalise.py`, `_solver.py`, `_derive.py`, `_validate.py`, `_golden.py`, `apps/api/tests/test_houseplans_api.py` | Tests |
| `tools/spikes/ortools_feasibility/` (`Dockerfile`, `bench.py`, `README.md`) | Isolated OR-Tools measurement; not application code |
| `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_1_ASSETS/*.svg` | Debug renders of the golden plans, for review |
| This report | |

## 2. Files modified

| Path | Change |
|---|---|
| `apps/api/src/p2b/core/vocabulary.py` | 39 new enums, added to `ALL_ENUMS` |
| `apps/api/src/p2b/core/errors.py` | `DesignInputRequired`, `PlanUnsupported`, `RulesetNotPublished`, `GenerationInProgress` |
| `apps/api/src/p2b/core/config.py` | Four `houseplans_*` settings; production refuses draft or synthetic rulesets; synthetic only in local and test |
| `apps/api/src/p2b/main.py` | Two routers |
| `apps/api/src/p2b/worker.py` | Handler and job blueprint |
| `apps/api/migrations/env.py` | Model import |
| `apps/api/pyproject.toml` | Import-linter: `p2b.houseplans` in the existing contracts; new "houseplans engine is pure" contract; `include_external_packages = true`. **No dependency added** |
| `apps/api/.env.example` | Local-only settings |
| `apps/api/tests/conftest.py` | Test environment turns the houseplans routes on. The draft and synthetic ruleset allowances are set only inside `test_houseplans_api.py`, so settings copied for production checks never inherit them |
| `apps/api/tests/test_schema.py` | Five CHECK-versus-vocabulary cases |
| `packages/contracts/openapi.json`, `src/schema.d.ts`, `src/vocabulary.ts` | Regenerated, not hand-edited |
| `SYSTEM_BLUEPRINT/01_ARCHITECTURE/DATA_ARCHITECTURE.md` 4.24, `API_ARCHITECTURE.md` 23, `02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_1.md`, `FOUNDATION_PLAN.md` | As-built notes |

No web source file changed.

## 3. Migration

`0019_houseplans` (revises 0018), rung M1, additive only:

| Table | Guards |
|---|---|
| `layout_rulesets` | One PUBLISHED (partial unique index); synthetic can never be APPROVED or PUBLISHED; approval and publication must name a person; the `synthetic` flag must match the content; content immutable (lifecycle-only trigger) |
| `house_plans` | State CHECK; document iff VALID; validity and report with the document; reasons iff INFEASIBLE; failure reason iff FAILED; `is_authoritative = false`; one generation in flight per project (partial unique index); intent, inputs and ruleset immutable (lifecycle-only trigger) |
| `house_plan_versions` | Append-only |

No seed data. Verified: downgrade to 0018 and upgrade to head on the test database; the drift test confirms migrations equal the models.

## 4. API endpoints implemented

All under `/api/v1`; 404 everywhere while `houseplans_enabled` is false (the default, and production's value until AD-05 and AD-06).

| Method and path | Who | Responses |
|---|---|---|
| `POST /projects/{project_id}/house-plans` | Owner | 202 QUEUED; 403 member not owner; 404; 409 `STATE_CONFLICT`, `GENERATION_IN_PROGRESS`, `RULESET_NOT_PUBLISHED`; 422 `DESIGN_INPUT_REQUIRED` (missing keys), `PLAN_UNSUPPORTED` (reasons), `VALIDATION_ERROR` (inputs contradicting the requirement); 429 |
| `GET /projects/{project_id}/house-plans` | Owner, members | 200 list |
| `GET /projects/{project_id}/house-plans/{plan_id}` | Owner, members | 200 with intent, provisional inputs, document, `PlanGeometry` (derived on read), report, infeasibility |
| `GET /ops/projects/{project_id}/house-plans` | OPS or ADMIN, MFA | 200 list |
| `GET /ops/house-plans/{plan_id}` | OPS or ADMIN, MFA | 200 detail plus internal `failure_detail` |

## 5. Module structure

```text
houseplans/            DB, API, jobs (may import other modules' interface.py only)
  models, schemas, router, ops_router, service, rulesets, handlers, jobs, interface
  engine/              pure: stdlib + Pydantic + p2b.core.vocabulary (import-linter enforced)
    model, canonical, upgrade, units, ruleset, intent
    geom, graph, place, generate, derive, validate, ops, repair
    solver/            LayoutSolver interface; mvp.DeterministicMVPLayoutSolver
```

## 6. HousePlan schema (1.0.0) summary

- Integer millimetres throughout; plot-local frame with the origin at the front-left corner as seen from the primary road edge (CP1-01, CP1-02), +y away from the road; `north_angle_deg` derived from the facing.
- `site`: rectangular plot (vertices, four edges each tagged FRONT/BACK/LEFT/RIGHT and ROAD/NEIGHBOUR), entry edge, per-edge setbacks with their source, parking specification.
- `floors[]` (one in the MVP): levels; `nodes`; `walls` (node to node, thickness, EXTERIOR/INTERIOR, `structural_role: "UNASSESSED"`); `rooms` (type, name, boundary as a node cycle, zone, enclosed, size specification, origin); `openings` (host wall, offset, width, height, sill, door leaf, hinge and side); `fixtures` (room, host wall, offset, side, size, origin); `stairs` (present, refused by the v1 validator).
- `constraints` with origin and outcome; `compromises` (empty at CP1).
- `meta`: schema and version, generator (engine, solver kind and version, seed, ruleset version and hash, intent hash), plan and project ids, `body_sha256` (hash of everything except `meta`).
- `extra="forbid"` everywhere: an opening or fixture cannot be given coordinates.

## 7. ArchitecturalIntent summary

`normalise(answers, design_inputs, ruleset)` returns `Normalised(intent)`, `NeedsInput(missing)`, `Unsupported(reasons)` or `InputConflict(keys)`. The intent holds: sources (question set, requirement version, inputs hash, ruleset version and hash); site (frontage, depth, facing and its origin, north angle, four setbacks with sources); `floors = 1`; programme items (key, room type, origin); relations (`room` reached only from `host` by door or open connection, HARD); orientation mode (recorded only, AD-13); parking; stair choice (NONE only); target built-up area. Base rooms (living, kitchen) come from `ruleset.base_programme` (CP1-09); utility's host from `ruleset.zoning.attached_to`. `DesignInputs` is `kind = PROVISIONAL_DESIGN_INPUTS`, `version = 1`, stored in its own column, accepted only behind the flag, and refused if it contradicts a requirement answer (CP1-03).

## 8. Solver interface

```python
class LayoutSolver(Protocol):
    kind: SolverKind          # DETERMINISTIC_MVP now; CP_SAT later
    version: str
    def solve(self, problem: LayoutProblem, *, seed: int) -> Placed | Infeasible: ...
```

`LayoutProblem`: wall-centreline region, grid, wall allowance, room demands (clear minimums and targets from the ruleset), relations, parking demand, zoning roles, passage width, door and void spans. `Placed`: rectangles, solver-added rooms, access topology, entry room, topology name. `Infeasible`: reasons with millimetre arithmetic. A solver never builds walls, openings or a HousePlan; `generate()` does, and the validator judges every solver's output.

## 9. Checkpoint 1 deterministic solver

`DeterministicMVPLayoutSolver`: area-budget pre-check; front band (ruleset `front_band` order, entry room takes the remaining width); a passage spine; column groups built from relations (a host followed by the rooms reached only through it); the anchored group behind the entry room; configurations tried in order (two columns with a centred spine, one column with the spine right, one column with the spine left). Sizes are conservative (clear minimum plus the exterior wall thickness), snapped to the ruleset grid. Rooms tile the region exactly. Leftover column depth goes to the room with the largest target area. No randomness; the seed is unused. Anything that does not fit returns INFEASIBLE with the arithmetic. Known quality limits (deep bedrooms, no orientation, no wet-area clustering) are CP-SAT's objective in Checkpoint 2.

## 10. Validator coverage

Stages SCHEMA → REFERENCES → everything else; a failed stage stops later ones. 39 codes are defined, all implemented and run at Checkpoint 1:

| Category | Codes |
|---|---|
| Schema, references | SCHEMA_INVALID, SCHEMA_VERSION_UNSUPPORTED, ID_DUPLICATE, REF_MISSING, OPENING_HOST_MISSING, FIXTURE_HOST_MISSING |
| Geometry | PLOT_INVALID, GEOMETRY_UNSUPPORTED_V1, ROOM_POLYGON_INVALID, ROOM_OVERLAP, ROOM_OUTSIDE_ENVELOPE, BUILDING_OUTSIDE_PLOT, ROOM_EDGE_NOT_ON_WALL, WALL_ZERO_LENGTH, WALL_NOT_ORTHOGONAL, WALL_OVERLAP, WALL_DANGLING_END |
| Openings | OPENING_OUTSIDE_HOST, OPENING_OVERLAP, WINDOW_ON_INTERIOR_WALL, HABITABLE_ROOM_NO_WINDOW |
| Fixtures | FIXTURE_NOT_ON_ROOM_WALL, FIXTURE_OUTSIDE_ROOM, FIXTURE_NOT_PERMITTED_IN_ROOM, FIXTURE_COUNT_EXCEEDS_SPEC, FIXTURE_OVERLAP, FIXTURE_CLEARANCE_BLOCKED, FIXTURE_BLOCKS_OPENING |
| Circulation | ENTRANCE_MISSING, ROOM_UNREACHABLE |
| Dimensions | WALL_THICKNESS_INVALID, OPENING_DIMENSION_INVALID, ROOM_BELOW_MIN_SHORT_SIDE, ROOM_BELOW_MIN_AREA, PASSAGE_TOO_NARROW |
| Requirements | ROOM_COUNT_MISMATCH, PARKING_MISSING, PARKING_TOO_SMALL, RELATION_UNMET |

Every issue carries its entities (for highlighting), an i18n `message_key`, parameters and an English message. Deterministic repair exists for OPENING_OUTSIDE_HOST (slide along the wall) and FIXTURE_OUTSIDE_ROOM (nearest clear position on the same wall), through typed operations, at most three passes, each strictly reducing errors; it never adds, removes or retypes anything. Coverage of `engine/validate.py`: 87% lines and branches.

## 11. Negative corpus results

Each case breaks one thing in the golden 3-bedroom plan. All 21 pass: the expected codes appear, and only listed side effects appear beside them.

| Case | Defect | Codes reported |
|---|---|---|
| wc_in_living | A WC in the living room | FIXTURE_NOT_PERMITTED_IN_ROOM (fixture, living) |
| duplicate_wc | Three WCs in one ordinary bathroom | FIXTURE_COUNT_EXCEEDS_SPEC (count 3, limit 1; the two additions named) |
| room_overlap | Bedroom 1 grows over its attached bath | ROOM_OVERLAP (both rooms, area); consequences ROOM_UNREACHABLE, RELATION_UNMET |
| room_outside_envelope | Rear rooms extend into the back setback | ROOM_OUTSIDE_ENVELOPE |
| door_host_missing | Door hosted by a missing wall | OPENING_HOST_MISSING |
| door_off_wall | Door past the end of its wall | OPENING_OUTSIDE_HOST; **repaired** to VALID |
| door_with_coordinates | Door given free x and y | SCHEMA_INVALID |
| window_host_missing | Window hosted by a missing wall | OPENING_HOST_MISSING |
| window_on_interior | Bedroom window moved to an interior wall | WINDOW_ON_INTERIOR_WALL, HABITABLE_ROOM_NO_WINDOW |
| room_unreachable | Bedroom 2 has no door | ROOM_UNREACHABLE |
| attached_door_missing | No door from bedroom to attached bath | RELATION_UNMET, ROOM_UNREACHABLE |
| no_entrance | Main entrance removed | ENTRANCE_MISSING, ROOM_UNREACHABLE |
| fixture_outside_room | Basin pushed into the wall corner | FIXTURE_OUTSIDE_ROOM; **repaired** to VALID |
| parking_missing | Parking room removed | PARKING_MISSING, ROOM_COUNT_MISMATCH |
| dangling_wall | A free-standing wall stub | WALL_DANGLING_END |
| unknown_major | Schema 2.0.0 | SCHEMA_VERSION_UNSUPPORTED |
| duplicate_id | A door with a room's id | ID_DUPLICATE |
| missing_node | A boundary naming a missing node | REF_MISSING |
| door_too_narrow | Door below the ruleset minimum | OPENING_DIMENSION_INVALID |
| negative_width | Door width −5 | SCHEMA_INVALID |
| wall_too_thin | Wall below the ruleset minimum | WALL_THICKNESS_INVALID |

Also covered: a room below a stricter ruleset's minimum area (ROOM_BELOW_MIN_AREA on all three bedrooms); an impossible programme (INFEASIBLE, AREA_BUDGET, with millimetre arithmetic; no plan); repair leaves requirement-level defects untouched.

## 12. Golden and determinism results

| Case | Topology | `body_sha256` |
|---|---|---|
| 3bhk_40x65_east (prototype 1) | two_columns_centre_spine | `bc430b40346fd7ad8eadb0f9301a919ed8a0c975668e7c19063dfbb21863b5b5` |
| 2bhk_30x50_north (prototype 2) | two_columns_centre_spine | `97f446ba0395aba89966d2ab58d9f66e1e5be1af7e9decca1d9d58a56b31fd6b` |
| 2bhk_40x80_west_two_cars | one_column_spine_right | `1ba2ffbc6c981041a78d139626be33dad9ad0f30312bf0999504e968e3315973` |

Each regenerates byte for byte in the same process, twice in a row, and in a fresh interpreter process. The 2-bedroom hash stayed identical through every refactor of the engine during this checkpoint. Debug renders: `AI_DESIGN_ENGINE_CHECKPOINT_1_ASSETS/`.

## 13. OR-Tools feasibility measurement

Measured on 2026-10-06 with `tools/spikes/ortools_feasibility`, layered on the current API image (Python 3.12.15, `python:3.12-slim-bookworm`, linux/amd64), Docker Desktop on the development machine, `--cpus=1 --memory=2g` standing in for one VPS core. **Not yet run on the VPS itself.**

| Item | Measured |
|---|---|
| Package | `ortools` 9.15.6755, wheel `manylinux_2_27/2_28_x86_64`, 29.8 MB; installs on bookworm (glibc 2.36) |
| Added packages | ortools 9.15.6755, numpy 2.5.3, pandas 3.0.6, protobuf 6.33.6, absl-py 2.5.0, immutabledict 4.3.1 (python-dateutil, six, typing-extensions already present) |
| Resolution | `uv pip check`: all installed packages compatible; no version of an existing API package changed |
| Licences | Apache-2.0 (ortools, absl-py), BSD-3-Clause (numpy, pandas, protobuf), MIT (immutabledict) |
| Image growth (layer, no cache) | **236 MB** (virtualenv 255 MB → 480 MB; ortools 80 MB, pandas 72 MB, numpy 70 MB) |
| Import time | `from ortools.sat.python import cp_model` 0.57 to 0.67 s; worker import 2.475 s → 2.63 s with OR-Tools |
| Memory | Worker process 155.5 MB → 217.4 MB (+62 MB) after importing OR-Tools; benchmark peak 100 to 105 MB |
| Solve, zoned shape (ADR-025 design), budget 5 deterministic units | FEASIBLE every run, p50 6.65 s, p95 6.86 s |
| Solve, zoned shape, budget 2 | FEASIBLE every run, p50 3.03 s, p95 3.37 s, **same solution** as budget 5 |
| Solve, free placement (no zoning), 7.6 × 16.5 m | OPTIMAL, p50 4.41 s, p95 4.66 s |
| Solve, free placement, 7.6 × 12.2 m | No solution in any of 20 runs (UNKNOWN at the 5-unit budget, about 8.5 s each): unguided packing is not viable; zoning first is required |
| Determinism | Zoned: 25 of 25 identical (20 in one container, 5 in fresh containers); free: 5 of 5 identical |
| Infeasibility proof | An over-full zoned instance was proved INFEASIBLE in under 10 ms |

Against the thresholds in the plan (section N.3):

| Threshold | Result |
|---|---|
| Image growth ≤ 200 MB | **FAIL** (236 MB) |
| Worker memory ≤ +300 MB | PASS (+62 MB) |
| Solve p95 ≤ 5 s on one core | PASS at budget 2 (3.37 s); FAIL at budget 5 (6.86 s). The budget is a tuning choice |
| Determinism 25 of 25 | PASS |
| No resolution conflict | PASS |
| Permissive licences | PASS |

**Decision applied:** a threshold failed, so OR-Tools was **not** added to `pyproject.toml` or `uv.lock`, and nothing imports it. Choosing among the options in plan section N.4 is a Checkpoint 2 blocker (section 16).

## 14. Test results (as run)

| Run | Result |
|---|---|
| Slice 3.7 baseline, before any Checkpoint 1 change | 532 passed, 1 skipped (R2 CORS needs local storage), 17 min 12 s |
| Checkpoint 1 tests (geometry, normalisation, solver, derivation, validation, golden, API and job) | 105 passed (plus 5 new schema cases in `test_schema.py`) |
| Full API suite after Checkpoint 1 | **642 passed, 1 skipped** (the same R2 CORS skip), 22 min 35 s. A first run failed three existing production-settings tests; fixed by scoping the test allowances (section 15), then this clean run |
| Coverage | `houseplans/service.py` 91% (gate 85%); `houseplans` module 92%; `engine/validate.py` 87%; `engine/solver/mvp.py` 92%; whole API 90% |
| ruff check, ruff format, mypy (src and tests, 298 files) | All clean |
| import-linter | 5 contracts kept, including "houseplans engine is pure" |
| Contracts | Regenerated; web `tsc --noEmit` clean; web Vitest passes |
| Migration 0019 | Downgrade to 0018 and upgrade to head clean; schema drift test passes |

## 15. Deviations from the plan

| Plan said | Built | Why |
|---|---|---|
| States QUEUED, RUNNING, SUCCEEDED, INFEASIBLE, FAILED | QUEUED, RUNNING, **VALID**, INFEASIBLE, FAILED | CP1-04: the lifecycle names the guarantee |
| CP1-04 asked about project statuses | Own `ELIGIBLE_STATUSES` in `houseplans/service.py` (submitted onward; not NEEDS_INFO; not closed), defined independently of Slice 3.1 | The answer rejected reusing 3.1's machine; the status rule is restated here for confirmation |
| Deterministic repair deferred to Checkpoint 2 | Implemented for two codes, through typed operations | The approval lists repair "where applicable" and requires the operation model now (CP1-11) |
| Validator checks in a `checks/` package | One `validate.py` with a check registry | Smaller; same contract |
| `SizeSpec` min width and min depth | `min_short_mm` plus `min_area_mm2` | Orientation-free; a room may be placed either way |
| Six codes not in the plan | FIXTURE_HOST_MISSING, FIXTURE_NOT_ON_ROOM_WALL, FIXTURE_CLEARANCE_BLOCKED, WALL_NOT_ORTHOGONAL, OPENING_DIMENSION_INVALID, PLOT_INVALID | Needed for the mandatory "invalid dimensions" and "invalid references" cases |
| Generator and validator share only `geom.py` | They also share `derive.py`'s definitions of where a hosted element sits | One definition of a fixture's footprint and a door's zone; the validator still re-derives everything from the document |
| Negative corpus as `invalid/*.json` files | Named mutations in `tests/houseplans_support.py` | Mutations survive engine changes; files would need regenerating |
| Prototype case `3bhk_30x50_east` | `3bhk_40x65_east` | With the synthetic numbers a 30 × 50 ft 3-bedroom is infeasible (correctly reported) |
| Import-linter ignore for `houseplans.interface` | Omitted | Import-linter rejects an ignore that matches nothing; added when a caller exists |
| Not in the plan | `include_external_packages = true` at the import-linter root | Lets the engine contract forbid SQLAlchemy, FastAPI and Procrastinate |
| Procrastinate `lock` verified by a test | Configured, not proved by a test | Proving serialisation needs a real multi-job worker race; recorded as a risk |
| Last room takes leftover depth | Room with the largest target area takes it | The debug render showed a 4.6 m-deep attached bath |
| Test environment allows the synthetic ruleset globally | Allowance scoped to the houseplans API tests | The first full run failed three existing production-settings tests, which copy the test environment; the production guard was right, the global test setting was not |

## 16. Remaining blockers for Checkpoint 2

1. **OR-Tools adoption (AD-08 condition):** image growth 236 MB against a 200 MB threshold. Options: accept a higher threshold; run the solver in a separate worker image consuming only `engine`; or keep the deterministic solver and grow it. Chirag's decision.
2. **Solve budget:** p95 passes at budget 2, fails at 5; the budget to adopt, and a real run on the staging VPS, are owed before adoption.
3. **AD-05:** ruleset values, citations and approver; no real ruleset exists, so production stays off.
4. **AD-03:** the design brief replaces the provisional inputs.
5. **AD-06:** allowance and credits; no quota exists.
6. **AD-04, AD-13, AD-16, AD-11** as recorded in the readiness document.
7. **Confirm** the project-status rule for generation (section 15).
8. **Layout quality** (deep rooms, no orientation, no wet clustering) is the CP-SAT objective's job and needs AD-13 for Vastu.

Checkpoint 2 has not been started.

~Sakha
