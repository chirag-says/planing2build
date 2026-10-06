# ADR-005: One Hostinger KVM VPS with Docker Compose; staging as a second stack on the same host

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03); staging placement decided by Chirag 2026-10-03 |
| Deciders | Chirag, Sakha |
| Related | CLOUD_AND_HOSTING_ARCHITECTURE.md, SCALABILITY_AND_MIGRATION_PLAN.md, ADR-016 |

## Context

The POC serves 30 to 100 active users per day with a peak under 5 requests per second. S06 proposed AWS ap-south-1 with managed services; Chirag's baseline is a Hostinger KVM VPS (2 vCPU, 8 GB, 100 GB NVMe) with Docker Compose and no AWS or Kubernetes.

## Decision

One VPS runs Caddy, Next.js, FastAPI, the worker, ClamAV and the monitoring agent as Compose services, plus a second Compose stack for staging with its own database project, buckets and secrets. The VPS is a deliberate single point of failure for compute; data lives in Supabase and R2. A rebuild from the repository takes under 2 hours.

## Why

- The workload fits in about 4 GB of RAM and a fraction of two vCPU with headroom (CLOUD_AND_HOSTING_ARCHITECTURE.md section 2.2).
- ₹799 to ₹1,199 per month against ₹8,000 and up for the smallest managed-Kubernetes or multi-service cloud layout.
- Compose is readable by any developer; the whole environment is one file per stack.
- Staging on the same host costs nothing extra and runs the same images; its data is synthetic so sharing a host carries no privacy risk, and it can be stopped during an incident.

## Alternatives considered

| Alternative | Why not |
|---|---|
| AWS or GCP with managed services | Cost and operational surface out of proportion to the load; the baseline excludes it for the POC |
| Two VPS from day one (application and worker) | Doubles the fixed cost before any signal; stage 4 of the scaling plan when the trigger appears |
| Platform-as-a-service (Railway, Render, Fly) | Convenient, but three services plus a worker plus ClamAV lands at $40 to $80 per month with less control over networking and India regions |
| Staging on a separate small VPS | Cleaner isolation for ₹500 to ₹800 per month; not justified while staging holds synthetic data; revisit if staging needs anonymised production copies regularly |

## Consequences

- Availability depends on one machine; the 99.5% target leaves about 44 hours per year, enough for a rebuild and Hostinger maintenance; measured monthly.
- A heavy staging test can affect production; staging runs at half limits and is stopped during load tests of production-like scenarios (which run against staging anyway with production stopped from the equation by scheduling).
- All configuration must be reproducible from `infra/` or the rebuild promise fails; the quarterly drill checks it.

## Migration path

Stages 2, 4 and 5 in SCALABILITY_AND_MIGRATION_PLAN.md: bigger VPS, split worker to a second VPS, two application nodes behind Cloudflare load balancing. Nothing in the application changes.
