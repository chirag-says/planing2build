# ADR-008: Modular monolith with 24 modules and background workers; extraction boundary defined

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03); module list amended by ADR-024 (2026-10-06): `engagements` replaces `leads`; amended by ADR-025 (2026-10-06): `houseplans` added (25 modules) and `design` recorded as built in `designs`, `buildplan` and `houseplans` |
| Deciders | Chirag (strong preference stated), Sakha |
| Related | SYSTEM_ARCHITECTURE.md section 6, DOMAIN_ARCHITECTURE.md, ADR-002, ADR-009 |

## Context

The product has a dozen interacting state machines and cross-module transactions (selection, variation activation, inspection approval). The team is two people. S06 lists microservices under "do not build now". Chirag asked for an evaluation with a strong preference for a modular monolith plus workers.

## Decision

One FastAPI codebase organised into 24 modules (core, identity, projects, catalog, specification, buildplan, design, professionals, leads, rfq, recommendation, construction, variations, money, assurance, issues, records, billing, documents, notifications, messaging, audit, ops, analytics). Rules: each module owns its tables; other modules use its `interface.py` or its events, never its tables or internals; cross-module side effects go through the outbox; configuration is data; routers are thin; an import linter enforces the boundaries. The worker runs the same code. Extraction of a module into a service is allowed when one of four triggers holds: a different scaling profile, a different runtime (for example GPU), a different release cadence, or no joins needed with the rest. First candidates: design, recommendation, rendering.

## Why

- One transaction per business action across modules; no distributed transactions or sagas for a POC.
- One deploy, one log stream, one database to reason about; incidents are debuggable by one person.
- The module rules give most of the benefit of services (clear ownership, replaceable parts) at none of the network cost.
- Extraction readiness is designed in, so the choice is reversible when a trigger appears.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Microservices from the start | Network calls where a function call suffices; distributed transactions for selection and inspection approval; a two-person team spends its time on plumbing; S06 says not now |
| A plain monolith without module rules | Fast at first, then every table is everyone's; extraction becomes a rewrite |
| Serverless functions | Cold starts on a latency-sensitive product; long-running renders and offline sync fit poorly; harder to reason about transactions |

## Consequences

- Discipline is enforced by tooling (import linter, code review), not by process alone.
- The module list is fixed in SYSTEM_ARCHITECTURE.md; adding a module is an architecture change with a reason.
- Some duplication of small read models across modules is accepted to avoid cross-module joins in hot paths.

## Migration path

DOMAIN_ARCHITECTURE.md's extraction readiness per module; the outbox relay publishes to a broker when the first service appears (EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md section 8).
