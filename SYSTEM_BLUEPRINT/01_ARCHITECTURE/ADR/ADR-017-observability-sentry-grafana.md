# ADR-017: Observability with Sentry, Grafana Cloud free tier (Alloy agent) and UptimeRobot

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03); decided by Chirag 2026-10-03 |
| Deciders | Chirag, Sakha |
| Related | OBSERVABILITY_AND_OPERATIONS.md, PERFORMANCE_ARCHITECTURE.md section 8 |

## Context

The sources ask for alerts on failed payments, failed jobs and sync conflicts (S06 §8), a 99.5% availability target (BR-154) and funnel analytics (S05). The team is small and the budget is near zero; the signals must still be enough to run a production system with real money and life-safety inspections.

## Decision

- Errors and traces: Sentry SDKs in the browser, Next.js, FastAPI and the worker; 100% errors, 10% transactions; PII scrubbing on.
- Metrics and logs: Grafana Alloy on the VPS ships container logs to Loki and host, container, API and job metrics to Mimir on the Grafana Cloud free tier; dashboards and alert rules in Grafana.
- Uptime: UptimeRobot external checks every 5 minutes on the three hosts and `/readyz`.
- Structured JSON logs with request ids end to end; business counters in `analytics_daily`; audit and security events in Postgres.
- Alert routing by email plus SMS for page-level alerts (AQ-31 for a chat channel).

## Why

- Three free tiers cover errors, metrics, logs and uptime with retention adequate for a POC (14 days of metrics and logs, 90 days of errors).
- Sentry's release tracking and source maps make browser and server errors actionable; Grafana's alerting handles thresholds on queues, resources and business signals.
- External uptime measurement is the only honest way to report availability to the client.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Self-hosted Prometheus, Loki and Grafana on the VPS | About 1 GB of RAM and disk growth on a host that is already the single point of failure; the managed free tier is better |
| Datadog or New Relic | Thousands of rupees per month for features the POC will not use |
| Logs only (no metrics) | Queue age, resource pressure and p95 latency need metrics to alert before users notice |
| PostHog for product analytics (S06 names it) | Reasonable later; at the POC funnel events in Postgres and Grafana suffice (AQ-28) |

## Consequences

- Free-tier limits (10K series, 50 GB logs) are watched; label cardinality is kept low (no per-user labels).
- Logs leave the VPS to Grafana Cloud (region per their offering); logs contain ids, not personal data, by the logging allow-list.
- Sentry receives stack traces and request metadata; scrubbing is tested.

## Migration path

Paid tiers of the same tools; OpenTelemetry-compatible exporters mean a vendor change is configuration.
