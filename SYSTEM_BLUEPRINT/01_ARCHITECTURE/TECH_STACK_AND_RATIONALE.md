# Plan2Build: technology stack and rationale

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/01_ARCHITECTURE/TECH_STACK_AND_RATIONALE.md` |
| Version | 0.1 (proposed) |
| Date | 2026-10-03 |
| Status | Architecture proposal for Chirag's review. No application code exists yet. Updated on 2026-10-03 after Chirag's decisions (email OTP first, OpenStreetMap, three hosts, English only, Supabase Free then Pro, Razorpay Checkout in-app, auditor PWA). |
| Business authority | `IHB_FLOW.md` v1.2 (sections 32, 33), `PROFESSIONALS_FLOW.md` v1.2 (sections 43, 44), `RECOMMENDATION_ENGINE.md` v0.1, then the Source of Truth, then general engineering knowledge |
| Decisions | Each choice below has an ADR in `ADR/`; the ADR holds the alternatives and the migration path |

## 1. The baseline, as given

Chirag fixed the baseline before this design: Next.js with TypeScript, FastAPI with Python, PostgreSQL on Supabase for the POC, Cloudflare R2 for files, Upstash Redis (free tier, optional per feature), one Hostinger KVM-class VPS (2 vCPU, 8 GB RAM, 100 GB NVMe). This document architects around that baseline. It does not re-open it; it fills in what the baseline leaves open (libraries, proxy, queue, auth, observability, providers) and records why.

## 2. Stack by layer

| Layer | Choice | Why this | What it costs | ADR |
|---|---|---|---|---|
| Edge | Cloudflare (DNS, proxy, WAF, TLS, cache for static assets and public images) | Free plan covers DNS, DDoS protection, TLS and caching; the product's public pages and listing are read-heavy; R2 sits in the same network | Cloudflare sees all traffic; cache rules need care for authenticated pages (never cache them) | ADR-016 |
| Reverse proxy on the VPS | Caddy | Automatic TLS and a 30-line config; HTTP/2 and compression built in; one binary | Smaller ecosystem than Nginx; team must learn Caddyfile syntax (small) | ADR-016 |
| Web | Next.js (App Router, React Server Components), TypeScript, Tailwind CSS, use-intl with English only at MVP (every string externalised, Hindi added as data later; ADR-022; implemented with use-intl, the framework-agnostic core of next-intl, because next-intl 4.5 and later load a native SWC binary in the Next.js plugin that failed on the development machine and next-intl 4.3 does not support Next.js 16; recorded 2026-10-04, `FOUNDATION_PLAN.md` N-16), a PWA service worker (offline for the auditor inspection flow only), react-hook-form with zod on forms | SSR gives fast first paint on low-end Android; server components keep client JavaScript small; one app serves three hosts (`plan2build.in` homeowners, `professionals.plan2build.in` professionals and auditors, `admin.plan2build.in` operations) by host-based route groups | Next.js on the VPS costs about 400 MB RAM and some CPU for SSR; its built-in image optimiser is not used (section 4) | ADR-001, ADR-021, ADR-022 |
| API | FastAPI, Python 3.12, Pydantic v2, SQLAlchemy 2.0 (async) with asyncpg, Alembic migrations, structlog, httpx | Chirag's choice; Pydantic models are the single source of request and response contracts and generate the OpenAPI spec the web app consumes; async I/O suits a request path that mostly waits on Postgres, R2 and providers | Python CPU-bound work (PDF, image resizing) must leave the request path, which the worker does | ADR-002 |
| Background jobs | Procrastinate (a PostgreSQL-backed job queue for Python: `SELECT ... FOR UPDATE SKIP LOCKED`, LISTEN/NOTIFY wake-ups, retries, periodic tasks), run as a separate worker container from the same codebase | No broker to run; a job is enqueued in the same transaction as the business write, so an API write and its job cannot disagree; migration to a managed queue stays behind one interface | Polling and job rows live in the main database; at high volume the queue competes with product queries, which is the trigger to move it out (section 6) | ADR-009 |
| Database | PostgreSQL 15 or later on Supabase, Mumbai region; extensions: PostGIS, pg_trgm, pgcrypto, pg_stat_statements | One relational primary carries this product far beyond the POC; PostGIS answers service-area and distance queries; trigram and full-text search cover the listing search; Mumbai keeps data in India (OQ-059) and close to the VPS | Supabase Free has no automatic backups and pauses after a week idle, so the project must be on Pro before real homeowners use it (COST_MODEL.md) | ADR-003, ADR-004, ADR-015 |
| Files | Cloudflare R2 through the S3 API (boto3), private buckets, presigned uploads and downloads | Zero egress fees; S3-compatible so a move to S3 or another store is a configuration change; large files never touch the VPS | No native object versioning on R2, so versions are modelled in the database and objects are never overwritten (ADR-011) | ADR-006, ADR-011 |
| Cache and counters | Upstash Redis (free tier, TLS) for rate-limit token buckets; a session cache and an estimate cache exist behind flags, off at the POC; nothing else | Rate limits need atomic counters with TTLs, which Redis does well; everything else stays in Postgres or in process, and every Redis use has a Postgres fallback | 500K commands a month on the free tier; every Redis use must justify its command budget (PERFORMANCE_ARCHITECTURE.md sections 5 and 6) | ADR-007 |
| Containers and hosting | Docker, Docker Compose, Ubuntu LTS on one Hostinger KVM 2 VPS; images built in CI and pushed to GitHub Container Registry | Reproducible deploys without Kubernetes; the same images run on any VPS or cloud VM later | One VPS is one failure domain; recovery is by rebuild from images and backups (CLOUD_AND_HOSTING_ARCHITECTURE.md) | ADR-005, ADR-008 |
| CI and CD | GitHub Actions: lint, type check, tests, build, container scan, deploy to staging, smoke test, manual approval, deploy to production | Free for this scale; the deploy is an SSH step that pulls images and restarts Compose services | Deploy secrets live in GitHub environments; a compromised repository is a compromised deploy, so branch protection and environment approvals are mandatory | ADR-014 |
| Errors and metrics | Sentry (errors, both apps), Grafana Cloud free tier (metrics and logs through Grafana Alloy), an external uptime check (UptimeRobot or Better Stack free) | Almost no RAM on the VPS, free at this scale, alerting included | Logs leave the VPS; personal data must be masked before it is logged (OBSERVABILITY_AND_OPERATIONS.md) | ADR-017 |
| Authentication | Own implementation in FastAPI: email OTP at MVP with phone numbers verified from day one, SMS OTP added later behind the same interface (Chirag, 2026-10-03), opaque server-side sessions in one HttpOnly Secure SameSite cookie per host, TOTP MFA for operations, admin and the structural engineer's sign-off | Session revocation and device lists need server state anyway; no JSON Web Token in browser storage; Supabase Auth is not used because the role model is per project and acknowledgement OTPs are bound to objects | SMS needs DLT registration before it can be switched on; attempt limits and lockouts are mandatory (SECURITY_ARCHITECTURE.md) | ADR-010 |
| Document rendering | fpdf2 (ADR-023, superseding the WeasyPrint proposal of ADR-018): Build Plan PDFs in the issuing and accepting request, invoices in the `render` job; a Unicode TTF font in production, Devanagari added with Hindi | Every issued document is a deterministic PDF built from the same snapshot data as its web view | Layout is code; designed layouts are a later pass; Hindi shaping is a later test | ADR-023 |
| Image processing | Pillow in the worker: EXIF stripped, resized variants, WebP output | Phone photos are 3 to 10 MB; the web must serve 50 to 300 KB variants | Processing runs after upload, so a photo appears as a placeholder for a few seconds | ADR-011 |
| AI image generation | Provider adapter with Gemini 3.1 Flash Image first; FLUX.1 Kontext and an archviz API as alternatives behind the same interface | CD-25 and `IHB_FLOW.md` section 33.6; models are retired often, so the adapter is the stable part | Per-image cost; a human check before a view is attached to the Build Plan | ADR-013 |
| Concept floor plan engine | Pure Python in `houseplans.engine`: integer-millimetre geometry, rule-based zoning, OR-Tools CP-SAT (Apache-2.0) for placement once the container check passes, deterministic derivation and an independent validator; no language model | PD-28; deterministic, testable, proves infeasibility | `ortools` brings numpy, pandas, protobuf, absl-py, immutabledict (about 30 MB wheel plus dependencies; measured before adoption); solve time on the worker | ADR-025 |
| Concept plan rendering | 2D: in-house React SVG components drawing server-derived `PlanGeometry`, no library. 3D: `three` with `@react-three/fiber`, lazy-loaded, no `@react-three/drei` | One geometry for 2D, 3D and PDF; small element counts suit SVG | Two web dependencies for 3D, added at the 3D checkpoint | ADR-026 |
| Recommendation engine | A module inside the API codebase with a pure core, executed as worker jobs for shortlists and quote recommendations, with versioned configuration in Postgres | `RECOMMENDATION_ENGINE.md` and AI_AND_RECOMMENDATION_ARCHITECTURE.md; rules and weights are data; no separate service until data volume demands it | Nightly metric jobs; reason templates in English with a locale column | ADR-012 |
| Payments | Razorpay Orders and Checkout embedded in the app, signed webhooks, daily reconciliation (Chirag, 2026-10-03) | Plan2Build's own package fee only (CD-01, CD-05); Razorpay is the provider named in the sources; in-app Checkout keeps the server in control of amounts | 2% plus GST per transaction; webhook idempotency and signature checks are mandatory | ADR-020 |
| Messaging | Resend for email (OTP, notices, digests) now; MSG91 for SMS after DLT registration; WhatsApp through a BSP when pilot data justifies it; in-app notifications in Postgres | Email first gets the MVP live without waiting for DLT (Chirag); the channel adapters share one interface so adding SMS and WhatsApp is configuration plus templates | Per-message cost; channel preferences per user; one provider outage must not block the others (per-channel queues) | ADR-020 |
| Maps | OpenStreetMap stack (Chirag, 2026-10-03): map pin as the primary plot input, tiles from MapTiler's free tier or self-hosted Protomaps, Nominatim with caching for address lookup, PostGIS for distance, an OSRM container only if road travel time is needed; Google Maps behind the same interfaces later | Raipur is the only city at the POC; no billing setup or per-call cost | Address search quality varies; the UI leads with the pin and the homeowner confirms it | ADR-015, ADR-020 |
| Testing | pytest with a Postgres test database, Schemathesis against the OpenAPI spec, Vitest and React Testing Library, Playwright end to end, k6 for load | Each layer has a standard, free tool; the state model and permission matrix become test tables | Test database per CI run; Playwright runs take minutes | TESTING_ARCHITECTURE.md |

## 3. What the baseline left open, and the answer

| Open point | Answer | Reason |
|---|---|---|
| Supabase: Postgres only, or also Auth, Storage, Realtime, Edge Functions? | Postgres only (plus its dashboard, backups and pooler) | The business logic lives in FastAPI; using Supabase Auth would split the role model, and Supabase Storage would duplicate R2. Keeping Supabase to Postgres makes the later move to any PostgreSQL host a connection-string change (validation question 9). |
| Where does Next.js run? | On the VPS, as a container behind Caddy, `output: 'standalone'` | Keeps one deployment unit and no vendor lock to Vercel; the VPS has the RAM for it. |
| How does the browser reach the API? | Same origin: `/api/v1/*` on the app host is proxied by Caddy to FastAPI. `api.plan2build.in` is an alias to the same FastAPI for non-browser clients | Same-origin cookies, no CORS surface for the web app, and SameSite cookies protect against CSRF by default. |
| Separate hosts per audience? | Yes (Chirag, 2026-10-03): `plan2build.in` for homeowners only, `professionals.plan2build.in` for every professional role including the auditor PWA, `admin.plan2build.in` for operations with MFA. One Next.js application serves all three by host-based route groups; one session cookie per host; `/api/v1` is same-origin on each host | Audience separation at the host level (cookies, CSP, routing of admin API paths) without three deployables. A person who holds two roles logs in on each host separately, which is acceptable at the POC. |
| Queue: Redis-backed (Celery, RQ, arq) or Postgres-backed? | Postgres-backed (Procrastinate) | Upstash's free tier is a command budget, not a broker; a Postgres queue gives transactional enqueue and one fewer service. |
| Job and session state in Redis? | No. Sessions in Postgres; Redis only for counters, limits and short caches | Redis can be lost without losing a user's session or a job. |
| Image optimisation | Variants generated once in the worker and served from R2 through Cloudflare; Next.js `<Image>` with a custom loader that points at the variant URL | Next.js's optimiser would resize on the VPS CPU on every cache miss. |
| PDF engine | fpdf2 (ADR-023), not WeasyPrint (ADR-018, superseded) or headless Chromium | Pure Python with no system libraries and a small memory footprint; WeasyPrint needs Pango and Cairo in every environment and Chromium 500 MB to 1 GB per render. |

## 4. How the stack meets the performance requirement

The platform must feel like a production website on a 2 vCPU box. The levers, in the order they are pulled (PERFORMANCE_ARCHITECTURE.md gives the targets and the monitoring):

1. Rendering: public pages are static or incrementally regenerated; authenticated pages are server-rendered with data fetched inside the VPS network (Next.js to FastAPI over localhost), so the browser gets finished HTML; client JavaScript is limited to the interactive parts (forms, uploads, the inspection app).
2. Database: every list endpoint is paginated with keyset pagination; every query is covered by an index named in DATA_ARCHITECTURE.md; `pg_stat_statements` is on from day one.
3. Payload: API responses are shaped per screen (no "return the whole project" endpoints); gzip or brotli at Caddy.
4. Files: uploads go from the browser straight to R2 with presigned URLs; downloads come from R2 through Cloudflare; the VPS never streams files.
5. Images: resized variants in WebP; lazy loading below the fold.
6. Background: anything slower than about 300 ms of CPU (PDFs, image variants, recommendation shortlists, notifications, AI renders) is a job.
7. Caching: browser and CDN caching for static assets and public images; small in-process caches for reference data (the 16 stages, 67 specification lines, configuration); Redis only where counters or cross-process locks are needed.

## 5. What is deliberately not in the stack yet

| Not used now | Why not now | What would justify it |
|---|---|---|
| Kubernetes | One VPS and three containers do not need a scheduler; it would consume 1 to 2 GB of RAM and an operator's week | Several VPS or cloud nodes with independent scaling of API, worker and web (SCALABILITY_AND_MIGRATION_PLAN.md stage 4) |
| Microservices | Every domain shares one database and one deploy; network calls between modules would add latency and failure modes without a benefit | A module with its own scaling or release cadence (section 6) |
| Kafka or any streaming platform | Event volume is tens per minute; a Postgres outbox and a worker carry it | Sustained thousands of events per second, or several consumers across services |
| OpenSearch or Elasticsearch | Listing search is a few hundred contractors with filters; Postgres full-text and trigram indexes cover it | Free-text search across millions of documents or relevance tuning Postgres cannot do |
| Service mesh, API gateway products | Caddy and FastAPI middleware cover routing, TLS, rate limits and auth | Several services needing mutual TLS and traffic policy |
| Multi-region | All users and data are in India; Supabase Mumbai and an Indian VPS serve them | A regulatory or latency reason outside India |
| A second database engine (MongoDB, DynamoDB) | Every entity is relational with strong consistency needs (money figures, acknowledgements, audit) | A workload Postgres cannot hold (none foreseen) |
| Paid observability platforms (Datadog, New Relic) | Sentry and Grafana Cloud free tiers cover errors, metrics and logs at this scale | Retention, SLAs or volume beyond the free tiers |
| Redundant databases, read replicas | One primary with daily backups and a documented restore meets the POC's recovery targets | Read latency or availability targets a single primary cannot meet |
| Native mobile apps | The sources and the client decisions want a responsive web and PWA; the only offline need (auditor) is a PWA module | Repeated field use that needs native camera or background sync beyond what the PWA offers (the sources mention an auditor app as a later option) |

## 6. Boundary for extracting a module into a service

A module leaves the monolith only when at least one of these holds, and the extraction is recorded in an ADR:

1. It needs a different scaling profile that the worker tier cannot give it (for example AI rendering saturating CPU while the API is idle).
2. It needs a different release cadence or a different team.
3. It needs a different runtime (for example a Node-based rendering engine).
4. Its data has no joins with the rest and can own its own store without duplicating identity or project data.

Until then a module is a Python package with an explicit public interface, its own tables (prefixed), and events through the outbox. DOMAIN_ARCHITECTURE.md section 3 defines the rules that keep extraction possible.

## 7. ADR index

| ADR | Title |
|---|---|
| ADR-001 | Frontend framework: Next.js with TypeScript |
| ADR-002 | Backend framework: FastAPI with Python |
| ADR-003 | PostgreSQL as the system of record |
| ADR-004 | Supabase as the POC PostgreSQL provider, Postgres only |
| ADR-005 | Hostinger VPS as the initial host |
| ADR-006 | Cloudflare R2 for files |
| ADR-007 | Upstash Redis, limited uses |
| ADR-008 | Modular monolith |
| ADR-009 | Background workers on a PostgreSQL-backed queue |
| ADR-010 | Authentication: OTP, server-side sessions, MFA for privileged roles |
| ADR-011 | File and document architecture |
| ADR-012 | Recommendation engine as a module with configuration in data |
| ADR-013 | AI image generation behind a provider adapter |
| ADR-014 | CI and CD with GitHub Actions and Compose deploys |
| ADR-015 | Search and geosearch in PostgreSQL (full-text, trigram, PostGIS) |
| ADR-016 | Edge and reverse proxy: Cloudflare and Caddy |
| ADR-017 | Observability stack |
| ADR-018 | Document rendering with WeasyPrint (superseded by ADR-023) |
| ADR-019 | Repository structure and shared contracts |
| ADR-020 | Payment, messaging, maps and scanning providers |
| ADR-021 | Auditor inspections as an offline PWA module |
| ADR-022 | English only at MVP with externalised strings |
| ADR-023 | fpdf2 for issued PDFs (supersedes ADR-018) |
| ADR-024 | `engagements` replaces `leads` in the module list (amends ADR-008) |
| ADR-025 | `houseplans` module and deterministic concept floor plan engine (amends ADR-008, ADR-013) |
| ADR-026 | three.js and React Three Fiber for the concept plan 3D viewer |
