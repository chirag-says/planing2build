# ADR-003: PostgreSQL as the only database (JSONB, PostGIS, full-text search, queue, outbox)

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03) |
| Deciders | Chirag (baseline), Sakha (proposal) |
| Related | DATA_ARCHITECTURE.md, ADR-004, ADR-009, ADR-015 |

## Context

The data is relational and transactional: projects, 67 specification lines per project with events, Build Plan versions, leads, RFQs and quotes, inspections with checkpoints, variations, milestones, invoices and payment events, audit. Some parts are semi-structured (requirement answers, update payloads, engine snapshots). Geospatial queries (service areas, distance) and text search (profiles, specification lines) are needed. The sources mention MongoDB nowhere and OpenSearch nowhere; S06 names PostgreSQL.

## Decision

PostgreSQL 16 is the only database. Semi-structured data lives in JSONB columns with a `schema_version`. PostGIS provides geography points, polygons and distance. `pg_trgm` and `tsvector` provide search. The job queue (Procrastinate) and the transactional outbox live in the same database. Every entity has a UUIDv7 primary key and a human code where people refer to it; states are text columns with CHECK constraints; `version` integers give optimistic locking; append-only tables have no UPDATE or DELETE grants.

## Why

- Transactions across modules (a selection touches rfq, leads, projects and money) are one `BEGIN ... COMMIT`; a second datastore would need sagas for data that fits in one database.
- JSONB covers the schemaless parts without a document store; PostGIS covers geosearch without a dedicated geo service; built-in search covers hundreds of profiles and tens of thousands of specification lines.
- One system to back up, restore, secure and monitor; the POC team is two people.
- The queue in Postgres gives transactional enqueue (no "committed but never enqueued" bugs) and removes a second stateful system.

## Alternatives considered

| Alternative | Why not |
|---|---|
| MongoDB for flexible documents | The data is relational; JSONB gives the flexibility where it exists; no cross-document transactions worth the trade |
| OpenSearch or Elasticsearch | Scale does not justify a second cluster; Postgres search covers it; revisit at a facet-heavy search product |
| Redis as a primary store for sessions or queues | Sessions must survive restarts and be revocable; Postgres is simpler and durable; Redis stays optional (ADR-007) |
| A separate geo index (H3 cells) | Tens to hundreds of members per city; a GIST index answers in milliseconds |

## Consequences

- Query discipline matters: shaped queries, indexes per screen, statement timeouts, `pg_stat_statements` review (PERFORMANCE_ARCHITECTURE.md).
- Large append-only tables get monthly partitions when they pass about 10 million rows.
- JSONB fields are read whole by id, not filtered in hot paths.

## Migration path

Plain Postgres: `pg_dump` moves it to any provider. A read replica, bigger compute and partitioning are the first steps; a purpose-built store appears only with a measured need (SCALABILITY_AND_MIGRATION_PLAN.md).
