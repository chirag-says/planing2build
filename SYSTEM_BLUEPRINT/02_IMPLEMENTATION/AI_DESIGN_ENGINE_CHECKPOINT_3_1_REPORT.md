# Plan2Build: AI design engine, Checkpoint 3.1 report (editor depth and persistence)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_3_1_REPORT.md` |
| Date | 2026-10-07 |
| Basis | Chirag's Checkpoint 3.1 brief (2026-10-07) and his four answers of the same day: room edits recorded as compromises, a new MOVE_EDGE, undo of structural edits by server restore, a new room gets a door and a window; `AI_DESIGN_ENGINE_CHECKPOINT_3_REPORT.md` (D-1 to D-8); HR O–S; IC 7, 17–20 |
| Branch | `houseplans-checkpoint-1`, on top of `c9c0341` (tag `houseplans-cp3`). Checkpoint 3.1 is in the working tree, **not committed, not tagged** |
| Scope kept out | No Gemini, LLM, natural-language editing, image generation, 3D, Three.js, PDF, OR-Tools, Vastu, structural or permit logic, VPS; no solver change; no HousePlan schema change; no migration |
| Ruleset | Every plan here comes from the **SYNTHETIC / TEST ONLY** ruleset (local env only). Production stays blocked (AD-05) |
| Review | **Awaiting Chirag's review.** Final tree verified 2026-10-08: API 827 passed, web 166 passed, build and static checks pass. Nine decisions need approval (section 14) |
| Assets | `AI_DESIGN_ENGINE_CHECKPOINT_3_1_ASSETS/plan_editing_montage.html`: eight real CP2.2.1 plans as generated and after the first accepted edit of each kind, drawn by the production component |

---

## 1. Outcome

On a tablet or computer the owner now:

- moves one side of a room by itself (MOVE_EDGE, the default), or the whole straight line through the plan (MOVE_WALL, one toggle away);
- renames a room, changes its type, removes it into a neighbour that shares a whole side, or splits a new room off one of its sides (with a door from it and a window when the type needs one);
- adds a door or window on a chosen side, and sets the width of, nudges or removes any door or window, from a keyboard-reachable list;
- saves named versions and restores a version or any earlier change as a new change.

Every one of these is a typed operation that the server applies, validates and stores only when the validator passes. Undo of a structural edit is a server restore of the previous revision, rebuilt from version 1 and the operation log and checked against the logged hash. Refusals name what they concern ("The door between Living room and Puja would end up joining different rooms"). Validation messages show lengths and areas in the chosen units ("Bedroom 3 is 2.75 m across; it needs at least 3.00 m"). Room additions, removals and type changes are recorded in the plan as the owner's changes from the requirement and listed under "Changes from your requirement"; the requirement itself is never modified.

Verified on the live local stack (desktop and phone, axe): a keyboard side move stored as MOVE_EDGE and undone by restore to the generated body hash; a rename; a door picked from the list with the keyboard and nudged; a named version saved; version 1 restored as a new revision; after a reload the same head, revision and history.

## 2. Files

**Backend (API)**

| File | Change |
|---|---|
| `src/p2b/houseplans/engine/graph_edit.py` (new) | Structural edits on the planar graph: room rectangles from the node graph, `move_edge`, `add_room`, `delete_room`, and the id-preserving rebuild with `graph.build_graph` that re-hosts doors, windows and fixtures by their position on the ground |
| `src/p2b/houseplans/engine/programme.py` (new) | The owner's programme changes as compromises (added, removed, retyped), kept net; `expected_counts` and `removed_rooms` for the validator |
| `src/p2b/houseplans/engine/ops.py` | MOVE_EDGE, REVERT_TO_REVISION, REVERT_TO_VERSION; ADD_ROOM becomes `(host_room, type, side, depth_mm)`; ADD_ROOM and DELETE_ROOM apply; `apply(plan, op, ruleset)`; SET_ROOM_TYPE checked against the ruleset and recorded; `OperationRejected.entities` |
| `src/p2b/houseplans/engine/edit.py` | `apply_edit` (everything `edit` does but validate, used for replay); a batch with a structural edit is undone by REVERT_TO_REVISION; a revert must stand alone |
| `src/p2b/houseplans/engine/validate.py` | `_requirements` counts rooms against the requirement plus accepted owner changes and drops relations of rooms the owner removed. No other check changed; no code added or weakened |
| `src/p2b/houseplans/service.py` | Restore (`_restored`, `revision_state`, `_replay` in a worker thread, capped), `save_version`, `list_versions`, `list_revisions`; `_owned_plan` shared by every change; restore and version audit events |
| `src/p2b/houseplans/router.py`, `schemas.py` | `GET`/`POST …/house-plans/{id}/versions`, `GET …/house-plans/{id}/revisions`; `EditingOut` gains room types, opening sizes and wall thicknesses (`editing_block`) |
| `src/p2b/core/vocabulary.py`, `core/errors.py` | `RoomSide`, `ProgrammeChange`, three operation kinds, nine rejection codes; `PLAN_HISTORY_UNAVAILABLE` (409) |
| `scripts/local_houseplans.py` (new) | Local only: load the synthetic ruleset; clear the rate counters e2e trips |
| `scripts/review_houseplan_edits.py` (new) | Visual review steps, attempt outcomes and engine timings on the real plans |
| `scripts/export_web_plan_fixtures.py` | Fixtures carry the full editing block |
| `tests/test_houseplan_cp31.py` (new), `tests/test_houseplans_history_api.py` (new), `tests/test_houseplan_cp3.py`, `tests/test_houseplan_validate.py`, `tests/test_houseplans_api.py` | Section 9 |
| `packages/contracts/*` | Regenerated |

**Web**

| File | Change |
|---|---|
| `src/lib/plan/edit.ts` | MOVE_EDGE by default (`MoveMode`), room and opening operation builders, merge targets, default names |
| `src/lib/plan/editor.ts` | `moveMode`; rejections carry entities; `PLAN_HISTORY_UNAVAILABLE`; the three histories documented |
| `src/lib/plan/messages.ts` (new) | Validation, rejection and change texts with formatted values and names |
| `src/lib/plan/units.ts`, `types.ts` | Areas to two decimals; new contract types |
| `src/components/plan2build/plan/plan-panels.tsx` (new) | Room, side and opening panels; the openings list; changes from the requirement |
| `src/components/plan2build/plan/plan-history.tsx` (new) | Saved versions and recent changes, save and restore |
| `plan-workspace.tsx`, `plan-canvas.tsx` | The panels, the move-mode toggle, formatted messages; gestures use the move mode |
| `messages/en.json` | `Plan`: rejections (rewritten, with names), room and fixture types, validation templates, changes, move mode, room, openings, history |
| `tests/unit/plan-cp31.test.tsx`, `plan-edit-montage.test.tsx` (new); `plan-edit.test.ts`, `plan-editor.test.ts`; `tests/fixtures/houseplans/*.json` | Section 9 (fixtures: only the editing block changed; plans byte-identical) |
| `e2e/floor-plan.spec.ts` | A second scenario (section 9) |

**Local development**: `infra/local/compose.houseplans.yml` (new), root `package.json` scripts `local:up:houseplans`, `local:houseplans:ruleset`, `local:reset-rate-limits`, README section "Concept floor plans locally".

## 3. Operation contracts

All operations are members of one closed discriminated union (`extra="forbid"`); the browser sends no coordinates.

| Operation | Fields | Applies | Inverse |
|---|---|---|---|
| MOVE_EDGE | room, side (LEFT, RIGHT, FRONT, BACK), delta_mm (along +x for LEFT/RIGHT, +y for FRONT/BACK) | Moves that side and only the rooms on either side of the same line whose extent overlaps the moving span, repeated until no more join; the line jogs where the span ends | REVERT_TO_REVISION(start) |
| MOVE_WALL | wall, delta_mm | Unchanged from CP3: the wall's whole straight run ("Whole line") | MOVE_WALL(−delta) |
| ADD_ROOM | host_room, type, side, depth_mm | A slice of the host across its full width, `depth_mm` deep, on `side`; one door from the host (ruleset width and height, centred on the longest shared wall, opening into the new room); a window centred on its longest outside wall when the type needs one and the slice did not take one of the host's | REVERT_TO_REVISION(start) |
| DELETE_ROOM | room, merge_into | Only into a room sharing one whole side and enclosed alike; the openings between the two go with their wall, the removed room's fixtures go with it, its other openings now belong to `merge_into` | REVERT_TO_REVISION(start) |
| RENAME_ROOM | room, name | Unchanged | RENAME_ROOM(old) |
| SET_ROOM_TYPE | room, type | With the ruleset: the type must exist and keep the room enclosed or open as it is; the room takes the type's zone and sizes; the change is recorded | SET_ROOM_TYPE(old), exact (the record is netted) |
| ADD_OPENING, DELETE_OPENING, SET_OPENING, MOVE_OPENING | as CP1 | Add, remove, resize (the web keeps the centre with SET_OPENING + MOVE_OPENING), move along the wall | exact, as CP1 |
| REVERT_TO_REVISION | revision | The plan as it was at that revision, as a new revision; alone in its batch | REVERT_TO_REVISION(head) |
| REVERT_TO_VERSION | version | The named version's document (this plan's only), as a new revision; alone in its batch | REVERT_TO_REVISION(head) |

**Structural rebuild.** Every room is a rectangle in generated plans (slicing layouts). A structural edit changes room rectangles, then rebuilds nodes, walls and boundaries with the generator's own builder, so the result is a graph a generated plan could have. Ids survive where the geometry allows: a node keeps its id where its point survives or where it moved to; a wall keeps its id when it joins the same two nodes; new ones get the next free number. Rebuilding an unchanged plan returns it byte for byte on all eight zoned goldens (tested). Doors, windows and fixtures keep their position on the ground (D-8): each moves to the new wall holding its whole span on the same line (the line moves only for items on the moved edge) and must stand between the same rooms; otherwise the edit is refused with the item named. Nothing is slid, resized or dropped to make an edit fit.

**Rejection codes** (422 `PLAN_OPERATION_REJECTED`, `details`: index, op, code, entities): the CP3 seven plus NOT_RECTANGULAR, HOSTED_ITEM_CHANGES_ROOMS, DOOR_DOES_NOT_FIT, ROOMS_WOULD_OVERLAP, NOT_A_SLICE, ROOMS_NOT_MERGEABLE, ROOM_TYPE_NOT_ALLOWED, REVERT_NOT_ALONE, UNKNOWN_REVISION. A result that applies but breaks a rule is the validator's: 422 `PLAN_EDIT_INVALID` with the report, nothing stored.

## 4. The owner's room changes

Adding, removing or retyping a room departs from the requirement, which is never modified. Each departure is a compromise in the plan (I-P6), at most one per room, accepted by the owner by making the edit:

| change_key | params | Counts as |
|---|---|---|
| ROOM_ADDED_BY_OWNER | room, room_type | +1 of the type |
| ROOM_REMOVED_BY_OWNER | room, room_type (as the requirement gave it) | −1 of the type |
| ROOM_TYPE_CHANGED_BY_OWNER | room, from_type, to_type | −1 from, +1 to |

Records are net: retyping back deletes the record; removing an owner-added room deletes its record; retype then remove becomes one removal of the original type. Each record points at the ROOM_PRESENT constraint of its type; a type the requirement did not ask for gets a USER_EDIT ROOM_PRESENT `{"count": 0}` (id `owner_room_<type>`), dropped once nothing points at it. Rooms the solver added for circulation are outside the requirement and record nothing. The validator counts rooms against the requirement plus accepted records and skips the requirement's relations for rooms the owner removed; a change nobody recorded, an unaccepted record or any other change key is still `ROOM_COUNT_MISMATCH` (tested). Generated plans have no such records, so generation and every golden are unchanged.

## 5. History and versions

| History | Where | Lifetime | How it moves back |
|---|---|---|---|
| Undo / redo | the page's reducer | this visit | sends the server's inverse batch; a structural edit's inverse is REVERT_TO_REVISION |
| Revisions | `house_plan_ops` (append-only, CP3) | permanent | REVERT_TO_REVISION from "Recent changes" |
| Named versions | `house_plan_versions` (append-only; version 1 = generated) | permanent, immutable | REVERT_TO_VERSION from "Saved versions" |

Saving a version (`POST …/versions` {name, expected_revision}, Idempotency-Key, owner only, row lock, 100 per plan, 30 per session per 10 minutes) snapshots the server's head at the revision the editor showed, never a document from the client. Restoring never rewrites anything: it appends a revision (reason REVERT), audited as `houseplan.restored` with the target; saving is audited as `houseplan.version_saved`.

To rebuild revision n, the server starts from the latest named version at or before n (moving earlier if a later restore reaches further back), replays each logged batch with `apply_edit` in a worker thread, takes the restored state for restore rows, and checks every step against the logged body hash. A mismatch (an engine that no longer reproduces its own log) or more than 1,000 batches to replay answers 409 `PLAN_HISTORY_UNAVAILABLE` and changes nothing; a named version can still be restored.

## 6. Concurrency and security

Unchanged and extended to every new change: owner only (403), membership for reads (404 for strangers), the plan row locked, `expected_revision` checked (409 `REVISION_CONFLICT`), the log append-only by trigger. Two edits racing on one revision: exactly one stored, the other 409 (tested with concurrent requests). Versions are looked up within the plan only, so a client cannot restore another plan's version; revision targets are bounded by the head; version names reject control characters. Members and operations staff stay read-only (the panels and restore buttons appear only with `can_edit`; the server checks again). The replay cap and the worker thread keep a long history from stalling the API.

## 7. Validation messages and accessibility

The web app formats 22 validator codes from `Plan.validation` templates: `*_mm` as lengths ("3.00 m", "9′ 10″"), `*_mm2` as areas ("2.80 m²"), fixture and opening ids as names ("The Western toilet in Bath 1", "The Door between Living room and Puja"), types as words. Codes without a template show the server's message. Rejections name their entities the same way. Areas now show two decimals everywhere, room labels included.

Keyboard parity: every door and window of the selected room (or of the plan) is a button in "Doors and windows"; once selected, its width, position (two buttons) and removal are form controls; the canvas arrow keys still nudge it. Room and side panels use labelled inputs and selects; the move mode is a pressed-state button group. axe passes on the page in both e2e scenarios.

## 8. Local development

| Need | Supported way |
|---|---|
| Feature on locally | `pnpm local:up:houseplans` (the stack plus `infra/local/compose.houseplans.yml`) |
| Synthetic ruleset | `pnpm local:houseplans:ruleset` (DRAFT, marked synthetic, idempotent by content hash) |
| Run the floor plan e2e | `pnpm --filter @p2b/web test:e2e floor-plan` |
| Reset only test rate counters | `pnpm local:reset-rate-limits`: deletes the counters of six named limits (per-IP sign-in and the floor plan routes) in the local database only |

`scripts/local_houseplans.py` refuses any database other than 127.0.0.1:55432 `p2b` or `p2b_test` and refuses when `P2B_ENV` is production. Production defaults are unchanged: the feature is off, and the configuration refuses draft and synthetic rulesets in production.

## 9. Tests

| Suite | Result |
|---|---|
| Engine (`test_houseplan_cp31.py`, new, 33) | Rebuild is the identity on all eight zoned goldens; non-rectangular rooms refused; MOVE_EDGE on five plans: only rooms with a side on the moved line change, and only that side, topology canonical, every opening joins the same rooms, inverse is REVERT_TO_REVISION, untouched walls keep ids; MOVE_EDGE changes fewer rooms than MOVE_WALL on real plans; rejections (zero, unknown, collapse with the room named); HOSTED_ITEM_LEAVES_WALL occurs; ADD_ROOM on a real plan (area split, one door of ruleset width between host and new room, window, record, constraint, canonical graph, other connections untouched) and its refusals (NOT_A_SLICE, ROOM_TYPE_NOT_ALLOWED ×2, HOSTED_ITEM_CHANGES_ROOMS); DELETE_ROOM on three plans (union area, others untouched, fixtures gone, record) and its refusals; add then remove leaves no record and the original constraints; retype recorded, counted, exactly undone; the validator still catches unrecorded, unaccepted or foreign records; types the ruleset cannot give refused; retype back and forth keeps one record; openings resized about the centre, deleted, added, window on an inside wall reported; structural batch inverse and revert-alone rule; replay reproduces a logged batch byte for byte; MOVE_WALL unchanged |
| API (`test_houseplans_history_api.py`, new, 6) | Structural edit undone by restore through the log, restore of a revision reached through an earlier restore, redo, revision list and paging, audit rows, log only appended, versions untouched; versions saved, listed by members, refused to members and strangers, restored (and the result's inverse), refusals (unknown version, no movement, unknown revision, revert not alone), control characters refused, versions immutable by trigger; two racing edits store one; room removal and retype recorded, PARKING refused with the room named; a log that no longer replays is not restored and nothing is stored; the replay limit and a named version shortening it |
| API, changed | `test_houseplans_api.py`: the editing block and rejection `entities` asserted; `test_houseplan_validate.py` and `test_houseplan_cp3.py`: the never-applied ADD_ROOM shape replaced, and the "not supported" checks now assert that structural edits need the ruleset and that a revert is the service's |
| Full API suite (final working tree, 2026-10-08) | **827 passed, 0 failed, 0 skipped** in 28 min 54 s, run on the final tree with nothing else running (local storage up, so `test_r2_cors` ran). History of this result: a first full run gave 821 passed and 5 failed, all five in the new history module, because importing the session job-app fixture into a second module built a second job app that never ran the queue; fixed with one cached job app in `test_houseplans_api.py`. A second full run on the final tree gave 827 passed and 1 teardown error in `test_assurance.py` (the shared TRUNCATE hit the statement timeout while a web production build ran at the same time); that module passed alone (12/12) and the third full run, with no other load, is the result above |
| Web unit (Vitest, 49 new, 166 passed, 2 opt-in montages skipped) | MOVE_EDGE is the default on every side of every room of nine plans; room moves as two edge moves, leading side first; merge targets share a whole side and are symmetric on nine plans; add, remove, rename and retype builders, default names follow the type only when unchanged; room panel controls all labelled; a door on every side of every room opens into the room and a window carries the ruleset sill; every opening on nine plans resizes about its centre; the openings list is one button per opening with names; message formatting in metres and feet, names instead of ids, server text for unknown codes; rejection texts name entities; change texts; undo and redo of a structural edit by restore, version restore undoable, reload starts from the server head with an empty undo stack; new API errors; typed lengths to grid steps. Two CP3 tests now ask for the "line" mode explicitly and one expects the new `entities` field |
| Web e2e (Playwright, live stack, axe) | Both scenarios pass on desktop; the CP3 scenario passes on the phone and the new one is skipped there by design (editing is for tablets and computers). The CP3 scenario now exercises MOVE_EDGE and the restore-based undo |
| Static (final tree) | API: ruff format and ruff on src, tests, migrations and scripts; mypy strict on src, tests and scripts (327 files); import-linter 5/5; contracts regenerate byte-identical. Web: ESLint, `tsc` strict, `next build` (exit 0). Repo: `check_ui_tokens` (0 raw colours), `check_words` on the new prose (0), `check_tables` on this report (0) |
| CP1–CP2.2.1 | All 249 engine tests pass unchanged in behaviour; the nine exported plans are byte-identical; no solver change; `ENGINE_VERSION` unchanged |

## 10. Visual review

`scripts/review_houseplan_edits.py` tries, on each plan, every side move of ±300 mm, every interior line move of ±300 mm, every new room (utility, toilet, bedroom at their minimum width) on every side of every room, every merge, every type change and a 300 mm wider window, and keeps the first edit of each kind the validator passes. The montage shows them side by side in one frame per plan.

Accepted / attempted:

| Plan | MOVE_EDGE | MOVE_WALL | ADD_ROOM | DELETE_ROOM | SET_ROOM_TYPE | Window resize |
|---|---|---|---|---|---|---|
| 25x40 | 14/48 | 4/16 | 0/72 | 2/30 | 26/55 | 5/5 |
| 30x50 two-wheeler | 15/64 | 3/22 | 0/96 | 5/56 | 27/73 | 5/5 |
| 40x80 two cars | 14/72 | 4/28 | 0/108 | 6/72 | 35/82 | 5/7 |
| 45x70 two cars, puja | 21/104 | 7/46 | 0/156 | 9/156 | 46/118 | 6/9 |
| 50x60 two cars | 16/96 | 4/40 | 0/144 | 7/132 | 44/109 | 7/9 |
| 60x90 4BHK | 27/120 | 8/46 | 1/180 | 16/210 | 57/136 | 7/11 |
| 80x28 wide | 12/72 | 5/30 | 0/108 | 9/72 | 34/82 | 4/7 |
| 30x40 no parking | 14/48 | 5/18 | 0/72 | 3/30 | 26/54 | 4/5 |

Findings:

| Finding | Detail |
|---|---|
| Local moves are local | 30x50: moving the living room's front 300 mm changed only the living room; the same side as a whole line changed kitchen, living room and passage |
| Refusals are mostly doors and windows | About a third of side moves are refused because a door or window would leave its wall (D-8: never slid); most of the rest the validator rejects for minimum sizes, the setback line or blocked fixture space |
| A new room is almost never possible on a generated plan | 1 of 936 attempts across the eight plans (a utility split off the 60x90 dining room). Nearly every side of a generated room carries a door, a window or a fixture, so a full-width slice would make a door join different rooms (refused, HOSTED_ITEM_CHANGES_ROOMS) or take the host's only window or space (rejected by the validator). The interaction is safe and unambiguous; it is rarely useful on tight plans. See decision E-6 |
| Owner removals are allowed by design | 25x40: removing the kitchen into the dining room passes, because the removal is recorded as the owner's change. Whether some rooms should never be removable is decision E-5 |
| Type changes do not rename | The engine keeps the name; the web renames only a room that still has its old type's default name |
| Drawing | Merged and split rooms, jogged lines and moved openings draw cleanly; no new overlap beyond the CP3 minor label crossings |
| Page review | Fixed during review: an outside door read "between Living room and EXTERIOR" in the inspector (a CP3 fault); door, window and fixture names were capitalised mid-sentence; inputs read "Width (Metres)"; versions read "Change 0". Now "The main entrance of Living room", "Width (m)", "as generated" |

## 11. Performance

Engine calls the API makes, median over the eight plans (development machine, separate from solver benchmarks):

| Operation (apply, re-measure, validate) | Median | Max |
|---|---|---|
| MOVE_EDGE | 3.8 ms | 13.1 ms |
| MOVE_WALL | 3.0 ms | 8.4 ms |
| ADD_ROOM | 13.7 ms | 13.7 ms (one accepted case) |
| DELETE_ROOM | 3.3 ms | 7.4 ms |
| SET_ROOM_TYPE | 2.0 ms | 4.8 ms |
| Opening resize | 3.1 ms | 8.8 ms |
| Fixed cost of any edit | 2.8 ms | 8.2 ms |
| Geometry derivation for the response | 3.9 ms | 7.2 ms |
| Restore replay, per logged revision | 3.5 ms | 5.6 ms |

Renderer (largest plan, Node): model build median 0.08 ms; full SVG median 8.1 ms (p95 9.9); drag frame median 2.1 ms (p95 2.7), level with CP3. A restore replaying the 1,000-batch limit would take about 3.5 s in a worker thread; saving versions shortens it. No regression was found, so nothing was optimised.

## 12. Known limitations

| ID | Limitation |
|---|---|
| L-1 | ADD_ROOM slices the host across its full width and is rarely accepted on generated plans (section 10) |
| L-2 | Structural edits need rectangular rooms (all generated rooms are); renumbered walls after a split or merge get new ids, so undo of a structural edit is a restore, not an inverse operation |
| L-3 | Restoring a revision needs the log to replay exactly: an engine change that alters a past batch's result makes revisions before the next named version unrestorable (409, nothing changed); restoring named versions is unaffected. Versions are saved only by the owner |
| L-4 | DELETE_ROOM removes the removed room's fixtures and the openings between the two rooms; a fixture of the kept room on the removed wall makes it refuse; retyping does not move fixtures, so a type that does not permit them is rejected by the validator |
| L-5 | The undo stack covers one visit; after a reload, "Recent changes" and "Saved versions" are the way back |
| L-6 | `local:reset-rate-limits` and `local:houseplans:ruleset` need `uv` on the PATH (a README prerequisite); the e2e still inserts its own copy of the synthetic ruleset when none is present |
| L-7 | The full 68-test e2e suite still meets the per-IP sign-in limits in one run; `pnpm local:reset-rate-limits` between specs is the supported workaround |
| L-8 | HTTP timings were not re-measured for CP3.1; the engine share is in section 11 and CP3 measured 44–125 ms per edit end to end |

## 13. Acceptance criteria

| # | Criterion | Met? | Evidence |
|---|---|---|---|
| 1 | HousePlan is the sole source of truth | Yes | Every change is a typed operation applied on the server; the browser builds operations and renders responses |
| 2 | Local wall edits without unnecessary whole-run resizing | Yes | MOVE_EDGE moves only what must move (tests: only rooms on the line, only that side; fewer rooms than MOVE_WALL) |
| 3 | ADD/DELETE_ROOM preserve topology | Yes | Canonical rebuild checked after every structural test edit; connections preserved; no orphan nodes or walls |
| 4 | Openings safe | Yes | Re-hosted by position, never slid; refused with the item named; resize keeps the centre; validator judges fit |
| 5 | Invalid rejected before storage | Yes | Validate-before-store for edits and restores (API tests) |
| 6 | Named history persistent and auditable | Yes | `house_plan_versions` append-only, audited save and restore |
| 7 | Restore creates new state without modifying history | Yes | Restore appends a revision; log and versions unchanged (API tests) |
| 8 | Undo server-op based | Yes | Inverse batches from the server; structural undo is REVERT_TO_REVISION |
| 9 | Concurrency | Yes | Two racing edits: one stored, one 409 |
| 10 | Keyboard openings | Yes | Openings list, opening panel; e2e selects a door with the keyboard; axe passes |
| 11 | Readable, unit-formatted errors | Yes | 22 templates, metres and feet, names instead of ids |
| 12 | CP3 tests green | Yes | Four CP3 tests adapted for the new contract (section 9), none weakened |
| 13 | CP2.2.1 engine unchanged | Yes | 249 engine tests, byte-identical exported plans, no solver change |
| 14 | No Gemini, LLM, 3D or solver changes | Yes | None added |
| 15 | Full backend, web, static and build pass | Yes | Final tree: API 827/827, web unit 166 passed (2 opt-in skipped), e2e 3 passed (1 skipped by design), static checks and build pass (section 9) |
| 16 | Real plans edited | Yes | Eight real plans in the review; live stack edits |

## 14. Decisions needing approval

| ID | Decision | Recommendation |
|---|---|---|
| E-1 | ADD_ROOM's contract is `(host_room, type, side, depth_mm)` instead of the never-applied `(x0, y0, x1, y1)`, so the browser sends no coordinates | Approve |
| E-2 | Owner changes recorded as described in section 4 (ids `owner_change_<n>`, `owner_room_<type>` constraints with count 0, records kept net) | Approve |
| E-3 | The validator's programme check counts accepted owner changes and skips relations of removed rooms; nothing else in the validator changed | Approve |
| E-4 | Restore by replay with a hash check, a 1,000-batch cap and 409 `PLAN_HISTORY_UNAVAILABLE`. The alternative is a document snapshot per revision (a migration and more storage) | Approve replay now; revisit if engine changes make old logs unreplayable |
| E-5 | Any room can be removed or retyped as a recorded owner change, including the kitchen or the last bathroom | Decide whether some rooms must stay (for example a kitchen and one bathroom); if so, add a refusal code |
| E-6 | ADD_ROOM as a full-width slice is safe but rarely accepted on generated plans | For CP3.2: add a room into an open area against an outside wall (yards and courts), and say before the attempt which doors stand in the way |
| E-7 | Areas show two decimals everywhere ("12.58 m²"), as the brief's example | Approve |
| E-8 | 100 named versions per plan; 30 saves per session per 10 minutes | Approve for development; set production limits with D-7 |
| E-9 | A room keeps whether it is enclosed or open: parking cannot be retyped to a room or back | Approve |

## 15. Next checkpoint

Not started. Candidates, for Chirag to choose: E-5 and E-6 above; a room added into open areas; production limits for edits and versions (D-7, E-8); AD-16 disclaimer wording before any production use. No Gemini, LLM editing or 3D until directed.
