# Plan2Build: cloud and hosting architecture

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/01_ARCHITECTURE/CLOUD_AND_HOSTING_ARCHITECTURE.md` |
| Version | 0.1 (proposed) |
| Date | 2026-10-03 |
| Status | Architecture proposal for Chirag's review. Hosting decisions confirmed by Chirag on 2026-10-03: Caddy, Next.js on the VPS, staging as a second Compose stack on the same VPS, Supabase Free while building then Pro. |
| Business authority | Chirag's baseline (Hostinger KVM VPS, Docker Compose, Supabase Postgres, R2, Upstash, no AWS or Kubernetes at the POC); BR-150 (99.5% availability target); S06 §11 (private buckets, secrets, backups) |
| Related | SYSTEM_ARCHITECTURE.md (topology), SECURITY_ARCHITECTURE.md (network controls), ENVIRONMENT_AND_DEPLOYMENT.md (how images reach the VPS), OBSERVABILITY_AND_OPERATIONS.md (monitoring, backups, restore), SCALABILITY_AND_MIGRATION_PLAN.md (when to leave this layout), COST_MODEL.md |

## 1. Inventory

| Component | Provider and size | Region | Role |
|---|---|---|---|
| VPS | Hostinger KVM 2: 2 vCPU, 8 GB RAM, 100 GB NVMe, 8 TB transfer (estimate ₹799/month promo, ₹1,199 renewal; re-verify) | India | Runs Caddy, Next.js, FastAPI, worker, ClamAV, monitoring agent, staging stack |
| Database | Supabase Postgres: Free while building (500 MB, pauses after 7 idle days, no automatic backups), Pro before the first real homeowner ($25/month, daily backups, 8 GB) | Mumbai (ap-south-1) | All relational data, the job queue, the outbox |
| Object storage | Cloudflare R2: `p2b-prod-private`, `p2b-prod-public`, `p2b-staging-private`, `p2b-staging-public`, `p2b-backups` | APAC location hint | Every file, rendered document, backup |
| Cache and limits | Upstash Redis free tier (500K commands per month, 256 MB) | Nearest region (Mumbai if offered; otherwise Singapore) | Rate-limit buckets, session cache, small hot caches; the application runs without it |
| Edge | Cloudflare free plan: DNS, proxy, WAF managed rules, origin certificate | Global | TLS termination at the edge, DDoS absorption, caching of static assets |
| Observability | Sentry (developer plan), Grafana Cloud free (metrics, logs), UptimeRobot free | SaaS | Errors, metrics, logs, external uptime checks |
| Email, payments, images | Resend, Razorpay, Gemini API (INTEGRATION_ARCHITECTURE.md) | SaaS | Providers |

No Kubernetes, no managed load balancer, no second VPS at the POC. Everything on the VPS is reproducible from the `infra/` directory of the repository plus the secrets file.

## 2. VPS layout

```text
/srv/p2b/
  edge/            Caddy (one instance for all hosts), ClamAV, Grafana Alloy
    compose.yml
    Caddyfile
    certs/         Cloudflare origin certificate and key (mode 600)
  prod/
    compose.yml    web, api, worker (and osrm when enabled)
    .env           production secrets (mode 600, owner deploy)
  staging/
    compose.yml    web, api, worker
    .env           staging secrets
  backups/         staging area for nightly dumps before upload to R2 (cleared after upload)
```

Docker networks: `edge` (Caddy to each stack's `web` and `api`; ClamAV reachable by both workers), `prod_internal`, `staging_internal`. Only Caddy publishes ports (80 and 443). Every other container binds to the Compose network; nothing binds `0.0.0.0` on the host.

### 2.1 Containers (production stack)

| Service | Image | Replicas | CPU limit | Memory limit | Health check | Notes |
|---|---|---|---|---|---|---|
| `web` | `ghcr.io/<org>/p2b-web:<tag>` (Next.js standalone on `node:22-alpine`) | 1 | 1.0 | 512 MB | `GET /api/health` | Serves all three hosts; middleware routes by host |
| `api` | `ghcr.io/<org>/p2b-api:<tag>` (Python 3.12 slim, uvicorn, 2 workers) | 1 | 1.0 | 768 MB | `GET /readyz` | Same image as the worker, different command |
| `worker` | same image, command `procrastinate worker --concurrency 8` | 1 | 1.0 | 1,024 MB | heartbeat file touched every 30 s | PDF rendering (fpdf2, ADR-023) and Pillow spike here; the limit leaves room |
| `osrm` (optional) | `osrm/osrm-backend` with the Chhattisgarh extract | 0 at the POC | 0.5 | 1,024 MB | `GET /nearest` | Enabled by configuration (AQ-21) |

Edge stack: `caddy` (64 MB), `clamav` (1,536 MB limit; about 1.3 GB resident), `alloy` (256 MB). Staging stack: the same three application services at half the limits.

### 2.2 Resource budget

| Consumer | RAM (typical) | Notes |
|---|---|---|
| OS, Docker, Alloy | 700 MB | |
| Caddy | 50 MB | |
| ClamAV | 1,300 MB | Shared by both stacks; the single largest resident |
| Production web, api, worker | 400 + 450 + 500 MB | Worker peaks to 900 MB during a render |
| Staging web, api, worker | 250 + 250 + 250 MB | Can be stopped during load tests or incidents |
| Total | about 4.1 GB typical, 4.6 GB peak | Leaves over 3 GB for page cache and headroom on 8 GB; a 2 GB swap file is configured for safety, with alerts if it is used |

CPU: 2 vCPU. Request handling is light (SSR plus a few JSON calls per screen); renders and scans are CPU-bound and run one at a time on the worker, which is why their queues have concurrency 1. A render that takes 10 seconds on one vCPU does not affect request latency because uvicorn runs in a different container with its own CPU share.

Disk: OS and Docker 15 GB, images and layers 10 GB, logs 5 GB (rotated), ClamAV signatures 1 GB, OSRM data 5 GB when enabled, temporary processing 10 GB, backup staging 5 GB; under 50 GB in use.

## 3. Operating system and hardening

| Item | Setting |
|---|---|
| OS | Ubuntu 24.04 LTS; `unattended-upgrades` for security patches; reboot window Sunday 03:00 IST when a kernel update requires it (announced in the status note) |
| Users | `deploy` (non-root, in the `docker` group, used by CI over SSH with a deploy key); Chirag's personal key; root login disabled; password authentication disabled |
| SSH | Port 22 open only to listed admin IPs where the team has fixed IPs; otherwise open with key-only auth and `fail2ban`; a WireGuard or Tailscale overlay replaces open SSH when a second person needs access (AQ-25) |
| Firewall (UFW) | Default deny inbound; allow 22 (as above), 80 and 443 only from Cloudflare's published IP ranges (refreshed weekly by a cron job that rewrites the rules); Docker's iptables chains bypass UFW, so no container publishes ports except Caddy, enforced by review of `compose.yml` and a CI check |
| Time | `chrony`; all application timestamps come from Postgres `now()` anyway |
| Docker | Official repository; daemon log driver `json-file` with `max-size 50m`, `max-file 5`; `live-restore` on so a daemon restart keeps containers running; containers run as non-root users inside images; read-only root filesystems where the image allows (web, api); `no-new-privileges` |
| Secrets on disk | `.env` files mode 600 owned by `deploy`; never copied into images; mounted as environment at start |
| Updates to images | Weekly rebuild of base images in CI (patches) even without code changes |

## 4. Reverse proxy and TLS (Caddy)

| Host | Route | Upstream |
|---|---|---|
| `plan2build.in`, `www` (redirect to apex) | `/api/v1/*` | `prod-api:8000` |
| | everything else | `prod-web:3000` |
| `professionals.plan2build.in` | `/api/v1/*` | `prod-api:8000` |
| | everything else | `prod-web:3000` |
| `admin.plan2build.in` | `/api/v1/*` (including `/api/v1/admin/*`, which other hosts cannot reach) | `prod-api:8000` |
| | everything else | `prod-web:3000` |
| `staging.`, `staging-professionals.`, `staging-admin.` | same pattern | `staging-api`, `staging-web`; HTTP basic auth in Caddy on top of the application's own login; `X-Robots-Tag: noindex` |
| `api.plan2build.in` (reserved; no browser origins) | `/api/v1/*` | `prod-api:8000` |
| `files.plan2build.in` | not on the VPS: Cloudflare R2 custom domain on the public bucket | R2 |

Caddy adds `X-Request-Id`, forwards the host and client IP (trusting Cloudflare's `CF-Connecting-IP` only from Cloudflare ranges), sets request body limits (10 MB on API routes; uploads do not pass through Caddy because they go straight to R2 by presigned URL), enables gzip and zstd, and serves the security headers that the application does not set itself. The Caddy admin API is disabled.

TLS: Cloudflare proxies every host with Full (strict) mode; Caddy serves a Cloudflare Origin CA certificate (15-year validity, created in the dashboard, stored in `edge/certs/`). No ACME on the VPS, so there are no rate limits or DNS tokens on the host. `api.plan2build.in` is proxied too. HSTS is set at Cloudflare and at Caddy.

## 5. Database connectivity

| Client | Connection | Why |
|---|---|---|
| `api` | Supabase pooler (Supavisor) in transaction mode, port 6543, TLS required, pool of 10 connections per uvicorn worker | Short transactions; the pooler keeps Postgres connections low |
| `worker` | Session mode (pooler port 5432, or direct) with 4 connections | Procrastinate relies on `LISTEN/NOTIFY`, which transaction pooling cannot carry; long jobs hold their own connection |
| Migrations (`app_migrate`) | Direct, one connection, run as a one-shot container during deploy | DDL and advisory locks |
| People (`app_readonly`) | Supabase dashboard or `psql` over TLS with named accounts | Analysis only; no writes |

Supabase direct connections resolve to IPv6 by default; Hostinger plans vary in IPv6 support. The session-mode pooler is IPv4 and is the default here; if a direct connection is ever required, Supabase's IPv4 add-on is the fallback (AQ-26). Network restrictions (allow-list of the VPS IP) are a Supabase Pro feature; on the Free plan the protection is TLS, strong role passwords and the pooler; this is one more reason Pro precedes real homeowner data.

## 6. Restart, health and failure behaviour

| Event | Behaviour |
|---|---|
| Container crash | `restart: unless-stopped`; health checks mark the container unhealthy after 3 failures and Caddy stops routing to it (Caddy health checks on upstreams) |
| VPS reboot | Docker `live-restore` and `restart` policies bring the stacks back without intervention; Caddy first (edge stack has no dependency), then the stacks; the worker resumes queued jobs |
| Database unreachable | API returns 503 on `/readyz`; Caddy serves a static maintenance page for the web hosts after 30 seconds of failed checks; worker idles with backoff |
| R2 unreachable | Uploads and document opens fail with a clear error; everything else works |
| Redis unreachable | Rate limits and session cache fall back to Postgres; latency rises a little |
| Disk above 80% | Alert; log rotation and image pruning job (`docker system prune` weekly for dangling layers) |
| VPS lost | Rebuild on a fresh VPS from `infra/` in under 2 hours (OBSERVABILITY_AND_OPERATIONS.md section 7); data lives in Supabase and R2 and is untouched; DNS points to the new IP |

Availability arithmetic: the VPS is a single point of failure by design (ADR-005). Hostinger's stated uptime plus a 2-hour rebuild window keeps the yearly target of 99.5% (about 44 hours of allowed downtime) reachable; the measured number is reported monthly from UptimeRobot.

## 7. Staging on the same VPS

Separate Compose stack, separate `.env`, separate Supabase project (Free plan), separate R2 buckets, separate Upstash database, separate Sentry and Grafana environments, hosts `staging.plan2build.in`, `staging-professionals.plan2build.in`, `staging-admin.plan2build.in` behind Caddy basic auth. Images are the same tags that go to production (promotion, not rebuild). Staging data is synthetic or anonymised (ENVIRONMENT_AND_DEPLOYMENT.md section 2); real homeowner data never goes to staging without written authorisation. Staging can be stopped with one command to free resources during an incident.

## 8. Networking and DNS

| Record | Type | Target | Proxy |
|---|---|---|---|
| `plan2build.in`, `www` | A | VPS IPv4 | On |
| `professionals`, `admin`, `api`, `staging`, `staging-professionals`, `staging-admin` | A | VPS IPv4 | On |
| `files` | CNAME | R2 public bucket custom domain | On (managed by R2) |
| `mail` or Resend's required records | TXT, CNAME, MX | Resend (SPF, DKIM, DMARC, return path) | n/a |
| `_dmarc` | TXT | `v=DMARC1; p=none` then `quarantine` | n/a |
| CAA | CAA | Cloudflare and Let's Encrypt | n/a |

Cloudflare settings: Full (strict) TLS, minimum TLS 1.2, HSTS, Always Use HTTPS, Brotli, WAF managed rules, rate-limiting rule on `/api/v1/auth/*` (extra layer above the application), cache rules for `/_next/static/*` (immutable) and the public listing pages (short TTL, bypass on cookie), webhook paths excluded from Bot Fight Mode and caching, no caching for `/api/v1/*` otherwise.

## 9. What is deliberately not here

No load balancer, no autoscaling, no second availability zone, no service mesh, no Kubernetes, no self-hosted Postgres or Redis, no CDN for private files (R2 presigned URLs are direct), no VPN at the POC beyond SSH keys. Each is named in SCALABILITY_AND_MIGRATION_PLAN.md with the trigger that would introduce it.

## 10. Open points

| ID | Question | Default until answered |
|---|---|---|
| AQ-25 | Admin access path when a second person needs the VPS (fixed IPs, or a Tailscale overlay) | Open SSH with keys and fail2ban until then |
| AQ-26 | IPv6 availability on the chosen Hostinger plan | Use the IPv4 session pooler; buy the IPv4 add-on only if a direct connection is ever required |
| AQ-27 | Hostinger VPS snapshots (weekly) as an extra layer | Enable if included in the plan; not relied on for recovery |
