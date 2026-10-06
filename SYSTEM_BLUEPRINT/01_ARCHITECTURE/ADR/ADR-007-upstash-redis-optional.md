# ADR-007: Upstash Redis free tier for rate limiting only; the application runs without it

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03) |
| Deciders | Chirag (baseline), Sakha |
| Related | PERFORMANCE_ARCHITECTURE.md sections 5 and 6, SECURITY_ARCHITECTURE.md section 3 |

## Context

Chirag's baseline allows Upstash Redis on the free tier (500K commands per month, 256 MB) "only where valuable". Candidates for Redis: rate limiting, session cache, catalog cache, estimate cache, the job queue, pub/sub for realtime.

## Decision

Redis is used for rate-limit token buckets at the POC and for nothing else by default. The session cache and the estimate cache exist behind flags, off. The job queue is Postgres (ADR-009). Every Redis use has a Postgres or compute fallback so an outage or an exhausted quota degrades precision, not availability. Command usage is alerted at 400K per month.

## Why

- Rate limiting is the one place where a fast shared counter is worth a dependency: it protects OTP endpoints and must be cheap per request.
- Session lookups by hash are sub-millisecond in Postgres through the pooler; caching them would double Redis commands for no measurable gain at POC load.
- Catalog and configuration are cached in process with a version pointer; no network hop is needed.
- Keeping Redis optional removes it from the recovery story.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Redis as the queue broker (RQ, Dramatiq, BullMQ-style) | Loses transactional enqueue; adds a second stateful system to back up; the free tier's command quota would be consumed by polling |
| Redis on the VPS in a container | Free and fast, but one more process to secure and monitor on a single host; Upstash's managed free tier is simpler and the fallback makes either choice low-stakes |
| No Redis at all (Postgres counters only) | Works, but adds a write per request to the database for limits; Redis is the right tool here at zero cost |

## Consequences

- The rate limiter has two implementations (Redis, Postgres) behind one interface, tested with the same suite.
- Quota pressure is a trigger to buy the $10 plan or move the limiter to Postgres for low-value tiers.

## Migration path

Switch to the paid plan or a self-hosted Redis by changing the URL; enable the session cache by flag when measurement justifies it.
