# Plan2Build: repository audit, foundation plan and slice 1 readiness

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/FOUNDATION_PLAN.md` |
| Version | 1.2 (2026-10-04, after Chirag's final rulings: question set locked, Handover 1 and 2 defined, slice 1 built) |
| Date | 2026-10-04 |
| Governed by | `01_ARCHITECTURE/00_APPROVAL/ARCHITECTURE_BASELINE.md`, `IMPLEMENTATION_CONTRACT.md` |
| Status words | "Built and verified" means the code exists and the check named beside it was run on 2026-10-04. "Built, not run" means the code exists but was not executed (CI workflows: no GitHub repository yet). "Designed" means no code. |

## 1. Repository audit (before this work)

| Question | Finding |
|---|---|
| What existed | `SOURCE_OF_TRUTH/` (15 DOCX, 11 PNG, one HTML prototype, one ZIP of 5 PNG mockups), `SYSTEM_BLUEPRINT/` (flows, engine, 17 architecture documents, 22 ADRs, two client DOCX files, the client flow HTML), `.sakha/` session notes. No git repository. |
| Application code | None. No `package.json`, `pyproject.toml`, Compose file, Dockerfile, SQL, `.py`, `.ts` or `.env` anywhere. The only JavaScript is inline in the S14 prototype and the client flow HTML. |
| Reusable | The S14 calculator formula (seed for the estimator rate card, baseline N-05); S04's 67 specification lines and 16 stage masters (seed for slice 2, after D-03 and D-04); the anti-slop check scripts from the blueprint work (moved into `tools/`). |
| Conflicting with the architecture | Nothing implemented, so nothing to correct. Inside the documents: baseline section 21 (B-01 to B-03) and section 22 (N-04, D-03, D-04). |
| To remove | Nothing. |
| Missing | Everything in section 2. |

## 2. Foundation design and status

Repository root is `D:\PLAN2BUILD` (future git root). The blueprint stays in `SYSTEM_BLUEPRINT/` beside the code; `.gitignore` keeps `SOURCE_OF_TRUTH/` and `.sakha/` out of version control (client evidence, vendor bank details in S09 and S12, AQ-30).

| Area | Design | Status |
|---|---|---|
| A. Repository structure | `apps/api` (FastAPI and worker, one image), `apps/web` (Next.js), `packages/contracts` (generated TypeScript), `infra/local` (Compose, Caddy), `tools/` (prose checks), `.github/workflows/ci.yml`, pnpm workspace with root scripts (ENVIRONMENT section 3; baseline N-11) | Built |
| B. Frontend | One Next.js 16 app, three hosts. `src/proxy.ts` maps the host to an audience and rewrites `/x` to `/{ihb,pro,ops}/x`; a path of another audience cannot resolve (404). Server components call the API through `src/lib/api/server.ts` with the cookie and host forwarded. Strings in `messages/en.json` through `use-intl`. Security headers in `next.config.ts`. Standalone output. Foundation shells per host show the real session state from `GET /api/v1/me` | Built and verified (section 4) |
| C. Backend | `p2b.main.create_app` composition root; `p2b.core` shared kernel (config, vocabulary, ids, errors and envelope, logging, DB unit of work, rule marker, transition tables, outbox, job app, edge middleware, health, Sentry); modules `identity` and `audit`; `/api/v1` versioning; OpenAPI off outside LOCAL | Built and verified |
| D. Shared contracts | `apps/api/scripts/export_contracts.py` writes `openapi.json` and `vocabulary.ts`; `openapi-typescript` generates `schema.d.ts`; `@p2b/contracts` exposes a typed `openapi-fetch` client that always sends the CSRF header; error envelope published as `ErrorResponse` for 4XX and 5XX. CI fails if the regenerated contract differs from the committed one | Built and verified locally; CI check built, not run |
| E. Database and migrations | Alembic with async engine, naming convention, hand-written migrations with literal CHECK values. `0001`: extensions, `users`, `sessions`, `audit_events`, `security_events`, `outbox_events`, append-only triggers, conditional grants. `0002`: Procrastinate 3.10.0 schema frozen as SQL | Built and verified: upgrade, downgrade to base, upgrade on `postgis/postgis:16-3.5`; drift test (models equal migrated schema); CHECK constraints equal the vocabulary |
| F. Session and auth | 256-bit tokens, only SHA-256 stored; `__Host-` cookie per host (prefix and `Secure` dropped only when `P2B_COOKIE_SECURE=false` in LOCAL); idle and absolute lifetimes per audience against database time; sliding idle expiry capped by the absolute limit, written at most every 5 minutes; logout revokes, audits, publishes `session.revoked`, clears the cookie. OTP, contacts, consents and MFA enrolment are slice 1 (B-03) | Built and verified |
| G. Authorisation | Every route carries exactly one rule (`public_route` or `require_actor(audiences, mfa, allow_suspended)`); a test walks the served routes and fails otherwise; public routes are a reviewed list. Chain: host audience allowed for the route (else 404), session, account status, MFA within 8 hours. CSRF in the edge middleware: `X-Requested-With: plan2build` plus an `Origin` matching the host, on state-changing requests carrying a session cookie; rejections recorded in `security_events`. Project membership checks arrive with `projects` (slice 1) | Built and verified |
| H. Events and outbox | `publish` in the caller's transaction with a UNIQUE dedupe key; relay claims with `FOR UPDATE SKIP LOCKED`, runs handlers per row in a savepoint, marks processed, counts attempts and stops at 10 | Built and verified, including concurrent relays without double delivery |
| I. Worker | `python -m p2b.worker`: Procrastinate worker for all or selected queues, outbox relay loop, heartbeat file for the container health check | Built and verified in Compose (healthy; relayed a real event) |
| J. File storage | `Storage` interface in `p2b.core.storage` (presign PUT bound to type and length, presign GET with attachment disposition, size, read, write, delete); S3 adapter in `p2b.integrations.storage` with separate internal and public endpoints (R2 in staging and production, SeaweedFS locally, N-27); in-memory store for tests. `documents` owns `file_objects` and `document_access_log` | Built and verified: a presigned PUT with the wrong length or type is refused by the store (403); CORS admits only the homeowner origin; end to end in Playwright |
| K. Provider adapters | One interface per need owned by `core` (`MessageProvider`, `PaymentProvider`, `GeocodeProvider`, `ImageProvider`, `ScanProvider`), adapters under `p2b.integrations.*`, timeouts per the registry (INTEGRATION section 10), `integration_calls` record | Built and verified: `MessageProvider` (Resend in production, SMTP to Mailpit, in-memory); `Scanner` (ClamAV INSTREAM, fails closed; `accept_all` for tests only, refused in production); `Geocoder` (Nominatim behind a cache table and a global limit of 1 request per second; `none`). `PaymentProvider`, `ImageProvider`, `integration_calls`: designed |
| L. Logging and observability | structlog JSON with a field allow-list (unknown keys dropped and counted); request id accepted from Caddy or minted, echoed in the response, bound to logs, stored on audit and outbox rows; access log line per request; Sentry with PII off when a DSN is set; `/healthz`, `/readyz` (database and migration head) | Built and verified (Sentry: code only, no DSN yet). `/metrics` for Grafana Alloy: designed |
| M. Testing | pytest against real PostGIS (truncate between tests), Vitest for host routing, Playwright with axe on a Pixel 7 profile against the running stack | Built and verified (section 4) |
| N. Docker and Compose | API image (Python 3.12 slim, uv, non-root, health check); web image (Node 22 alpine, standalone, non-root, health check); `infra/local/compose.yml`: db, migrate (one-shot), api (reload), worker, Mailpit, SeaweedFS (S3 on `localhost:9000`), ClamAV 1.5.4, Caddy on `:8080` routing `/api/v1/*` and host names exactly as production | Built and verified |
| O. CI | `.github/workflows/ci.yml`: api (format, lint, mypy strict, import-linter, migrations up-down-up, tests with 70% and 85% service coverage gates, pip-audit), contracts drift, web (lint, types, unit, build, pnpm audit), gitleaks, image builds with Trivy, e2e on the Compose stack | Built, not run (no GitHub repository; D-13) |
| P. Environment configuration | `pydantic-settings` with `P2B_` prefix, fail-fast; `apps/api/.env.example` and `apps/web/.env.example` document every variable; LOCAL values in Compose | Built and verified |

## 3. Deviations and implementation notes

| ID | What | Why | Reversible |
|---|---|---|---|
| N-15 | ADR-001 and ENVIRONMENT section 3 say route groups `(ihb)`, `(pro)`, `(ops)`. Built as real segments `ihb/`, `pro/`, `ops/` with every request rewritten into its host's segment | Two route groups cannot both own `/` in Next.js. Behaviour is what the ADR asks for: one host, one tree; a cross-host path is a 404 | Yes |
| N-16 | TECH_STACK names next-intl. Built with `use-intl`, next-intl's framework-agnostic core | next-intl 4.5 and later load a native SWC binary in the Next.js config plugin; on this machine it failed (blocked build script, then a Windows permission check on the SWC cache). The last pure-JS next-intl (4.3) does not support Next.js 16. Same message format and files, so ADR-022 holds and a later switch is mechanical | Yes |
| N-17 | The API reads the user's host from `X-Forwarded-Host`, falling back to `Host` | Node's `fetch` cannot set `Host`, so server-side rendering must name the host another way. Verified that Caddy overwrites a client-supplied `X-Forwarded-Host`; only Caddy and the web container reach the API; the session's audience binding is a second check | Yes |
| N-18 | `psycopg[binary]` added | The worker image had no libpq; the binary wheel bundles it | Yes |
| N-19 | Windows only: tests and the worker use the selector event loop | psycopg's async mode cannot run on the Proactor loop. Production is Linux | Not needed on Linux |
| N-20 | FastAPI 0.142 keeps included routers nested | The route-rule test walks `fastapi.routing.iter_route_contexts`, and fails loudly if it ever finds no routes | n/a |
| N-21 | The OTP email template is a file (`identity/templates/otp_login.en.txt`) | DATA puts templates in `notification_templates`, owned by the `notifications` module, which does not exist yet. The text is still outside code (ADR-022) | Yes: moves to the table with the module |
| N-22 | CSRF headers required on every state-changing request, not only cookie requests (API and SECURITY 0.2) | `otp/verify` sets a session, so an unchecked public write allows login CSRF | n/a (stricter) |
| N-23 | OTP challenge transitions are logged in `security_events` (issued, failed, locked, rejected, delivery failed, login succeeded or refused), not `audit_events` | SECURITY section 11 names that stream for authentication; user and session transitions still write `audit_events` | Yes |
| N-24 | Rate limits use Postgres counters only | ADR-007 makes Upstash the fast path with Postgres as fallback; Upstash is not provisioned. The interface is the same | Yes: add the Redis adapter |
| N-25 | SECURITY 3.1 "10 failed challenges per contact per hour" implemented as 10 wrong codes for the contact in a sliding hour (counted from `security_events`) | Stricter of the two readings (a locked challenge is 5 wrong codes, so the other reading allows 50 guesses an hour) | Yes: one constant |
| N-26 | The OTP code is also held encrypted (AES-GCM) until the delivery job sends it | Delivery is a job (EVENT 4.1), and a hash cannot be sent; SECURITY 3.1 and DATA 4.2 amended to say so | n/a |
| N-27 | Local object storage is SeaweedFS 4.48 (`weed mini`), not MinIO | MinIO no longer publishes community container images (its Docker Hub repository returns "not found"). SeaweedFS speaks the same S3 API, is maintained, and enforces presigned signatures and CORS origins. Staging and production stay on R2 (ADR-006) | Yes: any S3 store |
| N-28 | `Idempotency-Key` is a declared, required header on the three creating endpoints | It was read from the raw request, so it was missing from the OpenAPI contract and the typed web client could not send it | n/a |
| N-29 | Every homeowner page renders on request, the estimator and entry pages included | The shared header shows the session state from `/me`. PERFORMANCE section 2 wants a static shell for public pages; moving the header's session state into a client island gives that later | Yes |
| N-31 | The shadcn initialiser added Inter from Google Fonts and a dark theme; both removed | System fonts until brand typography is chosen (UI-01); no approved dark theme | Yes |
| N-30 | The requirement page shows the error page for a project whose question set version is not the active one | Only version 1 exists; serving an older set by version needs a small endpoint, built when a version 2 is approved | Yes |
| Gap G-01 (closed 2026-10-04) | DATA_ARCHITECTURE had no table for staff roles | Built as `staff_roles` with the two roles the sources name, OPS and ADMIN (SLICE2_READINESS 1); project roles OPS_ADVISOR and OPS_FIELD stay in memberships | n/a |

## 4. What was run, and the result (2026-10-04)

| Check | Result |
|---|---|
| `alembic upgrade head`, `downgrade base`, `upgrade head` on PostGIS 16 | Clean |
| API tests (`pytest`), 86 tests | 86 passed; coverage 93% overall, services 97% (gate 85%), `identity/service.py` 97%, `core/outbox.py` and `core/state_machine.py` 100% |
| `ruff format --check`, `ruff check`, `mypy --strict`, `lint-imports` | All clean; 2 import contracts kept |
| Web unit tests (Vitest) | 13 passed |
| `tsc --noEmit`, ESLint | Clean |
| `next build` (standalone) | Success |
| `docker compose up --build --wait` (db, migrate, api, worker, Caddy) | All healthy; worker health from its heartbeat |
| Through Caddy: three hosts render their shells; `/pro` on the homeowner host and `/ihb` on the professional host return 404; unknown host returns 400 `INVALID_HOST`; `/api/v1/me` returns the 401 envelope with the request id from Caddy | As expected |
| Signed-in path (session created in the dev database): homeowner page shows "Signed in"; same token on the professional host shows "Not signed in"; logout without CSRF header refused and logged; logout with header returns 204; page then shows "Not signed in"; the containerised worker marked the `session.revoked` outbox row processed | As expected |
| Playwright with axe (WCAG 2.0 A, AA and 2.2 AA), 9 tests | 9 passed |
| Web image build and run | Healthy; host routing and unknown-host 400 inside the container; runs as non-root |
| CI workflow | YAML parses; not executed (no repository) |

## 4a. Slice 1 work run on 2026-10-04 (after Chirag's rulings)

| Check | Result |
|---|---|
| Migration 0003 up from 0002 on the test database; drift test (models equal schema) | Clean |
| API tests | 213 passed; coverage 94% overall, services 96%, `identity/otp.py` 99%, `core/ratelimit.py` and `core/crypto.py` 100% |
| ruff, mypy strict, import-linter (3 contracts, now with `catalog` and `integrations`) | Clean |
| Web: Vitest 13, `tsc`, ESLint | Clean |
| Playwright on the live stack (12 tests, Pixel 7 profile): host shells, cross-host 404, headers, sign-up with the code read from Mailpit, HttpOnly cookie not readable by page script, sign-out, wrong code message, axe on the sign-in page | 12 passed |
| curl through Caddy: OTP start, email in Mailpit, verify sets the cookie, `/me`, replay refused; estimate returns the S14 figures flagged `is_demo` | As expected |

## 4b. Slice 1 build run on 2026-10-04 (after the question set was locked)

| Check | Result |
|---|---|
| Migration `0004_handover1_projects` up, down, up on the test database; drift test | Clean |
| API tests | 286 passed; coverage 94% overall |
| ruff format and check, mypy strict (src, tests, scripts), import-linter (3 contracts, now with `projects` and `documents`) | Clean |
| Contracts regenerated (17 API paths) | Done; the web app typechecks against them |
| Web: Vitest | 26 passed (13 host routing; 13 question helpers checked against the seeded set, and the safe redirect) |
| Web: `tsc`, ESLint, `next build` | Clean; 13 routes |
| Compose stack with SeaweedFS and ClamAV | All healthy; the scanner client flags the EICAR test string and passes a clean file |
| Playwright on the live stack (16 tests, Pixel 7 profile; axe WCAG 2.0 A/AA and 2.2 AA on every new screen) | 16 passed. Covers: "Need help?" capture; other-city capture; DEMO estimate; sign-up, project creation, all five steps, a PNG uploaded to storage then re-encoded and scanned by the worker and ClamAV, review, submit, project shown as Submitted with the file downloadable |
| Security defect found and fixed during the run | The PDF check missed JavaScript written inline in the document catalogue (`/OpenAction` as a direct object). It now walks every object reachable from the trailer; a test covers it |
| Accessibility defect found and fixed during the run | Answering "No" on the entry questions changed page on input (WCAG 3.2.2). The answer now reveals a Continue link |

## 4c. Design system run on 2026-10-04 (Chirag's instruction: shadcn/ui as the frontend foundation)

| Check | Result |
|---|---|
| shadcn/ui 4.21.1 (`radix-vega`, Radix base, Lucide) initialised in `apps/web`; 21 primitives added and tuned (`UI_DESIGN_SYSTEM.md` section 13) | Done; dependencies pinned |
| Token contrast (`python tools/check_contrast.py`, 13 pairs) | All pass |
| Slice 1 screens rebuilt on the system: home, estimator, start, need help, other city, sign-in, projects, new project, requirement wizard (all steps, map, ranking, uploads), review with confirmation, project page | Done; no API or business-flow change |
| Web: ESLint, `tsc`, Vitest 30 (4 new: validation from the question set), `next build` | Clean |
| Playwright with axe, 16 tests on the live stack | 16 passed |
| Found and fixed | Leaflet's attribution link failed WCAG 1.4.1 (colour only); shadcn's default control borders failed WCAG 1.4.11 (now 4.3:1); the generated spinner announced a hard-coded English status |
| Screens checked visually at 412 px and 1280 px | Done; remaining items in `UI_DESIGN_SYSTEM.md` section 15 |

Polish run (same day, after Chirag approved the design system as the frontend standard): desktop step row on one line; Playwright and axe now run on a phone and a desktop project (32 tests, all pass; axe tags WCAG 2.0, 2.1 and 2.2 A/AA); desktop issues found and fixed: the Account dropdown was a modal menu hiding the page with `aria-hidden` while its links stayed focusable (now non-modal), and the step list put `aria-label` on plain spans; page titles added to every page (WCAG 2.4.2); `tools/check_ui_tokens.py` reports no raw colours.

Local note: the API's rate limits (60 OTP starts per IP per hour, 20 enquiries per IP per 10 minutes) apply to the Playwright suite too; after about eight runs in an hour, clear `rate_counters` in the local database.

## 4d. Slice 2 foundation run on 2026-10-04 (after the readiness audit)

Readiness audit and decisions: `SLICE2_READINESS.md`. Built only the parts no open decision touches.

| Area | Built |
|---|---|
| Migration `0005_slice2_staff_and_review_queue` | `staff_roles`, `mfa_secrets`, `ops_queue_items`; backfill of an open review item for every project already SUBMITTED. Up, down and up again verified on the test database; on the dev database 19 submitted projects gave 19 queue items |
| Staff roles | `OPS` and `ADMIN`, additive, held per operations account; `require_actor(..., roles=...)` checks them after session and status and before MFA (SECURITY 4.1). Accounts and roles are created only by `python -m p2b.identity.staff grant/revoke` (reason required, audited, the email checked with the sign-in validator); revoking a role ends every session of the account |
| MFA | TOTP (pyotp 2.9.0, RFC 6238, 30 s, one step of drift, each step usable once), secret AES-GCM encrypted and bound to the user, QR as an SVG data URI (segno 1.6.6), ten argon2id recovery codes shown once and single use, 5 attempts per session per 10 minutes and 15 per account per hour, security events for every outcome, session id rotated on success while the absolute expiry is kept |
| Review queue | `requirement.submitted` opens an item through the outbox (idempotent); keyset pages oldest first; claim and release, one person at a time (409 otherwise), audited with the project id |
| Submission detail | Read-only: answers against the question set, review flags, homeowner email, files with logged downloads, who is reviewing |
| Endpoints | `GET /auth/mfa`, `POST /auth/mfa/enrolment`, `POST /auth/mfa/enrolment/confirm`, `POST /auth/mfa/verify`, `GET /admin/staff` (ADMIN, MFA), `GET /ops/queues/requirement-review`, `POST /ops/queue-items/{id}/claim`, `POST /ops/queue-items/{id}/release`, `GET /ops/projects/{id}`, `GET /ops/files/{id}/url` (OPS, MFA); `/me` gains `staff` on the admin host |
| Screens (admin host) | Staff sign-in, MFA setup with recovery codes, MFA verification, review queue, submission detail with claim and release. Same design system and header component as the homeowner host |
| Not built (waiting for decisions) | Ask for information, decline, accept with workspace creation, homeowner workspace view, notifications (`SLICE2_READINESS.md` section 2) |

| Check | Result |
|---|---|
| API tests | 313 passed (27 new: staff, MFA, roles, queue, detail, downloads, access); coverage 94% overall; `operations` 100%, `identity/mfa.py` and `identity/staff.py` 92% |
| ruff, mypy strict, import-linter (now with `operations`) | Clean; 3 contracts kept |
| Web: ESLint, `tsc`, Vitest 30, `next build` (17 routes) | Clean |
| Playwright, phone and desktop, axe on every screen | 36 passed. New: staff account by the server command, sign-in by emailed code, TOTP setup with the code computed from the shown key, recovery codes, queue entry delivered by the worker, detail, claim, release, a second session asking for the authenticator code (wrong code refused, next step accepted); operations pages absent from the homeowner host |
| Found and fixed | The staff command accepted addresses the sign-in form rejects (`.test` domains), which would create an account that can never sign in; it now validates with the same rules. The review queue table scrolled sideways on phones and hid the way in; the project code is now the link and secondary columns appear from `md` |

## 4e. Slice 2 review and workspace run on 2026-10-04 (after Chirag's rulings 2.1 to 2.10)

Rulings recorded in `SLICE2_READINESS.md` section 5. Stopped at the review to workspace flow: no contractor or professional work, RFQ or quotes, inspections, Build Record or Slice 3.

| Area | Built |
|---|---|
| Project transitions | `SUBMITTED → ACCEPTED` (accept), `SUBMITTED → NEEDS_INFO` (ask), `NEEDS_INFO → SUBMITTED` (resubmit), `SUBMITTED → CANCELLED` and `NEEDS_INFO → CANCELLED` (cancel). Each writes status history and an audit row with the role and, for ask and cancel, the message or reason. No REJECTED state; no way out of CANCELLED |
| Queue | `CLAIMED → RESOLVED` (resolve). Accept, ask and cancel of a SUBMITTED project need the actor's own claim and resolve the item; a NEEDS_INFO project has no open item and can be cancelled directly. Resubmission opens a new item |
| Migration `0006_review_and_workspace` | `spec_packages`, `spec_line_masters`, `spec_line_master_versions` (seeded from S04, ACTIVE), `stage_instances`, `project_spec_lines`, `spec_line_events` (append-only by trigger). Up, down and up verified on the test database |
| S04 seed | `tools/extract_s04_spec_lines.py` reads S04 tables 3, 5 to 7 and 10 and writes `apps/api/migrations/data/spec_lines_v1.json`; `--check` and a test confirm the JSON still equals S04. 67 lines: A 21, B 22, C 24. Structural (†): A01, A02, A04, A05, A09, A12, A13, A19, each with no brand category (S04's value kept only in the JSON as `s04_brand_category`) and engineer sign-off PENDING. Long lead: B07, B14, C16 to C22 |
| Workspace creation | Inside the accept transaction, under a row lock on the project: stage instances from the active stage master (stages 5, 6 and 9 once per floor: basement, ground, then each upper floor), then one line per master. Planned dates NULL; decide-by NULL until a schedule exists; gate stages start NOT_INSPECTED. A repeated or concurrent accept returns the existing result and creates nothing |
| Visibility | Homeowner `GET /projects/{id}/workspace` returns stages, packages and lines; `performance_specification` is null for every package until purchased, and nothing can be purchased yet, so all are withheld. Review flags and internal notes never reach the homeowner; the ask message and the cancel reason do |
| Notifications | Events → outbox → `send_notification` job (queue `notifications`, 5 retries, exponential wait) for: requirement submitted, requirement flagged, enquiry received (to operations), needs information, accepted, cancelled (to the family). Operations mailbox from `P2B_OPS_NOTIFICATION_EMAIL`; when unset the job logs and skips. One job per kind and event (queueing lock); the provider receives `kind:event_id` as its idempotency key. Six plain-text templates in `notifications/templates/` are drafts: their wording is not approved |
| Screens | Operations: decision panel (accept with confirmation; ask and cancel with a required message), history card; on phones the review card comes first. Homeowner: needs-information and closed notices, "Update your requirement" with the full form editable, the workspace (stages table with floor labels, gates and "Schedule to be confirmed"; decisions per package with Long lead, Structural and "Engineer sign-off pending" badges and the hidden-specification notice) |

| Check | Result |
|---|---|
| API tests | 340 passed; coverage 95% |
| ruff, mypy strict (120 files), import-linter (with `construction`, `specification`, `notifications`) | Clean; 3 contracts kept |
| Web: ESLint, `tsc`, Vitest 30, `next build`, `check_ui_tokens`, `check_contrast` | Clean |
| Playwright, phone and desktop, axe on every screen | 40 passed, run against the production build |
| Found and fixed | The review queue's `ON CONFLICT` named its partial index predicate as a bound parameter; after five executions on one connection Postgres switched to a generic plan and the insert failed ("no unique or exclusion constraint matching"). The predicate is now literal SQL, with a regression test. The test relay helper now fails on any handler error recorded on the outbox row, which had hidden it. A redelivered event raised `AlreadyEnqueued` in the notification handler; it is now treated as done |
| Test harness notes | E2E runs against `next build` and `next start`: a cold dev server let clicks land before hydration. The suite signs in about 23 times from one address and OTP verification allows 20 per address per 10 minutes, so locally it runs in two batches with `rate_counters` cleared between them; the production limit is unchanged. The queue helper follows "Next page", since the local queue holds more than 50 open items |

## 4f. Slice 3.0 run on 2026-10-05 (free dashboard, after the product-model baseline)

Baseline: `PRODUCT_FLOW_RECONCILIATION.md` v2.0, approved 2026-10-05; decisions PD-01 to PD-26 (IHB_FLOW 32.6). Scope stopped at 3.0: no AI generation, discovery, billing or later work.

| Area | Built |
|---|---|
| Free dashboard | `/projects/{id}` is a dashboard with a section nav (Overview, Requirement, Estimate, Construction stages and Specification once ACCEPTED, Documents). It opens on submission; a draft shows only its overview. Route group `(dashboard)`; the requirement form stays outside it |
| Background review | SUBMITTED shows "Your project is being reviewed by Plan2Build."; NEEDS_INFO shows the message and "Update your requirement"; ACCEPTED says the initial review is complete and that it does not approve the design, budget or any professional; CANCELLED shows the reason, read only |
| Indicative estimate | Stored with each submission in `project_estimates` (immutable) with its inputs and rate card; DEMO card outside production, "not available" otherwise (no invented figures); "Not sure yet" area gives no estimate; resubmission adds a row; projects submitted earlier get theirs on first read. Shared `EstimateFigures` component for the public and project estimate |
| Package card | Display only: what the package covers, that every service is optional, and its availability (NOT_SUBMITTED, UNDER_REVIEW, ELIGIBLE, NOT_ELIGIBLE). `purchasable` is false everywhere; no price, no button |
| A/B/C as groups | Table `spec_groups`, column `spec_line_masters.spec_group`; API `groups`; "Group A: Structure"; per-group `purchased` flag and `purchased_packages()` removed |
| F-09 | Setting `P2B_SPEC_CRITERIA_BEFORE_PACKAGE` (default false, per ruling 2.6); the workspace response says `criteria_visible` |
| Copy | Operations accept dialog and the family's accepted email describe ACCEPTED as the initial eligibility review only |

| Check | Result |
|---|---|
| Migration `0007_dashboard_and_estimates` | Up, down and up on the test database; no model drift (`alembic check`); dev database at 0007 |
| API tests | 351 passed (11 new in `test_dashboard.py`); coverage 95% |
| ruff, mypy strict (122 files), import-linter | Clean; 3 contracts kept |
| Web: ESLint, `tsc`, Vitest 30, `next build`, `check_ui_tokens`, `check_contrast` | Clean |
| Playwright, phone and desktop, axe on every screen, production build | 40 passed. New checks: dashboard on submission, section nav with aria-current, estimate with DEMO marking, requirement and documents areas, accepted notice wording, no buy button, construction stages, specification groups with criteria hidden, no "Package A/B/C" text |
| Found and fixed | The MFA confirmation hashes ten recovery codes with argon2id and took up to 6 s with six parallel enrolments; the e2e wait for the codes was 5 s and now allows 20 s (product unchanged). Stale `.next/dev` route types broke `next build` after the route move; cleaned |

## 4g. Slice 3.1 run on 2026-10-05 (AI design concepts)

Rules: PD-05, PD-22, PD-27 (F-08 first version). Stopped at 3.1: no billing, credits checkout, discovery or later work.

| Area | Built |
|---|---|
| Module `designs` | Models, prompt sanitiser and renderer, image finaliser, service (quota, request, job, list, reference), outbox handler, job on queue `ai`, router |
| Provider abstraction | `core/images.py` (`ImageProvider`, `ImageRequest` with prompt and image parameters only); `integrations/ai_images.py`: `demo` (deterministic local placeholders, zero cost) and `none` (off). Setting `P2B_AI_IMAGE_PROVIDER`, default `none`; production refuses `demo`. No vendor adapter until AQ-15 |
| Pipeline | POST with idempotency key, advisory locks on account then project, quota check, frozen sanitised snapshot, prompt from the ACTIVE template version, QUEUED row, `design.generation_requested`; handler defers one job per generation; job QUEUED to RUNNING, provider with timeout and configured attempts, decode, size and format checks, re-encode as JPEG without metadata with "Illustrative concept" burned in, private storage as AI_CONCEPT, SUCCEEDED; or FAILED with a reason. Stale in-flight rows expire (STALE) so they never hold quota |
| Quotas | Count QUEUED, RUNNING, SUCCEEDED; never FAILED. 3 free per project, 3 projects and 10 generations per account per rolling 24 hours, all settings. Generation needs a submitted requirement; paused in NEEDS_INFO; not for closed projects |
| Reference | `design_references` with authority fixed to ILLUSTRATIVE_ONLY; generations CHECK `is_authoritative = false`; marking starts nothing else |
| Files | `file_objects` purpose AI_CONCEPT; generated key; private bucket; inline signed links, each logged; excluded from the Documents list and the upload count |
| Screens | Designs area (gallery, Generate My Design, view choice, free count, waiting and generating with polling, failed with "did not use one of your free designs" and Try again, quota and other blocks), design detail (illustrative warning, details, Use as design reference), overview card (free count, latest concepts) |

| Check | Result |
|---|---|
| Migration `0008_ai_design_concepts` | Up, down and up on the test database; no drift; dev database at 0008 |
| API tests | 370 passed (19 new in `test_designs.py`); coverage 95%; `designs.service` 96% |
| ruff, mypy strict, import-linter (with `designs`) | Clean; 3 contracts kept |
| Web: ESLint, `tsc`, Vitest 30, `next build` | Clean |
| Playwright, phone and desktop, axe on every screen | 42 passed (new `designs.spec.ts`) |
| Live checks | Stored prompt of a real local generation contains design facts only; unsigned GET of the stored image returns 403 |
| Found and fixed | Finishing a generation set SUCCEEDED before the file id, and an autoflush hit the CHECK; values are now set together. The provider defaulted to `demo`, which a production settings test caught; the default is now `none`, and local Compose and tests opt in |

Slice 3.1 close-out (2026-10-05, after Chirag's approval). Kept as approved: one image per generation for the chosen view (outside, or inside: the living room); daily limits over a rolling 24 hours, as settings. Changed: the prompt includes the setbacks the family gave (numeric sides only; "Not sure" sides and unknown setbacks are left out, never guessed); a design reference is reversible (`DELETE .../reference`; migration `0009_reversible_design_references` adds `removed_at` and `removed_by`, one active reference per concept, history kept). Removing a reference changes nothing else: the generation row, its quota count and its illustrative status are untouched (tested). Results: migration 0009 up, down and up twice, no drift; 374 API tests (23 in `test_designs.py`), 95% coverage; Vitest 30; Playwright 42 on phone and desktop with axe, including remove and re-mark; production build clean; live checks: the stored prompt of a local generation carries the setbacks and no personal data, and an unsigned GET of the image returns 403. Found and fixed: the 0009 downgrade named the check constraint with its prefix, which the naming convention adds again; it now uses the short name.

## 4h. Slice 3.2 run on 2026-10-05 (professional registration, approval and free discovery)

Rules: SLICE3_2_READINESS.md section K0 (D-01 to D-11, confirmed by Chirag); D-05 OPEN, so no contractor enlistment class anywhere. Stopped at 3.2: no package purchase, connection, leads, messaging, RFQ, quotes, payments, ratings or recommendation changes.

| Area | Built |
|---|---|
| Categories and checklists | `service_categories` (7 categories, specialist subtypes as rows with a parent) and `listing_requirement_versions` (one ACTIVE version per category, requirements as data, `validity_months` 12, `reapply_months` 6). Version 1 seeded from D-02 as POC defaults; nothing hard-codes a registration body. `catalog.listing.unmet` evaluates a requirement set against recorded checks |
| Module `professionals` | Profile (one per account, created on first use), categories (listing state per professional and category), evidence (documents, references, portfolio items), verification cases and append-only checks, append-only listing history. Listing state machine: DRAFT, PENDING_REVIEW, CHANGES_REQUESTED, LISTED, REJECTED, SUSPENDED; only approval lists; `hidden` is the professional's own flag, separate from every state |
| Onboarding | Self-registration on the professionals host by emailed code; operations-created accounts (`identity.accounts.create_account_for`) enter the same flow. Name and firm fixed once a category is submitted. No fees |
| Evidence | Uploads with purposes VERIFICATION_EVIDENCE and PORTFOLIO through the existing presign, worker and ClamAV path; owner-only logged links; operations read through the staff link. Evidence is frozen while a category is in review. The page re-reads while a file is being scanned |
| Operations | Queue kind PROFESSIONAL_REVIEW fed by `professional.category_submitted`; detail page with requirements met or unmet, documents, references, portfolio review, recorded checks, decisions (approve, request changes, reject; claim and idempotency key), suspension and reinstatement with a reason (OPS or ADMIN, MFA), history; account creation |
| Public | Directory `/professionals` and profile `/professionals/{id}` on the homeowner host, no sign-in. Neutral daily shuffle (md5 of id and date), cursor pages of 24. Filters: category, subtype, name or firm, locality; signed-in families also "Near my project" (plot inside the service radius). Profile shows D-01 fields, what was verified, registration issuer and number when verified, approved portfolio; never contact details, documents, notes, reviewer or reasons. Project dashboard gains a Professionals link |

| Check | Result |
|---|---|
| Migration `0010_professionals` | Up, down and up on the test database; no drift; dev database at 0010 |
| API tests | 388 passed (14 in `test_professionals.py`; route guard lists the 3 new public routes); coverage `professionals.service` 84%, `professionals` router 93%, `operations.professionals_router` 99%, `catalog.listing` 94% |
| ruff, mypy strict, import-linter (with `professionals`) | Clean; 3 contracts kept; no warnings |
| Web: ESLint, `tsc`, Vitest 30, `next build` | Clean |
| Playwright, phone and desktop, axe on every screen | 46 passed (new `professionals.spec.ts`: registration to approval, public directory and profile, hide and show, suspend and reinstate; project filter) |
| Found and fixed | Two first requests for a new professional raced to create the profile and one failed on the unique key; creation is now `INSERT ... ON CONFLICT DO NOTHING` (regression test). Local storage CORS allowed only the homeowner host, so professionals' uploads failed; the professionals host is now allowed too. A `smallint` radius overflowed when converted to metres; it is cast first. The mobile menu axe check ran mid-animation; the helper now waits for it. The professionals host smoke test expected the old placeholder page |

Not built in 3.2 and reported: email notifications to professionals about decisions; operations editing a locked name or firm; automatic hiding of listings past their re-verification date; mapping a project's services needed to categories (the project filter uses location only); a public bucket for portfolio images (signed links are used).

## 4i. Slice 3.3 run on 2026-10-05 (package eligibility, billing core, AI credits)

Rules: SLICE3_3_READINESS.md (approved), section 0 locked decisions L-01 to L-08. No live money: the fake gateway locally and in tests; production refuses TEST configuration, the fake gateway and non-live keys.

| Area | Built |
|---|---|
| Eligibility (F-05) | `eligibility_checklist_versions` (v1 seeded with the five L-02 checks), `eligibility_assessments` (append-only). Accepting needs every item PASSED; the accept dialog records each item with a note; the review page shows the record |
| Module `billing` | Offerings (closed set PACKAGE, AI_CREDIT), versioned pricing rules (base, bands, conditions), instalment plans (first due on order, later due days after activation, never a construction stage), tax configuration (accountant's values; empty until published), offering versions; immutable once published (trigger) |
| Orders | Server price, tax by the buyer's state, dues that add up exactly, buyer and terms snapshot; amounts immutable (trigger); one open package order per project |
| Payments | Gateway interface (`core/payments.py`), Razorpay adapter and fake adapter; checkout reuses an open attempt; the browser callback verifies its signature and only queues a verified fetch; webhooks verified on the raw body, stored once, processed by a job under the order lock; captures applied once for the exact amount; wrong amount, unknown order, second capture and capture after cancellation become exceptions; late captures on expired or failed attempts apply |
| Reconciliation | Every 15 minutes: open attempts past the check window fetched (captures applied, authorised-only flagged, empty ones expired), processing refunds checked, unpaid-order sweep when configured. Daily 03:00 IST: captures of the last 3 days matched |
| Package | Entitlement ACTIVE on the first verified capture, history kept; ADMIN cancels with reason and MFA; activation changes no project status; criteria visibility reads it |
| Refunds | Buyer or staff request; OPS or ADMIN approve (amount up to what remains refundable, end the package or revoke an unused credit) or decline, with a reason the family sees; one provider refund per payment, idempotent by our id in the notes; retry after failure; credit notes |
| Invoices | Issued only after a verified capture or a completed refund; gapless numbers per series and Indian financial year; lines and tax lines; PDF rendered by a job (fpdf2, TEST banner for TEST orders), stored privately, logged links |
| AI credits | Append-only ledger with running balance; GRANT only on verified capture; CONSUME only with "Use 1 AI credit"; RETURN once per failed or stale paid generation |
| Screens | Homeowner: package page, order page with checkout (Razorpay or the fake test panel), billing page, buy a credit, credits in the designs area, overview card and Package section. Operations: accept dialog with the checklist, billing overview, order, refund and exception screens. ADMIN: configuration with drafts, publish, price preview, eligibility versions, reconciliation |
| Launch gate N-01 | `infra/r2/cors.{production,staging,local}.json` with exactly the homeowner and professionals hosts; `apps/api/scripts/check_r2_cors.py` validates a policy and runs live preflights; local storage allows the same two origins |

| Check | Result |
|---|---|
| Migration `0011_billing` | Up, down and up twice on the test database; `alembic check` clean on the test database; dev database at 0011 with TEST configuration seeded (its `alembic check` lists only the PostGIS tiger-geocoder and topology extension tables the database image installs there, no application table) |
| API tests | 450 passed (62 new in `test_billing.py`, `test_billing_rules.py`, `test_billing_operations.py`, `test_r2_cors.py`, the R2 preflights live against local storage); billing modules 82% covered before the operations tests were added |
| ruff, mypy strict, import-linter | Clean; 4 contracts kept, including "billing never imports professionals, construction or specification" |
| Web: ESLint, `tsc`, Vitest 30, `next build` | Clean (final state) |
| Playwright, phone and desktop, axe on every screen | 52 passed from the final code state (closure run, 2026-10-05: production build, four batches with rate limits reset, 32 + 10 + 4 + 6, no retries). `billing.spec.ts` covers the eligibility checklist, the package offer, an order, the fake checkout with a failed then a verified payment, package activation with the project unchanged, the refund decided by operations, an AI credit bought, spent only by choice, returned once when a paid generation fails (worker held, request aged past the stale limit) and spent again, and the operations and ADMIN screens |
| Found and fixed | Timestamps set as SQL `now()` left attributes unloaded (MissingGreenlet) and autoflush broke the entitlement CHECK: timestamps are read from the database clock without autoflush. The order page treated the earlier failed attempt as the outcome of a retry and stopped waiting: it now compares against the attempt shown when paying started. The admin page's scrollable JSON was not keyboard-focusable. The migration autogenerate put the downgrade cleanup in `upgrade()`; caught on first run and moved. Two test modules each built a job app from billing's blueprint, which binds to the first app: one shared fixture now. In the closure run, axe measured two dialogs mid-animation on the phone (blended colours); the tests now wait for the dialog's animation, as they already did for the phone menu |

## 4j. Slice 3.4 run on 2026-10-05 (modular services and connection)

Rules: SLICE3_4_READINESS.md section 0 (N-01 to N-12, confirmed); build result in its section R. Module `engagements` with migration `0012_engagements`: needs per category from the requirement (data mapping), package-gated connection requests (3 open per category, 48 hours, decline reasons, withdrawal), one active engagement per category, outside professionals, files shared by choice, N-10 withdrawals on refund or cancellation, N-12 usage on acceptance, quote-review intake, N-11 emails, and homeowner, professional and operations screens.

| Check | Result |
|---|---|
| Migration `0012_engagements` | Up, down, up; `alembic check` clean on the test database |
| API tests | 468 passed (18 new in `test_engagements.py`) |
| ruff, mypy strict, import-linter | Clean; 4 contracts kept |
| Web: ESLint, `tsc`, Vitest 30, `next build` | Clean |
| Playwright, phone and desktop, axe | 56 passed (32 + 10 + 8 + 6, production build, rate limits reset per batch) |

## 4k. Slice 3.5 run on 2026-10-05 (authoritative design and Build Plan)

Rules: SLICE3_5_READINESS.md section 0 (BP-01 to BP-20; BP-07A deferred). Result and checks: `SLICE3_5_IMPLEMENTATION_REPORT.md`. Module `buildplan`, migrations `0013_buildplan` and `0014_acceptance_statements`, item rate cards in `catalog`, confirmation codes in `identity`, functional screens on all three hosts. Status: implementation COMPLETE (approved 2026-10-05); production readiness NOT YET READY. PDF engine reconciled: ADR-023 (fpdf2) supersedes ADR-018.

## 5. Handover plan (Chirag's rulings, 2026-10-04)

Dates are engineering targets, not promises of feature completeness. A part is complete when its acceptance criteria hold and the named tests pass on the stack.

### 5.1 Handover 1: client acceptance MVP

| Part | Content | Acceptance | Status on 2026-10-04 |
|---|---|---|---|
| Public: website | Home with the client's S14 hero and calls to action | Pages render on the homeowner host; axe clean | Home built; the rest of the website waits for client content (blocker W-01) |
| Public: estimator | `/estimate`: area, floors, quality tier; range, per sq ft, stages | The DEMO card is always labelled; production shows "not available" until an approved card exists (D-16) | Built and verified (e2e) |
| Public: Raipur flow, coming soon, other city | `/start` (two entry questions, L.1), `/need-help` (type of work and email, R-1), `/other-city` (email, R-2) | Enquiries reach the database and the outbox; no change of page on input | Built and verified (e2e) |
| Public: email OTP and registration | Sign-in creates the account at verification (B-03), then returns to the page that asked | Codes from Mailpit; HttpOnly cookie; `next` cannot leave the site | Built and verified |
| Public: requirement questionnaire | `/projects/new`, `/projects/{id}/requirement`: five steps from the served set, then review and submit | The seeded set equals section L (test); the API validates answers; drafts saved with optimistic locking | Built and verified |
| Public: map and location | Leaflet pin, device location, typed coordinates; locality from the pin, correctable (R-3) | A locality the family typed is not overwritten by a later pin | Built and verified; production tiles and geocoder are blockers M-01 and M-02 |
| Public: uploads | Presigned PUT to storage, completion, worker checks, download links | Type, size and count come from the question set; a file is downloadable only after the checks | Built and verified |
| Public: project creation, submission, Submitted dashboard | `/projects`, `/projects/{id}` | Status Submitted with the next step; another family gets 404 | Built and verified |
| Operations: staff login | Staff accounts on the admin host with MFA (SECURITY 4.1) | Roles checked server-side; MFA within 8 hours on every operations route | Built and verified (section 4d) |
| Operations: submission review, review and accept states, workspace foundation | Queue of SUBMITTED projects with their review flags; `SUBMITTED` to `NEEDS_INFO` or `ACCEPTED`; workspace created on ACCEPTED from the stage master configuration | STATE_MODEL 5; no fake durations | Queue, detail, claim built and verified (4d); decisions and workspace wait for `SLICE2_READINESS.md` section 2 |
| Infrastructure: staging and production deployment, database, email, backups, security checks, monitoring | Section 6 items 4 to 7; Supabase, R2, Resend, ClamAV on the VPS, Sentry, Grafana | Restore drill passes; CI green; alerts fire | Not started; needs AQ-29 and the accounts (D-13) |

### 5.2 Handover 2: POC completion

Build Plan, the 67 specification decisions, contractor sourcing, professional portals, RFQ, quote submission, normalisation, recommendation, inspections, variations, payment-status tracking (homeowners and professionals pay each other directly; CD-01), the Build Record, and the remaining administration. Each becomes a slice with acceptance criteria once Handover 1 is accepted. Inputs already settled: the brand category is dropped from the five structural lines A04, A05, A09, A12 and A13 with no replacement (D-03); stage durations come only from an approved stage configuration or an operations-entered schedule (D-04).

### 5.3 Stage master and durations (D-04 ruling)

`stage_master_versions` (version, status DRAFT, ACTIVE or RETIRED, source note, approved by, activated at; one ACTIVE at a time) and `stage_masters` (version, number, code `STAGE_nn`, name, sequence, flags, `default_duration_days`, `cost_share_pct`). Version 1 is seeded ACTIVE with the 16 S04 names and flags, and NULL durations and cost shares. A stage without a duration shows "Schedule to be confirmed"; planned dates come only from an approved configuration or a schedule entered by operations. No code assumes a duration.

## 6. Remaining foundation work (not started)

1. The remaining provider interfaces (K), as slices first need them.
2. The Redis adapter for the rate limiter (waits for Upstash; the Postgres counters work now).
3. Pruning of `rate_counters`, expired `otp_challenges` and processed outbox rows (the `prune_and_archive` job).
4. Nonce-based CSP, report-only for a fortnight, then enforced (SECURITY 6). Slice 1 now ships interactive pages, so this is due before Handover 1: `connect-src` must name the storage public endpoint and `img-src` the map tile host.
5. `/metrics` endpoint and Grafana Alloy configuration (ADR-017).
6. Production and staging Compose files, the production Caddyfile with the origin certificate, `bootstrap-vps.sh`, `deploy.sh`, backup and restore scripts, database role bootstrap SQL (`app_rw`, `app_migrate`, `app_readonly`) for Supabase.
7. GHCR push, staging deploy and production deploy workflows (after AQ-29).
8. Periodic maintenance jobs (`prune_and_archive`, `backup_database`, `job_runs`, `job_failures`) as their tables arrive; include `idempotency_keys`, `geocode_cache`, and abandoned `PENDING_UPLOAD` files with their incoming objects.
9. Operations notification for `requirement.submitted` and `enquiry.created`: the events are published, but no handler sends anything yet.

## 7. Running it

```bash
pnpm install
pnpm local:up
pnpm dev:web
```

Optionally `pnpm local:demo-rates` (loads the DEMO rate card). On first start ClamAV needs about a minute and 1.5 GB of memory to load its signatures; uploads show "Checking" until then. Then open `http://ihb.localhost:8080`, `http://pro.localhost:8080`, `http://admin.localhost:8080`; sign-in codes arrive in Mailpit at `http://localhost:8025`. API tests: `pnpm test:api` (needs `uv` and the Compose database). Web: `pnpm test:web`, `pnpm lint:web`, `pnpm test:e2e` (needs the stack and `pnpm dev:web` running).
