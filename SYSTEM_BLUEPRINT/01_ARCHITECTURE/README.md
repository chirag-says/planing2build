# Plan2Build technical architecture: index and summary

| Item | Value |
|---|---|
| Folder | `SYSTEM_BLUEPRINT/01_ARCHITECTURE/` |
| Version | 0.1 (proposed), 2026-10-03 |
| Status | Complete first draft of every document for Chirag's review. Nothing here is implemented. |
| Source priority | Client decisions (CD-01 to CD-28) > `IHB_FLOW.md` v1.2 > `PROFESSIONALS_FLOW.md` v1.2 > `RECOMMENDATION_ENGINE.md` v0.1 > the Source of Truth documents > general engineering knowledge. The older D1, D2 and D3 architecture documents in the Source of Truth are evidence, not authority. |
| Conventions | Every document has a header table and an open-points table. Architecture open decisions are numbered AQ-01 to AQ-35 and listed in section 6 below. "Proposed" means Sakha's design awaiting Chirag; "decided" names Chirag and the date. |

## 1. Summary

Plan2Build is a modular monolith: one Next.js application serving three hosts (`plan2build.in` for homeowners, `professionals.plan2build.in` for every professional role including the auditor's offline PWA, `admin.plan2build.in` for operations with MFA), one FastAPI codebase organised into 24 modules and run twice (API and worker), one PostgreSQL database on Supabase (Mumbai) that also carries the job queue and the transactional outbox, Cloudflare R2 for every file, Upstash Redis for rate limits only, all on one Hostinger KVM 2 VPS behind Cloudflare and Caddy, with a staging stack beside production. Sessions are server-side in HttpOnly cookies per host; OTP by email first with phones verified from day one so SMS is a switch; Razorpay Checkout collects Plan2Build's fee with signed webhooks and daily reconciliation; construction money never passes through the platform. Documents render with fpdf2 (ADR-023, which supersedes the WeasyPrint proposal of ADR-018); 3D views come from an image provider behind an adapter and are never drawings of record; the recommendation engine is a pure core with data-driven rules, expert-weighted scoring, written reasons and team review, with learning deferred until outcomes exist. Observability is Sentry, Grafana Cloud and UptimeRobot; backups are Supabase daily plus encrypted nightly dumps to R2 with a tested restore; the fixed infrastructure cost is about ₹1,500 per month while building and about ₹6,000 per month in early production.

The design holds the sources' hard rules by construction: project isolation through membership joins on every project-scoped query; auditors blind to supplier and brand through separate response models; contractors never seeing another quote; the comparison headline never a price ranking; no brand recommendation and no paid influence through a tested configuration validator; every transition audited; overrides with reasons; files private, scanned and served by short-lived signed URLs; webhooks verified and idempotent.

## 2. Reading order

| Order | Document | What it answers |
|---|---|---|
| 1 | `TECH_STACK_AND_RATIONALE.md` | What the stack is, why, what it costs, what is deliberately absent |
| 2 | `SYSTEM_ARCHITECTURE.md` | Topology, hosts, request paths, architecture style, module map, sizing, failure inventory, the 20 validation answers, AQ-01 to AQ-11 |
| 3 | `DOMAIN_ARCHITECTURE.md` | The 24 modules: responsibility, tables, interface, dependencies, events, ownership, permissions, scalability; cross-module workflows; extraction readiness |
| 4 | `STATE_MODEL.md` | Every state machine with its transition table, actor, guard and side effects |
| 5 | `DATA_ARCHITECTURE.md` | Every table: purpose, keys, fields, relationships, constraints, indexes, versioning, soft delete, audit, privacy class, retention; geospatial, search, migrations, archival |
| 6 | `API_ARCHITECTURE.md` | Conventions and the endpoint catalogue per domain with actor, authorisation, request and response, validation, errors, transitions, idempotency, audit, notifications, pagination, rate tier |
| 7 | `EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md` | Outbox, queues, job contract, the event catalogue with consumers, the notification pipeline, scheduled jobs, failure handling, migration to a managed queue |
| 8 | `AI_AND_RECOMMENDATION_ARCHITECTURE.md` | Design generation (authoritative drawings versus illustrative views, provider adapter, jobs, review) and the engine (validation of the proposal, contracts, retrieval, eligibility, capacity, scoring, re-ranking, reasons, review, fallbacks, fairness, auditability) |
| 9 | `INTEGRATION_ARCHITECTURE.md` | Razorpay, Resend, SMS and WhatsApp later, OpenStreetMap stack, image providers, ClamAV, rendering, Cloudflare; the provider registry with timeouts, retries, idempotency and fallbacks |
| 10 | `SECURITY_ARCHITECTURE.md` | Trust boundaries, OTP, sessions, MFA, authorisation layers, the threat model with mitigations, headers, webhooks, files, secrets, data protection, audit, incident response, security testing |
| 11 | `PERFORMANCE_ARCHITECTURE.md` | Targets (p50, p95, p99), rendering strategy, database rules, every cache with key, TTL, invalidation and fallback, the Redis budget, measurement, what breaks first |
| 12 | `CLOUD_AND_HOSTING_ARCHITECTURE.md` | VPS layout, containers and limits, resource budget, hardening, Caddy routing and TLS, database connectivity, restart and failure behaviour, staging, DNS |
| 13 | `ENVIRONMENT_AND_DEPLOYMENT.md` | LOCAL, STAGING, PROD; seeds and anonymisation; the repository; branching and releases; the pipeline; migrations; rollback; secrets in CI |
| 14 | `OBSERVABILITY_AND_OPERATIONS.md` | Signals, dashboards, alerts, runbooks, backups, RPO and RTO, restore and rebuild procedures, the operational calendar |
| 15 | `TESTING_ARCHITECTURE.md` | Test layers, the S06 critical tests as assertions, end-to-end flows, test data, quality gates |
| 16 | `SCALABILITY_AND_MIGRATION_PLAN.md` | Stages with objective triggers, what each step changes and what it does not, deferred items with reasons, designed-in migration paths |
| 17 | `COST_MODEL.md` | Unit prices, four phases with fixed, usage and optional lines, the largest driver per phase and the change that halves it, cost per house |
| 18 | `ADR/ADR-001` to `ADR-024` (ADR-018 superseded by ADR-023; ADR-024 replaces `leads` with `engagements` in the module list) | One decision each: context, decision, why, alternatives, why not, consequences, migration path |

## 3. Decisions taken with Chirag on 2026-10-03

| Topic | Decision |
|---|---|
| Job queue | Postgres-backed (Procrastinate) with a transactional outbox (delegated to Sakha; ADR-009) |
| API exposure | Same-origin `/api/v1` on each host through Caddy (delegated; ADR-016) |
| Sessions | Server-side, HttpOnly cookies, one per host (ADR-010) |
| OTP | Email at MVP, SMS added later; phones verified from day one (ADR-010) |
| Reverse proxy | Caddy (ADR-016) |
| Next.js | On the VPS (ADR-001, ADR-005) |
| Staging | Second Compose stack on the same VPS (ADR-005) |
| Observability | Sentry plus Grafana Cloud free plus UptimeRobot (ADR-017) |
| Auditor app | Offline PWA module on the professional host (ADR-021) |
| Fee collection | Razorpay Checkout in-app with webhooks (ADR-020) |
| Email | Resend (ADR-020) |
| Maps | OpenStreetMap stack for Raipur; Google behind the same interface later (ADR-015, ADR-020) |
| Supabase | Free while building, Pro before the first real homeowner (ADR-004) |
| Language | English only at MVP; strings externalised (ADR-022; AQ-10 records the sources' Hindi requirement) |
| Domain and hosts | `plan2build.in` homeowners only; `professionals.plan2build.in`; `admin.plan2build.in` (AQ-01 confirms spelling) |

## 4. The 20 validation questions

Full answers are in `SYSTEM_ARCHITECTURE.md` section 12. In one line each: (1) one VPS carries the POC with about half its RAM in use; (2) the stack stays fast through rendering strategy, indexes, shaped payloads and files off the VPS; (3) every heavy operation is a job; (4) database compute and replicas scale by provider setting; (5) R2 scales by volume; (6) the engine runs as jobs and can become a service without changing contracts; (7) image generation has its own queue and provider quota; (8) nothing on the VPS is Hostinger-specific; (9) only plain Postgres features are used, so any provider works; (10) R2 is S3-compatible with neutral keys; (11) Upstash is plain Redis; (12) modules can be extracted under written rules with events already flowing through the outbox; (13) the security model covers production data classes; (14) project isolation is enforced on every endpoint and tested; (15) every sensitive operation writes audit; (16) payment webhooks are verified, idempotent and amount-checked; (17) uploads are presigned, sniffed, scanned and private; (18) VPS failure recovers within hours from images, git and the data providers; (19) deploys are gated, staged, health-checked and reversible; (20) an AI agent reading this folder in order finds a reason and an owner for every part.

## 5. Reconciliation of the three business documents with this architecture

| Topic | Sources say | Architecture does | Where |
|---|---|---|---|
| Language | Hindi and English from the first release (BR-057) | English only at MVP, strings externalised; the gap is flagged for the client | ADR-022, AQ-10 |
| OTP channel | SMS and email; contractors phone-first | Email first, phone verified, SMS later | ADR-010 |
| Notification channels | WhatsApp preferred by S06, email plus SMS first by S07 (PC-039) | Email and in-app now; SMS and WhatsApp as channels behind recipient rules | EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md section 5, AQ-04 |
| Auditor app | React Native app (S06, S09) | PWA module | ADR-021 |
| Payments | D1 gateway settlement model | Superseded by CD-01 and CD-09: marks only; Razorpay for Plan2Build's fee only | INTEGRATION_ARCHITECTURE.md section 2 |
| Maps | Google Maps "if needed" (S06, S13) | OpenStreetMap stack at the POC | ADR-015, ADR-020 |
| Retrieval index | H3 cells or PostGIS (RECOMMENDATION_ENGINE.md) | PostGIS only | AI_AND_RECOMMENDATION_ARCHITECTURE.md B1 |
| Travel time | Routing engine from day one | Straight-line with a factor at the POC; OSRM behind an interface | AQ-21 |
| 3D view guidance | Depth and line images from a 3D model (IHB_FLOW 33.6) | Reference images at the POC; control images when the 3D model exists | AI_AND_RECOMMENDATION_ARCHITECTURE.md A2 |
| Hosting | AWS ap-south-1 managed services (S06) | One VPS, Supabase, R2 | ADR-005 |
| Backups | Point-in-time recovery (S05, S06) | Daily backups plus nightly dumps; PITR when payment volume justifies it | AQ-32 |

## 6. What must be decided before development begins

Architecture decisions (AQ), by owner. Defaults apply if no answer arrives; each is recorded in the document that raised it.

| Owner | Must decide before coding starts | Can wait until the relevant sprint |
|---|---|---|
| Chirag | AQ-01 domain spelling and hosts; AQ-03 OTP code versus link; AQ-09 who owns production accounts and secrets; AQ-29 repository ownership and deploy approver; AQ-35 who pays for infrastructure accounts | AQ-02 admin IP allow-list; AQ-07 staging email policy; AQ-25 second-person VPS access; AQ-27 VPS snapshots; AQ-31 alert channel; AQ-33 backup key holder |
| Chirag with the client | AQ-10 Hindi timing (the sources require it); AQ-08 residency statement; AQ-06 auditor identity storage (CQ-15) | AQ-04 WhatsApp timing; AQ-12 mandatory versus optional notices; AQ-16 who checks drawings (CQ-26); AQ-17 fit-label and risk thresholds; AQ-22 account recovery steps; AQ-24 grievance officer |
| Sakha with Chirag | AQ-05 RLS later (default agreed) | AQ-13, AQ-14 digest and reminder steps; AQ-15 image provider after the trial; AQ-18 issue without views; AQ-19 tile provider; AQ-20 and AQ-11 invoice format with the accountant; AQ-21 OSRM; AQ-23 auditor MFA; AQ-26 IPv6; AQ-28 analytics tooling; AQ-30 client repository access; AQ-32 PITR; AQ-34 client acceptance testing |

Client questions (CQ, from `IHB_FLOW.md` section 32) that block specific modules:

| CQ | Blocks | Default used in the design |
|---|---|---|
| CQ-01 package price and instalments | `billing` configuration, the estimator's "from" price, revenue in the cost model | Offering rows with a blank price; instalments as our invoices |
| CQ-03 collection method | Answered for the MVP by Chirag: Razorpay Checkout in-app | |
| CQ-04 refunds and cancellation | `billing` refund rules | Operations-initiated refunds with reason and MFA; no automatic rule |
| CQ-12 variation acknowledgement window and closure authority | `variations` configuration | Configurable window; operations close with reason |
| CQ-13 payment marks and the contractor's money view | `money` response shaping | Milestones do not block; mismatch flagged after configured days; contractor sees cost booked against revenue |
| CQ-15 auditor ID | `professionals` profile fields | Category AUD profile with a visible code |
| CQ-22 structural scope | `buildplan` sign-off checklist | Structural lines signed per Build Plan version |
| CQ-24 budget for the engine and image generation | Whether these modules ship in the POC | Designed in; infrastructure cost is negligible; developer time is the budget question |
| CQ-25 architect design purchase and shortlisting | `design` architect path, `recommendation` architect use | Paid directly; shortlist by the engine once confirmed |
| CQ-26 who checks drawings | `design` approval role | Advisor plus structural engineer |
| CQ-17 reviews and ratings | Nothing at the POC | Not built; the engine does not need them |

Launch checklist (before the first real homeowner): Supabase Pro on production; Razorpay live KYC and webhook secret; Resend domain verified with DMARC; Cloudflare Full (strict) and HSTS; restore drill passed; penetration test done; DLT registration started if SMS is wanted within months; privacy notice with the residency statement; grievance contact published; alerting tested end to end.

## 7. Missing requirements the architecture had to supply

Items the business documents do not specify and this design fills with a stated default: the idempotency store for API writes; the capacity model behind "capacity free in the start window"; conflict-of-interest data until the independence protocol settles (POQ-053, POQ-054); fewer-than-three and zero-candidate behaviour for shortlists; deterministic tie-breaking; the frozen-set rule for quote recommendation; account recovery when email access is lost; data principal request handling (DPDP); digest and suppression rules for notifications; lead-time steps for decision reminders; the listing projection and its rebuild; invoice numbering and GST format; staging email policy; backup key custody; session lifetimes per audience; MFA re-verification windows; file size limits per purpose; cost caps for image generation; the rule that views are never authoritative.

## 8. Do not over-engineer

Not built at the POC, each with its trigger in `SCALABILITY_AND_MIGRATION_PLAN.md`: Kubernetes, microservices, Kafka or any streaming platform, OpenSearch, MongoDB, a managed queue, a service mesh or API gateway product, multi-region, native mobile apps, self-hosted image models, Redis as a primary store, read replicas, a second file provider copy, paid observability, Supabase Auth or Storage or RLS, H3 indexing, a routing engine (until needed), WebSockets (polling at 60 seconds is enough for the inbox), GraphQL, a CQRS or event-sourcing framework (the outbox and append-only event tables give the audit trail without it).

## 9. How to use this folder

Developers: read in the order above; implement module by module following `DOMAIN_ARCHITECTURE.md` and `STATE_MODEL.md`; every endpoint's rule is in `API_ARCHITECTURE.md`; every table in `DATA_ARCHITECTURE.md`. AI agents: the same order; treat AQ defaults as decisions unless a later note overrides them; never introduce a component listed in section 8 without a written trigger. Changes to any document bump its version and add a line to the open-points table or the ADR set; the business blueprints (`IHB_FLOW.md`, `PROFESSIONALS_FLOW.md`) remain the product authority and this folder follows them.
