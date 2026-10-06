# Plan2Build: observability, operations, backups and recovery

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/01_ARCHITECTURE/OBSERVABILITY_AND_OPERATIONS.md` |
| Version | 0.1 (proposed) |
| Date | 2026-10-03 |
| Status | Architecture proposal for Chirag's review. Tooling confirmed by Chirag on 2026-10-03: Sentry plus Grafana Cloud free tier plus an external uptime check. |
| Business authority | S06 §8 (alerts for failed payments, failed jobs, sync conflicts), BR-154 (99.5%), BR-158 (backups with point-in-time recovery, India), S06 §16, S01 §20 ("a production system is defined as much by its failure paths") |
| Related | CLOUD_AND_HOSTING_ARCHITECTURE.md, SECURITY_ARCHITECTURE.md (security events), PERFORMANCE_ARCHITECTURE.md (targets), EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md (job metrics) |

## 1. Signals

| Signal | Producer | Transport | Store | Retention |
|---|---|---|---|---|
| Application logs (structured JSON: timestamp, level, service, request id, user id, route, status, duration, event, ids) | Next.js, FastAPI, worker, Caddy access log | Docker json-file, collected by Grafana Alloy | Grafana Cloud Loki (free tier 50 GB per month) | 14 days in Loki; 30 days locally rotated |
| Errors and traces | Sentry SDKs (browser, Next.js server, FastAPI, worker), 10% transaction sampling, 100% error sampling | HTTPS | Sentry | Per plan (90 days on the developer plan) |
| Metrics (host, containers, API histograms, job counters, queue depth, database stats) | Alloy (node and Docker exporters), FastAPI `/metrics` on loopback, worker metrics task, Supabase metrics endpoint | Prometheus remote write | Grafana Cloud Mimir (free tier 10K series) | 14 days |
| Uptime | UptimeRobot checks every 5 minutes: three hosts, `/readyz`, staging home | External | UptimeRobot | 12 months of status |
| Audit and security events | Application | Postgres | `audit_events`, `security_events` | DATA_ARCHITECTURE.md retention |
| Business counters (projects by state, leads sent, quotes, inspections, payments) | Nightly analytics job | Postgres | `analytics_daily` | Permanent |
| Cost signals (provider calls, image generations, R2 class A operations, Redis commands) | `integration_calls`, provider dashboards | Postgres plus manual monthly check | | 90 days |

Request id flows from Caddy (`X-Request-Id`) through Next.js to FastAPI to jobs (stored on the outbox row and job payload) so one id ties a user action to its side effects. Logs never contain contact values, addresses, document contents or codes; a log allow-list in the logging configuration enforces it.

## 2. Dashboards (Grafana)

| Dashboard | Panels |
|---|---|
| Service health | Request rate, error rate (4xx, 5xx), p50/p95/p99 by route group, container CPU and memory, disk, swap, VPS load |
| Jobs | Queue depth and oldest age per queue, success and failure rate, duration p95 per job, outbox unprocessed count and age, periodic job last run age |
| Database | Connections (pooler and direct), statement p95, slow queries, table bloat, disk use, replication (none at the POC) |
| Business | Projects by state, leads by state, RFQs open, inspections due, payments captured today, OTP success rate, notification delivery rate per channel |
| Security | OTP lockouts, failed logins, CSRF rejections, webhook signature failures, admin logins by IP, permission denials |
| Cost | Image generations per day, R2 operations, Redis commands, email sends |

## 3. Alerts

Routed to Chirag and the on-call developer by email and a chat webhook (AQ-31 for the channel). Severity sets the response window: page (15 minutes), notify (next working hour), weekly digest.

| Alert | Condition | Severity |
|---|---|---|
| Site down | Any production host fails two consecutive external checks | Page |
| API errors | 5xx rate above 2% over 5 minutes, or any 5xx on `/webhooks/*` | Page |
| Database unreachable or `/readyz` failing | 2 minutes | Page |
| Payment webhook failures | Signature failure above 5 per hour, or an `AMOUNT_MISMATCH` event, or an attempt in INITIATED above 60 minutes | Page (mismatch), notify (others) |
| Jobs | `priority` queue oldest age above 2 minutes; any queue above 200 jobs or oldest above 10 minutes; a job reaching its failed state; a periodic job missing its run by 2x | Page (priority), notify (others) |
| Outbox | Unprocessed rows older than 5 minutes or any row with 10 attempts | Notify |
| OTP delivery | Delivery failure rate above 10% over 15 minutes | Page |
| Notifications | Channel failure rate above 20% over 30 minutes | Notify |
| Resources | Memory above 85% for 10 minutes; swap in use; disk above 80%; CPU above 90% for 15 minutes | Notify (page on disk above 90%) |
| Backup | Nightly dump missing or verification failed | Page next morning |
| Security | Admin login from a new IP; lockouts above 20 per hour; permission denials above 100 per hour for one user; `app_migrate` login outside a deploy | Notify (page for `app_migrate`) |
| Sync | Auditor sync batch rejected (sequence gap or hash mismatch) | Notify |
| Cost | Image generations above the daily cap; Redis commands above 400K in a month; R2 class A above 800K in a month | Notify |
| Certificates and DNS | Origin certificate expiry under 30 days (long-lived, so rare); DNS record drift detected by the weekly check | Notify |

## 4. Runbooks (summaries; the full text lives in `docs/runbooks/`)

| Runbook | Steps |
|---|---|
| Site down | Check UptimeRobot detail; Cloudflare status; SSH to the VPS; `docker compose ps`; Caddy logs; `/readyz`; restart the failing service; if the VPS is unreachable, Hostinger console, then the rebuild runbook |
| Database incident | Supabase status page; connection counts; kill long queries (`pg_stat_activity`); if the Free project paused (idle), restore it from the dashboard (one more reason for Pro); if data corruption is suspected, stop writes (maintenance flag), restore per section 7 |
| Payment mismatch | Open the `billing_exceptions` item; compare the Razorpay dashboard payment with the invoice; if the homeowner paid the right amount against the wrong order, record manually with evidence and reason (admin, MFA); never edit the webhook event |
| Stuck job or poison job | Admin console job failures; read the error; fix data or code; requeue through the admin action (audited) |
| Notification failures | Check the provider status; the `notification_deliveries` failed list; resend through the admin action when the provider recovers; for OTP, tell the user to request again |
| Secret rotation | SECURITY_ARCHITECTURE.md section 9; two-phase for database credentials; restart the stack; verify `/readyz` |
| Suspected compromise | SECURITY_ARCHITECTURE.md section 12 |
| Release and rollback | ENVIRONMENT_AND_DEPLOYMENT.md sections 5 and 7 |
| Capacity | PERFORMANCE_ARCHITECTURE.md section 9 and SCALABILITY_AND_MIGRATION_PLAN.md triggers |
| VPS rebuild | Section 7.3 |

Operational posture: one person on call during the POC (Chirag or the developer), working hours response with a page for the four page-level alerts; documented in the status note shown to the client.

## 5. Operations console as the first line

Operations staff work from queues and the exception feed (S05 O1), never from the database. The console shows failed jobs, failed deliveries, billing exceptions and sync conflicts with one-click audited actions (requeue, resend, record manually, discard with reason). Most incidents the business notices should be resolved there without a developer (S06 acceptance: "without developer intervention").

## 6. Backups

| Backup | Mechanism | Frequency | Location | Retention | Encrypted |
|---|---|---|---|---|---|
| Database (primary) | Supabase daily backups (Pro plan); PITR add-on (7 days) if purchased (AQ-32) | Daily (PITR continuous) | Supabase, Mumbai | 7 days | Provider |
| Database (independent) | `pg_dump --format=custom` from the worker's maintenance job, encrypted with `age` to the backup public key, uploaded to `p2b-backups/{env}/db/{yyyy-mm-dd}.dump.age` | Nightly 01:30 IST | R2 (APAC) | 30 daily, 12 monthly | Yes; private key held by Chirag and one named person, offline |
| Files | R2 objects are the primary copy; versioning is not enabled (objects are immutable and never overwritten); accidental deletes are prevented by the application never issuing deletes outside the prune job's narrow paths | n/a | R2 | Per retention class | Provider |
| Files (secondary copy) | Monthly `rclone sync` of `p2b-prod-private` to `p2b-backups/{env}/files/` (same provider, different bucket and token); a second provider copy when data volume justifies it (SCALABILITY_AND_MIGRATION_PLAN.md) | Monthly | R2 | Rolling | Provider |
| Configuration and infrastructure | `infra/` in git; `.env` files encrypted with `age` and stored in `p2b-backups/{env}/config/` on every change | On change | R2 | 10 versions | Yes |
| Catalog and engine configuration | Versioned rows in the database (covered by database backups); also exported as JSON into the repository's `seeds/` at each publish | On publish | Git | Permanent | n/a |

Free-plan caveat: Supabase Free has no automatic backups, so during the build phase the nightly dump is the only database backup; this is acceptable for synthetic data and is the reason Pro precedes the first real homeowner.

## 7. Recovery

### 7.1 Objectives

| Scenario | RPO (data loss) | RTO (time to service) |
|---|---|---|
| Application container failure | 0 | Under 1 minute (restart policy) |
| Bad release | 0 | Under 15 minutes (rollback) |
| VPS loss | 0 for data (lives in Supabase and R2); in-flight uploads and unsent notifications are retried by clients and jobs | 2 hours (rebuild) |
| Database corruption or accidental mass update | Up to 24 hours with the nightly dump; minutes with PITR if purchased | 4 hours (restore and verify) |
| Supabase region outage | As above | Until the provider recovers, or 4 hours to restore the dump into a new Postgres (another Supabase region or a managed Postgres elsewhere) with a configuration change |
| R2 outage | 0 | Until the provider recovers; the application degrades (no uploads or document opens) |
| Loss of all cloud accounts (worst case) | 24 hours | 1 working day from the encrypted backups and the repository |

### 7.2 Database restore procedure (tested monthly)

1. Declare the incident; set the maintenance flag (API returns 503 with a message; the web shows the maintenance page).
2. Decide the target: PITR to a timestamp (Supabase dashboard, Pro with the add-on), or the nightly dump.
3. For a dump: download `p2b-backups/{env}/db/{date}.dump.age`; decrypt with the offline key; create a fresh database (a new Supabase project, or a scratch database in the same project); `pg_restore --no-owner --role=app_migrate`; run `alembic upgrade head` if the dump predates the current schema.
4. Verify: row counts for `projects`, `users`, `audit_events`, `payment_events` against the last known counts (the nightly job records them in `backup_manifests`); open the admin console against the restored database on staging; spot-check three projects.
5. Reconcile the gap: payments (Razorpay dashboard versus `payment_events` since the restore point; replay missing webhooks from the Razorpay dashboard), uploads (R2 objects newer than the restore point without a `files` row are listed by the reconciliation script and re-registered or quarantined), notifications (deliveries since the point are resent or suppressed by rule).
6. Point the stacks at the restored database (`.env` change, restart), clear the maintenance flag, announce.
7. Post-mortem within 48 hours.

### 7.3 VPS rebuild procedure (tested quarterly on a temporary VPS)

1. Order a new VPS; add the SSH keys; run `infra/scripts/bootstrap-vps.sh` (users, UFW, Docker, Cloudflare IP rules, directories).
2. Restore `.env` files and the origin certificate from `p2b-backups/{env}/config/` (decrypt offline).
3. `git clone` the repository at the production tag; `docker compose pull` and `up -d` for edge, prod and staging.
4. Update the DNS A records in Cloudflare to the new IP (proxied, so the change is immediate for users).
5. Verify `/readyz`, a synthetic login on staging, UptimeRobot green; re-enable alerts.

### 7.4 Verification

- Monthly: restore the latest dump into the staging stack's scratch database and run the row-count checks (`verify_backups` job) plus a manual login.
- Quarterly: full VPS rebuild drill with timing recorded; the measured RTO replaces the target above.
- Every drill writes a dated note in `docs/runbooks/drills.md`.

## 8. Operational calendar

| Cadence | Task |
|---|---|
| Daily (automated) | Backups, reconciliation, metrics recompute, prune; alert review by the on-call |
| Weekly | Dependency updates (Dependabot PRs), base image rebuild, slow query review, cost dashboard glance, Cloudflare IP list refresh (automated) |
| Monthly | Restore drill; fairness report review (engine); availability report to the client; access review (who has SSH, Supabase, Cloudflare, Razorpay, GitHub) |
| Quarterly | VPS rebuild drill; load test on staging; secret rotation for database credentials; DNS and subdomain review |
| Yearly | External penetration test; provider terms review (image API data use, Resend, Razorpay) |

## 9. Open points

| ID | Question | Default until answered |
|---|---|---|
| AQ-31 | Alert channel (email only, or a chat tool such as Slack or Google Chat) | Email plus SMS through UptimeRobot for page-level alerts |
| AQ-32 | Supabase PITR add-on (about $100 per month) at launch, or nightly dumps only | Nightly dumps and Pro daily backups at launch; PITR when the daily payment volume makes a 24-hour loss unacceptable (trigger in SCALABILITY_AND_MIGRATION_PLAN.md) |
| AQ-33 | Named second holder of the backup decryption key | Chirag names one person before launch |
