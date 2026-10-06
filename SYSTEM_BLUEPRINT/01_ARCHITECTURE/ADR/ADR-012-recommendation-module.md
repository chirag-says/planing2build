# ADR-012: Recommendation engine as a module with a pure core; expert-weighted scoring now, learned ranking later; team review; no brands, no paid influence

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03); design delegated by Chirag ("answer on my behalf… proper scalable way… not simple if else") |
| Deciders | Chirag (to review), Sakha |
| Related | RECOMMENDATION_ENGINE.md, AI_AND_RECOMMENDATION_ARCHITECTURE.md Part B, ADR-008, ADR-015 |

## Context

CD-18, CD-25, CD-26 and CD-28 give the engine three uses at the POC: contractor shortlists, quote recommendation at comparison, architect shortlists (once CQ-25 settles). Hard rules: no brand recommendation (BR-066), the comparison headline is never a price ranking (BR-083), position is never for sale (S04 R5), reasons are required (BR-092), reproducible from stored rules (PBR-062), overrides recorded (BR-142), AI assists and never decides (S06 §12). Data at the POC: tens of members, a few projects a month, no repeat homeowners.

## Decision

- The engine is the `recommendation` module inside the monolith with a pure core (`recommendation/core`: no database, no imports from other modules) that runs a staged pipeline: eligibility rules (data), retrieval (PostGIS), scoring (fixed-scale normalisation, Beta smoothing, rank-order-centroid homeowner weights blended with expert weights), re-ranking (exposure caps now; diversity and exploration behind configuration), reasons from templates, team review.
- Quote recommendation by TOPSIS on a frozen quote set, beside the adjustment list, with risk flags never scored.
- Every request stores its snapshot, configuration version, seed and result; `recompute(request_id)` must reproduce it (CI test).
- The configuration validator rejects brand item types, payment-derived signals and price-sorted rules; the deny list is tested.
- Learning (LambdaMART) only after a few hundred outcomes, in shadow first; outcomes are logged from day one.

## Why

- Knowledge-based recommendation (match requirements to verified attributes) is the right method for rare, high-stakes choices; collaborative filtering has nothing to learn from one-time buyers.
- A pure core with snapshots gives reproducibility and testability, and is the extraction seam if the engine ever needs its own runtime.
- Expert weights with smoothing are explainable to homeowners and to the client's team, which the sources require (reasons, no league tables).
- Shortest-path algorithms belong to routing and allocation, not to fit; the design uses them there and nowhere else.

## Alternatives considered

| Alternative | Why not |
|---|---|
| If-else rules in code | Not configurable, not versioned, not reproducible; Chirag explicitly rejected it |
| A learned model from day one | No training data; opaque; fails BR-092 and PBR-062 at the POC |
| A hosted recommendation service | Sends professional and project data out; cannot express the brand and pay-to-play prohibitions as enforceable constraints |
| Elasticsearch function scoring | A search engine's scoring is not auditable per rule and adds a cluster |

## Consequences

- Plan2Build's team must set and sign off expert weights and thresholds (configuration versions) before the first shortlist.
- Review before showing adds operations work per request; `team_review_required` can be relaxed per use later.
- Metrics depend on the nightly job; stale metrics are flagged, not blocking.

## Migration path

Phase 1 (diversity, exploration) is configuration; phase 2 (learned ranking, allocation) replaces the scoring stage per use with the same contracts; extraction to a service sends snapshots over HTTP.
