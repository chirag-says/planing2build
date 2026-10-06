# ADR-025: `houseplans` module; deterministic concept floor plans from a zoning and CP-SAT layout engine

| Item | Value |
|---|---|
| Status | Accepted (Chirag, 2026-10-06: AD-01, AD-02, AD-07, AD-08, AD-10). OR-Tools enters the dependency set only after the container feasibility check in `AI_DESIGN_ENGINE_CHECKPOINT_1.md` section N passes |
| Deciders | Chirag (decision), Sakha (record) |
| Amends | ADR-008 (module list: 25 modules; records the `design` naming drift); ADR-013 (the rejected alternative "AI-generated floor plans as the drawings" stays rejected; a deterministic, non-authoritative concept plan is a different artefact, permitted by PD-28) |
| Related | PD-28 (IHB_FLOW 32.6); BP-03 as amended (SLICE3_5_READINESS section 0); `02_IMPLEMENTATION/AI_DESIGN_ENGINE_HAIRLINE_READINESS.md`; `02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_1.md`; ADR-002 (names OR-Tools and ezdxf for the later layout engine); AI_AND_RECOMMENDATION_ARCHITECTURE A1, A2; IMPLEMENTATION_CONTRACT 18 and forbidden pattern 10 |

## Context

Image models produce pictures that look like floor plans and are not: duplicate WCs in one bathroom, a WC in a living room, overlapping rooms, doors not on walls, dimensions that do not add up. Chirag decided (PD-28) that "Generate My Design" produces a concept floor plan as a structured, validated model, while images remain optional look-and-feel. The blueprint already planned a layout engine for a later stage (AI:33; IHB:4550; ADR-002:19). This ADR brings it forward as a homeowner-facing, non-authoritative concept plan.

## Decision

- A new module `houseplans` (`apps/api/src/p2b/houseplans/`) owns the HousePlan model, the generation pipeline, the layout ruleset, plan revisions, operations and versions.
- The canonical artefact is the HousePlan document: versioned schema, integer millimetres, a planar graph of wall nodes, walls and rooms, with openings and fixtures hosted by reference. SVG, PDF, 3D scenes and images are derived outputs and never written back.
- The generation path has no language model (PD-28, IC 18.6): requirement normalisation → architectural intent → constraints → layout solver → HousePlan → validation → deterministic repair → VALID concept plan. Natural-language editing and free-text interpretation are deferred.
- Layout solver: deterministic rule-based zoning, then OR-Tools CP-SAT for placement and sizing, then rule-based derivation of walls, openings and fixtures. Pinned version, fixed seed, deterministic limits, golden tests. Until the container check passes, the engine runs a dependency-free deterministic band solver behind the same interface.
- Validation is mandatory and independent of the generator. A plan with any ERROR issue is INVALID and is never presented as a result, referenced or exported.
- Rule values (room minimums, passage widths, wall thicknesses, door widths, fixture sizes and clearances, setbacks, ventilation ratios) live in a versioned `layout_rulesets` table. A ruleset is usable in production only when PUBLISHED with a cited source for each value and an approver. Until then it is DRAFT and production refuses generation.
- Authority: every plan carries `is_authoritative = false` (CHECK). A VALID plan version may be named as an illustrative reference on a design request; it never becomes a drawing of a drawing set and is never a BOQ or RFQ source (PD-28, AD-02).
- Access: owner views and edits; project members view; operations read only; professional access later through the professional workflow (AD-12).
- `houseplans.engine` is a pure package: no database, no I/O, no import from other `p2b` modules except `p2b.core.vocabulary`. An import-linter contract enforces it.

## Naming drift recorded (AD-10)

ADR-008 lists a module named `design` covering the whole concept design pipeline (DOMAIN_ARCHITECTURE 3.7). As built:

| ADR-008 `design` responsibility | Built where | Since |
|---|---|---|
| Illustrative image generation, prompt templates, illustrative references | `designs` (plural) | Slice 3.1, migration 0008 |
| Design requests, drawing sets, checker, approval | `buildplan` | Slice 3.5, migration 0013 |
| Concept floor plan (the "approved vector plan" and layout engine) | `houseplans` | This ADR |

`designs` keeps its name; renaming a built module with tables, routes and contracts would cost more than it clarifies. From this ADR on, ADR-008's `design` reads as `designs` plus the parts listed above, and the module count is 25.

## Why

- A model of rooms, walls and openings with deterministic geometry makes the reported failures unrepresentable or detectable; a picture cannot be checked.
- CP-SAT handles no-overlap, containment, minimum sizes, adjacency and exterior access declaratively and proves infeasibility, which lets the product say plainly why a programme does not fit a plot.
- A separate module keeps concept images (provider, prompts, credits per image) apart from geometry, rules and editing, which change for different reasons.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Image generation as the plan | The failure class this ADR exists to remove |
| A language model writing coordinates | Not reproducible, not checkable, and outside IC 18.6 |
| Extending `designs` | Mixes provider-driven images with deterministic geometry; the two have different state machines, quotas and tests |
| Templates per plot size only | Breaks on any plot or programme not anticipated |
| Metaheuristics or learned generators | No proof of feasibility; reproducible only with effort; same explainability problem as images |

## Consequences

- New tables in migration 0019 (Checkpoint 1): `layout_rulesets`, `house_plans`, `house_plan_versions`; additive changes only. `house_plan_ops` arrives with the editing checkpoint; design brief persistence waits for AD-03.
- New dependency `ortools` (Apache-2.0), with numpy, pandas, protobuf, absl-py and immutabledict, after the feasibility check. Measured image growth and solve time are recorded in the checkpoint report.
- The `engine` queue (declared in `core/jobs.py`, unused until now) carries plan generation with concurrency 1.
- IMPLEMENTATION_CONTRACT forbidden pattern 10 is unchanged in force: the concept plan is computed, not generated by a model, and it is not a drawing.

## Migration path

If the engine moves out of the monolith (ADR-008 triggers: CPU profile), `houseplans.engine` is already pure and can run as a separate worker image with no code change beyond the job entry point.
