# ADR-006: Cloudflare R2 for every file; never files in Postgres; presigned URLs both ways

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03) |
| Deciders | Chirag (baseline), Sakha |
| Related | DATA_ARCHITECTURE.md section 6, ADR-011, INTEGRATION_ARCHITECTURE.md section 7 |

## Context

The platform stores drawings, sanctioned plans, evidence photos and videos, inspection evidence, quotes, rendered PDFs, identity documents and backups: tens of gigabytes within a year, served to phones on slow networks. Chirag's baseline: Cloudflare R2 for all large files, never in Postgres.

## Decision

R2 holds every object in private buckets per environment plus one public bucket for approved listing images and one for backups. Browsers upload directly with presigned PUT URLs and download with presigned GET URLs issued by the API after authorisation. The VPS never carries file bytes except inside the worker's processing jobs. Objects are immutable (new version, new key); keys are server-generated.

## Why

- Zero egress fees: photos and PDFs are the dominant bytes and R2 charges nothing to serve them, where S3 egress would be the largest cost line.
- Direct browser-to-R2 transfer keeps the VPS out of the upload path, which matters on a 2 vCPU host.
- S3-compatible API: boto3, presigning and tooling are standard; no lock-in.
- Durability and backups are the provider's problem; the application's job is authorisation and metadata.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Postgres `bytea` or large objects | Bloats the database, backups and memory; the baseline forbids it |
| Supabase Storage | Adds a Supabase-specific layer and policies; R2 is cheaper to serve and keeps the database provider replaceable |
| Files on the VPS disk | No durability, no rebuild promise, and the disk is the host's |
| AWS S3 Mumbai | Egress charges and the AWS exclusion |

## Consequences

- R2's region is "APAC" with a location hint, not India specifically; the residency statement must say so (AQ-08).
- Presigned URLs expire in 15 minutes (5 for identity and financial documents); the client requests fresh ones; every private document open is logged.
- A processing pipeline (sniff, scan, variants) sits between upload and availability; the client sees "processing" for up to a minute.
- Object immutability means a "replace" is a new file row; references point at specific versions.

## Migration path

Bucket-to-bucket sync to any S3-compatible store; the key scheme and the metadata table are provider-neutral.
