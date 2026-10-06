# ADR-009: Postgres-backed job queue (Procrastinate) with a transactional outbox; no Kafka, no Redis broker

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03); Chirag delegated the choice ("you decide which is better") on 2026-10-03 |
| Deciders | Chirag, Sakha |
| Related | EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md, ADR-003, ADR-007 |

## Context

Background work: notification delivery, PDF rendering, file scanning and variants, image generation, recommendation computation, nightly metrics, deadline and expiry sweeps, reconciliation, backups. Volume at the POC: hundreds of jobs per day. Chirag's baseline: the simplest reliable mechanism on the VPS, no Kafka, with a migration path to a managed queue.

## Decision

Procrastinate (a Python job library on PostgreSQL) runs the queues using `SELECT ... FOR UPDATE SKIP LOCKED` and `LISTEN/NOTIFY`. Domain events are written to an `outbox_events` table inside the business transaction; a relay task fans them out to handlers and jobs. Named queues (`priority`, `notify`, `render`, `files`, `ai`, `engine`, `maintenance`) have per-queue concurrency. Retries with exponential backoff and jitter; failed jobs are the dead-letter state with an alert. Periodic tasks replace cron. All enqueueing goes through `core.jobs.enqueue` so the backend can change.

## Why

- Transactional enqueue: a job or event exists if and only if the business change committed; no lost or phantom side effects. This removes a whole class of bugs that broker-based setups must handle with outbox patterns anyway.
- No second stateful system to secure, back up or monitor on a single VPS.
- Postgres handles thousands of jobs per minute with SKIP LOCKED; the POC needs hundreds per day.
- Procrastinate is small, typed, async-friendly and maintained; its schema is separate (`procrastinate` schema), so it does not pollute the application schema.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Celery with Redis or RabbitMQ | Industry standard, but needs a broker (Redis free tier would be consumed by polling; RabbitMQ is another container), has weak transactional guarantees, and is heavier than the need |
| Dramatiq or RQ with Redis | Same broker objection; simpler than Celery but still non-transactional |
| Kafka or Redpanda | Streaming infrastructure for a product with hundreds of events a day; operationally expensive; explicitly excluded by the baseline |
| Cron plus database polling without a library | Reinvents retries, locking and visibility; Procrastinate provides them |
| Upstash QStash or a managed queue | Adds external latency to every job and a dependency for OTP delivery; keep as the migration target |

## Consequences

- The worker needs a session-mode database connection for LISTEN/NOTIFY (not the transaction pooler).
- Job tables add write load to the database; pruning keeps them small (14 days of succeeded jobs).
- Throughput ceiling (tens of jobs per second) is far above the POC; the trigger for a managed queue is in SCALABILITY_AND_MIGRATION_PLAN.md.

## Migration path

Replace the `enqueue` adapter and the relay target; handlers are plain functions; the outbox row format is already the message format for a broker topic.
