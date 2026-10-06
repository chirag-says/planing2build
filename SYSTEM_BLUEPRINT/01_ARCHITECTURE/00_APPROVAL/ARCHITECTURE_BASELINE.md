# Plan2Build: architecture baseline for implementation

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/01_ARCHITECTURE/00_APPROVAL/ARCHITECTURE_BASELINE.md` |
| 1. Status | Baseline for implementation. Effective for engineering work from the date below. Chirag's signature (section 25) is pending; until he signs, every item marked "decided by delegation" stays reversible at his word. |
| 2. Version | 1.2 (2026-10-04: Chirag's final rulings: B-02 decided and the question set locked; Handover 1 and 2 defined; D-03 and D-04 ruled; slice 1 built; new launch blockers M-01, M-02, S-01, W-01). 1.1 earlier the same day: B-01, B-03, rate card |
| 3. Effective date | 2026-10-04 |
| Prepared by | Sakha (lead architect), from a full read of `01_ARCHITECTURE/` (17 documents, 22 ADRs), `IHB_FLOW.md` v1.2, `PROFESSIONALS_FLOW.md` v1.2, `RECOMMENDATION_ENGINE.md` v0.1, and an audit of `SOURCE_OF_TRUTH/` (S04, S05, S14, S23 checked against the blueprint) |
| What this document does | Converts the v0.1 architecture proposal into the baseline that code is written against. It does not restate the architecture; it names what is fixed, what is open, and what blocks what. Where it is silent, the architecture document named in the row governs. |
| Companion | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/IMPLEMENTATION_CONTRACT.md` (the rules code must follow); `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/FOUNDATION_PLAN.md` (repository audit, foundation design, slice 1 readiness) |

## 4. Source authority hierarchy

| Rank | Source | Notes |
|---|---|---|
| 1 | Client decisions CD-01 to CD-28 (`IHB_FLOW.md` section 32.2, identical in `PROFESSIONALS_FLOW.md` section 43.2) | CD-25 to CD-28 are Chirag's decisions or designs delegated to Sakha; they count as decided for the MVP and carry "Proposed answer" until Chirag reviews them |
| 2 | `IHB_FLOW.md` v1.2 | Section 33 is the MVP flow; sections 1 to 31 record what the sources say |
| 3 | `PROFESSIONALS_FLOW.md` v1.2 | Section 44 is the POC flow |
| 4 | `RECOMMENDATION_ENGINE.md` v0.1 | |
| 5 | Approved architecture decisions: this baseline, then ADR-001 to ADR-022 | An ADR governs over the narrative documents where they differ (example in section 21, item N-04) |
| 6 | Other `01_ARCHITECTURE/` documents | Equal rank among themselves; a disagreement between two of them is a conflict to record, not to resolve silently |
| 7 | `SOURCE_OF_TRUTH/` (S01 to S25) | Evidence, read-only; the D1 and D3 directions are evidence, not authority |
| 8 | General engineering knowledge | Only where ranks 1 to 7 are silent, and never for business rules |

A conflict is reported with both statements, the higher-ranked source, and whether it blocks. Section 21 and 22 list the conflicts found while preparing this baseline.

## 5. Approved technology stack

ALREADY DECIDED (Chirag's baseline, 2026-10-03; rationale in `TECH_STACK_AND_RATIONALE.md`).

| Layer | Baseline | Version pin for implementation (checked 2026-10-04) |
|---|---|---|
| Web | Next.js App Router, TypeScript, Tailwind CSS, one app for three hosts, PWA for the auditor module only | Next.js 16.x, React 19.x, Tailwind 4.x, TypeScript 5.x (7.x is out but its tooling compatibility with Next.js is unproven; revisit) |
| Forms | react-hook-form with zod | zod 4.x |
| API | FastAPI, Python, Pydantic v2, SQLAlchemy 2 async with asyncpg, Alembic, structlog, httpx | Python 3.12 in images (ADR-002); local development may run 3.13; code must run on both |
| Jobs | Procrastinate on Postgres plus a transactional outbox | Procrastinate 3.x |
| Database | PostgreSQL 16 on Supabase (Mumbai); PostGIS, pg_trgm, pgcrypto, pg_stat_statements | Local: `postgis/postgis:16-3.5` container |
| Files | Cloudflare R2 through boto3, private buckets, presigned URLs | |
| Cache and limits | Upstash Redis for rate limits only, with a Postgres fallback | |
| Edge and proxy | Cloudflare, Caddy | |
| Hosting | One Hostinger KVM 2 VPS, Docker Compose, staging stack beside production | |
| Observability | Sentry, Grafana Cloud free (Alloy), UptimeRobot | |
| Testing | pytest, Schemathesis, Vitest, Testing Library, Playwright, k6 | |
| Providers | Razorpay Checkout, Resend, OpenStreetMap stack, ClamAV, Gemini image API behind an adapter | |

Not in the stack (README section 8, `SCALABILITY_AND_MIGRATION_PLAN.md` section 5): Kubernetes, microservices, Kafka or any broker, OpenSearch, MongoDB, managed queues, service mesh, multi-region, native apps, self-hosted image models, Redis as a primary store, read replicas, Supabase Auth, Storage or RLS, H3, a routing engine (until AQ-21), WebSockets, GraphQL, CQRS or event-sourcing frameworks. Adding any of these needs an ADR and a measured trigger.

## 6. Approved infrastructure topology

ALREADY DECIDED. `SYSTEM_ARCHITECTURE.md` section 4 and `CLOUD_AND_HOSTING_ARCHITECTURE.md` sections 1 to 8. Browser to Cloudflare to Caddy on one VPS; Caddy routes `/api/v1/*` to FastAPI and everything else to Next.js; the worker runs the API image with a different command; Postgres on Supabase, files on R2, rate limits on Upstash. Staging is a second Compose stack on the same VPS with its own Supabase project, buckets and secrets. Only Caddy publishes ports.

## 7. Approved application topology

ALREADY DECIDED (ADR-001, ADR-016; host split by Chirag 2026-10-03).

| Host | Audience | Session cookie | Route group |
|---|---|---|---|
| `plan2build.in` | Public, homeowners, household members | `__Host-p2b_ihb_session` | `(ihb)` |
| `professionals.plan2build.in` | Every professional role, auditor PWA under `/inspections` | `__Host-p2b_pro_session` | `(pro)` |
| `admin.plan2build.in` | Operations and admin, MFA required | `__Host-p2b_ops_session` | `(ops)` |

The API is same-origin at `/api/v1` on each host. `/api/v1/admin/*` is reachable only from the admin host. The API derives the audience of an unauthenticated request from the validated `Host` header and of an authenticated request from the session; a mismatch is rejected. Host spelling is AQ-01 (non-blocking: hosts are configuration).

## 8. Approved domain and module structure

ALREADY DECIDED (ADR-008, `DOMAIN_ARCHITECTURE.md`). A modular monolith with 24 modules: `core`, `identity`, `projects`, `catalog`, `specification`, `buildplan`, `design`, `professionals`, `leads`, `rfq`, `recommendation`, `construction`, `variations`, `money`, `assurance`, `issues`, `records`, `billing`, `documents`, `notifications`, `messaging`, `audit`, `ops`, `analytics`. Each module owns its tables; other modules use its `interface.py` or its events; `core` imports no module; `integrations` import no module; `recommendation/core` imports nothing from the application. Adding a module is an architecture change.

Modules are created when their first slice needs them, not in advance. An empty module package is not created to "reserve" a name.

## 9. Approved database direction

ALREADY DECIDED (ADR-003, ADR-004, `DATA_ARCHITECTURE.md`).

- PostgreSQL is the only system of record. One application schema (`public`). Files are never in Postgres.
- UUIDv7 primary keys generated in the application; human codes where people read them.
- States are `text` with CHECK constraints generated from one Python vocabulary; never Postgres enums.
- `version integer` on every mutable aggregate; stale writes return 409 `VERSION_CONFLICT`.
- Append-only tables have no UPDATE or DELETE grant for `app_rw`; this baseline adds a trigger that raises on UPDATE or DELETE as a second layer, so the rule holds in local and test databases where the roles are not separated.
- JSONB only for payloads versioned by a `schema_version` column and never used in joins (DATA section 1, principle 3).
- Money `numeric(14,2)` INR. No payment amounts between homeowner and professional exist anywhere (CD-09).
- Expand-contract migrations; every migration has a downgrade or is marked irreversible with a written manual path.
- Procrastinate's tables live in `public` with their `procrastinate_` prefix (DATA section 4.1 lists them that way; section 1 principle 2 mentions a separate schema; the library default is used; non-blocking).
- Supabase is Postgres only. Connection: transaction pooler for the API (asyncpg with the statement cache disabled), session mode for the worker.

## 10. Approved authentication model

ALREADY DECIDED (ADR-010, `SECURITY_ARCHITECTURE.md` section 3; Chirag 2026-10-03).

- Email OTP at the MVP; six-digit code, argon2id-hashed with a pepper, 10-minute validity (AQ-03 default, non-blocking: Chirag chose "OTP", and a link is a later option); phone numbers collected and verified from day one; SMS later behind the same interface.
- Server-side sessions: 256-bit random token in an HttpOnly, Secure, SameSite=Lax, host-only `__Host-` cookie; only `sha256(token)` stored; idle and absolute lifetimes per audience (homeowner 14 d and 90 d; professional 7 d and 30 d; operations 12 h and 24 h); immediate revocation.
- TOTP MFA for operations, admin and the structural engineer's sign-off; re-verification every 8 hours and before privileged actions.
- No JWT in the browser, no token in any browser storage, no Supabase Auth, no passwords.
- CSRF: SameSite=Lax plus `X-Requested-With: plan2build` and an `Origin` matching the host on every state-changing cookie request.

## 11. Approved file and storage architecture

ALREADY DECIDED (ADR-006, ADR-011). Server-generated keys `{env}/{purpose}/{yyyy}/{mm}/{file_uuid}`; immutable objects; presigned PUT bound to type and size; sniff, scan, re-encode before `AVAILABLE`; presigned GET of 15 minutes (5 for P3); share tokens hashed and revocable; public bucket only for approved listing images. The VPS never streams file bytes. Implementation note (1.2): uploads land under `incoming/` and the worker writes the checked object to the final key, so nothing unchecked is ever at a served key; locally the S3 store is SeaweedFS because MinIO no longer publishes images (FOUNDATION_PLAN N-27).

## 12. Approved events and jobs architecture

ALREADY DECIDED (ADR-009, `EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md`).

- A domain event is an `outbox_events` row written in the same transaction as the business change. That is the only way a module tells another module or the outside world that something happened.
- The relay runs in the worker, claims unprocessed rows with `FOR UPDATE SKIP LOCKED`, calls the subscribed handlers, and marks rows processed. Handlers are idempotent; delivery is at least once.
- Implementation note (clarifies TECH_STACK section 2, which says a job is enqueued "in the same transaction as the business write"): Procrastinate can join an external transaction only through psycopg, and the API uses asyncpg (ADR-002). The transactional guarantee is therefore carried by the outbox: request handlers never enqueue jobs directly; handlers in the relay enqueue them. The outcome the architecture asks for holds: a job exists only if the business change committed.
- Named queues `priority`, `notify`, `render`, `files`, `ai`, `engine`, `maintenance`; jobs receive ids only; retries with backoff; failed jobs are the dead-letter state.

## 13. Approved AI and recommendation boundaries

ALREADY DECIDED (CD-18, CD-25, CD-28; ADR-012, ADR-013; `AI_AND_RECOMMENDATION_ARCHITECTURE.md`).

| Rule | Consequence in code |
|---|---|
| Structural design is never generated by AI (BR-055) | No code path sends structural artefacts to, or accepts them from, an AI provider |
| 3D views are illustrative and never authoritative | `is_authoritative = false` on every `VIEW_3D`; BOQ, RFQ and quotes read only authoritative artefacts; attachment points are typed |
| Drawings govern | Approved dimensioned drawings are the measurement source |
| Recommendations are reviewed by Plan2Build's team before a homeowner sees them (POC) | `team_review_required = true`; no auto-approval path is built at the POC |
| Explainable | No recommendation is shown without at least two written reasons from templates with evidence values |
| No paid influence, no brand recommendation, no price ranking, no hidden signal | Signals come from an allow-list; a tested configuration validator rejects brand item types, payment-derived signals and price-sorted rules |
| Reproducible | Every request stores snapshot, configuration version and seed; `recompute(request_id)` must reproduce the result (CI test) |
| No model output creates an irreversible business state | Model output lands in a reviewable state (`PENDING` review, `COMPUTED`); only a person's action or a rule-based transition moves the business state |
| No personal data to AI providers | Prompt builder tests assert the absence of P2 and P3 fields |
| No language model at the POC | Reasons are template-rendered |

## 14. Approved security principles

ALREADY DECIDED (`SECURITY_ARCHITECTURE.md`). Authentication, then authorisation, then business logic, on the server, every request. Deny by default: every route declares its rule, and a test fails any route without one. Project isolation by membership on every project-scoped query; 404 outside visibility. Response models per audience (auditor never sees supplier or brand; contractor never sees another quote; homeowner never sees contractor internal costs). Every transition and override writes an audit row in the same transaction. Secrets from the environment only; nothing secret in images, the client bundle, logs or Sentry. Webhooks verified on the raw body and idempotent by provider event id.

## 15. Approved observability approach

ALREADY DECIDED (ADR-017, `OBSERVABILITY_AND_OPERATIONS.md`). Structured JSON logs with an allow-list of fields and a request id from Caddy through Next.js, FastAPI and jobs; Sentry for errors (PII off); Grafana Cloud for metrics and logs; UptimeRobot for availability. `/healthz` (process) and `/readyz` (database reachable, migrations at head) unauthenticated. Audit and security events in Postgres.

## 16. Approved testing approach

ALREADY DECIDED (`TESTING_ARCHITECTURE.md`). Tests are written with the code they cover. Layers: unit, service against real Postgres with PostGIS, contract (OpenAPI, Schemathesis), authorisation matrix generated from the route registry, response-shape snapshots per audience, job idempotency, provider adapters against fixtures, web unit, Playwright end to end, migration up and down. The S06 critical tests (TESTING section 3) exist from the first slice that touches their subject. Coverage gate 85% on `service.py` files.

Local tests use a disposable Postgres with PostGIS (Compose service), not testcontainers, so a developer without Docker-in-Docker can still run them; CI uses a service container. This is a tooling choice inside the decided approach.

## 17. Approved deployment approach

ALREADY DECIDED (ADR-014, `ENVIRONMENT_AND_DEPLOYMENT.md`). Trunk-based; CI on every push; images built once and promoted by digest; staging on merge to `main`; production on a `v*` tag after manual approval; migrations as a one-shot container before the worker, API and web restart with health waits; rollback by redeploying the previous tag. Task runner: root `package.json` scripts (pnpm) instead of the `make` targets named in ENVIRONMENT section 9, because the development machine is Windows without `make`; the commands are the same.

## 18. Explicit POC scope

From `IHB_FLOW.md` section 33 and `PROFESSIONALS_FLOW.md` section 44, Raipur only:

- Public website (English), free cost estimate, entry actions, registration by email OTP.
- New-home projects only (CD-03); requirement capture with multiple-choice answers and a priority ranking (CD-02, CD-28); Plan2Build review; project workspace (16 stages, 67 decisions).
- Quote review for homeowners already holding a quote (CD-04); one package with Build Plan, quote review and comparison, stage inspections; paid at once or per milestone through Razorpay Checkout (CD-05, CQ-03 answered).
- Build Plan with concept drawings (team-made, checked) and generated 3D views (illustrative); structural sign-off by the engineer.
- Specification decisions with OTP acknowledgement; decisions calendar.
- Own contractor with basic verification and project-only access; Champions Club; contractor listing with leads to at most three (CD-26); recommendation engine with team review.
- Standard RFQ, quote versions with validity dates, scope-normalised comparison with recommendation, selection by OTP.
- Build tracking with standard updates; materials ledger (verification only); variations with qualification, OTP acknowledgement, discussion and closure; money position with marks and no payment amounts.
- Gate inspections through the auditor PWA; non-conformances; issue log; disputes by operations.
- Handover and the permanent build record; back-office opt-ins for coming-soon services.
- Operations console with MFA; notifications by email and in-app.

## 19. Explicit POC exclusions

Construction money through the platform, escrow, Razorpay Route (CD-01); payment amounts between homeowner and professional (CD-09); project types other than new homes (CD-03); material supply (CD-13); the matched marketplace (CD-22); the brand dashboard (CD-23); ratings and reviews (CQ-17, until answered); post-handover service orders (CD-12); Hindi UI (ADR-022); native apps (ADR-021); SMS and WhatsApp channels (until enabled); payment links and subscriptions; lead allocation by min-cost flow and learned ranking (engine phase 2); AI-generated drawings or structural design; any language model; price ranking or price sort anywhere; paid prominence.

## 20. Approved ADR list

All 22 ADRs are part of this baseline. Status after this baseline: "Accepted for implementation, pending Chirag's signature" for all; the "decided by" column shows where Chirag's word already exists.

| ADR | Title | Decided by |
|---|---|---|
| 001 | Next.js, one app, three hosts | Chirag (hosts); proposal accepted |
| 002 | FastAPI and Python | Chirag (baseline) |
| 003 | PostgreSQL only | Chirag (baseline) |
| 004 | Supabase Postgres only; Free then Pro | Chirag (plan timing) |
| 005 | Hostinger VPS with Compose; staging beside production | Chirag |
| 006 | R2 for files | Chirag (baseline) |
| 007 | Upstash Redis for rate limits only | Chirag (baseline), Sakha (scope) |
| 008 | Modular monolith | Chirag (preference), Sakha |
| 009 | Postgres queue and outbox | Delegated to Sakha by Chirag |
| 010 | Email OTP, server sessions, TOTP MFA | Chirag |
| 011 | File architecture | Sakha, inside Chirag's rules |
| 012 | Recommendation module | Delegated to Sakha (CD-28) |
| 013 | Image generation adapter; views never authoritative | Chirag (CD-25), Sakha (method) |
| 014 | CI and CD | Chirag (GitHub Actions), Sakha |
| 015 | Search and geosearch in Postgres | Sakha |
| 016 | Cloudflare, Caddy, same-origin API | Chirag (Caddy), delegated (same origin) |
| 017 | Sentry, Grafana Cloud, UptimeRobot | Chirag |
| 018 | WeasyPrint (superseded by ADR-023, 2026-10-05) | Sakha |
| 019 | Monorepo and generated contracts | Sakha |
| 020 | Providers | Chirag (Razorpay Checkout, Resend, OSM) |
| 021 | Auditor offline PWA | Chirag |
| 022 | English only, strings externalised | Chirag |
| 023 | fpdf2 for issued PDFs (supersedes 018) | Chirag (2026-10-05) |
| 024 | `engagements` replaces `leads` in the module list (amends 008) | Chirag (2026-10-06) |

## 21. Blocking open decisions

Rulings received from Chirag on 2026-10-04: B-01 approved as recommended; B-03 approved (user created only after OTP verification; DATA, STATE_MODEL, API and SECURITY amended to version 0.2); B-02 not approved: a traced proposal was required first and is in `02_IMPLEMENTATION/REQUIREMENT_QUESTIONS_V1.md`, awaiting his approval. The rows below keep the original analysis with the outcome added.

Classification: BLOCKING BEFORE CODING applies to the named scope only. Nothing below blocks the foundation (repository, API and web skeletons, database and migrations, sessions, authorisation framework, outbox, worker, logging, errors, tests, CI). Each item blocks the slice or module named.

| ID | Blocks | Conflict or gap | Sources | Recommended decision |
|---|---|---|---|---|
| B-01 (DECIDED, Chirag 2026-10-04: as recommended) | Slice 1 end point | The requested slice runs "initial project requirements → homeowner workspace". The workspace (16 stage instances, 67 lines) is created only after Plan2Build's team accepts the submission: "The Plan2Build team reviews; nothing is published automatically" (IHB_FLOW 33.1 step 8, [S]); STATE_MODEL section 5: `SUBMITTED → ACCEPTED` by Operations, "workspace instantiation succeeds"; DOMAIN 6.1. Building the workspace directly after submission would invent a transition. | IHB_FLOW rank 2 over the slice wording | Slice 1 ends at SUBMITTED with the homeowner's project dashboard (status, answers, next action). Slice 2 adds the operations review on the admin host (MFA), `ACCEPTED`, and workspace instantiation. |
| B-02 (DECIDED, Chirag 2026-10-04: final rulings R-1 to R-15; `REQUIREMENT_QUESTIONS_V1.md` v2.0 LOCKED, section L is the implementation version; seeded as question set version 1 and implemented) | Slice 1 requirement step | The requirement questions and their options are open (OQ-039; CD-02 fixes only the multiple-choice format). Sources give field names (S05, S06, S07) and some options (S23c services and styles; S14 finish levels), but the budget, timeline and property-type lists are not legible or not given, and sources conflict (S23c has no floors or quality tier; S05 requires both; S23c offers renovation and material supply, which CD-03 and CD-13 exclude). | IHB_FLOW 8.7, 32.5; S05, S23c | Build the form engine data-driven (a versioned question set in the catalog). Sakha drafts question set v1 from the sources, with each option traced to its source and every gap marked, for Chirag to approve. The slice ships only with an approved version. |
| B-03 (DECIDED, Chirag 2026-10-04: user created only after successful OTP verification; documents amended; implemented) | Slice 1 registration | API section 2 creates the user only when the OTP is verified ("returns 200 even for unknown contacts ... a new contact registers on verification"). DATA section 4.2 binds `otp_challenges.contact_id` to an existing `user_contacts` row, which requires the user to exist before verification. STATE_MODEL section 2 allows either reading. | Two rank-6 documents disagree | Store the challenge against the normalised contact (encrypted value plus a lookup hash), not a contact row; create the user, contact and session in one transaction at verification, recording the `(new) → PENDING_VERIFICATION → ACTIVE` transitions in audit. Keeps enumeration resistance and creates no account rows for mistyped emails. Requires a one-line amendment to DATA 4.2. |

## 22. Non-blocking deferred decisions

### 22.1 NON-BLOCKING / CAN IMPLEMENT (default applies; reversible by configuration or a small change)

| ID | Item | Default used |
|---|---|---|
| N-01 | AQ-01 host spelling | `plan2build.in` and subdomains as configuration |
| N-02 | AQ-03 OTP code or link | Six-digit code, 10 minutes |
| N-03 | AQ-05 row-level security | Application layer only; `project_id` kept on every scoped row |
| N-04 | Cookie names: API section 1 and SYSTEM section 5 say `p2b_ihb_session`; ADR-010 and SECURITY 3.2 say `__Host-p2b_ihb_session` | ADR-010 (higher rank). Local HTTP development without TLS drops the prefix and `Secure` by configuration only in the LOCAL environment |
| N-05 | Estimator rate card | Ruling, Chirag 2026-10-04: the prototype rates are not production Raipur rates. Implemented as a DEMO card (`rate_cards.is_demo = true`, label starting "DEMO:") loaded only by a command that refuses production; demo cards are never served in production and every estimate from one carries `is_demo`. The engine is implemented; real rates are later blocker D-16 |
| N-06 | Estimator input bounds (OQ-043) | API section 3: area 300 to 12,000 sq ft, floors G to G+3, finish Standard, Premium, Luxury |
| N-07 | Estimate PDF by contact (OQ-042) | Deferred out of slice 1; the estimate is shown on screen and stored with its rate-card version |
| N-08 | Enquiry statuses and the "Talk to an expert" channel (OQ-025, OQ-034) | `enquiries` row plus an operations queue item; follow-up by the team outside the platform; an enquiry links to an account when the same contact registers |
| N-09 | Python 3.13 locally, 3.12 in images | Code and CI target 3.12; local runs on 3.13 are allowed |
| N-10 | Procrastinate tables in `public` | Library default |
| N-11 | `make` versus pnpm scripts | pnpm scripts at the root |
| N-12 | Transactional enqueue through the outbox (section 12) | As described |
| N-13 | AQ-07 staging email | Allow-list only |
| N-14 | AQ-13, AQ-14 digest and reminder steps | Documented defaults |
| N-15 to N-20 | Implementation notes from the foundation: host segments instead of route groups, `use-intl` instead of next-intl (also recorded in TECH_STACK section 2 and ADR-022), `X-Forwarded-Host` for the audience, `psycopg[binary]`, the Windows event loop, FastAPI's nested routers | `FOUNDATION_PLAN.md` section 3 |
| N-21 to N-25 | Implementation notes from the OTP work: the OTP email template is a file until the `notifications` module exists; CSRF applies to every state change (login CSRF); OTP challenge transitions are logged in `security_events`; rate limits on Postgres until Upstash is provisioned; the contact lock reads "10 failed challenges" as 10 wrong codes in a sliding hour | `FOUNDATION_PLAN.md` section 3 |

### 22.2 DEFERRED TO LATER PHASE (blocks the module named when its slice starts)

| ID | Blocks | Open point |
|---|---|---|
| D-01 | `billing` | CQ-01 price and instalments; CQ-04 refunds; AQ-11 and AQ-20 invoice format |
| D-02 | Quote-holder path | CQ-02 |
| D-03 (DECIDED in part, Chirag 2026-10-04) | `specification` seed | Ruled: the brand category is dropped from the five structural lines A04, A05, A09, A12 and A13, with no replacement brand or vendor concept. Still open: the A01 point recorded in 1.1 (S04 rule R9 omits A01); the ruling did not cover it, so it goes to Chirag with the 67-line seed (slice 2) |
| D-04 (DECIDED as a model, Chirag 2026-10-04; values open) | Workspace instantiation (slice 2) | Ruled: no invented durations. A versioned stage master configuration holds code, name, sequence, default duration and cost share, each version DRAFT, ACTIVE or RETIRED (built in migration 0004; version 1 has the 16 S04 names and NULL durations and cost shares). A stage without a duration shows "Schedule to be confirmed"; planned dates come only from an approved configuration or an operations-entered schedule. Still open: the duration and cost-share values themselves, and who approves a configuration version |
| D-05 (later blocker, tracked) | `assurance` | No checkpoint masters exist in any source; CQ-15 auditor ID; AQ-23 auditor MFA |
| D-06 | `variations` | CQ-12 window and closure authority |
| D-07 | `money` | CQ-13 marks and contractor view |
| D-08 | `buildplan`, `design` | CQ-22 structural scope; CQ-26 who checks drawings; AQ-15 image provider; AQ-18 issue without views |
| D-09 | `recommendation`, `design` funding | CQ-24; AQ-17 fit-label thresholds; expert weights signed off by the team |
| D-10 | `professionals`, `leads` | CQ-07 enlistment class; CQ-08 joining routes live; CQ-23 failed own-contractor verification |
| D-11 | Hindi | AQ-10 with the client |
| D-12 | Production launch | AQ-09 secrets owner; AQ-35 account ownership; Supabase Pro; Razorpay live KYC; Resend domain; penetration test; restore drill (README launch checklist) |
| D-13 | CI running on GitHub | AQ-29 repository owner and deploy approver (workflows are written; they run once the repository exists) |
| D-14 | Other AQs (02, 04, 06, 08, 12, 16, 19, 21, 22, 24 to 28, 30 to 34) | Each in the document that raised it |
| D-16 | Public estimator release | Production Raipur rate card: values, approver and shape (the S14 formula, or S05 section 5 "material and labour rates" per tier, which would be rate card schema version 2). Until then only the DEMO card exists and production serves no estimate |
| D-17 | Registration in production | Privacy notice and terms versions for `consents` (F-017; API section 2 `consents`); grievance contact (AQ-24). Sign-in works without them in LOCAL and STAGING; production self-registration must not open before they exist |
| D-19 | Schedule | Chirag, 2026-10-04: Handover 1 (client acceptance MVP) in about 1 to 1.5 months (about 2026-11-04 to 2026-11-19), then Handover 2 (POC completion). Dates are engineering targets; completion is defined by acceptance criteria and passing tests (`FOUNDATION_PLAN.md` section 5). D-12, D-16, D-17 and the blockers below fall inside the Handover 1 window |
| M-01 | Handover 1 map in production | The map tile provider for production (AQ-19). The public OpenStreetMap tiles are allowed for development only; without a provider the form still works with device location and typed coordinates |
| M-02 | Handover 1 locality in production | The reverse geocoder for production. The public Nominatim service allows 1 request per second and forbids heavy use; options are a self-hosted Nominatim, a paid provider, or typed locality only. OpenStreetMap often has no neighbourhood for Raipur pins, so families will often type the locality |
| S-01 | Handover 1 uploads in production | R2 bucket and its CORS rule (PUT from the homeowner host only); ClamAV on the VPS (about 1.5 GB of memory, which the VPS sizing in CLOUD_AND_HOSTING must confirm); the nonce-based CSP naming the storage endpoint and tile host |
| W-01 | Handover 1 website | Website content beyond the home hero (services, about, how it works, contact, privacy and terms pages) must come from the client; the home page uses the client's own S14 hero copy |
| D-18 (DECIDED 2026-10-04) | Requirement form (slice 1) | Locked as `REQUIREMENT_QUESTIONS_V1.md` section L; open points O-1 to O-4 there do not block version 1 |
| D-15 (later blocker, tracked) | Operations console (slice 2) | Gap G-01: no table holds staff roles (operations, admin, advisor, field) although SECURITY 4.1 and API section 18 depend on them; recommendation in `FOUNDATION_PLAN.md` section 3 |

### 22.3 ALREADY DECIDED

Sections 5 to 17 and the README section 3 table (Chirag, 2026-10-03). README section 6 lists AQ-01, AQ-03, AQ-09, AQ-29, AQ-35 and AQ-10 as "must decide before coding starts". On inspection none of them changes code: AQ-01 and AQ-03 have defaults (N-01, N-02), AQ-09, AQ-35 and AQ-29 gate deployment and CI hosting (D-12, D-13), AQ-10 is decided as English only with externalised strings (ADR-022). This baseline reclassifies them accordingly.

## 23. Known risks

| Risk | Impact | Mitigation |
|---|---|---|
| One VPS is one failure domain | Outage until rebuild | Rebuild runbook under 2 hours; data off the box |
| Supabase Free pauses after 7 idle days and has no backups | Staging outage; data loss while building | Synthetic data only; nightly dump; Pro before the first real homeowner (hard launch gate) |
| asyncpg behind Supabase's transaction pooler | Prepared-statement errors | Statement cache disabled on the API engine; worker on session mode |
| Requirement questions change after the lock | Answers stored against an old set | A change is a new question set version; each requirement keeps the version it was answered against |
| S04 seed inconsistencies (A01 marking left from D-03; D-04 values) | Wrong specification ledger or schedule | Ruling before the seed; tests on the seed's invariants; "Schedule to be confirmed" until values are approved |
| Delegated designs (CD-25 to CD-28) unreviewed by Chirag | Rework | Review before the modules that implement them |
| Two-person team, wide scope | Slow delivery, shortcuts | Slice discipline; the implementation contract; CI gates |
| Fast-moving front-end toolchain (Next.js 16, TypeScript 7, ESLint 10) | Breakage on upgrade | Pinned versions and a lockfile; upgrades in their own PRs |
| Free-tier ceilings (Resend 100 emails a day, Upstash 500K commands) | Throttled OTP | Alerts; Resend Pro at go-live per COST_MODEL |
| Docker Desktop required for local tests | Developers without it cannot run service tests | Documented; CI always runs them |

## 24. Implementation status

| Item | Status on 2026-10-04 |
|---|---|
| Application code before this baseline | None existed (repository audit in `FOUNDATION_PLAN.md` section 1) |
| Foundation | Built and verified locally on 2026-10-04 (`FOUNDATION_PLAN.md` sections 2 and 4); CI workflow written, not yet run; file storage, scanner and geocoder adapters built and verified |
| Slice 1 (Handover 1, public part) | Built and verified locally on 2026-10-04: home, estimator (DEMO), entry questions, "Need help?" and other-city capture, email OTP registration, project creation, the locked requirement form with map pin, locality and uploads (storage, worker checks, ClamAV), review, submission, Submitted dashboard. 286 API tests, 26 unit tests, 16 Playwright tests pass (`FOUNDATION_PLAN.md` section 4b). Not built: operations part of Handover 1 (slice 2, held), infrastructure part (deployment, backups, monitoring) |
| Later modules | Not started |

## 25. Final approval statement

This baseline fixes the architecture that Plan2Build code is written against, as of version 1.0. The technology stack, topology, module structure, data rules, authentication model, file, event and AI boundaries, security principles, observability, testing and deployment approach in sections 5 to 17 are fixed for implementation. A change to any of them needs a new ADR or a new version of this document, with a reason. Blocking items in section 21 stop only the work they name. Business ambiguity is never resolved by invention.

| Role | Name | Decision | Date |
|---|---|---|---|
| Architect | Sakha | Prepared and recommends approval | 2026-10-04 |
| Owner | Chirag | Pending | |

## Open points

| ID | Question | Owner |
|---|---|---|
| Slice 2 | Permission to start the operations part of Handover 1 (staff login with MFA, review queue, accept, workspace foundation); needs G-01 (staff roles) | Chirag |
| D-03 rest, D-04 values | A01 structural marking; stage durations, cost shares and their approver | Chirag |
| M-01, M-02, S-01, W-01 | Map tiles, geocoder, production uploads, website content | Chirag with the client |
| D-16, D-17 | Production rate card; consent documents | Chirag with the client |
| Signature | Section 25 | Chirag |
