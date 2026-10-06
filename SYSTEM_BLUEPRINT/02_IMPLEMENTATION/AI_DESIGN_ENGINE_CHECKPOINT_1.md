# Plan2Build: AI design engine, Checkpoint 1 plan (HousePlan foundation)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_1.md` |
| Version | 1.0 (2026-10-06) |
| Status | PLAN ONLY, awaiting Chirag's approval. No code, migration, API or UI written |
| Governing basis | `AI_DESIGN_ENGINE_HAIRLINE_READINESS.md` v1.1 (section 0 governs); PD-28 (IHB_FLOW 32.6); ADR-025; ADR-026; IMPLEMENTATION_CONTRACT (IC) including 18.6 and 18.7; `REFERENCE/hairline/HairlineStudy.md` (reference only: nothing from Hairline enters this checkpoint) |
| Decided inputs | AD-01, AD-02, AD-07, AD-08 (subject to section N), AD-09, AD-10, AD-12, AD-14, AD-15 |
| Pending inputs | AD-03 (brief), AD-04 (single floor), AD-05 (ruleset values), AD-06 (allowance and credits), AD-11 (timing), AD-13 (Vastu), AD-16 (label wording). This plan works around each without deciding it (section P, unresolved decisions CP1-01 to CP1-11) |
| Markers | **[DECIDED]** a recorded decision. **[REC]** Sakha's recommendation. **[OPEN]** needs Chirag |

### Approval and final answers (Chirag, 2026-10-06)

Checkpoint 1 APPROVED. Where this table differs from sections A to Q, it governs.

| ID | Answer |
|---|---|
| CP1-01 | YES. Plot width is parallel to the designated primary road and entry edge; depth is perpendicular. With several roads, the design brief must select the primary edge explicitly; never inferred |
| CP1-02 | YES. LEFT and RIGHT as seen standing on the primary road edge looking toward the plot. The interpretation is stored once (plot frame, `SetbackSide`, plot edges with `side`) and used by requirements, solver, validator and renderer alike |
| CP1-03 | YES, RESTRICTED. Provisional design inputs are explicitly marked provisional (`kind = PROVISIONAL_DESIGN_INPUTS`), versioned, stored apart from RQ v1 answers, accepted only behind the feature flag, never overwrite an RQ v1 answer, never treated as final requirements. No second requirement system |
| CP1-04 | NO. HousePlan generation has its own lifecycle (QUEUED, RUNNING, VALID, INFEASIBLE, FAILED); Slice 3.1 states unchanged; an INVALID plan is never a successful output |
| CP1-05 | YES. Feature flag off in production until AD-05 and AD-06 |
| CP1-06 | YES. Synthetic ruleset in local and test only: marked, never approvable, never publishable, never accepted or used in production |
| CP1-07 | YES for Checkpoint 1. No quota policy, no AI credit; one generation in flight per project; idempotent requests; concurrent requests serialised or rejected |
| CP1-08 | YES. Slice 3.7 committed as the clean baseline before Checkpoint 1 code |
| CP1-09 | YES for MVP. Living and kitchen as ruleset/programme data (`base_programme`), never hard-coded in geometry functions |
| CP1-10 | YES. Ground floor only; no basement geometry, circulation or solver behaviour |
| CP1-11 | YES. No operation-history table; the typed operation model is defined in code now and used by deterministic repair |

Solver naming per the approval: `LayoutSolver` interface; `DeterministicMVPLayoutSolver` (section J's band-and-spine solver); CP-SAT later behind the same interface.

### What Checkpoint 1 proves

One known structured requirement (rectangular plot, known width and depth, known setbacks, 2 or 3 bedrooms, known bathrooms, living, kitchen, parking) becomes:

```text
requirement answers (+ provisional design inputs)
  → normalise → ArchitecturalIntent
  → deterministic layout (band-and-spine solver, no dependency)
  → HousePlan (integer mm, planar graph, hosted openings and fixtures)
  → independent validation → ValidationReport
  → derive → PlanGeometry
```

and the validator rejects, with machine-readable codes tied to entities: a WC in the living room, a duplicate WC beyond the room's specification, overlapping rooms, a room outside the buildable envelope, a door not hosted by a wall, a window not hosted by a wall, and an inaccessible room.

### What Checkpoint 1 does not build

No 2D editor, no 3D, no language model, no multi-floor generation, no production ruleset, no production export, no editing operations, no repair loop, no CP-SAT, no web UI, no Hairline code. The full list is section Q.

---

## A. Files and modules to create

### A.1 Backend module `apps/api/src/p2b/houseplans/`

| File | Contents |
|---|---|
| `__init__.py` | Module docstring: concept floor plans, never authoritative (PD-28) |
| `interface.py` | Public interface. Empty `__all__` at Checkpoint 1 with a docstring; `plan_reference_facts` arrives with reference marking (checkpoint 7). Exists now because IC requires one per module |
| `models.py` | `LayoutRuleset`, `HousePlanRow`, `HousePlanVersion` (section C); `MUTABLE_COLUMNS` and `APPEND_ONLY` guard lists |
| `schemas.py` | API request and response models (section D.3) |
| `router.py` | Homeowner routes (section D.1) |
| `ops_router.py` | Operations read-only routes (section D.2) |
| `service.py` | `request_generation`, `run_generation`, `list_plans`, `get_plan`, ops reads, stale expiry; transition table (section I) |
| `rulesets.py` | `load_ruleset` and `check_citations` (section H.3) |
| `handlers.py` | Outbox subscription: `houseplan.generation_requested` → job |
| `jobs.py` | `generate_plan` task on queue `engine` |

### A.2 Pure engine `apps/api/src/p2b/houseplans/engine/`

No database, no I/O, no FastAPI, SQLAlchemy or Procrastinate; imports only the standard library, Pydantic and `p2b.core.vocabulary` (import-linter contract, section B).

| File | Contents |
|---|---|
| `__init__.py` | Public engine API: `normalise`, `generate`, `validate`, `derive`, `canonical_hash`, `ENGINE_VERSION` |
| `units.py` | Feet to millimetres with `Decimal` and half-even rounding; millimetre formatting for messages |
| `model.py` | HousePlan schema 1.0.0 (section E) |
| `canonical.py` | Canonical JSON (sorted keys, no whitespace, UTF-8) and sha256 over the plan body |
| `upgrade.py` | Schema version registry: accepts 1.x, refuses unknown majors with `SCHEMA_VERSION_UNSUPPORTED`; no upgraders yet |
| `intent.py` | `DesignInputs` (provisional), `ArchitecturalIntent`, `normalise()` and its outcomes (section F) |
| `ruleset.py` | `RulesetContent` model (section H) |
| `geom.py` | Integer geometry: `Rect`, area, containment, overlap area, shared-edge length, point-on-segment, segment splitting, polygon area (shoelace), polygon simplicity for axis-aligned polygons |
| `graph.py` | Room rectangles → nodes, walls and room boundary cycles (T-junction split, exterior or interior kind, open edges of non-enclosed rooms) |
| `solver/__init__.py` | `LayoutSolver` protocol, `LayoutProblem`, `SolveOutcome` (section J) |
| `solver/bands.py` | The Checkpoint 1 solver: deterministic band-and-spine layout; kept afterwards as the dependency-free fallback and as a test oracle |
| `place.py` | Rule-based openings (doors, main entrance, voids, windows) and fixtures from ruleset templates |
| `generate.py` | Pipeline: intent + ruleset → problem → solve → graph → place → assemble → validate; returns `GenerationResult` |
| `derive.py` | `PlanGeometry` 1.0.0 (section E.4) |
| `validate.py` | Check registry, `ValidationContext`, `validate()` (section G) |
| `checks/schema.py`, `checks/geometry.py`, `checks/openings.py`, `checks/fixtures.py`, `checks/circulation.py`, `checks/dimensions.py`, `checks/requirements.py` | One function per code (section G.3) |

### A.3 Migration, scripts, tests, fixtures

| Path | Contents |
|---|---|
| `apps/api/migrations/versions/0019_houseplans.py` | Section C |
| `apps/api/scripts/update_houseplan_golden.py` | Regenerates golden files from the requirement fixtures; prints the diff summary; never run by CI |
| `apps/api/scripts/render_houseplan_debug.py` | Development aid: writes a plain SVG of a `PlanGeometry` for human review of golden cases. Not product code, not served, not a renderer the web app uses |
| `apps/api/tests/houseplans_support.py` | Fixture loaders, synthetic ruleset insertion, plan builders for the negative corpus |
| `apps/api/tests/test_houseplan_geom.py` | Section K |
| `apps/api/tests/test_houseplan_normalise.py` | Section K |
| `apps/api/tests/test_houseplan_solver.py` | Section K |
| `apps/api/tests/test_houseplan_validate.py` | Section K (negative and positive corpus) |
| `apps/api/tests/test_houseplan_derive.py` | Section K |
| `apps/api/tests/test_houseplan_golden.py` | Section K |
| `apps/api/tests/test_houseplans_api.py` | Section K (routes, access, states, job end to end) |
| `apps/api/tests/fixtures/houseplans/ruleset_synthetic_test_only.json` | Synthetic ruleset (section H.4) |
| `apps/api/tests/fixtures/houseplans/requirements/*.json` | Requirement answers + design inputs (section L.1) |
| `apps/api/tests/fixtures/houseplans/invalid/*.json` | Negative corpus (section L.2) |
| `apps/api/tests/fixtures/houseplans/golden/*.json` | Golden outputs: plan body, report summary, hash |

### A.4 Documents

| Path | When |
|---|---|
| `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_1_REPORT.md` | At the end of Checkpoint 1: what was built, test results as run, section N measurements, deviations |

---

## B. Existing files to modify

| File | Change |
|---|---|
| `apps/api/src/p2b/core/vocabulary.py` | New enums (section E.5) and their addition to `ALL_ENUMS` |
| `apps/api/src/p2b/core/errors.py` | `DesignInputRequired` (422 `DESIGN_INPUT_REQUIRED`), `PlanUnsupported` (422 `PLAN_UNSUPPORTED`), `RulesetNotPublished` (409 `RULESET_NOT_PUBLISHED`), `GenerationInProgress` (409 `GENERATION_IN_PROGRESS`) |
| `apps/api/src/p2b/core/config.py` | Settings `houseplans_enabled` (default false), `houseplans_allow_draft_ruleset` (false), `houseplans_allow_synthetic_ruleset` (false), `houseplans_solve_timeout_seconds` (technical budget, default 30). Guards: production refuses draft and synthetic; synthetic only in `local` and `test` (the fake-gateway pattern, `config.py:150-185`) |
| `apps/api/src/p2b/main.py` | Include `houseplans.router` and `houseplans.ops_router` |
| `apps/api/src/p2b/worker.py` | Register `houseplans.handlers` and the `houseplans` job blueprint |
| `apps/api/migrations/env.py` | `import p2b.houseplans.models` |
| `apps/api/pyproject.toml` | Import-linter: add `p2b.houseplans` to the `core` and `integrations` forbidden lists and to the independence contract; add `p2b.** -> p2b.houseplans.interface` to `ignore_imports`; new contract "houseplans engine is pure": `p2b.houseplans.engine` may not import any other `p2b` module except `p2b.core.vocabulary`, nor `sqlalchemy`, `fastapi`, `procrastinate`, `httpx`, `boto3` (`include_external_packages = true`). No new runtime dependency |
| `apps/api/tests/test_schema.py` | CHECK-versus-vocabulary cases for the new tables |
| `apps/api/.env.example` | The four settings, with `P2B_HOUSEPLANS_ENABLED=true`, `P2B_HOUSEPLANS_ALLOW_DRAFT_RULESET=true` and `P2B_HOUSEPLANS_ALLOW_SYNTHETIC_RULESET=true` for local development only |
| `packages/contracts/openapi.json`, `packages/contracts/src/schema.d.ts`, `packages/contracts/src/vocabulary.ts` | Regenerated by `pnpm contracts`; never edited by hand |
| `SYSTEM_BLUEPRINT/01_ARCHITECTURE/DATA_ARCHITECTURE.md` 4.24, `API_ARCHITECTURE.md` 23 | "Proposed" becomes "As built" with any deviation, after the checkpoint |
| `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/FOUNDATION_PLAN.md` | Status line for Checkpoint 1, after the checkpoint |

No web source file changes. Existing route-rule and append-only tests pick the new routes and guards up automatically; they must pass unchanged.

---

## C. Migration plan

**Migration `0019_houseplans`**, `down_revision = "0018"`. Rung M1 (additive only): new tables, no change to existing tables or data. No seed data: no ruleset row is created (AD-05).

### C.1 `layout_rulesets`

| Column | Type | Rule |
|---|---|---|
| `id` | uuid PK | |
| `version` | integer, unique | |
| `status` | varchar(10) | CHECK in DRAFT, APPROVED, PUBLISHED, RETIRED |
| `is_synthetic` | boolean | CHECK `NOT (is_synthetic AND status IN ('APPROVED','PUBLISHED'))`: synthetic test data can never be approved or published |
| `schema_version` | varchar(16) | Ruleset content schema, `1.0.0` |
| `content` | jsonb | `RulesetContent`; immutable |
| `content_sha256` | char(64) | |
| `note` | text | |
| `created_by`, `created_at` | uuid null, timestamptz | |
| `approved_by`, `approved_at`, `published_by`, `published_at`, `retired_at` | uuid null, timestamptz null | CHECK PUBLISHED ⇒ `published_by` and `approved_by` set |

Index: partial unique on `(status)` where `status = 'PUBLISHED'` (one published ruleset). Guard: lifecycle columns only (`status`, approval, publication and retirement columns); `content` never changes; a change is a new version.

### C.2 `house_plans`

| Column | Type | Rule |
|---|---|---|
| `id` | uuid PK | |
| `project_id` | uuid FK `projects.id` | |
| `sequence` | integer | unique `(project_id, sequence)` |
| `generation_state` | varchar(12) | CHECK in QUEUED, RUNNING, SUCCEEDED, INFEASIBLE, FAILED |
| `design_inputs` | jsonb | Provisional `DesignInputs` as received (CP1-03) |
| `intent` | jsonb | `ArchitecturalIntent` computed at request time |
| `intent_sha256` | char(64) | |
| `question_set_version`, `requirement_version` | integer | |
| `ruleset_id` | uuid FK `layout_rulesets.id` | The exact ruleset used |
| `ruleset_version` | integer | |
| `engine_version`, `solver` | varchar(20), varchar(12) | Solver `BANDS` at CP1 |
| `seed` | bigint | sha256(project:sequence) truncated, as 3.1 does |
| `head_revision_no` | integer default 0 | |
| `head_document` | jsonb null | HousePlan; set iff SUCCEEDED |
| `head_validity` | varchar(8) null | VALID or INVALID; set iff SUCCEEDED |
| `head_report` | jsonb null | ValidationReport; set iff SUCCEEDED |
| `infeasibility` | jsonb null | Reasons; set iff INFEASIBLE |
| `failure_reason` | varchar(32) null | Set iff FAILED: ENGINE_ERROR, ENGINE_INVALID_OUTPUT, ENGINE_TIMEOUT, STALE |
| `failure_detail` | text null | Internal only, never returned |
| `solve_ms`, `attempts` | integer null, smallint | |
| `is_authoritative` | boolean default false | CHECK `is_authoritative = false` (PD-28) |
| `requested_by` | uuid FK `users.id` | |
| `created_at`, `started_at`, `completed_at`, `updated_at`, `version` | | `version` for optimistic locking |

Indexes: `(project_id, generation_state)`; partial unique `(project_id)` where state in QUEUED, RUNNING (one generation in flight per project, enforced by the database). Guard: lifecycle columns only; `design_inputs`, `intent`, ruleset and versions never change after insert.

### C.3 `house_plan_versions`

| Column | Type | Rule |
|---|---|---|
| `id` | uuid PK | |
| `plan_id` | uuid FK `house_plans.id` | unique `(plan_id, version_no)` |
| `version_no` | integer | 1 = the generated result |
| `name` | varchar(80) | "Generated" for version 1 |
| `revision_no` | integer | |
| `schema_version` | varchar(16) | |
| `document`, `content_sha256` | jsonb, char(64) | |
| `validity`, `report` | varchar(8), jsonb | |
| `created_by`, `created_at` | uuid null (system), timestamptz | |

Append-only (existing trigger pattern). Checkpoint 1 writes only version 1.

### C.4 Not in 0019

`house_plan_ops` (editing operations, checkpoint 5), design brief storage (AD-03), file purpose for plan PDFs (checkpoint 7), `design_requests.reference_plan_version_ids` (checkpoint 7).

### C.5 Dependency on uncommitted work

0018 (Slice 3.7C) is in the working tree, uncommitted, awaiting review. 0019 revises 0018. If 3.7 review changes 0018, 0019 is unaffected (it touches no 3.7 table) and only its `down_revision` must still name the head. CP1-08 recommends committing 3.7 before Checkpoint 1 starts.

---

## D. API contracts

All under `/api/v1`, the standard error envelope, CSRF headers on state changes. When `houseplans_enabled` is false every route answers 404 (the feature does not exist in that environment).

### D.1 Homeowner routes (`router.py`, audience IHB)

| Method and path | Who (AD-12) | Request | Responses |
|---|---|---|---|
| `POST /projects/{project_id}/house-plans` | Owner | Header `Idempotency-Key` (required). Body `GenerateHousePlanRequest` | **202** `HousePlanSummaryOut` (QUEUED). **404** not a member, or feature off. **403** member but not owner. **409** `STATE_CONFLICT` project status not in the generating set (CP1-04); `GENERATION_IN_PROGRESS`; `RULESET_NOT_PUBLISHED`. **422** `DESIGN_INPUT_REQUIRED` with `details.missing[]` (`key`, `reason`); `PLAN_UNSUPPORTED` with `details.reasons[]`; `VALIDATION_ERROR` for a malformed body. **429** rate limit (CP1-07) |
| `GET /projects/{project_id}/house-plans` | Owner, members | | **200** `HousePlanListOut`. **404** |
| `GET /projects/{project_id}/house-plans/{plan_id}` | Owner, members | | **200** `HousePlanDetailOut`. **404** (also for a plan of another project) |

Normalisation runs inside the POST request, before any row is written. A request that cannot be normalised creates nothing and consumes nothing.

### D.2 Operations routes (`ops_router.py`, audience OPS, MFA, roles OPS or ADMIN; read only)

| Method and path | Response |
|---|---|
| `GET /ops/projects/{project_id}/house-plans` | `HousePlanListOut` |
| `GET /ops/house-plans/{plan_id}` | `HousePlanDetailOut` plus `failure_detail` (internal) |

### D.3 Schemas (`schemas.py`, all `extra="forbid"`)

```python
class GenerateHousePlanRequest(BaseModel):
    design_inputs: DesignInputs | None = None          # provisional until AD-03 (CP1-03)

class HousePlanSummaryOut(BaseModel):
    plan_id: str
    sequence: int
    state: PlanGenerationState
    validity: PlanValidity | None                      # set when SUCCEEDED
    failure_reason: PlanFailureReason | None
    ruleset_version: int
    ruleset_status: RulesetStatus                      # lets any UI label "rules not yet verified"
    ruleset_is_synthetic: bool
    is_authoritative: Literal[False]
    created_at: datetime
    completed_at: datetime | None

class HousePlanListOut(BaseModel):
    items: list[HousePlanSummaryOut]

class InfeasibilityOut(BaseModel):
    reasons: list[InfeasibleReasonOut]                 # code, params, message_key

class HousePlanDetailOut(HousePlanSummaryOut):
    intent: ArchitecturalIntent
    document: HousePlan | None                         # SUCCEEDED only
    geometry: PlanGeometry | None                      # derived on read from document; never stored
    validation: ValidationReport | None
    infeasibility: InfeasibilityOut | None
```

Plot dimensions and room data are not personal data; no name, contact, address, coordinates or locality appears in any of these payloads.

### D.4 Events and job

| Event (outbox) | Payload | Effect |
|---|---|---|
| `houseplan.generation_requested` | `plan_id`, `project_id` | `handlers.py` defers `houseplans:generate_plan` on queue `engine` with `queueing_lock = "plan:{id}"` and `lock = "houseplans:engine"` (Procrastinate runs jobs sharing a `lock` one at a time: concurrency 1 without a separate worker; verify on the pinned 3.10 at implementation) |
| `houseplan.generation_finished` | `plan_id`, `project_id`, `state` | No consumer at Checkpoint 1 |

Audit records through `audit.interface`: generation requested, generation finished (state, solver, ruleset version, timings).

---

## E. HousePlan schema (engine `model.py`, version 1.0.0)

All models `ConfigDict(extra="forbid", frozen=True)`. A payload with a field not in the schema (for example a door with `x` and `y`) is `SCHEMA_INVALID`; there is no way to give an opening or a fixture free coordinates.

### E.1 Scalars

```python
SCHEMA = "p2b.houseplan"
SCHEMA_VERSION = "1.0.0"
Mm = Annotated[int, Field(ge=-10_000_000, le=10_000_000)]        # integer millimetres
PosMm = Annotated[int, Field(gt=0, le=1_000_000)]
Id = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,47}$")]
```

Coordinate frame (plot-local): origin at the plot's front-left corner as seen from the road; +x along the front (road) edge to the right; +y into the plot, away from the road. Polygons counter-clockwise. `north_angle_deg` is the clockwise angle from +y to true north, so a plot facing South has `north_angle_deg = 0`, East 90, North 180 and West 270 (formula: (180 − facing bearing) mod 360). Integer degrees.

### E.2 Document

```python
class Origin(BaseModel):
    kind: OriginKind                                  # REQUIREMENT | DESIGN_INPUT | RULESET | USER_EDIT | INTERPRETATION
    ref: Annotated[str, Field(max_length=120)]        # e.g. "requirement:bedrooms", "ruleset:base_programme"

class Point(BaseModel):  x: Mm; y: Mm

class PlotEdge(BaseModel):
    id: Id; start: int; end: int                      # vertex indices
    kind: PlotEdgeKind                                # ROAD | NEIGHBOUR | OPEN
    side: SetbackSide                                 # FRONT | BACK | LEFT | RIGHT
    road_width_mm: PosMm | None = None

class Plot(BaseModel):
    vertices: Annotated[list[Point], Field(min_length=4, max_length=64)]
    edges: list[PlotEdge]

class Setback(BaseModel):
    edge: Id; distance_mm: Annotated[int, Field(ge=0, le=1_000_000)]
    source: SetbackSource                              # REQUIREMENT | DESIGN_INPUT | RULESET

class Parking(BaseModel):
    spaces: Annotated[int, Field(ge=1, le=4)]; kind: ParkingKind
    space_w_mm: PosMm; space_d_mm: PosMm
    placement: ParkingPlacement                        # INSIDE_FOOTPRINT at CP1
    origin: Origin

class Site(BaseModel):
    plot: Plot
    north_angle_deg: Annotated[int, Field(ge=0, lt=360)]
    facing: Facing                                     # N, NE, E, SE, S, SW, W, NW
    entry_edge: Id
    setbacks: list[Setback]
    parking: Parking | None

class Node(BaseModel):  id: Id; x: Mm; y: Mm

class Wall(BaseModel):
    id: Id; a: Id; b: Id                               # node ids
    thickness_mm: PosMm; height_mm: PosMm | None = None
    kind: WallKind                                     # EXTERIOR | INTERIOR | PARAPET | LOW
    structural_role: Literal["UNASSESSED"] = "UNASSESSED"

class SizeSpec(BaseModel):
    min_short_mm: PosMm; min_area_mm2: Annotated[int, Field(gt=0)]
    pref_area_mm2: int | None = None; max_area_mm2: int | None = None

class Room(BaseModel):
    id: Id; type: RoomType; name: Annotated[str, Field(max_length=60)]
    boundary: Annotated[list[Id], Field(min_length=4)] # ordered CCW cycle of node ids
    zone: Zone; enclosed: bool; required: bool
    size_spec: SizeSpec; origin: Origin

class DoorSpec(BaseModel):
    leaf: DoorLeaf                                     # SINGLE | DOUBLE | SLIDING
    hinge: HingeSide                                   # A_SIDE | B_SIDE (relative to wall a→b)
    opens_to: WallSide                                 # LEFT | RIGHT of the wall's a→b direction

class Opening(BaseModel):
    id: Id; kind: OpeningKind                          # DOOR | MAIN_ENTRANCE | WINDOW | VOID
    wall: Id                                           # the host; the only position reference
    offset_mm: Annotated[int, Field(ge=0)]             # from node a to the near jamb, along the wall
    width_mm: PosMm; height_mm: PosMm; sill_mm: Annotated[int, Field(ge=0)]
    door: DoorSpec | None = None                       # model validator: required iff DOOR or MAIN_ENTRANCE

class Stair(BaseModel):                                # schema present; not generated at CP1
    id: Id; from_floor: Id; to_floor: Id | None; room: Id
    shape: StairShape; origin_corner: Point; run_axis: Axis
    width_mm: PosMm; riser_mm: PosMm; tread_mm: PosMm; risers: Annotated[int, Field(ge=1)]
    landing_d_mm: Annotated[int, Field(ge=0)]

class Fixture(BaseModel):
    id: Id; type: FixtureType
    room: Id; wall: Id; offset_mm: Annotated[int, Field(ge=0)]; side: WallSide
    w_mm: PosMm; d_mm: PosMm                           # copied from the ruleset catalogue
    origin: Origin

class Floor(BaseModel):
    id: Id; level: Annotated[int, Field(ge=0, le=3)]; name: str
    ffl_mm: Mm; floor_to_floor_mm: PosMm; clear_height_mm: PosMm; slab_mm: PosMm; plinth_mm: Annotated[int, Field(ge=0)]
    nodes: list[Node]; walls: list[Wall]; rooms: list[Room]
    openings: list[Opening]; stairs: list[Stair]; fixtures: list[Fixture]

class Constraint(BaseModel):
    id: Id; kind: ConstraintKind; strength: ConstraintStrength
    weight: Annotated[int, Field(ge=0, le=1000)]
    subjects: list[str]; params: dict[str, int | str | bool | list[str]]
    origin: Origin; outcome: ConstraintOutcome         # MET | RELAXED | UNMET | NOT_EVALUATED

class Compromise(BaseModel):
    id: Id; constraint: Id; change_key: str; params: dict[str, int | str]
    accepted_by_user: bool | None = None

class GeneratorInfo(BaseModel):
    engine: Literal["p2b-houseplans"]; engine_version: str
    solver: SolverKind; solver_version: str; seed: int
    ruleset_version: int; ruleset_sha256: str; intent_sha256: str

class Meta(BaseModel):
    schema_: Literal["p2b.houseplan"] = Field(alias="schema")
    schema_version: str                                # semver; upgrade.py checks the major
    plan_id: UUID | None = None; project_id: UUID | None = None
    question_set_version: int | None = None; requirement_version: int | None = None
    revision_no: int = 0; source: PlanSource           # GENERATED | EDITED | REGENERATED
    generator: GeneratorInfo
    created_at: datetime | None = None; created_by: str | None = None
    body_sha256: str | None = None

class HousePlanBody(BaseModel):
    site: Site; floors: Annotated[list[Floor], Field(min_length=1, max_length=4)]
    constraints: list[Constraint]; compromises: list[Compromise]

class HousePlan(HousePlanBody):
    meta: Meta
```

### E.3 Conventions the engine guarantees and the validator re-checks

- Room boundaries lie on wall centrelines. Exterior wall centrelines sit half the exterior thickness inside the buildable envelope, so the wall's outer face is on the envelope line, never in the setback.
- Clear (carpet) dimensions and areas are the room polygon inset by half of each bounding wall's thickness; they are derived, never stored.
- Ids are deterministic: rooms from intent keys (`bedroom_1`, `bath_attached_1`), nodes and walls numbered in sorted coordinate order. Identical input gives identical ids.
- `body_sha256` = sha256 of the canonical JSON of `HousePlanBody`. `meta` is excluded, so plan ids and timestamps do not change the hash.

### E.4 PlanGeometry (engine `derive.py`, version 1.0.0)

The only geometry any renderer, PDF or 3D view consumes. Derived on every read; never stored, never accepted as input.

```python
class PlanGeometry(BaseModel):
    geometry_version: Literal["1.0.0"]; units: Literal["mm"]
    bounds: BBox; plot: Polygon; envelope: Polygon
    floors: list[FloorGeometry]

class FloorGeometry(BaseModel):
    level: int
    rooms: list[RoomGeom]          # id, type, name, zone, polygon, clear_polygon, clear_w_mm, clear_d_mm, carpet_area_mm2, label_at
    walls: list[WallGeom]          # id, kind, a, b, thickness_mm, length_mm, outline (polygon with opening gaps),
                                   # pieces: [{s0_mm, s1_mm, z0_mm, z1_mm}] (solid, sill and lintel pieces for later 3D)
    openings: list[OpeningGeom]    # id, kind, wall, jamb_a, jamb_b, swing {hinge, radius_mm, start_deg, end_deg} | None,
                                   # connects: [room id or "EXTERIOR", room id or "EXTERIOR"]
    fixtures: list[FixtureGeom]    # id, type, room, footprint (polygon), clearance (polygon)
    dimensions: list[DimensionChain]  # id, kind (PLOT | ENVELOPE | ROOM_CLEAR), start, end, offset_mm, value_mm
```

### E.5 Vocabulary additions (`core/vocabulary.py`)

`Facing`, `SetbackSide`, `PlotEdgeKind`, `SetbackSource`, `ParkingKind`, `ParkingPlacement`, `OriginKind`, `RoomType`, `Zone`, `WallKind`, `OpeningKind`, `DoorLeaf`, `HingeSide`, `WallSide`, `StairShape`, `Axis`, `FixtureType`, `ConstraintKind`, `ConstraintStrength`, `ConstraintOutcome`, `RelationKind`, `OrientationMode`, `DiningArrangement`, `KitchenArrangement`, `StairChoice`, `DesignInputKey`, `MissingInputReason`, `UnsupportedReason`, `InfeasibleReason`, `PlanSource`, `SolverKind`, `RulesetStatus`, `PlanGenerationState`, `PlanFailureReason`, `PlanValidity`, `ValidationCode`, `ValidationCategory`, `ValidationSeverity`, `RepairHint`, `EntityKind`. Values as listed in the readiness document sections I.4, K.2 and L.3 and in this section. All reach `vocabulary.ts` through the existing generator.

---

## F. ArchitecturalIntent schema and normalisation (engine `intent.py`)

### F.1 Provisional design inputs (CP1-03; replaced when AD-03 is decided)

```python
class DesignInputs(BaseModel):                         # every field optional; extra="forbid"
    facing_override: Facing | None = None              # AD-15: facing is the road side unless corrected here
    setbacks_ft: dict[SetbackSide, Decimal] | None = None   # fills "Not sure" sides only
    bedrooms_exact: int | None = None                  # when bedrooms = 5_PLUS
    bathrooms_exact: int | None = None                 # when bathrooms = 5_PLUS
    attached_bathrooms: int | None = None
    parking_spaces: int | None = None
    parking_kind: ParkingKind | None = None
    dining: DiningArrangement | None = None            # SEPARATE | IN_LIVING
    kitchen: KitchenArrangement | None = None          # CLOSED | OPEN
    stair: StairChoice | None = None                   # NONE | INTERNAL | EXTERNAL
    utility: bool | None = None
```

### F.2 Intent

```python
class SiteIntent(BaseModel):
    frontage_mm: PosMm; depth_mm: PosMm                # CP1-01: width = frontage along the road
    facing: Facing; north_angle_deg: int
    setbacks_mm: dict[SetbackSide, int]                # all four sides; CP1-02: LEFT/RIGHT as seen from the road
    road_width_mm: PosMm | None = None

class ProgrammeItem(BaseModel):
    key: Id; room_type: RoomType; must_have: bool
    size_pref: SizePref | None = None; origin: Origin

class Relation(BaseModel):
    kind: RelationKind                                 # ADJACENT_WITH_DOOR | ADJACENT_OPEN | ADJACENT | NOT_ADJACENT_DOOR
    a: Id; b: Id; strength: ConstraintStrength; origin: Origin

class ParkingIntent(BaseModel):  spaces: int; kind: ParkingKind; placement: ParkingPlacement
class StairIntent(BaseModel):    choice: StairChoice
class OrientationIntent(BaseModel):
    mode: OrientationMode                              # OFF | SOFT | SOFT_HIGH from the vastu answer
    sectors: list[SectorPreference] = []               # empty until AD-13; the solver ignores orientation at CP1

class ArchitecturalIntent(BaseModel):
    intent_version: Literal["1.0.0"]
    sources: IntentSources                             # question_set_version, requirement_version, design_inputs_sha256,
                                                       # ruleset_version, ruleset_sha256
    site: SiteIntent
    floors: Literal[1]                                 # CP1 and MVP pending AD-04
    programme: list[ProgrammeItem]
    relations: list[Relation]
    orientation: OrientationIntent
    parking: ParkingIntent | None
    stair: StairIntent
    target_built_up_mm2: int | None
    fixture_overrides: list[FixtureOverride] = []      # explicit extra fixtures; none can come from RQ v1
    interpretation: list[None] = []                    # reserved; always empty (PD-28: no language model)
```

### F.3 `normalise(answers, design_inputs, ruleset) -> Normalised | NeedsInput | Unsupported`

Deterministic. Never guesses: a missing fact is `NeedsInput`, an unsupported case is `Unsupported`.

| Input | Rule | Outcome when not usable |
|---|---|---|
| `plot_is_rectangular` | Must be true | Unsupported `PLOT_NOT_RECTANGULAR` |
| `plot_width_ft`, `plot_depth_ft` | mm by `units.ft_to_mm` | |
| `facing` | `design_inputs.facing_override` else the answer | `NOT_SURE` without override → NeedsInput `facing` |
| `setbacks` | Numeric sides used; `NOT_SURE` sides from `design_inputs.setbacks_ft` | Still missing → NeedsInput `setbacks.<side>`. No ruleset default at CP1 (AD-05) |
| `floors` | `G` only | Otherwise Unsupported `FLOORS_NOT_SUPPORTED` (AD-04) |
| `basement` | false only | true → Unsupported `BASEMENT_NOT_SUPPORTED` (CP1-10) |
| `bedrooms` | 1 to 4, or `bedrooms_exact` for 5_PLUS | 5_PLUS without exact → NeedsInput |
| `bathrooms` | same | same |
| attached split | `attached_bathrooms` ≤ min(bedrooms, bathrooms); bedrooms 1..k get BATH_ATTACHED with ADJACENT_WITH_DOOR HARD; the rest BATH_COMMON | missing → NeedsInput `attached_bathrooms` |
| `pooja_room` | true → PUJA | |
| `car_parking` | true → PARKING with `parking_spaces`, `parking_kind` | missing → NeedsInput |
| base programme | `ruleset.base_programme` (for example LIVING, KITCHEN), origin RULESET (CP1-09) | |
| dining | SEPARATE → DINING; IN_LIVING → none | missing → NeedsInput `dining` |
| kitchen | CLOSED → ADJACENT_WITH_DOOR(kitchen, dining or living); OPEN → ADJACENT_OPEN | missing → NeedsInput `kitchen` |
| utility | true → UTILITY with ADJACENT_WITH_DOOR(utility, kitchen) | missing → NeedsInput `utility` |
| stair | NONE only at CP1 | INTERNAL or EXTERNAL → Unsupported `STAIR_NOT_YET_SUPPORTED` |
| `vastu` | OrientationIntent.mode only | |
| `built_up_area_sqft` | target, soft | `NOT_SURE` → None |
| `style`, `quality_tier`, budget, timing, notes, uploads | Not read | |

Size specifications come from the ruleset per room type; the intent carries no rule values of its own.

---

## G. Validation interface (engine `validate.py`)

### G.1 Contract

```python
def validate(
    document: Mapping[str, Any] | HousePlan,
    ruleset: RulesetContent,
    *,
    intent: ArchitecturalIntent | None = None,
) -> ValidationReport: ...
```

- Accepts raw JSON or a model. Parsing failure returns a report with `SCHEMA_INVALID` issues (Pydantic error locations as params); it never raises for bad input.
- Independent of the generator: it recomputes all derived values from the document through `derive`, and shares only `geom.py` primitives.
- Deterministic: issues sorted by category order, code, then entity ids.
- `valid` is true iff `errors` is empty.

```python
class EntityRef(BaseModel):     kind: EntityKind; id: str          # ROOM | WALL | NODE | OPENING | FIXTURE | PLOT | ENVELOPE | REQUIREMENT
class ValidationIssue(BaseModel):
    code: ValidationCode; category: ValidationCategory; severity: ValidationSeverity   # ERROR | WARNING
    entities: list[EntityRef]; message_key: str; params: dict[str, int | str | bool | list[str]]
    message: str; repair: RepairHint                                                    # AUTO | USER | NONE
class ValidationReport(BaseModel):
    valid: bool; schema_version: str; engine_version: str
    ruleset_version: int; ruleset_sha256: str
    errors: list[ValidationIssue]; warnings: list[ValidationIssue]
    checks_run: list[ValidationCode]

class Check(Protocol):
    codes: tuple[ValidationCode, ...]; category: ValidationCategory
    requires: frozenset[Stage]                          # SCHEMA, REFS, GEOMETRY: skipped if an earlier stage failed
    def __call__(self, ctx: ValidationContext) -> Iterable[ValidationIssue]: ...
```

### G.2 Stages

1. **SCHEMA**: parse, schema version major check. Failure stops here.
2. **REFS**: ids unique; every reference resolves (wall nodes, room boundary nodes, opening host wall, fixture room and wall, setback edges, entry edge). Failure stops geometry checks that depend on the broken reference.
3. **GEOMETRY and the rest**: all other checks on the derived context.

### G.3 Codes implemented at Checkpoint 1

| Code | What fails | Required by this checkpoint's proof |
|---|---|---|
| SCHEMA_INVALID | Payload does not match the schema (includes free `x`/`y` on an opening or fixture) | Floating door or window |
| SCHEMA_VERSION_UNSUPPORTED | Unknown major version | |
| ID_DUPLICATE, REF_MISSING | Duplicate id; unresolved reference other than the specific ones below | |
| OPENING_HOST_MISSING | A door or window names a wall that does not exist | **Door / window not hosted by a wall** |
| OPENING_OUTSIDE_HOST | `offset + width` beyond the wall length less jamb clearance at either end | **Door not hosted by a wall** (runs off it) |
| WINDOW_ON_INTERIOR_WALL | Window on an INTERIOR wall | **Window not hosted by a valid wall** |
| OPENING_OVERLAP | Two openings overlap on one wall | |
| GEOMETRY_UNSUPPORTED_V1 | Plot or room polygon not axis-aligned | |
| ROOM_POLYGON_INVALID | Fewer than 4 distinct nodes, zero area, self-intersection, or clockwise | |
| ROOM_OVERLAP | Two room polygons overlap with positive area (params: overlap area) | **Room overlap** |
| ROOM_OUTSIDE_ENVELOPE | Any part of a room or wall outer face outside the buildable envelope | **Room outside envelope** |
| BUILDING_OUTSIDE_PLOT | Any part outside the plot | |
| ROOM_EDGE_NOT_ON_WALL | An enclosed room edge not covered by walls | |
| WALL_DANGLING_END | A wall node of degree 1 (except LOW and PARAPET) | |
| FIXTURE_OUTSIDE_ROOM | Fixture footprint not inside its room's clear polygon | |
| FIXTURE_NOT_PERMITTED_IN_ROOM | Fixture type not permitted for the room type by the ruleset matrix | **WC in living room** |
| FIXTURE_COUNT_EXCEEDS_SPEC | More fixtures of a type than the room template allows plus explicit `fixture_overrides` | **Duplicate WC** |
| FIXTURE_OVERLAP | Fixture footprints overlap | |
| FIXTURE_BLOCKS_OPENING | Fixture footprint or clearance overlaps a door swing or opening zone | |
| ENTRANCE_MISSING | No MAIN_ENTRANCE on an exterior wall | |
| ROOM_UNREACHABLE | Enclosed room not reachable from the main entrance through doors and voids (graph search) | **Inaccessible room** |
| ROOM_BELOW_MIN_SHORT_SIDE, ROOM_BELOW_MIN_AREA | Clear dimensions or area below the ruleset (by room type) | |
| PASSAGE_TOO_NARROW | PASSAGE clear width below the ruleset | |
| HABITABLE_ROOM_NO_WINDOW | A room the ruleset marks as needing a window has none on an exterior wall | |
| ROOM_COUNT_MISMATCH | Count per room type differs from the intent (when `intent` is given) | |
| PARKING_MISSING, PARKING_TOO_SMALL | Intent asks for parking; none, or smaller than spaces × space size | |
| RELATION_UNMET | A HARD relation (for example attached bath door) not satisfied | |

All other L.3 codes of the readiness document exist in the vocabulary and are reported as not run (`checks_run` omits them) until their checkpoint.

---

## H. Ruleset interface

### H.1 Content model (engine `ruleset.py`)

```python
class RoomRule(BaseModel):
    zone: Zone; enclosed: bool; needs_window: bool; wet: bool
    min_short_mm: PosMm; min_area_mm2: int; pref_area_mm2: int | None; max_area_mm2: int | None

class FixtureRule(BaseModel):
    w_mm: PosMm; d_mm: PosMm; clear_front_mm: int; clear_side_mm: int
    permitted_rooms: list[RoomType]

class TemplateItem(BaseModel):  fixture: FixtureType; count: int; max_count: int

class Citation(BaseModel):  document: str; clause: str; note: str | None = None

class RulesetContent(BaseModel):
    schema_: Literal["p2b.layout-ruleset"] = Field(alias="schema")
    content_version: Literal["1.0.0"]; units: Literal["mm"]
    grid_mm: PosMm
    walls: WallRules                                   # exterior_mm, interior_mm
    levels: LevelRules                                 # floor_to_floor_mm, clear_height_mm, slab_mm, plinth_mm
    rooms: dict[RoomType, RoomRule]
    base_programme: list[RoomType]
    openings: OpeningRules                             # door_width_mm per use, main_entrance_width_mm, door_height_mm,
                                                       # jamb_clearance_mm, window_width_mm, window_height_mm, window_sill_mm, void_width_mm
    passage_min_width_mm: PosMm
    fixtures: dict[FixtureType, FixtureRule]
    templates: dict[RoomType, list[TemplateItem]]
    parking: dict[ParkingKind, ParkingRule]            # space_w_mm, space_d_mm
    sources: dict[str, Citation]                       # JSON pointer of each value → its source
```

### H.2 Lifecycle

DRAFT → APPROVED (by an ADMIN, recording the architect's review) → PUBLISHED (ADMIN; one at a time) → RETIRED. Content never changes. The authoring and publishing endpoints are **not** in Checkpoint 1 (they need AD-05); Checkpoint 1 creates the table, the loader and the citation check.

### H.3 Loader and checks (`rulesets.py`)

```python
@dataclass(frozen=True)
class LoadedRuleset:
    id: UUID; version: int; status: RulesetStatus; is_synthetic: bool
    content: RulesetContent; sha256: str

async def load_ruleset(session: AsyncSession, settings: Settings) -> LoadedRuleset:
    """The PUBLISHED ruleset. Otherwise, only where settings allow it: the newest APPROVED or DRAFT
    one, and a synthetic one only when houseplans_allow_synthetic_ruleset (local and test).
    Raises RulesetNotPublished when nothing usable exists."""

def missing_citations(content: RulesetContent) -> list[str]:
    """JSON pointers of values without a citation. Publication will require an empty list."""
```

The job loads the ruleset by the id stored on the plan row, never "the current one", so a plan is always reproducible against the exact rules it used.

### H.4 Synthetic test ruleset

`tests/fixtures/houseplans/ruleset_synthetic_test_only.json` carries `"is_synthetic": true`, a note "SYNTHETIC TEST DATA. NOT ARCHITECTURAL RULE VALUES. NOT A PROPOSAL.", and numbers chosen only so the fixtures exercise every code. These numbers are not recommendations and must not be copied into any real ruleset. The database CHECK forbids approving or publishing a synthetic ruleset, and production refuses to load one.

---

## I. Generation job and state model

### I.1 Transition table (`service.py`, `core/state_machine.TransitionTable`)

| From | To | Trigger | Actor | Effect |
|---|---|---|---|---|
| none | QUEUED | `request` | Owner (POST) | Row inserted with intent, ruleset id and version, seed; audit; outbox `houseplan.generation_requested` in the same transaction |
| QUEUED | RUNNING | `start` | Worker | `started_at`, `attempts + 1` |
| RUNNING | SUCCEEDED | `succeed` | Worker | Only when the validator returns `valid = true`: `head_document`, `head_validity = VALID`, `head_report`, version 1 row; outbox `houseplan.generation_finished` |
| RUNNING | INFEASIBLE | `infeasible` | Worker | `infeasibility` reasons (feasibility pre-check or solver); no document |
| RUNNING | FAILED | `fail` | Worker | `failure_reason` ENGINE_ERROR, ENGINE_INVALID_OUTPUT (the generator produced a plan the validator rejected: an engine defect, logged at error level with the report), or ENGINE_TIMEOUT |
| QUEUED | FAILED | `expire` | Request path (stale sweep) | STALE after `houseplans_solve_timeout_seconds × 3 + 600` seconds, the 3.1 pattern |

A generated plan is never stored as SUCCEEDED with errors. Nothing in Checkpoint 1 can produce `head_validity = INVALID` (that needs editing operations).

### I.2 Job body (`run_generation`)

1. Transaction 1: lock the row; return if not QUEUED (idempotent); move to RUNNING.
2. Outside any transaction: load the ruleset by id; run `engine.generate(intent, ruleset, solver=BandSolver(), seed)` in a worker thread with the time budget.
3. Transaction 2: lock the row; return if not RUNNING; write the outcome per I.1; publish the finished event.

Infrastructure retries by Procrastinate (`RetryStrategy(max_attempts=3, exponential_wait=5)`); the engine itself is deterministic, so a retry gives the same answer.

### I.3 Generation pipeline (`engine/generate.py`)

```text
intent + ruleset
  → feasibility pre-check (area budget, minimum short sides against envelope width, parking width)
      fail → INFEASIBLE(reasons)
  → LayoutProblem → BandSolver.solve → Placed(rects) | Infeasible(reasons)
  → graph: nodes, walls, room boundaries
  → place: main entrance, doors, voids, windows, fixtures
      a required placement does not fit → INFEASIBLE(FIXTURE_FIT | OPENING_FIT)
  → assemble HousePlanBody (constraints with outcomes)
  → validate(body, ruleset, intent)
      valid → SUCCEEDED; invalid → FAILED(ENGINE_INVALID_OUTPUT)
```

---

## J. Minimal solver architecture

### J.1 Interface (`engine/solver/__init__.py`)

```python
class LayoutProblem(BaseModel):
    envelope: Rect                                     # structural grid region: envelope inset by half the exterior wall
    grid_mm: int
    rooms: list[RoomDemand]                            # key, type, zone, min_short_mm, min_area_mm2, pref_area_mm2
    relations: list[Relation]
    parking: ParkingDemand | None
    passage_width_mm: int; opening_span_mm: int        # door width + 2 × jamb clearance

class Placed(BaseModel):     rects: dict[str, Rect]; topology: str
class Infeasible(BaseModel): reasons: list[InfeasibleReasonOut]

class LayoutSolver(Protocol):
    kind: SolverKind; version: str
    def solve(self, problem: LayoutProblem, *, seed: int) -> Placed | Infeasible: ...
```

CP-SAT (checkpoint 2, after section N passes) implements the same protocol. The band solver remains as the fallback and as a cross-check in tests.

### J.2 Band-and-spine solver (Checkpoint 1)

Deterministic, no dependency, no randomness (the seed is accepted and unused). It tiles the structural grid region completely, so overlaps and gaps are impossible by construction; the validator still checks.

1. **Front band** across the full width: PARKING at the left (as seen from the road) sized spaces × space width by space depth, LIVING across the rest. Band depth = the larger of the parking depth and the living depth needed for its preferred, else minimum, area at that width, snapped up to the grid.
2. **Spine**: a PASSAGE strip of `passage_min_width_mm` running from the back of the front band to the rear of the region.
3. **Columns** beside the spine take every other room in groups, in this fixed order: [DINING (or none), KITCHEN, UTILITY], [PUJA], each [BATH_COMMON], each [BEDROOM_i, BATH_ATTACHED_i]. Each group goes to the column with the smaller filled depth (ties: left). A room's depth is its preferred area (else minimum) divided by the column width, at least its minimum short side, snapped to the grid. The last room in each column takes any remaining depth.
4. **Configurations tried in order**, first feasible wins: (a) two columns with the spine centred; (b) one column with the spine on the right; (c) one column with the spine on the left. A configuration fails if a column is narrower than a room's minimum short side, a column overflows the depth, or the spine head overlaps LIVING by less than `opening_span_mm`.
5. **None feasible** → `Infeasible` with the arithmetic of the closest configuration (for example "rear depth needed 14,850 mm, available 12,190 mm").

Placement rules (`place.py`): MAIN_ENTRANCE on LIVING's front exterior wall; a VOID from LIVING to the spine head; one DOOR from the spine to each column room whose access is the spine (dining or the first room of its group, puja, common baths, bedrooms), at jamb clearance from the wall end nearest the front, hinged on that side, opening into the room; kitchen from dining (DOOR if CLOSED, VOID if OPEN), utility from kitchen, attached bath from its bedroom. Windows centred on one exterior wall segment of each room whose rule needs one. Fixtures from the room template along walls without openings, in template order, each with its clearance zone; a template that does not fit is `INFEASIBLE(FIXTURE_FIT)`.

This layout is a foundation prototype. It proves the pipeline and the guarantees. It does not attempt good architecture (orientation, Vastu, wet clustering, daylight balance); that is the CP-SAT objective's job in checkpoint 2.

---

## K. Test strategy

All tests run in the existing pytest setup against the test database; engine tests need no database. IC coverage gate: `houseplans/service.py` at least 85%; target 100% branch coverage on `engine/geom.py` and `engine/validate.py`.

| File | Tests |
|---|---|
| `test_houseplan_geom.py` | Area, containment, overlap area, shared edge, point-on-segment, segment split at T-junctions, CCW and simplicity, all with exact integers including boundary-touching cases |
| `test_houseplan_normalise.py` | Each F.3 row: the normal case, the NeedsInput case and the Unsupported case; feet to mm rounding; facing to `north_angle_deg` for all eight facings; facing override; setbacks with NOT_SURE filled and not filled |
| `test_houseplan_solver.py` | Each configuration (a), (b), (c) chosen when expected; tiling: union of rects equals the region and pairwise overlap is zero; infeasible arithmetic message; identical output on repeated calls |
| `test_houseplan_validate.py` | **Negative corpus** (L.2): each file yields exactly its expected code(s) and no other error. **Positive corpus**: every golden plan yields zero errors. Raw JSON with unknown fields → SCHEMA_INVALID, never an exception. Determinism of issue order |
| `test_houseplan_derive.py` | Clear dimensions and carpet area by hand calculation; wall outlines with opening gaps; wall pieces cover the wall length minus openings exactly; door swing geometry; `connects` for every opening; dimension chain values equal plot and envelope sizes |
| `test_houseplan_golden.py` | Each requirement fixture → body equals the golden file byte for byte and `body_sha256` matches; run twice in one process and once in a fresh subprocess. Updating goldens is a deliberate script run with a reviewed diff |
| `test_houseplans_api.py` | Feature off → 404 on every route; owner POST → 202 QUEUED; member POST → 403; non-member → 404; another project's plan id → 404; idempotent retry → one row; second POST while in flight → 409 GENERATION_IN_PROGRESS (and the database partial index holds under two concurrent requests); project in DRAFT or NEEDS_INFO → 409; missing inputs → 422 DESIGN_INPUT_REQUIRED with keys and **no row**; unsupported → 422 PLAN_UNSUPPORTED; no usable ruleset → 409 RULESET_NOT_PUBLISHED; **job end to end** for the two prototype fixtures → SUCCEEDED, document, geometry, report `valid = true`, version 1 row; infeasible fixture → INFEASIBLE with reasons; stale QUEUED row → FAILED STALE; ops routes need MFA and are read only; responses contain no personal data; `failure_detail` only on the ops route |
| `test_schema.py` (extended) | Migrations equal models; new CHECK constraints equal the vocabulary; synthetic ruleset cannot be APPROVED or PUBLISHED; `is_authoritative` cannot be true; versions are append-only; immutable columns refuse updates |
| Config tests | Production refuses `houseplans_allow_draft_ruleset` and `houseplans_allow_synthetic_ruleset`; synthetic outside local and test refused |
| Existing suites | `test_route_rules.py` (every new route has exactly one authorisation rule), import-linter (including the new purity contract), contract drift check, full API suite and Playwright regression unchanged |

---

## L. Example fixtures

### L.1 Requirement fixtures (`requirements/*.json`)

Each holds the RQ v1 answers exactly as stored, the provisional design inputs, and the expected outcome.

```json
{
  "name": "3bhk_30x50_east",
  "answers": {
    "property_type": "INDEPENDENT_HOUSE", "plot_is_rectangular": true,
    "plot_width_ft": 30, "plot_depth_ft": 50, "facing": "E",
    "setbacks": {"FRONT": 10, "BACK": 5, "LEFT": 3, "RIGHT": 3},
    "built_up_area_sqft": "NOT_SURE", "floors": "G", "basement": false,
    "quality_tier": "STANDARD", "bedrooms": "3", "bathrooms": "2",
    "pooja_room": true, "car_parking": true, "vastu": "WHERE_POSSIBLE"
  },
  "design_inputs": {
    "attached_bathrooms": 1, "parking_spaces": 1, "parking_kind": "CAR",
    "dining": "SEPARATE", "kitchen": "CLOSED", "stair": "NONE", "utility": false
  },
  "expect": "SUCCEEDED"
}
```

| Fixture | Purpose | Expected |
|---|---|---|
| `3bhk_30x50_east` | Prototype case 1 | SUCCEEDED, VALID |
| `2bhk_30x40_north` | Prototype case 2: 2 bedrooms, 1 common bath, open kitchen, dining in living | SUCCEEDED, VALID |
| `2bhk_40x30_south_two_cars` | Forces configuration (b) or (c) | SUCCEEDED, VALID |
| `3bhk_20x25_too_small` | Programme does not fit | INFEASIBLE with arithmetic |
| `missing_inputs` | `attached_bathrooms`, `dining` absent; one setback NOT_SURE | NeedsInput listing exactly those keys |
| `not_rectangular` | `plot_is_rectangular = false` | Unsupported PLOT_NOT_RECTANGULAR |
| `g_plus_1` | `floors = G_PLUS_1` | Unsupported FLOORS_NOT_SUPPORTED |
| `facing_not_sure` | `facing = NOT_SURE`, no override | NeedsInput `facing` |

Plot sizes and setbacks in these fixtures are example homeowner inputs, not rules.

### L.2 Negative corpus (`invalid/*.json`)

Each file is a golden VALID plan with one deliberate defect, plus the expected issue.

| File | Defect | Expected code and entities |
|---|---|---|
| `wc_in_living.json` | A WC_WESTERN fixture hosted in `living` | FIXTURE_NOT_PERMITTED_IN_ROOM: fixture, `living` |
| `duplicate_wc.json` | Two more WC fixtures added to `bath_common_1` (three in one bath) | FIXTURE_COUNT_EXCEEDS_SPEC: `bath_common_1`, the extra fixtures (and FIXTURE_OVERLAP if they overlap) |
| `room_overlap.json` | `bedroom_2` boundary moved over `bath_attached_1` | ROOM_OVERLAP: both rooms, overlap area |
| `room_outside_envelope.json` | `bedroom_1` boundary node moved into the rear setback | ROOM_OUTSIDE_ENVELOPE: `bedroom_1` |
| `door_host_missing.json` | A door's `wall` names `w_999` | OPENING_HOST_MISSING: the door |
| `door_off_wall.json` | A door's `offset_mm` beyond its wall | OPENING_OUTSIDE_HOST: the door, its wall |
| `door_with_coordinates.json` | A door given `x`, `y` instead of a host | SCHEMA_INVALID: location of the extra fields |
| `window_host_missing.json` | A window's `wall` names a missing wall | OPENING_HOST_MISSING: the window |
| `window_on_interior.json` | A window moved to an interior wall | WINDOW_ON_INTERIOR_WALL: window, wall |
| `room_unreachable.json` | The spine door of `bedroom_2` removed | ROOM_UNREACHABLE: `bedroom_2` |
| `bedroom_without_attached_door.json` | Door between `bedroom_1` and `bath_attached_1` removed | RELATION_UNMET (and ROOM_UNREACHABLE for the bath) |
| `fixture_outside_room.json` | A basin offset past its room | FIXTURE_OUTSIDE_ROOM |
| `bedroom_too_small.json` | `bedroom_3` shrunk below the synthetic minimum | ROOM_BELOW_MIN_SHORT_SIDE or ROOM_BELOW_MIN_AREA |
| `no_entrance.json` | MAIN_ENTRANCE removed | ENTRANCE_MISSING (and ROOM_UNREACHABLE for every room) |
| `parking_missing.json` | PARKING room removed while intent asks for it | PARKING_MISSING, ROOM_COUNT_MISMATCH |
| `dangling_wall.json` | A wall to a new free node | WALL_DANGLING_END |
| `unknown_major.json` | `schema_version` "2.0.0" | SCHEMA_VERSION_UNSUPPORTED |

---

## M. Acceptance criteria

Checkpoint 1 is complete only when every item holds, verified by tests that ran (IC: never claim a test passes unless it ran).

1. Migration 0019 upgrades and downgrades cleanly on a copy of the current schema; the schema drift test passes.
2. No ruleset row exists after migration; no rule value appears in application code or migrations.
3. With `houseplans_enabled = false`, every houseplans route returns 404; the existing API and Playwright suites pass unchanged.
4. `normalise` turns `3bhk_30x50_east` and `2bhk_30x40_north` into an `ArchitecturalIntent` whose programme matches the answers exactly, and returns `NeedsInput` or `Unsupported` for the L.1 cases with exactly the listed keys or reasons.
5. `generate` turns both prototype fixtures into a HousePlan whose `validate` report has `valid = true`, and `derive` returns a `PlanGeometry` whose room areas, clear dimensions and dimension chains match hand-checked values in the tests.
6. Every negative-corpus file yields its expected code and entities and no unexpected error; the seven cases named in this checkpoint's brief are among them.
7. A door or window cannot be given coordinates: such a payload is SCHEMA_INVALID.
8. `3bhk_20x25_too_small` returns INFEASIBLE with a reason that states the shortfall in millimetres.
9. The same fixture produces a byte-identical body and the same `body_sha256` across runs, processes and machines (CI and local).
10. Through the API with the synthetic ruleset in the test environment: POST → job on queue `engine` → SUCCEEDED; GET returns document, geometry and a report with `valid = true`; a version 1 row exists with the same hash.
11. Access follows AD-12: owner generates; members read; non-members see 404; operations read through MFA routes only.
12. One generation in flight per project, enforced by the database under concurrent requests.
13. `is_authoritative` is false in every response and cannot be stored as true.
14. Import-linter passes, including "houseplans engine is pure"; contracts regenerate with no drift after commit.
15. Coverage: `houseplans/service.py` at least 85%.
16. Section N measurements are recorded in the checkpoint report with a pass or fail against each threshold, whether or not they pass.
17. `AI_DESIGN_ENGINE_CHECKPOINT_1_REPORT.md` written, including debug SVGs of the golden cases for review, deviations from this plan, and the test counts as run.

---

## N. Deployment and container feasibility check for OR-Tools

Runs during Checkpoint 1 as a measurement on a throwaway branch. `ortools` is **not** added to `main`'s dependencies in Checkpoint 1; adoption is a checkpoint 2 step only if every threshold passes.

### N.1 Known facts (PyPI, 2026-10-06)

| Item | Value |
|---|---|
| Latest | `ortools` 9.15.6755, Python ≥ 3.9, Apache-2.0 |
| Linux x86_64 wheel for CPython 3.12 | `manylinux_2_27_x86_64.manylinux_2_28_x86_64`, 29.8 MB (needs glibc 2.28; `python:3.12-slim-bookworm` has 2.36) |
| Linux aarch64 wheel | Available, 27.6 MB |
| Runtime requirements | `absl-py ≥ 2.0.0`, `numpy ≥ 2.0.2`, `pandas ≥ 2.0.0`, `protobuf ≥ 6.33.1, < 6.34`, `typing-extensions ≥ 4.12`, `immutabledict ≥ 3.0.0` |
| Already in `apps/api/uv.lock` | None of numpy, pandas, protobuf, absl-py, immutabledict. All five are new |

### N.2 Procedure

1. Branch `spike/ortools-feasibility`. Add `ortools==9.15.6755` to `apps/api/pyproject.toml`; `uv lock`; record every resolved version and any resolution conflict (the protobuf pin is the likely one).
2. Build the API image (`apps/api/Dockerfile`) for `linux/amd64` before and after; record `docker image inspect --format '{{.Size}}'` for both.
3. In the after-image: `python -X importtime -c "from ortools.sat.python import cp_model"` (import time) and resident memory of a worker process after the import.
4. Benchmark script (kept in the spike branch): a CP-SAT model shaped like checkpoint 2's (12 rooms, 75 mm grid on a 7.6 m × 12.2 m region, no-overlap, containment, minimum sizes, 6 adjacency constraints, a weighted objective) with `num_workers = 1`, a fixed `random_seed` and a deterministic time limit. Run 20 times in one container and 5 times across fresh containers; record wall time p50 and p95, peak memory, and whether every solution is identical.
5. Run on the staging VPS (2 vCPU, 8 GB, shared) as well as CI, because the production profile is the VPS.
6. Licence review of each new package: ortools Apache-2.0, numpy BSD-3, pandas BSD-3, protobuf BSD-3, absl-py Apache-2.0, immutabledict MIT (confirm from each package's metadata).

### N.3 Thresholds [REC; Chirag to accept or change]

| Measure | Pass if |
|---|---|
| Image growth | ≤ 200 MB |
| Worker memory after import | ≤ 300 MB increase |
| Solve time on the VPS, one candidate | p95 ≤ 5 s |
| Determinism | 25 of 25 runs identical |
| Resolution | No conflict with the current lockfile |
| Licences | All permissive and compatible |

### N.4 If it fails

| Failure | Response |
|---|---|
| Image or memory too large | A separate solver worker image consuming only the `engine` queue (ADR-008 extraction trigger), keeping the API image unchanged |
| Solve time too long | Smaller grid module, fewer candidates, or the band solver as the first pass with CP-SAT only refining sizes |
| Non-deterministic | Stricter parameters (single worker, deterministic limit only); if still failing, CP-SAT is not adopted and the band solver grows instead |
| Conflict | Pin compatible versions, or the separate image |

---

## O. Rollback strategy

| Layer | Rollback |
|---|---|
| Feature | `houseplans_enabled = false` hides every route (404) with no deploy |
| Data | 0019 downgrade drops the three tables and their guards; no existing table or row is touched. Production holds no plan rows while the flag is off there, so the downgrade loses nothing in production |
| Jobs | Queued `houseplans:generate_plan` jobs left behind by a rollback fail as unknown tasks and are cleared with the existing Procrastinate tooling; the `engine` queue returns to unused |
| Code | The module is isolated by import-linter: removing `houseplans/` and its lines in `main.py`, `worker.py`, `env.py`, `vocabulary.py`, `errors.py`, `config.py`, `pyproject.toml` restores the previous state; contracts regenerate |
| Contracts | The web app does not call these routes in Checkpoint 1, so generated types can change or disappear without breaking any page |

Order for a full rollback: flag off → deploy code without the module → run the 0019 downgrade → regenerate contracts.

---

## P. Risks and unresolved decisions

### P.1 Risks

| ID | Risk | Mitigation |
|---|---|---|
| CR-01 | Synthetic test values mistaken for real rules | `is_synthetic` column, CHECK against approval or publication, production guard, the file's own note, `ruleset_is_synthetic` in every response |
| CR-02 | The band solver read as the final layout quality | Section J.2 states its limits; the checkpoint report shows the golden plans as foundation output; CP-SAT is checkpoint 2 |
| CR-03 | Normaliser conventions wrong (frontage, left and right) | CP1-01 and CP1-02 asked explicitly; both are one function each and fully tested, so a change is cheap |
| CR-04 | Provisional `design_inputs` contract changes when AD-03 lands | Flag-gated, no web caller, documented as provisional |
| CR-05 | Shared files (`main.py`, `worker.py`, `vocabulary.py`, `config.py`, `pyproject.toml`, `env.py`) are modified in the uncommitted 3.7 work | CP1-08: commit 3.7 first |
| CR-06 | Thread-based time budget cannot stop a runaway computation | The band solver is linear-time; CP-SAT (checkpoint 2) has its own deterministic limit |
| CR-07 | Procrastinate `lock` behaviour differs from expectation on 3.10 | Verified by a test that two queued plans never run at once; fallback is a dedicated worker process with `--queues engine --concurrency 1` |

### P.2 Unresolved decisions for Checkpoint 1

| ID | Question | Recommendation |
|---|---|---|
| CP1-01 | Is "plot width" the frontage along the road, and "depth" the distance away from it? | Yes |
| CP1-02 | Are LEFT and RIGHT setbacks as seen from the road, looking at the plot? | Yes |
| CP1-03 | Until AD-03 is decided, may the generation request carry the provisional `design_inputs` object (flag-gated, no UI)? | Yes |
| CP1-04 | Generate plans in the same project statuses as concept images (submitted onward; not while NEEDS_INFO; not when closed)? | Yes |
| CP1-05 | Feature flag off in production until AD-05 (published ruleset) and AD-06 (allowance) are decided? | Yes |
| CP1-06 | Allow a clearly synthetic ruleset in local and test only, never approvable or publishable? | Yes |
| CP1-07 | No quota until AD-06; one generation in flight per project; the per-session rate limit tier used by concept images? | Yes |
| CP1-08 | Commit Slice 3.7 (after your review) before Checkpoint 1 code starts? | Yes |
| CP1-09 | Living and kitchen always in the programme, as ruleset data (`base_programme`) subject to AD-05 approval? | Yes |
| CP1-10 | Basement = yes is unsupported in the MVP generator? | Yes |
| CP1-11 | Defer the `house_plan_ops` table to the editing checkpoint rather than creating it unused now? | Yes |

Still pending from the readiness document and worked around here: AD-03, AD-04, AD-05, AD-06, AD-11, AD-13, AD-16.

---

## Q. Work intentionally deferred

| Item | Checkpoint |
|---|---|
| CP-SAT solver, orientation and Vastu objective (after AD-13), wet clustering, multiple candidates, deterministic repair loop, compromises | 2 |
| Design brief persistence and UI (AD-03), quota and credits (AD-06), ruleset authoring, approval and publication endpoints (AD-05) | 2 and 3 |
| Staircase generation | 2 |
| Read-only 2D viewer, issues panel, Designs page integration, brief page | 4 |
| Editing operations, `house_plan_ops`, undo and redo, revisions beyond 1, named versions | 5 |
| 3D viewer (three.js + React Three Fiber, ADR-026) | 6 |
| Concept plan PDF, file purpose, reference marking on design requests, label wording (AD-16) | 7 |
| Multi-floor (AD-04), basement, irregular plots, angled walls | After MVP |
| Natural-language editing, free-text interpretation, any language model | After MVP, needs an IC 18.6 amendment |
| DXF export, elevations and sections, plan-conditioned concept images | After MVP |
| Professional access to plans | With the professional workflow |
| Anything from Hairline | Never as code; reference only |

---

## Stop point

This document is the Checkpoint 1 plan. No implementation starts until Chirag approves it and answers CP1-01 to CP1-11.

~Sakha
