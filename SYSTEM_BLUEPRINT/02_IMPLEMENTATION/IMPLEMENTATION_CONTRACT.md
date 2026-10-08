# Plan2Build: implementation contract

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/IMPLEMENTATION_CONTRACT.md` |
| Version | 1.0 |
| Effective | 2026-10-04 |
| Applies to | Every change to the Plan2Build repository, by any developer or AI agent |
| Governed by | `01_ARCHITECTURE/00_APPROVAL/ARCHITECTURE_BASELINE.md` (what is fixed and what is open) |

This contract is binding. A pull request that breaks a rule here is not merged, however good the code is otherwise. A rule that turns out to be wrong is changed here first, with a reason, then in code.

**Business ambiguity must never be resolved by invention.**

## 1. Source hierarchy

1. Client decisions CD-01 to CD-28.
2. `IHB_FLOW.md` v1.2 (section 33 for the MVP).
3. `PROFESSIONALS_FLOW.md` v1.2 (section 44 for the POC).
4. `RECOMMENDATION_ENGINE.md`.
5. `ARCHITECTURE_BASELINE.md`, then ADR-001 to ADR-022.
6. The other `01_ARCHITECTURE/` documents.
7. `SOURCE_OF_TRUTH/` (evidence, read-only).
8. General engineering knowledge, never for business rules.

Before writing code for a feature, read the stage in the flow documents, the module in `DOMAIN_ARCHITECTURE.md`, its machine in `STATE_MODEL.md`, its tables in `DATA_ARCHITECTURE.md`, its endpoints in `API_ARCHITECTURE.md` and its events in `EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md`. Cite the identifiers (CD, BR, J, F, AQ, CQ) in the pull request.

## 2. Stop and report instead of guessing

Stop and report when:

1. Two sources of rank 1 to 6 genuinely conflict.
2. A business rule, field, option list, threshold, window or message the feature needs is missing.
3. A state transition is not in `STATE_MODEL.md`.
4. Who may do something (actor, role, scope, audience) is ambiguous.
5. A rule about money, payment, fee, refund or tax is undefined.
6. A legal or compliance requirement (DPDP, GST, retention, consent wording) cannot be read from the sources.
7. The change would alter a decision in the baseline or an ADR.
8. The feature looks outside the POC scope (baseline section 19).
9. A new dependency, provider or service has consequences the blueprint does not cover.
10. Seed or reference data contradicts a rule (for example a structural line with a brand category).

A report has six parts: BLOCKER, WHY IT MATTERS, SOURCE(S), WHAT IS KNOWN, WHAT IS UNKNOWN, RECOMMENDED DECISION. Write it in the pull request or the session report, and add the item to the open-points table of the document that owns it. Work that does not depend on the blocker may continue.

A default written in an architecture document (an AQ default) may be implemented; cite it. A default you would have to make up may not.

## 3. Coding principles

1. Production-quality code, POC-sized infrastructure.
2. Every line earns its place: no speculative abstraction, no dead code, no commented-out code, no unused parameters.
3. One way to do each thing across the codebase. Follow the existing pattern; change it everywhere or nowhere.
4. Configuration and reference data are rows in versioned tables, not constants and not branches in code (stages, specification masters, rate cards, class rules, windows, engine configuration, form questions, templates).
5. Business logic lives in services on the server. The web app renders and validates for usability only.
6. Every path handled: success, validation failure, authorisation failure, state conflict, version conflict, provider failure; every screen has loading, empty and error states.
7. Types everywhere: `mypy --strict` on the API, `tsc --noEmit` with `strict` on the web.

## 4. Module boundaries

| Rule | Enforcement |
|---|---|
| A module is a package under `apps/api/src/p2b/<module>/` with `interface.py`, `service.py`, `models.py`, `schemas.py`, `router.py`, and `events.py`, `jobs.py`, `queries.py` when needed | Review |
| Other modules import only `p2b.<module>.interface` | import-linter contract in `apps/api/pyproject.toml` |
| `p2b.core` imports no module; `p2b.integrations` import no module; `p2b.recommendation.core` imports only the standard library and Pydantic | import-linter |
| A module owns its tables. No other module reads or writes them, except query services that join for read-only screens, marked as such | Review |
| Cross-module side effects go through outbox events, never a direct call that writes another module's data inside the caller's logic | Review |
| Routers are thin: validate, authorise, call one service function, map the result | Review |
| A module is created when its first slice needs it, with the name from the module list. No new module without an ADR | Review |

## 5. Naming

| Thing | Convention |
|---|---|
| Python | `snake_case` functions and variables (verbs for functions, nouns for values, `is_`/`has_`/`should_` for booleans), `PascalCase` classes |
| TypeScript | `camelCase` values, `PascalCase` components and types, file names `kebab-case.ts`, React components `PascalCase.tsx` |
| Tables | `snake_case`, plural; columns singular; `_id` foreign keys; `_at` timestamps; `is_` booleans |
| States | `UPPER_SNAKE_CASE`, defined once in `p2b/core/vocabulary.py` |
| Events | `module.noun_verbed` past tense (`requirement.submitted`) |
| Endpoints | `/api/v1/` plural nouns; transitions as verb sub-resources (`/submit`, `/choose`); never PATCH a `state` field |
| Error codes | `UPPER_SNAKE_CASE` from the list in API_ARCHITECTURE section 1 |
| Ubiquitous language | Terms from DOMAIN_ARCHITECTURE section 2, identical in code, tables, API and UI (Enquiry is not Lead; Package is not Instalment; Payment mark is not Payment) |

## 6. Database

1. Every schema change is an Alembic migration with a hand-reviewed upgrade and a downgrade (or `irreversible` with the manual path written in the PR).
2. Expand-contract for anything running code depends on; no rename in one step; indexes on existing tables `CONCURRENTLY`.
3. UUIDv7 primary keys from `p2b.core.ids.new_id()`; `created_at`, `updated_at` as `timestamptz`; `version integer` on mutable aggregates.
4. State columns are `text` with a CHECK constraint generated from the vocabulary; no Postgres enums.
5. Foreign keys declared, `ON DELETE RESTRICT` by default. Business uniqueness is a constraint, never only a check in code.
6. Append-only tables (`audit_events`, `security_events`, `*_events`, `outbox_events` except its processing columns) are protected by the immutability trigger and by grants.
7. JSONB only with a `schema_version` and never holding a foreign key or a filtered field in a hot path.
8. Money is `numeric(14,2)` with `currency`. No column ever holds a payment amount between homeowner and professional (CD-09).
9. Every new query used by a screen has an index; the PR carries its `EXPLAIN`. No `SELECT *`. No N+1: screen endpoints declare a statement budget and a test counts statements.
10. Lists use keyset pagination on `(created_at, id)`.
11. Seed and reference data ship as versioned, idempotent data loads, never edited in place once published.
12. Privacy class (P0 to P3) of every new column is written in DATA_ARCHITECTURE; P2 and P3 never reach logs, analytics or AI providers.

## 7. API

1. Base path `/api/v1/`; additive changes only; breaking changes go to `/api/v2/` with both served.
2. Pydantic `...Request` and `...Response` models for every endpoint; response models per audience where fields differ. Never return ORM objects or `dict` built ad hoc.
3. Error envelope `{"error": {"code", "message", "details", "request_id"}}` from the shared handlers; no stack traces or internals in responses.
4. Validation at the boundary (422 `VALIDATION_ERROR` with `fields`); business preconditions in services (409).
5. Every POST that creates or transitions accepts `Idempotency-Key`; mutating requests on stateful resources carry `version`.
6. Times ISO 8601 UTC; money as strings with two decimals plus `currency`; ids as UUID strings.
7. OpenAPI is the contract. The web app uses only the generated client in `packages/contracts`; hand-written request or response types are forbidden.
8. OpenAPI UI is off outside LOCAL.

## 8. Authorisation

1. Every route declares exactly one rule dependency from `p2b.identity.interface`: `public_route`, or `require_actor(...)` with audience, roles and MFA. A test walks every registered route and fails if one lacks a rule.
2. Order: session, account status, audience, role, MFA, ownership or project membership, state, version.
3. Project-scoped queries always join the actor's membership. An object outside the actor's visibility returns 404, a visible object without the right returns 403.
4. Roles come from the database, never from the client. The UI hiding a button is not a control.
5. Each new endpoint adds rows to the authorisation matrix test (own, foreign, anonymous, wrong audience at minimum).
6. Response shaping is by model, never by deleting fields after serialisation.

## 9. State transitions

1. States change only through the module's transition table (`p2b.core.state_machine`), checked in the service before any write.
2. A transition not in the table returns 409 `STATE_CONFLICT` with the current state. Overrides only where the table marks `override_allowed`, only with a reason, audited with `is_override`.
3. A transition, its audit row, its ledger event row (where the entity has one) and its outbox event are one transaction.
4. Terminal and important records are never hard-deleted.
5. Every machine's table has a test that tries every disallowed pair.

## 10. Audit and events

1. Every transition, override, approval, configuration publish, permission change, admin action and private-document view writes `audit_events` in the same transaction, through `p2b.audit.interface.record`.
2. Security-relevant events (logins, OTP failures, lockouts, revocations, CSRF and webhook rejections, permission denials) go to `security_events`.
3. Domain events go through `p2b.core.outbox.publish` inside the business transaction. Names and payloads are added to EVENT_AND_BACKGROUND_JOB_ARCHITECTURE section 4 in the same PR.
4. Event payloads carry ids and facts, never P2 or P3 data.
5. Event handlers and jobs are idempotent: re-read state, check the precondition, write once by constraint.

## 11. Files

1. Clients never choose object keys or paths; keys come from `{env}/{purpose}/{yyyy}/{mm}/{file_uuid}`.
2. Uploads are presigned PUT bound to declared type and size; nothing is served before sniff and scan mark it `AVAILABLE`.
3. Downloads are presigned GET issued after authorisation, 15 minutes (5 for P3), never logged with the query string.
4. Objects are never overwritten or deleted outside the prune job's narrow paths.
5. No file bytes stream through the VPS request path.

## 12. Background jobs

1. A job is a function in the owning module's `jobs.py`, registered with the Procrastinate app, receiving ids only.
2. Request handlers never enqueue jobs. They publish outbox events; relay handlers enqueue jobs.
3. Every provider call has connect and read timeouts; retries only inside jobs with backoff.
4. Every periodic job writes `job_runs`; failures land in the failed state with a `job_failures` row.
5. Scheduled transitions check current state before acting and compare against database time.

## 13. Errors

1. Raise typed errors from `p2b.core.errors` (`NotFound`, `Forbidden`, `StateConflict`, `VersionConflict`, `ValidationFailed`, ...); the handlers map them to the envelope.
2. Unexpected exceptions return 500 `INTERNAL` with the request id, are logged with context and sent to Sentry.
3. Never swallow an exception silently. Never use a bare `except`.

## 14. Logging

1. Structured JSON through `structlog` with request id, user id, route, status, duration.
2. Only allow-listed fields reach logs. Never contact values, names, addresses, OTP codes, tokens, cookies, presigned URLs, document contents or request bodies.
3. `404` is not an error-level event. Business rejections are `info`; failures of our own code are `error`.

## 15. Testing

1. Tests ship in the same PR as the code. A feature without tests is not done.
2. For every slice: unit, service (real Postgres with PostGIS), API contract, authorisation matrix, state-transition, migration up and down, web unit, and Playwright end to end for the flow.
3. Tests derive from STATE_MODEL, API_ARCHITECTURE, SECURITY and the flow's acceptance criteria; cite them in test names or docstrings.
4. The S06 critical tests (TESTING section 3) exist from the first slice that touches their subject.
5. No test depends on order, wall-clock time (use the injected clock or `freezegun`), the network, or real providers.
6. Coverage gate 85% on `service.py` files; coverage never decreases on a PR.
7. Never claim a test passes unless it ran.

## 16. Dependencies

1. A new dependency needs a reason in the PR: what it replaces, its maintenance status, licence, and size. Fewer than about 20 clear lines of our own code beats a dependency.
2. Security-critical work (crypto, auth primitives, payments, parsing real formats, drivers) uses established libraries; small pure domain logic is written in-house.
3. Lockfiles (`uv.lock`, `pnpm-lock.yaml`) are committed; versions are pinned; upgrades are their own PRs.
4. Anything in baseline section 5's "not in the stack" list needs an ADR first.

## 17. Security

1. Secrets come from the environment through `p2b.core.config`; `.env` files are never committed; `.env.example` lists every variable.
2. No auth token in browser storage; cookies HttpOnly, Secure, SameSite=Lax, host-only.
3. State-changing cookie requests pass the CSRF check; no state change on GET.
4. Raw SQL only with bound parameters; no string-built SQL.
5. No `dangerouslySetInnerHTML`; user text is escaped everywhere, including PDF templates.
6. Rate limits on every public and authentication endpoint per API_ARCHITECTURE tiers.
7. Webhooks verify signatures on the raw body before parsing and are idempotent by provider event id.
8. gitleaks, pip-audit, pnpm audit and Trivy run in CI; findings block the merge.

## 18. AI and recommendation

1. AI and model output lands in a reviewable state; only a person's action or a rule-based transition changes business state.
2. Structural design is never sent to or accepted from an AI provider; generated views are never authoritative and never attached where a drawing is required.
3. No brand recommendation, no paid signal, no price ranking, no hidden signal: the configuration validator enforces it and its deny-list test must pass.
4. Every recommendation is reproducible from its stored snapshot, configuration version and seed, and carries written reasons.
5. No personal data in any prompt or provider request; tests assert it.
6. No language model at the POC. The concept floor plan path (PD-28, ADR-025) uses none; natural-language editing waits for an amendment to this rule.
7. Concept floor plans (PD-28): generated only by the deterministic `houseplans` engine; never presented, referenced or exported unless the independent validator reports no errors; `is_authoritative` is false by CHECK; rule values only from a PUBLISHED layout ruleset in production.

## 19. Frontend

1. One Next.js app; host routing in one place; a route group never renders on another audience's host.
2. Server components fetch from the API with the user's cookie forwarded; client components only where interaction needs them.
3. All user-facing strings in message files (English at the MVP, ADR-022); no string literals in JSX.
4. Forms: react-hook-form with zod schemas derived from or checked against the generated contract; the server remains the validator of record.
5. No auth logic or role checks as security in the client; the UI reflects what the API returns.
6. No client state library beyond React and SWR.
7. Images through the custom loader; no Next.js image optimiser on the VPS.

## 20. Accessibility

1. WCAG 2.2 AA for every screen: semantic HTML, labels on every input, visible focus, keyboard operable, colour contrast 4.5:1 for text.
2. Errors are announced (`aria-live`) and tied to their field (`aria-describedby`).
3. Touch targets at least 44 by 44 CSS pixels; usable at 360 px width.
4. axe checks run in the end-to-end suite on the main screens; violations fail the nightly run.

## 21. Performance

1. Targets in PERFORMANCE_ARCHITECTURE section 1 (public LCP 2.5 s p95 on 4G mid-range Android; API reads 300 ms p95; writes 500 ms p95).
2. Bundle budgets: 170 KB JavaScript gzipped on public pages, 250 KB on authenticated pages.
3. Anything over about 300 ms of CPU runs as a job.
4. Responses under 200 KB; lists capped at 100 items.

## 22. Deployment

1. `main` is always deployable; short branches; squash merges; CI green and one review.
2. Images are built once in CI and promoted by digest; production deploys from a `v*` tag after approval.
3. Migrations run as a one-shot step before the services restart; code must work against the schema before and after its own migration.
4. No production credentials outside the production VPS and the owner's password manager; no real client data outside production.

## 23. Forbidden implementation patterns

1. Inventing a field, option, state, role, window, price, rule or message the sources do not give.
2. Changing a state by assignment outside the transition table, or a PATCH of a `state` field.
3. A route without an authorisation rule; a project-scoped query without the membership join.
4. Authorisation, pricing or eligibility decided in the browser.
5. JWT or any token in `localStorage`, `sessionStorage`, IndexedDB (except the auditor PWA's inspection queue, which holds no credentials) or a non-HttpOnly cookie.
6. Files in Postgres; client-chosen object keys; public URLs for private objects.
7. Request handlers calling providers that the user is not waiting on, or enqueueing jobs directly.
8. Payment amounts between homeowner and professional anywhere (CD-09); any path that moves construction money (CD-01).
9. Brand recommendation, price-ranked or price-sorted listings, paid prominence, star ratings.
10. AI-generated drawings or structural design; a model output that commits a business state. (A PD-28 concept floor plan is computed by a deterministic engine and is not a drawing; it is governed by section 18 rule 7.)
11. Hard deletes of transactional or audit records; UPDATE on append-only tables.
12. P2 or P3 data in logs, events, analytics or provider requests.
13. String-built SQL; `dangerouslySetInnerHTML`; shell calls with user input.
14. Hand-written API types in the web app.
15. Components from baseline section 5's exclusion list, or new infrastructure, without an ADR.
16. Fake screens: a UI that does not call the real API and database.
17. Claiming something is implemented, tested or deployed when it is only designed, written or built.

## 24. Definition of done for a slice

1. Database, service, API, authorisation, frontend, validation, audit and events implemented end to end against the real stack.
2. Tests in section 15 written and passing in CI.
3. OpenAPI regenerated; contracts package updated; no unmarked breaking change.
4. Blueprint documents updated where the slice settled a detail (open-points tables, DATA amendments, event catalogue).
5. Session report lists what was built, what was verified and how, and what remains.
