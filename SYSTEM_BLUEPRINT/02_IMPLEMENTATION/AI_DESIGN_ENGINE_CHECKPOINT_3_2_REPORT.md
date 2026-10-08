# Plan2Build: AI design engine, Checkpoint 3.2 report (open-area room insertion)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_3_2_REPORT.md` |
| Date | 2026-10-08 (overnight run under Chirag's standing instructions) |
| Basis | Chirag's overnight brief of 2026-10-08, sections 4 to 10 (decision E-6 of the CP3.1 report); `AI_DESIGN_ENGINE_CHECKPOINT_3_1_REPORT.md` |
| Branch | `houseplans-checkpoint-1`, on top of `4ec4323` (tag `houseplans-cp3.1`) |
| Scope kept out | No free polygons, node editing, solver change, new topology family, 3D, Gemini, image generation, PDF or VPS work; no HousePlan schema change; no migration; validator unchanged |
| Ruleset | Every plan here comes from the **SYNTHETIC / TEST ONLY** ruleset (local env only). Production stays blocked (AD-05) |
| Assets | `AI_DESIGN_ENGINE_CHECKPOINT_3_2_ASSETS/open_area_insertion_montage.html`: eight real CP2.2.1 plans as generated and with the first accepted room of up to four types added in open space, drawn by the production component |

---

## 1. Scope and outcome

CP3.1's ADD_ROOM (a full-width slice of an existing room) was safe but accepted only once in 936 attempts on generated plans. CP3.2 adds the strategy Chirag directed: a room added **in open space against an outside wall** of the house.

On a tablet or computer the owner selects an open area (forecourt, side yard, rear yard or court) in "Open areas". The panel then:

- lists the outside walls that face that area, with how deep and how long the free space is;
- takes a room type and a size (depth from the wall, length along it, placed at the start or end of the wall);
- explains before anything is sent why a size cannot fit ("This rear yard is 2.10 m deep here, but a bedroom needs at least 2.80 m.");
- draws the room on the plan as a preview, which is UI only.

"Add room" sends one typed ADD_ROOM_OUTSIDE. The server checks the placement again, rebuilds the wall graph, adds a door from the room it stands against and a window when the type needs one, re-hosts every door, window and fixture, records the owner's change, and stores the result only when the validator passes. The open areas are derived again from the new plan; no open-space entity is ever stored.

On the eight review plans, 230 of 419 attempts were accepted. Every accepted result passed independent checks: existing rooms unchanged, no overlap, the canonical graph, exactly one door from the host, a deterministic body and the open area reduced by exactly the room's footprint.

## 2. Architecture

```
derived on read (never stored)              typed operation (server)
PlanGeometry.open_areas  ─┐                 ADD_ROOM_OUTSIDE(host_room, type, side,
insertion_slots(plan) ────┼─> editor panel ─>  offset_mm, length_mm, depth_mm)
room_types (min sizes) ───┘   (fit check,       │ placement checks (outside wall, buildable
                               preview)         │ area, no overlap, type allowed)
                                                │ graph rebuild + re-hosting (CP3.1 machinery)
                                                │ door from host, window if needed, record
                                                ▼
                                       validator → store or reject → open areas derived again
```

- **Slots** (`engine/insertion.py`): a stretch of an enclosed room's outside wall with buildable, open space in front of it. No other room meets the wall there, no door or window sits there (the jamb clearance stays free on both sides), no fixture stands against it, and it is long enough for a door. Its depth is the distance to the buildable region's edge (envelope inset by half an outside wall, the same region the open areas use) or to the nearest room in front. Where the depth varies along a wall, each stretch is offered at every depth its whole length allows. Slots carry the facing open area and the wall allowances that turn centreline sizes into clear sizes. They are suggestions, never permissions.
- **ADD_ROOM_OUTSIDE** (`graph_edit.add_room_outside`): the rectangle `depth_mm` beyond the host's side, `length_mm` long from `offset_mm` along it. Refusals happen before anything applies:
  - ROOM_TYPE_NOT_ALLOWED: an open or unknown type;
  - NOT_ON_OUTSIDE_WALL: a span past the side's end, another room meeting the side, or an open host;
  - OUTSIDE_BUILDABLE_AREA;
  - ROOMS_WOULD_OVERLAP.

  The CP3.1 rebuild then keeps every door, window and fixture on the ground or refuses (HOSTED_ITEM_LEAVES_WALL or HOSTED_ITEM_CHANGES_ROOMS, the item named). DOOR_DOES_NOT_FIT applies when the shared wall cannot hold a door. The door and window placement is the code CP3.1's ADD_ROOM uses, refactored into `_connect`.
- The inverse is REVERT_TO_REVISION, as for every structural edit; undo and restore work unchanged.

## 3. Files

| File | Change |
|---|---|
| `apps/api/src/p2b/houseplans/engine/insertion.py` (new) | Insertion slots |
| `apps/api/src/p2b/houseplans/engine/graph_edit.py` | `add_room_outside`, `buildable_region`, `side_line`, `outside_rect`, `touching`; `_new_room` and `_connect` shared with ADD_ROOM (behaviour unchanged, CP3.1 tests green) |
| `apps/api/src/p2b/houseplans/engine/ops.py` | `AddRoomOutside` in the closed union and STRUCTURAL |
| `apps/api/src/p2b/core/vocabulary.py` | `PlanOpKind.ADD_ROOM_OUTSIDE`; `NOT_ON_OUTSIDE_WALL`, `OUTSIDE_BUILDABLE_AREA` |
| `apps/api/src/p2b/houseplans/schemas.py`, `router.py` | `InsertionSlotOut`; `EditingOut.insertion_slots` (owner only: empty for members and staff); `RoomTypeOut.min_area_mm2` |
| `apps/api/scripts/export_web_plan_fixtures.py` | Fixtures carry the slots |
| `apps/api/scripts/review_houseplan_insertions.py` (new) | The review, integrity checks and timings of section 7 |
| `apps/api/tests/test_houseplan_cp32.py` (new), `test_houseplans_cp32_api.py` (new) | Section 6 |
| `apps/web/src/lib/plan/insert.ts` (new) | Smallest fitting size, fit problems with numbers, the operation, the preview rectangle, slots facing an area |
| `apps/web/src/lib/plan/editor.ts`, `types.ts` | `preview` (UI only), the `area` selection |
| `apps/web/src/components/plan2build/plan/plan-panels.tsx` | `OpenAreaPanel` |
| `apps/web/src/components/plan2build/plan/plan-workspace.tsx`, `plan-canvas.tsx` | Open areas selectable and marked "A room can be added here" or not; the preview drawn on the plan |
| `apps/web/messages/en.json` | `Plan.insert` |
| `apps/web/tests/unit/plan-cp32.test.tsx` (new), `plan-edit-montage.test.tsx`, `e2e/floor-plan.spec.ts`, `tests/fixtures/houseplans/*.json` | Section 6 (fixtures: only the editing block changed; plans byte-identical) |
| `packages/contracts/*` | Regenerated |

## 4. Open-space types

The derived kinds stay as CP3 defined them: FORECOURT, SIDE_YARD, REAR_YARD, COURT. The brief's OPEN_AREA is not a separate kind in PlanGeometry 1.1.0; every unbuilt part of the buildable region is one of these four, so no kind was added. A room added in an area becomes a canonical room; what remains is derived again on read and may be classified differently (for example, a utility splitting the 60x90 rear yard leaves a strip now labelled "Side yard"). No placeholder or garden entity is created.

## 5. Security and integrity

Owner only (403 for members, 404 for strangers, as every edit); slots are computed by the server from the stored document and offered to the owner only. The browser sends a position along a known side, never coordinates; the server checks it again and the validator judges the result. The plan row lock, expected revision, append-only log, audit and restore are unchanged.

## 6. Tests

| Suite | Result |
|---|---|
| Engine (`test_houseplan_cp32.py`, new, 20) | Slots on eight plans are deterministic, inside the buildable area and of door length; the whole slot at full depth never fails placement (only re-hosting may refuse it) and 1 mm deeper is refused (outside the area or overlapping); the plan without open space offers none; on seven plans a room is added and checked: existing rooms unchanged, no overlap, canonical graph, one door from the host, window when needed, old openings unchanged, owner record, REVERT inverse, deterministic body, open area reduced by the footprint; at least 20 accepted across the plans; refusals with codes (open and unknown types, span past the side, a side another room meets, outside the area, open host, no ruleset); a room too small is the validator's to reject; a shared wall too short for a door |
| API (`test_houseplans_cp32_api.py`, new, 2) | Slots and `min_area_mm2` offered to the owner; a room added through `/ops`, valid, recorded, open area smaller; undo restores the generated body; outside the area refused with its code and nothing stored; members see no slots and get 403 |
| Full API suite | **853 passed, 0 failed, 0 skipped** in 31 min 50 s on the final CP3.2 tree (831 from CP3.1 plus 22 new) |
| Web unit (Vitest, 13 new, 179 passed, 2 opt-in montages skipped) | Every slot of nine plans turned into a room that fits it, standing outside the host's wall; reasons with numbers for too shallow, too narrow, too small, too deep, too long; no slot on the plan without open space; the panel labels every control and offers each facing wall; the preview never changes the plan and is dropped on a new selection or a stored change |
| Web e2e (live stack, axe; 4 passed, 2 phone skips by design) | New scenario: an open area marked "A room can be added here", a bedroom explained as not fitting with the Add button disabled, a utility previewed (drawn, nothing sent), added against the first wall that takes it, recorded under "Changes from your requirement", axe clean, undone to the generated body. All earlier floor-plan scenarios pass |
| Static | API: ruff format and ruff, mypy strict (331 files), import-linter 5/5, contracts regenerated. Web: ESLint, `tsc` strict, `next build`. Repo: `check_ui_tokens` 0, `check_words` 0 |
| CP2.2.1 | Engine tests inside the full suite; the nine exported plans byte-identical after re-export; no solver change |

## 7. Benchmark and visual review

Every slot of the eight review plans was tried with every enclosed room type at its smallest size and at the slot's full size:

| Plan | Slots | Attempts | Accepted | Validator rejected | Refused before applying |
|---|---|---|---|---|---|
| 25x40 | 2 | 24 | 12 | 12 | 0 |
| 30x50 two-wheeler | 4 | 51 | 26 | 15 | 10 (HOSTED_ITEM_CHANGES_ROOMS) |
| 40x80 two cars | 2 | 31 | 14 | 7 | 10 (HOSTED_ITEM_CHANGES_ROOMS) |
| 45x70 two cars, puja | 5 | 65 | 27 | 28 | 10 (HOSTED_ITEM_CHANGES_ROOMS) |
| 50x60 two cars | 4 | 68 | 53 | 5 | 10 (HOSTED_ITEM_CHANGES_ROOMS) |
| 60x90 4BHK | 11 | 167 | 92 | 42 | 23 (HOSTED_ITEM_CHANGES_ROOMS), 10 (HOSTED_ITEM_LEAVES_WALL) |
| 80x28 wide | 1 | 13 | 6 | 7 | 0 |
| 30x40 no parking | 0 | 0 | 0 | 0 | 0 (no open space against a wall) |
| **Total** | **29** | **419** | **230** | **116** | **73** |

The validator's reasons for the 116 rejections (a rejection can carry several): ROOM_BELOW_MIN_SHORT_SIDE 110, ROOM_BELOW_MIN_AREA 50, PASSAGE_TOO_NARROW 2. They come from the full-slot attempts in slots too small for the type (the script tries the full slot whatever its size); the editor's fit check stops those before they are sent.

Refusals before applying are rooms whose end walls would cover a neighbour's window or door, or split a neighbour's wall under an opening (the slot derivation checks the host's wall, not the neighbours'); the server names the item. Every accepted result passed the script's integrity checks (section 1).

Visual review (montage, and the live page): rooms attach cleanly to outside walls in forecourts, side yards, rear yards and courts; doors open from the host; open areas re-derive and relabel; no new label collisions beyond CP3's minor ones. A room at the slot's full depth can reach far into a yard (the 60x90 utility at 3.65 m); that is the owner's choice and the preview shows it before adding.

## 8. Performance

| Measure (development machine) | Median | Max |
|---|---|---|
| Slot derivation per plan (added to the detail response for the owner) | 1.2 ms | 3.3 ms |
| ADD_ROOM_OUTSIDE edit (apply, re-measure, validate), 419 attempts | 6.7 ms | 18.0 ms |

Renderer cost is unchanged (the preview is one rectangle). No optimisation was needed.

## 9. Known limitations

| ID | Limitation |
|---|---|
| L-1 | A new room may still be refused when its end walls meet a neighbour's window or door (73 of 419 attempts); the reason names the item, and choosing the other end of the wall or a shorter length usually avoids it |
| L-2 | One room per operation, rectangular, against one wall of one room; rooms spanning several rooms' walls are not offered |
| L-3 | Slot depth is conservative where the space in front varies; the deeper part of a wall is offered as its own shorter slot |
| L-4 | Sizes are entered as centreline lengths with a note that the inside is slightly smaller; the fit check and messages use clear sizes |
| L-5 | Production rate limits for edits remain the development values (D-7); no placeholder configuration was added in CP3.2 |

## 10. Decisions taken under the overnight instructions

| ID | Decision |
|---|---|
| F-1 | A new operation, ADD_ROOM_OUTSIDE, rather than a variant of ADD_ROOM: the two have different preconditions and refusals, and CP3.1's contract stays as approved |
| F-2 | The browser sends a position along a known side of a known room (offset, length, depth), as openings already do; no free coordinates |
| F-3 | Slots are derived on read and offered to the owner only; they never authorise anything |
| F-4 | Open-space kinds stay the four CP3 derives; no OPEN_AREA kind was added |

## 11. Acceptance criteria

| Criterion | Met? | Evidence |
|---|---|---|
| Open-area room insertion works for valid cases | Yes | 230 accepted on seven plans; engine, API and e2e tests |
| Invalid insertions are safely rejected | Yes | Typed refusals before applying; validator rejections never stored |
| Existing CP3.1 behaviour intact | Yes | CP3.1 engine, API, web and e2e tests pass unchanged |
| HousePlan remains authoritative | Yes | Slots and preview are derived or UI-only; only the server's answer changes the plan |
| CP2.2.1 generation byte-identical | Yes | Exported plans identical; engine goldens in the suite |
| All existing tests remain green; all new tests pass | Yes | API 853/853; web 179 passed; floor-plan e2e 4 passed, 2 skipped by design (editing on phones) |
| Real plans visually reviewed | Yes | Section 7, montage |
| Frontend, build and static checks pass | Yes | Section 6 |
| Report exists; commit and tag created | Yes | This report; section 12 |

## 12. Verdict, commit and tag

**Accepted for commit**: every gate above passed on the final tree. Commit `AI design engine Checkpoint 3.2: open-area room insertion`, tag `houseplans-cp3.2`; the commit hash is in `AI_DESIGN_ENGINE_OVERNIGHT_RUN_2026-10-08.md` (a report cannot name the commit that contains it). Next: CP4, structured AI intent and conversational editing.
