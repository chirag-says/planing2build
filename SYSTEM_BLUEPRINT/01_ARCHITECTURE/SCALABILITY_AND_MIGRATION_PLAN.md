# Plan2Build: scalability and migration plan

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/01_ARCHITECTURE/SCALABILITY_AND_MIGRATION_PLAN.md` |
| Version | 0.1 (proposed) |
| Date | 2026-10-03 |
| Status | Architecture proposal for Chirag's review. |
| Business authority | Chirag's baseline (migration-friendly; spend only where it materially improves reliability, speed, security, functionality or velocity); S06 "do not build now" (microservices, native app before repeat usage); SYSTEM_ARCHITECTURE.md sizing |
| Related | CLOUD_AND_HOSTING_ARCHITECTURE.md, PERFORMANCE_ARCHITECTURE.md, DOMAIN_ARCHITECTURE.md (extraction readiness), COST_MODEL.md |

## 1. Principle

No step is taken without its trigger. Each stage below names the objective signal that forces it, what changes, what does not change, and the cost. The architecture was designed so that each step is a configuration or deployment change, not a rewrite: stateless containers, one database with module-owned tables, events through the outbox, files in R2, providers behind adapters, and a pure recommendation core.

## 2. Stages

| Stage | Shape | Triggers (any one, sustained for two weeks unless stated) | What changes | What stays | Monthly cost delta (estimate) |
|---|---|---|---|---|---|
| 0: POC (now) | One VPS, Compose, Supabase Free then Pro, R2, Upstash free | | | | Baseline (COST_MODEL.md) |
| 1: Pro database and more worker | Same VPS; Supabase Pro; a second worker container for `render`, `files`, `ai` | First real homeowner (Pro, regardless of load); `render` or `files` queue wait p95 above target; worker memory above 80% | Compose file: second worker service with queue subset; Supabase plan | Everything else | +$25 (Pro) |
| 2: Bigger VPS | Hostinger KVM 4 (4 vCPU, 16 GB) by in-place upgrade | VPS CPU above 70% for 15 minutes daily; memory above 85% typical; ClamAV plus stacks leave under 1 GB free | Plan upgrade (Hostinger resizes in place); limits in Compose | Everything | +₹300 to ₹1,200 |
| 3: Database compute | Supabase Small or Medium compute; PITR add-on | Statement p95 above 50 ms for a week on the pooler; connection waits; daily payment volume where a 24-hour loss is unacceptable (PITR) | Supabase compute setting; `.env` unchanged | Everything | +$15 to $60; +$100 PITR |
| 4: Split web and worker from API | Second VPS: worker and ClamAV move; first VPS keeps Caddy, web, api | Request p95 above target while the worker is busy, or worker needs more than 4 GB (OSRM, larger renders) | A second Compose stack pointing at the same database and R2; the worker's `.env`; firewall between VPS hosts (private networking or TLS) | Code unchanged; modules unchanged | +₹1,200 |
| 5: Redundant application tier | Two application VPS behind Cloudflare load balancing (or a Hostinger load balancer); sessions already in Postgres; sticky sessions not needed | Availability target missed for two months because of VPS incidents; or the client requires an availability statement above 99.5% | Cloudflare Load Balancer ($5 plus per-origin pricing) or a small HAProxy VPS; Caddy on each node; deploy script runs per node | Code unchanged | +₹1,200 plus $5 to $20 |
| 6: Read replica and caching | Supabase read replica; Redis session cache on (Upstash paid); ISR and edge caching unchanged | Database CPU above 60% from reads; p95 on reads above target after index work | Read-only sessions routed to the replica for lists and dashboards (SQLAlchemy bind by request kind) | Writes unchanged | +$25 to $100 |
| 7: Managed queue | Redis-backed or managed broker behind `core.jobs.enqueue` | Queue depth sustained above 5,000; throughput above 50 jobs per second; cross-service consumers needed | The enqueue adapter and the relay target; Procrastinate tables retired after drain | Job functions unchanged; outbox unchanged | +$10 to $50 |
| 8: First extraction | `design` or `recommendation` as a separate service (DOMAIN_ARCHITECTURE.md extraction readiness) | A module's runtime or scaling profile differs (GPU for self-hosted image models; a learned ranker with its own release cadence); or a team of more than five developers wants independent deploys | The module's interface becomes HTTP or messages; its tables move to its own database; the outbox relay publishes to a broker topic | Other modules unchanged; the monolith remains for the rest | Depends on the service |
| 9: Multi-city, multi-region | Still one region (India); city rate cards, service areas and tiles are data; a second region only for residency or a global audience, which is not in sight | Second city launch (data only); a regulatory or latency reason for a second region (none foreseen) | Catalog versions per city; map tiles for the new state; OSRM extract | Everything else | Marginal |

Order is not strict; stage 3 can precede stage 2, and stages 4 and 5 can merge if the trigger for both appears.

## 3. Signals that are watched (objective triggers)

| Signal | Source | Threshold | Stage |
|---|---|---|---|
| VPS CPU, memory, swap | Grafana | 70% CPU 15 minutes daily; 85% memory; any swap | 2, 4 |
| Queue wait p95 per queue | Grafana | Above PERFORMANCE_ARCHITECTURE.md targets | 1, 4, 7 |
| Statement p95, connections | Supabase metrics | 50 ms; pooler waits | 3, 6 |
| Request p95 by route group | Grafana | Above targets | 2, 4, 6 |
| Monthly availability | UptimeRobot | Under 99.5% twice | 5 |
| Payment volume | Billing | Daily captured amount where a 24-hour loss exceeds the PITR cost | 3 (PITR) |
| Upstash commands | Upstash dashboard | 400K per month | Paid Upstash before 6 |
| R2 operations and storage | Cloudflare | Beyond the free tier (10 GB, 1M class A) | Cost only |
| Image generations | `integration_calls` | Cost above $50 per month | Provider negotiation or self-hosting (stage 8) |
| Developer count | Team | More than five | 8 |
| Candidate counts for the engine | Engine metrics | Retrieval above 1,000 per request | Engine phase 2 (allocation), unrelated to infrastructure |

## 4. What each step does not require

- No rewrite of modules, routers, jobs or templates at any stage up to 8.
- No change to the data model for stages 1 to 7 (tables stay; a replica or a bigger instance is transparent).
- No change to the file architecture at any stage; R2 scales without action.
- No change to authentication: Postgres sessions work across nodes.
- No change to the web app: it is stateless and host-routed.

## 5. Explicitly deferred (with the reason)

| Item | Why not now | Earliest trigger |
|---|---|---|
| Kubernetes | Two containers per stack do not need an orchestrator; the operational cost exceeds the benefit until there are several nodes and services | Stage 8 with more than one extracted service |
| Microservices | One team, one deploy cadence, shared transactions across modules (selection touches rfq, leads, projects, money) | Stage 8 |
| Kafka or a streaming platform | Hundreds of events a day; the outbox and Postgres queue carry millions before it matters | Stage 7 and beyond |
| OpenSearch or Elasticsearch | Postgres full-text and trigram search cover 67 lines per project and hundreds of profiles | A search product need (facets over tens of thousands of documents) |
| MongoDB or another document store | JSONB covers the schemaless parts (answers, update payloads, snapshots) | None foreseen |
| Multi-region | India only; residency satisfied in Mumbai | None foreseen |
| Native mobile apps | The PWA covers homeowners and auditors; a native app is justified by repeat usage (BR-151) | Post-handover services with repeat engagement |
| Self-hosted image models with GPU | Hosted APIs cost under $1 per project | Image spend above the cost of a GPU host, or control inputs (depth, edges) needed for stage-2 views |
| Service mesh, API gateway product | Caddy and the FastAPI dependency chain do what is needed | Stage 8 |

## 6. Migration paths that were designed in

| Path | Mechanism already in place |
|---|---|
| Supabase to another Postgres | Plain Postgres, no Supabase-specific features (no Auth, no Storage, no Edge Functions, no RLS dependency); `pg_dump` and restore; connection string change |
| R2 to another S3-compatible store | S3 API through boto3; object keys are provider-neutral; a bucket sync and a configuration change |
| Resend, Razorpay, image providers, maps | Adapters per INTEGRATION_ARCHITECTURE.md |
| Procrastinate to a managed queue | `core.jobs.enqueue` adapter; handlers are plain functions |
| Hostinger to any Linux host | `infra/` bootstrap script; Compose; nothing provider-specific |
| Monolith to services | Module interfaces, outbox events, module-owned tables, import linter |
| Expert scoring to learned ranking | Snapshots, shown items, outcomes logged from day one; the core's `score` stage is swappable per use |
