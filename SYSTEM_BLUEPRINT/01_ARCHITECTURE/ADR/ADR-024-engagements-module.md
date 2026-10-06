# ADR-024: `engagements` replaces `leads` in the module list

| Item | Value |
|---|---|
| Status | Accepted (Chirag, 2026-10-06; resolves H-03 before Slice 3.6) |
| Deciders | Chirag (decision), Sakha (record) |
| Amends | ADR-008 (module list; the count stays 24) |
| Related | SLICE3_4_READINESS.md section 0 (N-01 to N-12, "Connection and lead"), SLICE3_6_READINESS.md section 0 (QD-01, QD-02, QD-12), DATA_ARCHITECTURE.md 4.18, STATE_MODEL.md 9a, ADR-019 |

## Context

ADR-008 fixes 24 modules, including `leads` (listing leads and their windows). Slice 3.4 superseded leads: the family's request to a professional is a connection, and the professional relationship is a per-category engagement ("Connection and lead" decision, N-02, N-03). The code built a module named `engagements` for that model. IMPLEMENTATION_CONTRACT §4 requires an ADR for a module not on the list. Slice 3.6 adds a second way into an engagement (a homeowner's RFQ selection), so the module's place in the architecture must be recorded first.

## Decision

- `engagements` takes the place of `leads` in the ADR-008 list. The count stays 24. No `leads` module is built.
- `engagements` owns `project_service_needs`, `connections`, `project_engagements`, `engagement_documents`, `engagement_events` and `quote_review_requests` (3.4 intake).
- The engagement is the only professional relationship record per project and category (N-02: one ACTIVE per category). No other module keeps a relationship state for professionals.
- An engagement starts in one of three ways, recorded as its `origin`:
  - CONNECTION: a listed professional accepts a connection (3.4);
  - OUTSIDE: the family records an outside professional (3.4);
  - RFQ_SELECTION: the homeowner selects a contractor's quote in an RFQ (3.6, QD-01, QD-12).
- `rfq` reaches engagements only through `engagements/interface.py`: read the ACTIVE engagement of a category, create or reuse the engagement for a selection, withdraw open connections. `engagements` never imports `rfq`.
- The substantial-work record stays in billing. `engagements` writes CONNECTION_ACCEPTED (N-12). `rfq` writes RFQ_SELECTION (QD-02, a new product decision). Both go through `billing/interface.py`.

## Why

- The 3.4 decisions already replaced leads with connections and engagements; the module list should say so.
- Keeping the engagement as the single relationship record stops RFQ invitations and quotes from becoming a second professional lifecycle.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Keep `leads` and add `engagements` as a 25th module | `leads` would be empty; two names for one concern |
| Put RFQ selection inside `engagements` | Mixes the sourcing process (invitations, quotes, comparison) with the relationship record |

## Consequences

- SYSTEM_ARCHITECTURE section 8, DOMAIN 3.9 and ARCHITECTURE_BASELINE read `leads` as `engagements` from this ADR on.
- The import linter lists `engagements` and `rfq` in the independence contract; `rfq` may import `engagements.interface`, not the reverse.
