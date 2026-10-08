# Plan2Build: AI and recommendation architecture

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/01_ARCHITECTURE/AI_AND_RECOMMENDATION_ARCHITECTURE.md` |
| Version | 0.1 (proposed) |
| Date | 2026-10-03 |
| Status | Architecture proposal for Chirag's review. Validates `RECOMMENDATION_ENGINE.md` v0.1 and the drawings pipeline in `IHB_FLOW.md` 33.6; proposes contracts, not code. |
| Business authority | CD-25 (concept design by default, 3D through image-generation APIs, architect design on request), CD-28 (engine), BR-055 (structural design never by AI), S06 §12 (AI assists, never the authority), BR-066 and S04 R6 (no brand recommendation), S04 R5 and S14 (position never for sale), BR-092 and PBR-031 (reasons, no guarantee), PBR-062 (reproducible), BR-142 (overrides recorded) |
| Related | DOMAIN_ARCHITECTURE.md (`design`, `recommendation` modules), DATA_ARCHITECTURE.md (tables), EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md (jobs on `ai` and `engine` queues), INTEGRATION_ARCHITECTURE.md (provider adapters), SECURITY_ARCHITECTURE.md (AI data leakage threat) |

Two subsystems share one principle: a model produces a candidate, a person or a rule decides. Nothing a model outputs becomes a drawing of record, a shortlist shown to a homeowner, or a state change without the review step named below.

## Part A: design generation

### A1. Artefact classes

| Class | Artefact types | Authoritative | Produced by | Label |
|---|---|---|---|---|
| Drawings | `SITE_PLAN`, `FLOOR_PLAN` (one per floor), `ELEVATION`, `SECTION`, `STRUCTURAL` (engineer's), `ARCHITECT_PACK` | Yes: the BOQ, estimate, RFQ and quotes are measured from them | Plan2Build's team in CAD (POC), the layout engine (later), the architect (on request), the structural engineer (always, for structure) | none; `is_authoritative = true` |
| Views | `VIEW_3D` (exterior; main interiors optional) | Never | Image-generation provider through the adapter | "Illustrative; the drawings govern" burned into the image and stored in metadata; `is_authoritative = false` |
| Concept plans (PD-28, ADR-025) | HousePlan document (one floor in the MVP) with derived 2D, 3D and PDF | Never: not a drawing, not a BOQ, RFQ, permit or structural source; may be named as an illustrative reference on a design request | The deterministic `houseplans` engine (zoning, CP-SAT, rule-based derivation, independent validation); no language model | Concept plan label on screen and on every PDF page (wording pending AD-16); `is_authoritative = false` by CHECK |

`design_artefacts` carries `type`, `is_authoritative`, `source` (TEAM, LIBRARY, ENGINE, PROVIDER, ARCHITECT, ENGINEER), `provider`, `model`, `prompt_version`, `seed`, `input_artefact_ids`, `review_state`, `file_id` (R2), `version`. A view always points at the drawings it was generated from, so a changed plan invalidates its views (`stale = true` until regenerated).

The rule that keeps the two classes apart is structural, not procedural: the Build Plan's BOQ measurement reads only artefacts with `is_authoritative = true`; the RFQ pack composes drawings and views into separate sections; the comparison and quotes reference drawing versions only. A view cannot be attached where a drawing is required because the attachment points are typed.

### A2. Pipeline by stage

> **Amended 2026-10-06 (PD-28, ADR-025).** The stage 2 layout engine below is brought forward as the homeowner-facing concept plan generator in module `houseplans`. Its output is a non-authoritative concept plan (A1), not the stage 2 DXF drawings; drawings still come from people and are checked (CQ-26). Design: `02_IMPLEMENTATION/AI_DESIGN_ENGINE_HAIRLINE_READINESS.md`.

The §33.6 flow assumed depth and line images exported from a 3D model guide generation. Hosted image APIs today accept reference images and text, not ControlNet-style depth or edge control (that control exists for self-hosted open models). The pipeline therefore has two stages; the second arrives with the in-house 3D model.

| Step | Stage 1 (POC) | Stage 2 (MVP, after the layout engine) |
|---|---|---|
| Plans | Sanctioned plan digitised, or a library layout fitted to the plot in CAD by the team; uploaded as DXF and PDF; checked (CQ-26) | Layout engine (constraint solver) writes DXF options; team checks |
| Elevations and section | Drawn by the team from the plan | Generated from the 3D model built from the plan |
| Guidance for views | Reference images: the floor plan, the elevation line drawing, a massing sketch if drawn; plus a style prompt from the requirement form (style words only) | Depth and line images exported per camera preset from the 3D model; generation through a provider with structural control (self-hosted open model with a union ControlNet, or a hosted API that adds control inputs) |
| Match check | Team reviews every view against the plan (floors, openings, roof, massing) and approves or rejects with a reason | Same review; an automated pre-check compares silhouette masks and flags mismatches before the reviewer |
| Views per request | 3 exterior camera presets (front, front-corner, rear); interiors on request; at most 2 regeneration rounds | Same, plus a per-room preset list |

Structural design has no AI step in either stage (BR-055). The engineer uploads `STRUCTURAL` artefacts and signs lines through the Build Plan sign-off endpoint.

### A3. Provider adapter

One interface in `design/providers/`: `ImageProvider.generate(GenerateInput) -> GenerateOutput`.

| Field | Content |
|---|---|
| `GenerateInput` | `reference_images` (list of R2 keys, read server-side and sent as bytes), `prompt` (rendered from a versioned template plus style words), `negative_prompt`, `size`, `seed` (optional), `control` (optional, stage 2: depth and edge images), `request_tag` (artefact id, for provider-side idempotency where supported) |
| `GenerateOutput` | `image_bytes`, `mime`, `provider`, `model`, `seed_used`, `safety_flags`, `latency_ms`, `cost_estimate` |
| Errors | `ProviderUnavailable` (retryable), `ProviderRejected` (content or policy; not retryable with the same prompt), `ProviderQuota` (defer), `ProviderBadOutput` (empty or corrupt) |

Providers at the POC: `GeminiImageProvider` (Gemini 3.1 Flash Image, default) and `FluxKontextProvider` (through fal.ai or Replicate) as the fallback, selected by configuration (`design.provider.primary`, `design.provider.fallback`). The trial in §33.6 picks the primary; the adapter makes the choice reversible. Prompt templates live in `design_prompt_templates` (versioned, data), with style vocabulary mapped from requirement-form answers; the template text is reviewed like any content.

### A4. Jobs

| Job | Queue | Trigger | Steps | Idempotency and retry |
|---|---|---|---|---|
| `prepare_view_inputs` | `ai` | `design.plan_approved` | Loads approved drawings, produces the reference image set (rasterised PDF pages at fixed size; stage 2: depth and line exports), stores them under `{env}/design/{yyyy}/{mm}/{file_uuid}` in the private bucket, creates one `VIEW_3D` artefact row per camera preset in state `QUEUED`, enqueues `generate_view` per artefact | Re-run finds existing rows and skips |
| `generate_view` | `ai` (concurrency 1) | per artefact | Calls the adapter; on success writes the image to R2, burns the label and stores metadata (provider, model, seed, prompt version), creates a thumbnail, sets `review_state = PENDING`, emits `design.view_generated` | Retries 3 times with backoff on `ProviderUnavailable`; `ProviderRejected` adjusts the prompt once (safer template variant) then fails to ops; `ProviderQuota` defers 10 minutes; a success is final (artefact has a file) |
| `regenerate_view` | `ai` | reviewer rejects | New seed, reviewer's note appended to the prompt within the template's allowed slots; round counter incremented; at round 3 the artefact is `FAILED_REVIEW` and ops decide (issue without this view, or team-made view) | per artefact and round |
| `design_cost_guard` | inline check | before any generation | Per request cap (default 12 images) and per day cap (default 100) from configuration; exceeding returns the artefact to `BLOCKED_COST` and raises an ops exception | none |

Views are not required to issue a Build Plan: if generation fails, the version issues with drawings only and the homeowner sees "3D views to follow" (the event `design.generation_failed` reaches ops, not the homeowner).

### A5. Review and attachment

1. Drawings: a qualified person on the team marks each drawing `APPROVED` (CQ-26 open on who; default: the advisor with the structural engineer for anything structural). Only approved drawings can be referenced by a Build Plan version.
2. Views: the ops review queue shows each view beside its source plan with the checklist (floors, openings, roof, massing, nothing that contradicts the plan). Approve or reject with a reason code; the decision is audited.
3. When all required drawings are approved and either all views are approved or the request is marked "issue without views", the module emits `design.approved`; `buildplan` attaches the artefact ids to the draft version.
4. The homeowner decides on the concept (accept, request changes, request an architect). Accept moves to Build Plan issue. Changes re-enter at the plan step and mark views stale. An architect request opens the architect path (CD-25; shortlist through the engine once CQ-25 is settled); the architect's pack replaces the concept drawings and the BOQ is measured again (CD-20).

### A6. Storage and privacy

- All design inputs and outputs are private R2 objects; views the homeowner chooses to share go out through share tokens, never through the public bucket.
- The provider receives rasterised geometry and style words. Reference images are rendered from the drawings with the title block stripped (title blocks carry names and plot addresses). The prompt template has no slot for free text from the homeowner; style words are selected from a vocabulary. Logged provider requests contain the artefact id, not the project.
- Provider data-use terms are recorded in INTEGRATION_ARCHITECTURE.md with the date checked; the paid tier whose terms exclude training on inputs is required (to verify at purchase).
- Cost per project at the POC: about 10 images (3 views, up to 2 rounds, some interiors) at roughly $0.04 to $0.07 each, under $1; the cost guard exists for runaway retries, not for budget.

### A7. Failure modes

| Failure | Effect | Handling |
|---|---|---|
| Provider outage | Views delayed | Circuit breaker (EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md section 7); fallback provider after the breaker opens if configuration allows; the Build Plan can issue without views |
| Model retired by the vendor | `ProviderRejected` on every call | Configuration switch to the fallback provider; the adapter hides the API differences; a weekly canary generation on staging detects deprecation before homeowners do |
| Poor match to the plan | Reviewer rejects | Regeneration with a new seed; team-made view as the last resort |
| Safety filter blocks an exterior house view (false positive) | `ProviderRejected` | Safer template variant once; then ops |
| Plan changed after views | Stale views | `stale = true`; the Build Plan cannot attach stale views; regeneration enqueued when the new plan is approved |

## Part B: recommendation engine

### B1. Validation of `RECOMMENDATION_ENGINE.md` v0.1

| Claim | Verdict | Architecture consequence |
|---|---|---|
| Staged pipeline (eligibility, retrieval, scoring, re-ranking, allocation, reasons, review) | Keep | Each stage is a pure function in `recommendation/core/` with typed inputs and outputs; the orchestration job calls them in order; no stage reads the database |
| H3 cells or PostGIS for retrieval | PostGIS only | Tens to hundreds of members per city; a `ST_Covers(service_area, site_point)` query with a GIST index returns in under 10 ms; H3 adds a dependency for no gain (ADR-015) |
| Road travel time from a routing engine, cached per cell pair | Defer | POC: straight-line distance times an urban factor (1.4, configuration) as the travel signal; `TravelTimeProvider` interface with `StraightLineProvider` now and `OsrmProvider` when the OSRM container is enabled; cache per (profile id, project id) in the candidate snapshot, not per cell pair |
| Fixed-scale normalisation and Beta smoothing | Keep | Priors and scales in configuration; the smoothing function is unit-tested against the worked example (A 0.73, B 0.81, C 0.72) |
| Rank-order centroid for homeowner weights, λ = 0.5 blend | Keep | Weight derivation is deterministic and stored in the request snapshot |
| Diversity (MMR), exposure caps, Thompson sampling | Phase 1, config present at POC with `exploration_slots: 0` | Any randomness uses a seed stored on the request so recomputation is identical (PBR-062) |
| Min-cost-flow allocation | Phase 2 | No code at the POC; the interface point is the allocation stage returning the input list unchanged |
| TOPSIS for quotes | Keep, with two rules added | TOPSIS can reorder when a quote is added or removed (rank reversal). Rule: the recommendation is computed on the frozen quote set at finalisation; a later withdrawal or new version requires a new comparison version through operations, never a silent recompute. Rule: with one valid quote there is no recommendation, only the adjustment list and risk flags |
| Reasons in Hindi and English, AI may help phrase | English only at MVP (Chirag, 2026-10-03); no language model at the POC | Reasons are rendered from templates in `recommendation_reason_templates` with the evidence values filled in; `locale` column kept; a later LLM phrasing step would be a review-gated job, never inline |
| Team review before showing (POC) | Keep | `review.team_review_required` per use; the API in API_ARCHITECTURE.md section 11 |
| Learning phase (LambdaMART) | Later; log from day one | The snapshot, shown items, overrides and outcomes tables are the training set; no model runtime at the POC |
| Guardrails enforced by the configuration validator | Keep, and test | The validator is a unit-tested function with a fixed deny list of signal sources and item types; CI fails if a configuration fixture with a brand item type or a payment-derived signal passes |

Gaps the proposal did not cover, now specified: fewer than three eligible candidates (B6), zero candidates, deterministic tie-breaking, the capacity model (B3), conflict-of-interest data until POQ-053 and POQ-054 settle, stale metrics, and what professionals are told about a lead.

### B2. Contracts

All contracts are Pydantic models in `recommendation/contracts.py`; JSON forms are stored in the tables named.

| Contract | Fields | Stored in |
|---|---|---|
| `RecommendationRequest` | `use` (CONTRACTOR_SHORTLIST, QUOTE_RECOMMENDATION, ARCHITECT_SHORTLIST), `project_id`, `trigger` (HOMEOWNER_ASK, SHORTFALL, DECLINE_REPLACEMENT, EXPIRY_REPLACEMENT, ADJUSTMENTS_COMPLETE, ARCHITECT_REQUESTED), `context` (rfq id for quotes; excluded profile ids; slots needed), `config_version_id`, `model_version` (`expert-v1` at the POC), `rng_seed`, `requested_by`, `requested_at` | `recommendation_requests` |
| `HomeownerInputs` | priority ranking (ordered criterion keys), budget band, start window, floors, project class, site point (P2: read by the engine inside the transaction, never stored in the snapshot beyond a cell-level rounding of 500 m) | inside the request snapshot |
| `CandidateSnapshot` | `subject_type` (PROFESSIONAL, QUOTE_VERSION), `subject_id`, signal values with `as_of` per signal, capacity facts, travel minutes, class, `metrics_run_id` | `recommendation_candidates.snapshot` |
| `EligibilityResult` | `eligible`, `failed_rules` (rule key, reason code, homeowner-safe text, evidence) | `recommendation_candidates` |
| `ScoredCandidate` | criterion values after normalisation and smoothing, blended weights, `score`, penalties applied | `recommendation_candidates` |
| `RankedResult` | ordered candidates with `position`, `fit_label` (STRONG, GOOD, FAIR from thresholds), `reasons` (2 to 3, each with criterion key, template key, evidence values), `tradeoff` (quotes only), risk flags | `recommendation_candidates`, `recommendation_results` |
| `ReviewAction` | `action` (APPROVE, REMOVE, REORDER, DISCARD), `candidate_id`, `reason`, `old_value`, `new_value`, actor, at | `recommendation_review_actions` |
| `ShownItem` | `subject_id`, `position`, `fit_label`, `shown_to_user_id`, `shown_at` | `recommendation_shown_items` |
| `Outcome` | per subject and project: lead state, quoted, selected, outcome measures (on-time share, unrectified critical NCs, change share), label 0 to 4, `labelled_at` | `recommendation_outcomes` |
| `EngineConfig` | the YAML of `RECOMMENDATION_ENGINE.md` section 10 as JSONB with `schema_version`, `use`, `version`, `active_from`, `created_by`, validation report | `engine_configs` |

Determinism: `recompute(request_id)` loads the stored snapshot, configuration version and seed, runs the pure core and must produce an identical `RankedResult`; a CI test asserts this on fixtures, and operations can run it from the admin console for any past request (PBR-062).

### B3. Retrieval, eligibility, capacity

Retrieval (one SQL statement, `recommendation/queries.py`): Club members `ADMITTED` and `VERIFIED` for the category, whose `service_areas` cover the site point or whose base is within their declared radius, excluding profile ids in the request context. At the POC this returns the whole eligible set; the retrieval limit (200) matters only later.

Eligibility rules are rows in `engine_configs.eligibility` evaluated by a rule interpreter over the `CandidateSnapshot`: each rule is `{key, operator, field, value}` or a named predicate from a fixed registry (`class_covers_project`, `capacity_free_in_start_window`, `no_conflict_of_interest`, `quote_valid_on_date`, `adjustments_complete`). Every failure is stored with a homeowner-safe reason ("outside their service area", "no capacity in your start window"), which is what `POST /projects/{id}/leads` returns for a failed pick.

Capacity model: `free_sites(profile, window) = max_concurrent_sites − active_sites_overlapping(window) − accepted_leads_overlapping(window) − open_invitations_overlapping(window)`; `paused_until` within the window makes it zero. `active_sites` are project memberships with projects in BUILDING; windows overlap when the project's start window intersects the site's planned stage range. The same function serves the listing's "available" flag, so the homeowner and the engine see one truth.

Conflict of interest: a `professional_conflicts` table (ops-recorded: profile id, project id or homeowner id, reason) until the independence protocol is settled (POQ-053, POQ-054); the rule reads it and nothing else.

### B4. Scoring, re-ranking, reasons

Scoring follows `RECOMMENDATION_ENGINE.md` section 5 exactly; the only architectural additions are tie-breaking and metric staleness:

- Ties (equal score to 4 decimals) break by lower exposure in the current week, then by earlier Club admission, then by profile code. Deterministic.
- Signals come from `professional_metrics` written by the nightly `recompute_metrics` job (EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md section 6). The snapshot records `metrics_run_id`; if the latest run is older than 48 hours the request is computed anyway and flagged `metrics_stale` for the reviewer.

Re-ranking at the POC applies the exposure cap only (`exposure_cap_per_week`, read from `exposure_ledger`); diversity and exploration are implemented behind configuration and switched off (`diversity_lambda: 1.0`, `exploration_slots: 0`) so phase 1 is a configuration change plus a review of outcomes, not a release.

Reasons: for each shown candidate, take the three criteria with the largest weight × value contribution; render the template for each criterion with the evidence values and, where the criterion maps to a homeowner priority, the priority's rank ("which you ranked first"). A candidate with fewer than two renderable reasons is not shown (BR-092); the reviewer sees why.

Quote recommendation (TOPSIS, section 6 of the proposal): computed once when `rfq.adjustments_complete` fires, on quote versions that are SUBMITTED and valid on that date; risk flags computed from configuration thresholds and attached, never scored; the reviewer approves; `rfq.comparison.finalise` freezes the result into the comparison snapshot.

### B5. Review, override, exposure to users

| Audience | Sees | Never sees |
|---|---|---|
| Operations reviewer | Candidates, scores, criterion values, failed rules, reasons, staleness flag, exposure counts; can approve, remove, reorder, discard with a reason (BR-142); overrides are audit rows with `is_override` | nothing withheld |
| Homeowner | Up to three candidates (firm name, class, service area name, portfolio summary), fit label, reasons, and for quotes the trade-off sentence and risk flags | numeric scores, ranks as numbers, other candidates' data, the reviewer's actions |
| Professional | For a lead: the reasons it was sent to them (positive, evidence-based, from the same templates), their own metrics with the Club average for context | their rank, other members' metrics, whether they were removed by a reviewer, any homeowner identity before acceptance (CD-26) |
| Admin | Configuration versions, validation reports, fairness reports, recompute tool | nothing withheld |

### B6. Fallbacks

| Situation | Behaviour |
|---|---|
| Fewer than three eligible | Show what passed with the reasons, tell the homeowner how many were found and why others were not eligible (aggregate reasons); ops may widen the service radius or class rule for this request only through an override with a reason |
| Zero eligible | `recommendation.failed` with reason NO_CANDIDATES; ops build a manual shortlist through the leads endpoint; the homeowner is told Plan2Build is finding contractors, with no time promise |
| Engine job fails (bug, data) | Retries per the job contract; then `recommendation.failed`; ops exception; manual path; Sentry |
| Metrics job missing | Flag `metrics_stale`; proceed |
| Configuration invalid | Cannot be activated (validator); the previous active version keeps serving |
| Travel provider down | Straight-line fallback with a flag on the snapshot |

### B7. Fairness, outcomes, auditability

- `fairness_report` job, monthly: share of suggestions and leads per member, new (admitted under 6 months) against established, by area cell, Gini of lead distribution, acceptance and quote rates by group; written to `fairness_reports` and shown in the admin console; thresholds raise an ops item, not an automatic change.
- Outcomes: `recommendation_outcomes` filled from events (`lead.*`, `rfq.quote_version_created`, `rfq.selection_recorded`) and, at project completion, from construction and assurance facts; label thresholds in configuration (section 7 of the proposal).
- Every request keeps its snapshot, configuration version, seed, result, review actions and shown items for the project's retention period; the audit log carries the review actions; the admin recompute tool proves reproducibility on demand.

### B8. Module boundary and extraction

`recommendation/core/` has no imports from other modules and no database access; `recommendation/service.py` builds snapshots through the public interfaces of `professionals`, `projects`, `rfq` and `assurance` (read-only), runs the core, and stores results. This is the extraction seam: the core can become a service that receives snapshots over HTTP without changing its contracts (DOMAIN_ARCHITECTURE.md extraction readiness). At the POC it runs as a job on the `engine` queue, finishing in well under a second for Raipur-sized candidate sets.

## Part C: open points

| ID | Question | Default until answered |
|---|---|---|
| AQ-15 | Primary image provider after the one-week trial (Gemini 3.1 Flash Image is the starting pick) | Gemini primary, FLUX Kontext fallback |
| AQ-16 | Who approves drawings before issue (CQ-26) | The advisor; the structural engineer for anything structural |
| AQ-17 | Fit-label thresholds (STRONG, GOOD, FAIR) and the risk-flag thresholds (15% below the estimate band) | Thresholds as in the proposal; team to sign off with the configuration version |
| AQ-18 | Whether "issue without views" is allowed by default or needs ops approval | Allowed, flagged to the homeowner as "to follow" |
