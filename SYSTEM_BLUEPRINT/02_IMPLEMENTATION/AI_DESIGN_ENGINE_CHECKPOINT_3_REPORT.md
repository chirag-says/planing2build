# Plan2Build: AI design engine, Checkpoint 3 report (2D renderer and editor foundation)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_3_REPORT.md` |
| Date | 2026-10-07 |
| Basis | Chirag's Checkpoint 3 brief (2026-10-07); `AI_DESIGN_ENGINE_CHECKPOINT_3_DISCOVERY.md`; `AI_DESIGN_ENGINE_CHECKPOINT_3_RENDERER_ARCHITECTURE.md`; HR sections O–S; IC 7, 17–20; `UI_DESIGN_SYSTEM.md` |
| Branch | `houseplans-checkpoint-1`. Checkpoint 1 is `22628ab` (tag `houseplans-cp1`, unchanged). Checkpoints 2 to 2.2.1 and 3 are in the working tree, **not committed, not tagged** |
| Scope kept out | No Gemini, LLM, image generation, 3D, Three.js, OR-Tools, VPS or deployment work; no solver change; no HousePlan schema change; validator unchanged |
| Ruleset | Plans shown here come from the **SYNTHETIC / TEST ONLY** ruleset (local env only). Production stays blocked (AD-05) |
| Review | **Approved technically by Chirag on 2026-10-07**, with D-1 to D-8 (section 3). Next: CP3.1, editor depth and persistence (section 16). No Gemini, LLM editing or 3D yet |
| Assets | `AI_DESIGN_ENGINE_CHECKPOINT_3_ASSETS/plan_renderer_montage.html` (the production drawing component over nine real CP2.2.1 plans, fitted and zoomed out) |

---

## 1. Outcome

A homeowner opens a concept floor plan at `/projects/{id}/designs/plans/{planId}` and sees it drawn from the API's derived geometry, with a persistent disclaimer, a complete room list and the checks. On a tablet or computer the owner selects rooms, room sides, doors and windows and changes them by dragging or with the keyboard. Every change is a typed operation batch that the server applies, validates with the unchanged validator, and stores as a new logged revision only when the validator passes; otherwise the plan stays as it was and the reasons are shown. Undo and redo send server-computed inverses. Members and phones view only.

Verified live on the local stack with real engine plans: a keyboard side move stored as revision 1 (`MOVE_WALL w8 +50`) and undone to the generated body hash; a pointer side drag accepted (kitchen 2.50 → 2.85 m); an over-drag refused by the validator with its reasons, nothing stored; a door dragged along its wall and saved.

## 2. Files

**Backend (API)**

| File | Change |
|---|---|
| `src/p2b/houseplans/engine/ops.py` | MOVE_WALL implemented (`_move_wall`, `wall_run`); `OperationRejected.code` (machine-readable); ADD_ROOM / DELETE_ROOM still refuse |
| `src/p2b/houseplans/engine/edit.py` (new) | `edit()`: apply a batch whole or not at all, re-measure soft terms, validate, stamp revision, EDITED source and body hash; `BatchRejected` with the failing index |
| `src/p2b/houseplans/engine/derive.py` | PlanGeometry 1.1.0: `FloorGeometry.open_areas` (`open_areas()`), derived only |
| `src/p2b/houseplans/service.py` | `apply_operations()` (owner, row lock, expected revision, validate-before-store, op log); `PlanView.can_edit` |
| `src/p2b/houseplans/router.py`, `schemas.py` | `POST /projects/{p}/house-plans/{id}/ops`; `EditingOut` (`can_edit`, `revision_no`, `grid_mm`) on the detail; `EditHousePlanRequest/Out` |
| `src/p2b/houseplans/models.py`, `migrations/versions/0020_house_plan_ops.py` (new) | `house_plan_ops` (append-only, additive, rung M1) |
| `src/p2b/core/vocabulary.py`, `core/errors.py` | `PlanOpRejection`, `PlanOpReason`; `REVISION_CONFLICT`, `PLAN_OPERATION_REJECTED`, `PLAN_EDIT_INVALID` |
| `scripts/export_web_plan_fixtures.py` (new) | Exports real engine plans as web fixtures |
| `tests/test_houseplan_cp3.py` (new), `tests/test_houseplans_api.py`, `tests/test_schema.py` | Engine, API and schema tests (section 9) |
| `packages/contracts/*` | Regenerated |

**Web**

| File | Change |
|---|---|
| `src/lib/plan/types.ts`, `viewport.ts`, `render-model.ts`, `edit.ts`, `editor.ts`, `units.ts` (new) | Contract types, coordinate transforms, render model, gesture → operation builders and snapping, the editor reducer, unit formatting |
| `src/components/plan2build/plan/plan-drawing.tsx`, `plan-canvas.tsx`, `plan-workspace.tsx`, `plan-list.tsx` (new) | SVG drawing, interactive canvas, workspace (toolbar, inspector, room list, checks, problems), "Your floor plans" list |
| `src/app/ihb/projects/[projectId]/designs/plans/[planId]/page.tsx` (new) | The plan page, outside the dashboard layout |
| `(dashboard)/designs/page.tsx`, `components/plan2build/page-header.tsx` | Plan list above the image gallery; `PageContainer width="full"` |
| `messages/en.json` | `Plan` namespace (additions only) |
| `vitest.config.ts` | `.tsx` unit tests |
| `tests/unit/plan-*.test.ts(x)`, `tests/unit/plan-fixtures.ts`, `tests/fixtures/houseplans/*.json`, `tests/unit/__snapshots__/` (new) | Unit tests on nine real plans |
| `e2e/floor-plan.spec.ts` (new) | Live-stack spec (phone and desktop) |

## 3. Architecture decisions

| ID | Decision | Status |
|---|---|---|
| A-1 | The renderer draws the server's PlanGeometry; the browser computes no area, size, wall outline or validity (HR:232, 663) | From the blueprint |
| A-2 | Edits are typed operation batches through `POST …/ops`; the response replaces the plan; the drag preview is never sent | From the blueprint (HR O.1) |
| A-3 | Revisions, not versions: each accepted batch is a revision appended to `house_plan_ops`; version 1 stays the generated plan | From the blueprint (HR R.2); migration 0020 |
| A-4 | One reducer per page; no state library; no string literals in JSX; tokens only | IC 19, UI design system |
| D-1 | Invalid edits are rejected and never stored | **Approved** 2026-10-07 (HR:562, which allowed INVALID working revisions, is superseded) |
| D-2 | MOVE_WALL moves the wall's straight run; resizing a room also resizes the rooms along the same line | **Approved** 2026-10-07 for this checkpoint; local edge moves come with MOVE_NODE / graph editing (CP3.1) |
| D-3 | Open areas are a derived PlanGeometry field (geometry 1.1.0), classified FORECOURT / SIDE_YARD / REAR_YARD / COURT | **Approved** 2026-10-07: presentation data only, never HousePlan entities |
| D-4 | Disclaimer: the AD-16 draft ("Concept floor plan. Not a construction, structural or approval drawing.", plus the architect sentence), persistent on the page | **Approved** 2026-10-07 for the concept-plan UI; AD-16 must be final before production use |
| D-5 | Proceeded with CP2–CP2.2.1 uncommitted | **Approved** 2026-10-07: CP2.x committed first, CP3 separately |
| D-6 | No `Idempotency-Key` on `…/ops`: `expected_revision` already makes a replay a 409, and storing full plan responses per edit would bloat the idempotency table | **Approved** 2026-10-07; a stale replay returns 409 REVISION_CONFLICT (tested) |
| D-7 | Edit rate limit 600 batches per session per 10 minutes (nudges are one batch each) | **Approved for development and testing only**; synthetic until a production rate-limit policy is approved |
| D-8 | Openings and fixtures on a stretched or shrunk wall keep their place on the ground; one that would leave its wall is refused (op-level code or validator), never slid | **Approved** 2026-10-07 |

## 4. Rendering coordinate model

World millimetres (integer, canonical) → SVG millimetres with one fixed y-flip per plan (`svg.y = bounds.min_y + bounds.max_y − world.y`, road edge at the bottom) → screen through a millimetre viewBox with `xMidYMid meet`. Zoom and pan change only the viewBox; text and hairlines are sized in screen pixels; gestures convert back once and every operation carries integer world millimetres. Detail: renderer architecture document, section 2.

## 5. State model

The reducer (`lib/plan/editor.ts`) holds the last server response (`document`, `geometry`, `validation`, `editing`), and UI state only: selection (room, room side, opening), a drag preview, busy, the last problem, undo and redo stacks of `{ops, inverse}`, snap on/off, units. The plan changes only on a server answer (`committed`); a refusal (`failed`) keeps it. Viewport state lives in the canvas. Nothing else holds plan geometry.

## 6. Operation model and supported edits

| Edit | Operation | Constraint enforced where |
|---|---|---|
| Move a room side (drag, or choose a side and use arrow keys) | `MOVE_WALL` on a wall of that side (its straight run moves) | Op: perpendicular walls only, no collapse, hosted items stay on their walls; validator: everything else |
| Move a room (drag on the selected room; arrow keys) | Two `MOVE_WALL`, leading side first, one batch | Same |
| Move a door, opening or window along its wall | `MOVE_OPENING` | UI keeps the offset on the host wall; validator checks clearances and fit |
| Undo / redo | The stored inverse batch, sent as a new batch | Same pipeline; logged |

Operations are the existing CP1-11 contract (`extra="forbid"`, discriminated union, integer mm); serialisation is plain JSON (tested both sides). Order is deterministic: batches apply in sequence, and the server's inverse is the reversed list of inverses.

**Not supported yet:** add or delete a room, add, delete or resize an opening, moving a fixture by hand, renaming or retyping a room from the UI (operations exist; no UI), moving a single wall segment or node (MOVE_NODE), named versions and restore, free polygons, multi-select, generating a plan from the UI (needs the design brief, AD-03), PDF, 3D.

## 7. Validation flow

```text
gesture → ops → POST {expected_revision, ops}
  404 not a member or feature off · 403 member not owner · 409 STATE_CONFLICT no document
  409 REVISION_CONFLICT stale (current_revision) → "This plan changed meanwhile", Reload
  422 VALIDATION_ERROR malformed (schema; free coordinates are refused)
  422 PLAN_OPERATION_REJECTED {index, op, code} → readable reason per code
  422 PLAN_EDIT_INVALID {report} → "That change was not saved" + the validator's messages, offending rooms and openings outlined
  200 → new revision, document, geometry, report, inverse
```

The validator is the only judge; the browser runs no geometry rule. Nothing is stored unless the report has no errors (IC 18.7).

## 8. Open-space presentation

`PlanGeometry.open_areas` comes from the server: the unbuilt part of the wall-centreline region, split on room corners, grouped by shared edges, and labelled by where it lies (road edge, back, side, or enclosed). It is drawn as a light fill with an italic label and listed under "Open areas" with its area. No room entity is created; the HousePlan schema is unchanged.

## 9. Tests

| Suite | Result |
|---|---|
| Engine (`test_houseplan_cp3.py`, new, 26) | MOVE_WALL runs, node movement, exact inverses (body hash restored), every rejection code, collapse, openings kept on the ground, edit revision/source/hash/soft terms, determinism, validator-reported failures, batch index, batch bounds, door constrained to host, open-area classification and exact coverage on real plans |
| API (`test_houseplans_api.py`, 5 new) | Owner edits and undoes (log rows, version 1 untouched); invalid, rejected, stale and free-geometry edits change nothing; member 403, stranger 404, ops staff cannot edit and see `can_edit` false; op log append-only (UPDATE and DELETE refused by trigger); feature off → 404 |
| Schema (`test_schema.py`, 1 new case) | `house_plan_ops.reason` CHECK equals the vocabulary; migrations equal the models |
| Full API suite | 788 tests, 0 failed: 788 passed with local storage up; 787 passed and 1 skipped (`test_r2_cors`, needs the storage container) in the pre-commit run. One Checkpoint 1 test changed by design: `test_operations_are_a_closed_typed_contract` asserted MOVE_WALL refuses "until the editing checkpoint"; it now asserts the same for ADD_ROOM, which still refuses |
| Web unit (Vitest, 102 new, 117 total, 1 opt-in montage skipped) | Viewport (flip, fit, zoom anchor, letterbox round trip); render model on all 9 real plans (counts, determinism, server sizes, y-flip, door leaf and arc, window symbol, open areas, label level of detail); SVG structure on all 9 (plot, envelope, rooms, walls, openings, fixtures, open areas, dimensions, parking), determinism, labels, hit targets only when interactive, no raw colours, 2 structural snapshots; room sides from the node graph on every room; side and room moves land exactly where dragged (checked against the engine's left-normal rule); door and window kept on their wall; JSON serialisation; snapping; reducer (preview and cancel never touch the plan, commit, refusal keeps the plan, every API error mapped, undo/redo batches in order); renderer timings |
| Web e2e (Playwright, live stack, phone and desktop, axe) | New `floor-plan.spec.ts`: real generation, designs list, page, disclaimer, drawing counts equal the API, room list, checks, axe; phone read-only; desktop keyboard edits until one is accepted, stored revision and EDITED source checked, undo restores the generated body hash. **All 68 tests of the whole suite pass** when run per spec (see section 13 for the local rate-limit caveat) |
| Static | API: ruff, ruff format (342 files), mypy strict (321 files), import-linter 5/5. Web: ESLint, `tsc` strict, `check_ui_tokens` (0 raw colours), `check_contrast`, `next build` (route built) |
| CP1–CP2.2.1 | CP1 goldens unchanged; all CP2, 2.1, 2.2, 2.2.1 tests pass unchanged; zoned goldens unchanged by CP3 (no solver change) |

## 10. Visual review

Live on the local stack (desktop 1440 × 900 and phone 375 × 812) with plans the engine generated for 25x40, 30x50 two-wheeler, 40x80 two cars, 45x70 two cars, 50x60 two cars, 60x90 4BHK, 80x28 wide and 30x40 without parking; and in the montage for those plus 22x60.

| Plan | Finding |
|---|---|
| 30x50 two-wheeler | Reads as a plan: solid walls, door swings, three-line windows, fixtures, the forecourt in a light fill with the small two-wheeler bay, passage. Fixed during review: long room names overflowed small rooms; "Road" collided with the plot dimension |
| 50x60 two cars | 5.05 × 5.10 m car bay against the living room, L-shaped forecourt labelled; attached baths back to back; selection, side handles, inspector and live edits all worked |
| 60x90 4BHK | Large plan reads correctly. Fixed during review: names in the narrow bedroom wing vanished at the fitted zoom; a compact label size now shows them |
| 80x28 wide | Rear yard strip, corridor, car bay, rooms labelled; a door arc crosses the living room's area text (minor) |
| 25x40 | Clear; the kitchen counter crosses the kitchen's size text (minor) |
| No parking (30x40) | Draws without parking or open areas, as generated |
| Phone | Read-only; full-width drawing; hint to edit on a tablet or computer; the room list carries every name and size; the narrowest rooms drop their labels in the drawing |

The page reads as a conceptual plan tool: restrained tokens, no decoration, the disclaimer and "Rules not yet verified" notices always above the drawing, no compliance claim anywhere.

## 11. Performance

| Measure (development machine) | Result |
|---|---|
| Plan detail GET, largest plan (15 rooms, 47 walls, 25 openings), through Caddy | about 24 ms |
| Edit POST (apply, re-score, validate, derive geometry, store, respond) | 44–125 ms |
| Page DOMContentLoaded / load (dev server) | 256 / 349 ms |
| Render model build, largest plan (Node) | median 0.10 ms, p95 0.23 ms |
| Full SVG render, largest plan (Node SSR as a stand-in for React render) | median 7.5 ms, p95 10.1 ms |
| Drag preview step (reducer + redraw) | median 2.1 ms, p95 3.1 ms |
| Zoom / pan | a viewBox change only; not timed in a visible browser (the pane was hidden; frame timing needs a foreground window) |

Solver benchmarks are untouched and not mixed in.

## 12. Security and authorisation

Owner-only edits enforced in the service (403 otherwise), membership for reads (404 for strangers), feature flag 404, ops staff have no edit route (tested); the browser only hides tools (`can_edit`). Inputs are a closed discriminated union with `extra="forbid"`; free coordinates are refused by the schema; batches are bounded (1–50); per-session rate limit; row lock plus expected revision against concurrent edits; append-only op log by trigger; no client-provided geometry is trusted. No `dangerouslySetInnerHTML`; CSRF header from the contracts client.

## 13. Known limitations

| ID | Limitation |
|---|---|
| L-1 | Moving a side moves the whole straight line (D-2): other rooms on that line change too; a local edge move needs MOVE_NODE or graph splitting (later) |
| L-2 | Doors and windows on a shrinking wall are refused rather than slid (D-8): move them first |
| L-3 | Parking's open sides cannot be moved (no wall there); parking itself moves only with the house sides it shares |
| L-4 | Doors and windows are selectable only with a pointer (rooms and sides also by keyboard); add an openings list for full keyboard parity |
| L-5 | Validator messages are the validator's English sentences (e.g. "3002000 mm²"); translating `message_key` with formatted units is pending (HR S i18n) |
| L-6 | Labels can overlap fixtures and door arcs; on phones the narrowest rooms show no label (the room list carries them) |
| L-7 | Undo/redo history lives in the page (lost on reload); every step is still a logged revision |
| L-8 | No generation UI: plans are created through the API until the design brief (AD-03) exists; the designs page lists and opens them |
| L-9 | Single floor only (AD-04); `level` 0 rendered |
| L-10 | Local e2e: the full 68-test suite exceeds the per-IP OTP limits (60 starts per hour, 20 verifications per 10 minutes) and loads the dev server; run per spec with the local `rate_counters` cleared, as done here. Pre-existing for the suite size, not caused by CP3 |
| L-11 | The plan page and e2e need `houseplans_enabled` and the synthetic ruleset locally; the override used is not committed (`.sakha/tmp/compose.houseplans.yml`): document a supported local switch next checkpoint |
| L-12 | Zoom/pan frame timing not measured in a foreground browser |

## 14. Acceptance criteria

| Criterion | Met? | Evidence |
|---|---|---|
| A. HousePlan remains the sole source of truth | Yes | Plan changes only through typed ops on the server; reducer holds the server response; drawing and preview never written back |
| B. Renderer faithfully displays existing valid HousePlans | Yes | Nine real plans; counts equal the geometry (unit and e2e); visual review |
| C. Renderer output deterministic | Yes | Same model and markup on repeat (tests on all nine); structural snapshots |
| D. Room, door and window interactions through explicit typed operations | Yes | MOVE_WALL / MOVE_OPENING batches; live and tested |
| E. Invalid edits cannot become accepted canonical HousePlans | Yes | Validate-before-store; API test and live refusal |
| F. Backend validator remains authoritative | Yes | Unchanged validator decides every edit |
| G. CP1–CP2.2.1 engine behaviour unchanged | Yes | No solver change; all earlier tests and goldens pass |
| H. Existing backend suite passes | Yes | 788 passed; one CP1 assertion updated because MOVE_WALL now applies (section 9) |
| I. No Gemini/LLM/3D/image-generation code | Yes | None added |
| J. Works with real CP2.2.1 generated plans | Yes | Live stack generation and editing; fixtures from the engine |
| K. Clearly a conceptual floor-plan editor, not a CAD authority | Yes | Persistent disclaimer, rules-not-verified notice, no compliance claims, simple tools |

## 15. Decisions

D-1 to D-8 approved on 2026-10-07 (section 3). Still open: AD-16 (final disclaimer wording) before any production use; a production rate-limit policy for edits (D-7).

## 16. Next checkpoint: CP3.1 (editor depth and persistence), as directed 2026-10-07

1. MOVE_NODE and local edge editing (graph-level).
2. ADD_ROOM and DELETE_ROOM graph edits.
3. Opening add, delete and resize.
4. Room rename and type editing in the inspector.
5. A keyboard-accessible openings list.
6. Validation messages formatted from `message_key` with units.
7. Named versions and restore (`house_plan_versions`, REVERT_TO_VERSION as a logged batch).
8. A supported local houseplans feature switch.
9. An e2e rate-limit reset and harness.

The generation solver is not changed unless CP3.1 shows an actual engine contract problem. No Gemini, LLM editing or 3D.
