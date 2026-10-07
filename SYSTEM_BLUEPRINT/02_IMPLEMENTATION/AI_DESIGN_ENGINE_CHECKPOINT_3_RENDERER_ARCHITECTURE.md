# Plan2Build: AI design engine, Checkpoint 3 renderer and editor architecture

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_3_RENDERER_ARCHITECTURE.md` |
| Date | 2026-10-07 |
| Basis | `AI_DESIGN_ENGINE_CHECKPOINT_3_DISCOVERY.md`; HR sections O, P, R, S (`AI_DESIGN_ENGINE_HAIRLINE_READINESS.md`); IC 7, 17–20; `UI_DESIGN_SYSTEM.md` |

## 1. One model, three representations

```text
HousePlan (canonical document, integer mm)            ← the only thing ever stored as the plan
   │  server: derive.plan_geometry (Python, tested)
   ▼
PlanGeometry 1.1.0 (derived on every read, never stored, never accepted as input)
   │  browser: lib/plan/render-model.ts (presentation projection only)
   ▼
RenderModel (SVG points, y-flipped)  →  PlanDrawing (SVG)  →  screen
```

| Layer | Where | Owns | Never does |
|---|---|---|---|
| HousePlan | `house_plans.head_document` | Rooms, walls, nodes, openings, fixtures, constraints | — |
| Typed operations | `engine/ops.py`, `engine/edit.py` | The only way a stored plan changes | Repair, adjust or "fix" an edit |
| Validator | `engine/validate.py` (39 codes, unchanged) | Whether a plan may be stored or shown | — |
| PlanGeometry | `engine/derive.py` | Wall outlines with openings cut, door swings, clear sizes, areas, dimension chains, open areas | Get stored or written back |
| Render model | `apps/web/src/lib/plan/render-model.ts` | SVG coordinates (y flip), primitives, label level of detail | Compute an area, a size, a wall or a validity |
| Drawing | `components/plan2build/plan/plan-drawing.tsx` | Tokens, layers, symbols, hit targets | Hold state |
| Editor state | `lib/plan/editor.ts` (one reducer per page) | Selection, drag preview, busy, problem, undo/redo stacks, snap, units | Hold a second plan model |

## 2. Coordinates

| Space | Units | Origin and axes |
|---|---|---|
| World (canonical) | integer mm | Front-left plot corner on the road edge; +x along the road; +y away from it |
| SVG | mm (floats only for zoom) | `svg.y = flip − world.y`, `flip = bounds.min_y + bounds.max_y`, fixed per plan, so the road edge is at the bottom |
| Screen | CSS px | The SVG laid out with `preserveAspectRatio="xMidYMid meet"` in a container |

- The viewBox is in mm; zoom and pan change only the viewBox (`lib/plan/viewport.ts`: `fitViewBox`, `zoomViewBox` about an anchor, `panViewBox`, `screenToSvg`/`svgToScreen` with letterboxing).
- Text and hairlines are sized in screen pixels: font size = px ÷ (px per mm); strokes use `vector-effect: non-scaling-stroke`.
- Gestures convert screen → SVG → world once; every operation carries integer world millimetres. Nothing in screen or SVG space is sent or stored.

## 3. Rendering

- Layers, bottom to top: site (plot boundary, setback envelope, road caption), open areas, rooms (zone fills), fixtures, walls (server outlines), openings (doors: jambs, leaf, dashed swing; windows: jambs, both faces, glazing), plot dimensions, labels, selection, preview, hit targets.
- Colours are shadcn tokens only (`fill-secondary`, `fill-info-muted`, `stroke-ring`, `stroke-destructive`, …); `tools/check_ui_tokens.py` reports none raw.
- Labels: full (name, clear size, area), name, compact name, or none, chosen from the room's on-screen box and the name's length, so labels simplify as the plan zooms out and never spill over walls.
- Open areas: `PlanGeometry.open_areas`, computed by the server from the unbuilt part of the wall-centreline region and classified FORECOURT / SIDE_YARD / REAR_YARD / COURT. They are labels, never rooms.
- Text alternative: the room list (name, clear size, area), open areas and the checks list are complete without the drawing (HR:798).

## 4. Editing

```text
pointer or key gesture
  → preview overlay (UI state only, never sent)
  → release: typed operations (MOVE_WALL, MOVE_OPENING) in integer mm
  → POST /projects/{p}/house-plans/{id}/ops {expected_revision, ops}
  → server: owner check → row lock → revision check → apply batch (whole or nothing)
            → re-measure soft terms → validate → store only if valid (IC 18.7)
            → append house_plan_ops → derive PlanGeometry
  → 200 {document, geometry, validation, editing, inverse} replaces the plan in the reducer
  → or 409 REVISION_CONFLICT / 422 PLAN_OPERATION_REJECTED / 422 PLAN_EDIT_INVALID (report)
```

| Gesture | Operation(s) |
|---|---|
| Drag a room side, or choose a side and press an arrow key | One `MOVE_WALL` on a wall of that side. The engine moves the wall's straight run (decision D-2), so every room along that line changes; the preview shows the new line |
| Drag a selected room (axis chosen by the first movement), or arrow keys | Two `MOVE_WALL` in one batch, the leading side first |
| Drag a selected door or window, or arrow keys | `MOVE_OPENING`; the offset is projected onto the host wall and kept within it, so an opening cannot leave its wall |
| Escape | Drops the gesture (then the selection); nothing was sent |
| Ctrl/⌘+Z, Ctrl/⌘+Shift+Z, Undo/Redo buttons | The top batch's server-computed inverse, sent as a new batch |

Snapping works in world mm: onto existing wall lines, the setback envelope and the plot boundary within 10 screen px, otherwise in whole steps of the ruleset grid (`editing.grid_mm`); Alt or the Snap toggle moves in whole millimetres. A side never snaps to the line it starts on.

Undo and redo: each committed batch is stored with its inverse; undo sends the inverse with the current revision and moves the server's new inverse to the redo stack; a new edit clears redo. History is linear and every step is a logged revision (`house_plan_ops`), so it is auditable and reproducible from version 1.

## 5. Authority and access

- The API decides `editing.can_edit` (owner of the project and a plan with a document; AD-12). The page shows tools only when it is true and the screen is at least 768 px wide (AD-14); the server checks the owner again on every edit.
- Members read; strangers get 404; ops staff read through their GET routes and have no edit route.
- No string literal in JSX; no client state library; no `dangerouslySetInnerHTML`; no auth logic in the client.

## 6. Extension points (later checkpoints)

| Need | Where it plugs in |
|---|---|
| ADD_ROOM, DELETE_ROOM, MOVE_NODE | New appliers in `engine/ops.py` (graph edits); new gestures emit them; nothing else changes |
| Named versions and restore | `house_plan_versions` + `REVERT_TO_VERSION` as a logged batch (`reason` REVERT) |
| 3D | Consumes the same `PlanGeometry` (wall pieces already derived); ADR-026 |
| PDF | Server-side from `PlanGeometry`, with the AD-16 label on every page |
| Natural-language edits | Compile to the same operation union; preview diff; apply only on confirmation |
