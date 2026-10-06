# ADR-004: Supabase for managed Postgres only; Free while building, Pro before the first real homeowner

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03); plan timing decided by Chirag 2026-10-03 |
| Deciders | Chirag, Sakha |
| Related | ADR-003, CLOUD_AND_HOSTING_ARCHITECTURE.md section 5, OBSERVABILITY_AND_OPERATIONS.md section 6 |

## Context

Chirag's baseline is PostgreSQL on Supabase for the POC. Supabase also offers Auth, Storage, Edge Functions, Realtime and row-level security. Running Postgres on the VPS would save the subscription but put backups, upgrades and disk management on a two-person team. The Free plan pauses after seven idle days and has no automatic backups.

## Decision

Use Supabase as a managed Postgres in Mumbai and nothing else: no Supabase Auth (sessions and OTP are ours, ADR-010), no Supabase Storage (R2, ADR-006), no Edge Functions, no Realtime, no RLS at the POC (authorisation is in the service layer; RLS is a later defence-in-depth option, AQ-05). Connect through the Supavisor pooler: transaction mode for the API, session mode for the worker (LISTEN/NOTIFY). Stay on the Free plan for both production and staging while building with synthetic data; move production to Pro before the first real homeowner's data (daily backups, no pausing, network restrictions).

## Why

- Managed backups, upgrades and monitoring for $25 per month are cheaper than the hours they replace.
- Avoiding Supabase-specific features keeps the database portable (plain `pg_dump`) and keeps every rule in the application where it is tested.
- Free during the build phase costs nothing and loses nothing (synthetic data; nightly dumps still run).

## Alternatives considered

| Alternative | Why not |
|---|---|
| Postgres in a container on the VPS | Saves $25 per month, costs backup discipline, disk management, major-version upgrades and a single point of failure for data as well as compute; wrong trade at this team size |
| Neon, Railway, Render managed Postgres | Comparable; Supabase has a Mumbai region and is the baseline; nothing to gain by switching |
| Supabase Auth and RLS as the authorisation model | Authorisation here depends on project membership, role, state and object (quote owner, inspection assignee); expressing that in RLS policies duplicates the service layer and is hard to test; service-layer authorisation with generated matrix tests is clearer |
| AWS RDS Mumbai | More expensive at this size and against the "no AWS for POC" baseline |

## Consequences

- Residency: data in Mumbai (BR-158 satisfied for the database).
- The Free plan's pause means staging may need a wake-up after a quiet week; a weekly keep-alive query in the scheduled jobs avoids it.
- Pro before launch is a hard gate in the launch checklist (README).
- IPv6 direct connections may not work from the VPS; the pooler is IPv4 (AQ-26).

## Migration path

Change the connection string. Dump and restore to any Postgres 16; no feature lock-in by design.
