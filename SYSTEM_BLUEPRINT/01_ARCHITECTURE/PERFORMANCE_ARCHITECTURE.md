# Plan2Build: performance architecture

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/01_ARCHITECTURE/PERFORMANCE_ARCHITECTURE.md` |
| Version | 0.1 (proposed) |
| Date | 2026-10-03 |
| Status | Architecture proposal for Chirag's review. All numbers in section 1 are targets, not measurements. |
| Business authority | BR-150 (public pages on low-end Android over 3G), BR-152 (estimator interactive within 3 seconds on 3G; Build Plan within 30 seconds), BR-153 (dashboards and API under 2 seconds on 4G; progressive load), BR-058, BR-154 (99.5% availability), S05 P1 and P3 acceptance (PDF legible on a phone) |
| Related | SYSTEM_ARCHITECTURE.md (sizing), DATA_ARCHITECTURE.md (indexes), API_ARCHITECTURE.md (pagination), CLOUD_AND_HOSTING_ARCHITECTURE.md (resources), OBSERVABILITY_AND_OPERATIONS.md (how the targets are measured), SCALABILITY_AND_MIGRATION_PLAN.md (triggers) |

## 1. Targets

Measured at the 50th, 95th and 99th percentiles over a rolling 7 days in production, from the sources named in section 8. "4G" means a throttled profile of 9 Mbps down, 170 ms RTT; "3G" means 1.6 Mbps, 300 ms RTT; "mid-range Android" means a 4x CPU slowdown in Lighthouse.

| Area | Metric | p50 | p95 | p99 | Source rule |
|---|---|---|---|---|---|
| Public pages (home, estimator, listing, profiles) | Largest Contentful Paint on 4G mid-range Android | 1.5 s | 2.5 s | 3.5 s | BR-150 |
| Estimator | Interactive (first result after input) on 3G | 2 s | 3 s | 4 s | BR-152 |
| Public pages | Time to first byte at the edge (cached) | 100 ms | 300 ms | 600 ms | |
| Authenticated pages (workspace, dashboard, comparison) | Server render complete on 4G | 0.8 s | 2 s | 3 s | BR-153 |
| Authenticated pages | Interaction to Next Paint | 100 ms | 200 ms | 400 ms | |
| API reads (shaped screen queries) | Server time | 80 ms | 300 ms | 600 ms | |
| API writes (transitions with audit and outbox) | Server time | 120 ms | 500 ms | 900 ms | |
| OTP | Challenge created to provider accepted | 1 s | 5 s | 15 s | |
| Database | Statement time for application queries | 5 ms | 50 ms | 200 ms | |
| Uploads | Presigned URL issue | 50 ms | 200 ms | 400 ms | |
| Uploads | File available after upload completes (sniff, scan, variants) | 15 s | 60 s | 120 s | |
| Downloads | Presigned URL issue; the bytes come from R2 | 50 ms | 200 ms | 400 ms | |
| Build Plan PDF | Issue to PDF available | 10 s | 20 s | 30 s | BR-058, BR-152 |
| Comparison and inspection PDFs | Request to available | 10 s | 30 s | 60 s | |
| 3D views | Plan approved to all views pending review | 2 min | 6 min | 15 min | |
| Recommendation compute | Request to computed | 1 s | 5 s | 10 s | |
| Jobs | Queue wait, `priority` | 1 s | 2 s | 5 s | |
| Jobs | Queue wait, `notify` | 5 s | 30 s | 60 s | |
| Jobs | Queue wait, `render`, `files`, `engine` | 10 s | 60 s | 300 s | |
| Auditor sync | Batch of 50 checkpoints with evidence references, server time | 500 ms | 2 s | 5 s | |
| Availability | Monthly, measured externally on the three hosts | 99.5% | | | BR-154 |
| Capacity | Peak sustained requests per second on the current VPS before scaling triggers | 50 rps | | | SYSTEM_ARCHITECTURE.md sizing (POC peak under 5 rps) |

## 2. Rendering strategy (Next.js)

| Page group | Strategy | Why |
|---|---|---|
| Marketing and content (home, how it works, stage guides, coming-soon pages) | Static generation at build; revalidated by tag when content changes | Zero server work per request; cacheable at the edge; fastest on 3G |
| Estimator | Static shell; the active rate card published as a versioned static JSON asset at build or on `catalog.version_published`; the calculation runs in the browser instantly; `POST /public/estimate` records the enquiry and returns the server-computed result for the PDF | Meets "interactive within 3 seconds on 3G" without a round trip per input; the server result is authoritative for anything stored |
| Listing and public profiles | Incremental static regeneration: tag `listing` (revalidate 600 s) and `profile:{id}`; the worker calls the revalidation endpoint on Club and profile events | Fresh within a minute of a change, cached otherwise |
| Share links and build record public view | Server-rendered per request, `Cache-Control: private, no-store` | Token-scoped content must not be cached |
| Authenticated pages | Server components fetch from FastAPI over loopback with the user's cookie; one request per screen to a shaped endpoint; client components use SWR for in-page refresh (inbox every 60 s, workspace on focus) | Fast first paint with data, no waterfall of client fetches |
| Operations console | Server-rendered lists with keyset pagination; heavy tables virtualised | |
| Auditor PWA (`/inspections/*` on the professional host) | Client-rendered app shell precached by the service worker; job pack fetched once; IndexedDB queue; background sync | Must work without a network |
| Documents | Never rendered in the browser from data; PDFs come from R2 by presigned URL | |

Bundle budgets: public pages 170 KB of JavaScript (gzipped) on first load; authenticated pages 250 KB; the map library and chart libraries load lazily on the pages that need them; fonts self-hosted and subset; images through `next/image` with the public bucket as the loader; no client-side state library beyond React and SWR.

## 3. API and database performance

| Rule | Detail |
|---|---|
| One shaped query set per screen | A screen endpoint runs at most three statements (one main query with joins or CTEs, one for counts, one for related lists); the N+1 test counts statements per endpoint in CI and fails above the declared budget |
| Async everywhere | FastAPI with `asyncpg` through SQLAlchemy 2 async; no blocking calls in request handlers (file processing, rendering and provider calls are jobs) |
| Pooling | Transaction-mode pooler for the API (10 connections per uvicorn worker); session mode for the worker; `statement_timeout` 5 s on the API role, 60 s on job connections, 10 minutes for maintenance |
| Indexes | Every filter, join and sort column used by a screen has an index listed in DATA_ARCHITECTURE.md; partial indexes for hot states (`processed_at IS NULL`, `state IN ('SENT','VIEWED')`); composite indexes ordered by selectivity; no unindexed `ILIKE` (pg_trgm) |
| Keyset pagination | All lists; no `OFFSET` beyond the first page |
| JSONB | Read whole documents by id; no filtering on JSONB fields in hot paths except through GIN-indexed expression columns |
| Counts | Dashboard counts come from narrow indexed queries, not `COUNT(*)` over wide tables; daily aggregates in `analytics` for KPI pages |
| Reads for documents | Metadata from Postgres; bytes from R2; the API never streams file bytes |
| Serialisation | Pydantic v2 models; no ORM object graphs serialised directly; responses under 200 KB (lists capped at 100 items) |
| Render | fpdf2 (ADR-023; WeasyPrint superseded): Build Plan PDFs in the issuing request, invoices on the worker; templates avoid large images (thumbnails for photos); the Build Plan PDF stays under 50 pages and under 15 MB; fonts preloaded in the image |
| Query review | `EXPLAIN (ANALYZE, BUFFERS)` for every new screen query in the PR description; `pg_stat_statements` reviewed weekly; slow query log above 200 ms shipped to Grafana |

## 4. Upload and download paths

Uploads go from the browser to R2 by presigned PUT; the VPS never receives file bytes, so a 10 MB photo on 4G takes about 10 to 20 seconds of network time and no server time. The PWA uploads evidence in the background and retries on reconnect. Downloads are presigned GET from R2, served from Cloudflare's network; the application spends under 200 ms issuing the URL. Variants (thumbnail, 1600 px) are generated once and served for lists and galleries so the original is fetched only on demand.

## 5. Caching

Every cache in the system, with its contract. Nothing else is cached.

| Cache | Where | Key | TTL | Invalidation | Fallback | Consistency |
|---|---|---|---|---|---|---|
| Static assets | Cloudflare edge and browser | URL with content hash (`/_next/static/*`) | 1 year, immutable | New deploy produces new hashes | Origin | Exact |
| Public page HTML | Cloudflare edge | URL (cookie-less requests only) | 300 s with `stale-while-revalidate` 600 s | Purge by URL from the worker on `catalog.version_published` and listing rebuilds | Origin ISR page | Up to 5 minutes stale; acceptable for marketing and listing (no prices, no availability promises) |
| ISR pages and data | Next.js data cache on the VPS | Route plus tag (`listing`, `profile:{id}`, `content`, `ratecard`) | 600 s (listing, profile), 3,600 s (rate card), until tag revalidation (content) | `revalidateTag` through `POST /internal/revalidate` (shared secret, loopback only) called by the worker on the relevant events | Regenerate on request | Fresh within seconds of the event, otherwise up to the TTL |
| Rate card JSON for the estimator | Static asset with a version in the file name | `/data/ratecard-{version}.json` | 1 year, immutable | New version, new file; the page references the current version through the ISR `ratecard` tag | Server estimate endpoint | Versioned, never mixed |
| Estimate results | Redis (optional) or none | `est:{sha256 of inputs}:{ratecard_version}` | 3,600 s | None (versioned) | Compute (milliseconds) | Exact |
| Rate limits | Redis token buckets | `rl:{tier}:{subject}` | Window length | None | `rate_counters` table in Postgres (fail closed for T1 OTP limits, fail open with a log for T2) | Approximate by design |
| Session lookup | Redis, behind a flag, off at the POC | `sess:{sha256(token)}` | 60 s | `DEL` on revoke, role change, MFA change | Postgres session row (hash index, under 1 ms) | Revocation exact; role changes up to 60 s stale when enabled |
| Active catalog versions and engine configuration | In-process (API and worker) | `catalog:{name}` plus a version pointer | Pointer refreshed every 60 s; content held until the pointer changes | `catalog.version_published` bumps the pointer | Postgres | Versioned; a request sees one consistent version |
| Geocode results | Postgres `geocode_cache` | Normalised query | Permanent | Manual | Provider | Exact for the query |
| Travel time | Candidate snapshot | (profile, project) | Life of the request | None | Straight-line | Snapshot semantics |
| Listing projection | Postgres `listing_entries` (materialised by job) | Profile id | Rebuilt daily and on Club events | Job | Live join (slower) | Within minutes |
| Browser data | SWR in the client | Endpoint URL | Revalidate on focus and interval (inbox 60 s) | Mutations call `mutate` | Fetch | Eventual within the interval |
| Idempotency responses | Postgres `idempotency_keys` | (session, key) | 24 h | Expiry | n/a (it is a store, not a cache) | Exact |

Never cached: project data for authenticated screens beyond the request, money views, comparisons, quotes, OTP state, permissions, anything on `admin.plan2build.in`, presigned URLs (issued fresh per request).

Cache pathologies: stampede on public pages is absorbed by Cloudflare and Next.js single-flight regeneration; penetration on profile pages (random ids) returns a cached 404 for 60 s; avalanche is avoided because the few TTLs are staggered and content is versioned.

## 6. Redis command budget

Upstash free tier: 500K commands per month. Estimated POC usage: 100 active users per day × 40 API requests × 2 commands (rate limit) = 8,000 per day, about 240K per month, plus OTP and public limits, about 300K. The session cache is therefore off at the POC (it would double the count); it is enabled when Postgres session reads show in the p95 or when the paid Upstash plan is justified. An alert fires at 400K commands in a month; the fallback path (Postgres counters) means exhausting the quota degrades rate limiting precision, not availability.

## 7. Worker and job performance

Queues have per-queue concurrency so a burst of renders cannot starve OTP delivery (`priority` has its own slots). The worker's CPU share is limited so request latency on the API container is unaffected. Render jobs report duration; a Build Plan render above 20 seconds raises a warning and the template is reviewed (image sizes are the usual cause). ClamAV scans run at one at a time; a 10 MB PDF scans in about a second.

## 8. Measurement

| Signal | Tool | Where it is read |
|---|---|---|
| Web Vitals (LCP, INP, CLS) by page group | Sentry browser SDK performance sampling (10%) | Grafana dashboard through Sentry metrics, or Sentry's own performance view |
| Server time per route, p50/p95/p99 | FastAPI middleware histogram exported through Alloy | Grafana Cloud |
| Database statement time | `pg_stat_statements` and the slow query log | Supabase dashboard and Grafana |
| Queue wait and job duration per queue | Procrastinate metrics job writing to the metrics endpoint | Grafana |
| Availability | UptimeRobot checks every 5 minutes on the three hosts and `/readyz` | Monthly report |
| Synthetic page performance | Lighthouse CI on every pull request for the public pages with budgets (performance score 90, LCP 2.5 s on the 4G profile) | GitHub checks |
| Load | k6 against staging each quarter and before any pricing launch: 10x the expected peak (50 rps) for 10 minutes | Report attached to the release |

## 9. What breaks first

1. (ADR-023: fpdf2 now) A PDF render on an oversized Build Plan (many full-size photos): limit image sizes in templates; move renders to a second worker container if the `render` queue wait exceeds its target.
2. Supabase Micro compute (shared CPU) under reporting queries: move KPI aggregates to the nightly job; upgrade to Small ($15 per month) when p95 statement time exceeds 50 ms for a week.
3. ISR regeneration storms if many profiles change at once (Club curation day): the revalidation endpoint batches tags and spreads regeneration over a minute.
4. Public estimator traffic spikes from marketing: static shell and edge cache mean the VPS sees only enquiry POSTs; T0 limits protect the API.

## 10. Open points

| ID | Question | Default until answered |
|---|---|---|
| AQ-28 | Web Vitals sampling rate and whether PostHog (named by S06) is added for funnel analytics | Sentry performance at 10% sampling; funnel events stored in `analytics_events` and viewed in Grafana; PostHog later if product analytics outgrows that |
