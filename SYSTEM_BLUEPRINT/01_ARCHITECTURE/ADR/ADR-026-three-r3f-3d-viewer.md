# ADR-026: three.js and React Three Fiber for the concept plan 3D viewer

| Item | Value |
|---|---|
| Status | Accepted (Chirag, 2026-10-06: AD-09). The packages are added when the 3D checkpoint starts, not before |
| Deciders | Chirag (decision), Sakha (record) |
| Related | ADR-025; `02_IMPLEMENTATION/AI_DESIGN_ENGINE_HAIRLINE_READINESS.md` section P; IMPLEMENTATION_CONTRACT 171-176 (dependencies) |

## Context

The concept plan needs a basic 3D view derived from the same HousePlan: walls, floors, openings, stairs and fixtures at true dimensions, with orbit, zoom and a simple walkthrough. The web app (Next.js 16, React 19) has no 3D or canvas library today.

## Decision

- Use `three` with `@react-three/fiber`. The scene is built from `PlanGeometry` returned by the API (wall pieces around openings, floor polygons, stair steps, fixture blocks), so the browser runs no geometry rules and 2D and 3D cannot disagree.
- Do not add `@react-three/drei`. Orbit and pointer-lock controls come from three's own examples modules. `drei` is added only when a concrete requirement shows it is needed, with that requirement recorded.
- Load the viewer with `next/dynamic` and no server render, only when the 3D tab is opened; render on demand (`frameloop="demand"`).

## Why

- React Three Fiber lets the scene re-render from props like any React view; three.js is the most widely used WebGL library with long-term maintenance.
- No CSG library is needed: openings are made by splitting straight walls into pieces, computed on the server.

## Alternatives considered

| Alternative | Why not |
|---|---|
| three.js with a hand-written React wrapper | More glue and teardown code for the same result |
| Babylon.js | Larger bundle and an engine-shaped API; more than a basic viewer needs |
| `@react-three/drei` by default | Large surface for two controls three already ships |

## Consequences

- Two new web dependencies, pinned, with licence (MIT) and size recorded in the checkpoint that adds them.
- Pages that do not open the 3D view load none of it.
