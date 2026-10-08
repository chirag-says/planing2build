# Plan2Build: AI design engine, Checkpoint 3 discovery (2D renderer and editor foundation)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_3_DISCOVERY.md` |
| Date | 2026-10-07 |
| Basis | Chirag's Checkpoint 3 brief (2026-10-07); Source of Truth and approved blueprint as listed below |
| Outcome | **No major architectural conflict.** The approved blueprint already describes the pipeline the brief asks for. Five points need Chirag's decision (section 6); implementation proceeds on the stated defaults, each reversible |

Abbreviations: HR = `AI_DESIGN_ENGINE_HAIRLINE_READINESS.md` (approved for implementation preparation; section 0 records decisions, sections A–Y are recommendations), IC = `IMPLEMENTATION_CONTRACT.md`, UI = `UI_DESIGN_SYSTEM.md`, CP1 = `AI_DESIGN_ENGINE_CHECKPOINT_1.md`.

---

## 1. Source of Truth and decisions that bind this checkpoint

| Topic | Binding statement | Where |
|---|---|---|
| HousePlan is the only source of truth | "SVG, PDF, 3D and images are derived from it and never written back" | `engine/model.py` docstring; PD-28 (IHB_FLOW 32); ADR-025 |
| Who edits | AD-12 (decided): owner views and edits; project members view; operations read only. 404 for a non-member or when the flag is off, 403 for a member who is not the owner | HR:52; CP1:228; DOMAIN_ARCHITECTURE:345 |
| Mobile vs desktop | AD-14 (decided): mobile views the plan, room list and validation issues; desktop and tablet edit | HR:54; IHB:4326 |
| Geometry is derived once, in Python | `PlanGeometry` is produced by the backend `derive` step; "the renderer draws only PlanGeometry … computes no areas, no wall outlines and no validity"; "No geometry rule runs in the browser" | HR:232, 663, 795; CP1:430 |
| Edits are server-side typed operations | `POST …/ops {expected_revision, ops[]}` (≤ 50, discriminated union, `extra="forbid"`); returns revision, geometry, report, inverse; 409 on a stale revision; 422 when an operation cannot apply | HR:762; HR O.1 |
| Revisions vs versions | An operation batch is a new revision appended to `house_plan_ops`; the head is overwritten under optimistic locking. `house_plan_versions` are named immutable snapshots (version 1 = generated) | HR:746–751; ADR-025:56; DATA_ARCHITECTURE:512 |
| Never present an unvalidated plan | IC 18.7: "never presented, referenced or exported unless the independent validator reports no errors" | IC:197 |
| Frontend rules | Server components fetch with the cookie; client components only where interaction needs them; no string literals in JSX; no auth logic in the client; no client state library beyond React and SWR | IC 19.2–19.6 |
| Accessibility | WCAG 2.2 AA; 44 px targets; usable at 360 px; the canvas needs a text alternative (room list, issues list) and keyboard selection/nudging | IC 20; HR:798 |
| Design system | shadcn/ui (radix-vega), Tailwind 4, Lucide; tokens only, no raw colours; no decoration; light theme only; no separate mobile interface | UI:8–44, 231–239 |
| Claims | No structural, statutory, permit, construction or Vastu compliance claim anywhere; walls carry `structural_role: "UNASSESSED"` | CP2:416; HR:254, 893 |
| Disclaimer | **AD-16 pending.** Draft: "Concept floor plan. Not a construction, structural or approval drawing. A qualified architect and structural engineer must prepare and check the drawings you build from." | HR:56, 896 |
| Feature flag | `houseplans_enabled` (default off); every route answers 404 when off | CP1:128, 222; `core/config.py` |
| Workspace route | `/projects/{id}/designs/plans/{planId}`, outside the dashboard layout for full width; designs page gains a "Your floor plan" section | HR:790–793 |
| Older source | `SOURCE_OF_TRUTH/Plan2Build_MVP_Build_Plan.docx` lists plan generation as out of scope; PD-28 supersedes it (IHB:4290) | — |

## 2. Backend as built

| Item | Finding |
|---|---|
| API | `GET/POST /projects/{id}/house-plans`, `GET /projects/{id}/house-plans/{plan_id}` (owner generates, members read); ops staff `GET` only (`ops_router.py`). No edit endpoint |
| Detail response | `HousePlanDetailOut`: the canonical `document`, the derived `geometry: PlanGeometry`, `validation: ValidationReport`, `quality`, `intent`, state. Head revision number not exposed |
| Storage | `house_plans` (head document, `head_revision_no`, head validity and report, optimistic `version`; guard trigger allows only listed columns to change); `house_plan_versions` (append-only; version 1 written by generation). No `house_plan_ops` |
| Typed operations | `engine/ops.py` (CP1-11): `apply(plan, op) → (plan, inverse)` for MOVE_OPENING, SET_OPENING, ADD/DELETE_OPENING, MOVE/ADD/DELETE_FIXTURE, RENAME_ROOM, SET_ROOM_TYPE. **MOVE_WALL, ADD_ROOM, DELETE_ROOM are defined and refuse to apply** "until the editing checkpoint". Inverses make undo exact |
| Validator | `validate(document, ruleset, intent=…)` → `ValidationReport` with 39 codes; every issue has entity references and a readable message; authority unchanged |
| PlanGeometry | `derive.plan_geometry`: plot and envelope polygons; rooms (polygon, clear polygon, clear w/d, carpet area, label point); walls (outline polygons with openings cut out, pieces for 3D); openings (jambs, door swing); fixtures (footprint, clearance); dimension chains (plot, envelope, room clear). `geometry_version` 1.0.0. No open-area information |
| Plan frame | Integer mm; origin at the front-left plot corner; +x along the road; +y away from the road; polygons counter-clockwise |
| Errors | One envelope `{error: {code, message, details, request_id}}`; typed `AppError` classes |

## 3. Web app as built

| Item | Finding |
|---|---|
| Stack | Next 16.3.8 App Router, React 19.2, TypeScript strict; `AGENTS.md`: read `node_modules/next/dist/docs/` first (breaking changes, e.g. middleware is `src/proxy.ts`) |
| Hosts | `src/proxy.ts` rewrites by host to `src/app/{ihb,pro,ops}` |
| Project area | `src/app/ihb/projects/[projectId]/(dashboard)/…` with a hard-coded nav; `requirement/` sits outside the group for full width |
| Data | Server components: `serverApi()` (cookie forwarded). Client: `browserApi` (openapi-fetch from `@p2b/contracts`, CSRF header), `Idempotency-Key` per action, then `router.refresh()`. No state library; no server actions |
| Contracts | `packages/contracts`: generated `schema.d.ts` (HousePlan, PlanGeometry, ValidationReport, …), `vocabulary.ts`; regenerate with `pnpm contracts` |
| Design system | shadcn components in `src/components/ui` (no tooltip, tabs, toggle group, slider or popover yet); tokens in `globals.css` (oklch, light only); lucide icons; app components in `src/components/plan2build` |
| Drawing code | None (only a Leaflet plot map). No HousePlan UI at all |
| Tests | Vitest node-only (`tests/unit/**/*.test.ts`, 15 tests); Playwright e2e against the live stack on Pixel 7 and desktop with axe (13 specs) |
| i18n | `getTranslator` over `messages/en.json` |
| Flags | No flag system in the web app; a 404 from the plans list means the feature is off |

## 4. How the brief maps onto the blueprint

| Brief | Blueprint | Resolution |
|---|---|---|
| "HousePlan → geometry projection → render model → SVG" | Renderer draws server `PlanGeometry`; no geometry rule in the browser | The geometry projection is `PlanGeometry` (Python, tested, shared with 3D/PDF later). The browser builds only a presentation render model (layers, label level of detail, transforms) |
| Typed operations, validation, rerender | HR O.1 and R.3 `POST …/ops` | Implement as specified |
| "Prefer immutable/version-aware updates"; "no editor-specific entity" | Revisions in `house_plan_ops` (planned in ADR-025 and DATA_ARCHITECTURE for this checkpoint), head under optimistic locking | Add `house_plan_ops` (migration 0020, additive, append-only). It is the approved operation log, not an editor convenience |
| Reject invalid edits | IC 18.7 forbids presenting an unvalidated plan; HR:562 (recommendation) allowed saving an INVALID working revision | Reject: nothing is stored unless the validator passes (decision D-1) |
| Room move / resize | O.4 MOVE_WALL: "moves a wall perpendicular to itself; its nodes move; attached walls stretch" | MOVE_WALL moves the wall's straight run (decision D-2); resize = one MOVE_WALL; move = two in one batch |
| Door/window along host wall | MOVE_OPENING exists | Use as is |
| Open areas without fake rooms | Renderer must not compute geometry | Add derived `open_areas` to `PlanGeometry` (decision D-3) |
| Disclaimer | AD-16 pending | Show the HR draft through i18n, marked pending (decision D-4) |
| Undo/redo | Client stack of server inverses (HR O.3) | Inverses returned by the endpoint; a simple linear client stack |
| Snapping | Grid from the ruleset, nodes, centrelines, alignment | Snap in world mm to the ruleset grid and existing wall lines; `grid_mm` exposed read-only in the detail response |
| Route | `/projects/{id}/designs/plans/{planId}` outside the dashboard layout | As specified |

## 5. Items out of scope for this checkpoint (from the blueprint's R.3 / O.4)

ADD_ROOM, DELETE_ROOM, MOVE_NODE, REVERT_TO_VERSION, named versions (`…/versions`, restore, reference, PDF), generation UI and the design brief (AD-03 pending), 3D (ADR-026), ops staff UI. Their contracts stay as they are.

## 6. Decisions (all defaults approved by Chirag on 2026-10-07; see the CP3 report section 3)

| ID | Question | Default used | Why |
|---|---|---|---|
| D-1 | Invalid edits: reject, or store as an INVALID working revision (HR:562)? | Reject; nothing stored; the report is returned to the editor | IC 18.7 and the CP3 brief ("Invalid edits cannot become accepted canonical HousePlans") |
| D-2 | MOVE_WALL scope: one wall segment, or its straight run? | The straight run: the wall and every collinear wall joined to it through nodes on the same line move together; perpendicular walls stretch | Moving one segment of a straight line would bend its collinear neighbours (non-orthogonal walls the validator rejects). The run is the slicing cut the engine generated. Consequence: resizing one room also resizes the other rooms along the same line, which the preview shows |
| D-3 | Open areas | Derived `PlanGeometry.open_areas` (geometry_version 1.1.0): unbuilt cells of the wall-centreline region, grouped and classified FORECOURT / SIDE_YARD / REAR_YARD / COURT / OPEN_AREA by which envelope edges they touch | No new canonical entity; computed in Python once, as HR requires; presentation only (CP2.2.1 L-2) |
| D-4 | Disclaimer wording | HR draft first two sentences, persistent on the plan page, flagged pending AD-16 | AD-16 is pending; the brief gives the same wording |
| D-5 | Prerequisites | Proceed although CP2–CP2.2.1 are uncommitted and the CP2.1 report placed the editor after the VPS gate | Chirag's CP3 instruction supersedes the earlier sequencing; recommend committing CP2.x before CP3 is committed |
