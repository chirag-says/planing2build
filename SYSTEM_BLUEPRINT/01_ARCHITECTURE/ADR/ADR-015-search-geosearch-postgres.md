# ADR-015: Search and geosearch in Postgres (pg_trgm, tsvector, PostGIS); no search cluster, no H3

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03) |
| Deciders | Sakha (proposal) |
| Related | DATA_ARCHITECTURE.md sections 5 and 7, ADR-003, AI_AND_RECOMMENDATION_ARCHITECTURE.md B1 |

## Context

Search needs: public listing filters (category, class, locality, services, name), operations search across projects and professionals, specification line lookup, audit search. Geosearch needs: service areas covering a plot, members within a radius, straight-line distance for eligibility and the travel signal. Scale: hundreds of professionals, thousands of projects over years, Raipur first.

## Decision

- Text: `tsvector` columns with GIN indexes for profile and project search; `pg_trgm` GIN indexes for name and code prefix matching; a materialised `listing_entries` projection rebuilt by job for the public listing.
- Geo: PostGIS `geography(Point)` for plot and base points, `geography(Polygon)` for service areas, GIST indexes, `ST_Covers` and `ST_DWithin` for retrieval, `ST_Distance` for the distance signal; OSRM behind an interface only when road time is needed.
- No OpenSearch, Elasticsearch, Algolia, Typesense or H3 grid at the POC.

## Why

- The dataset is small; Postgres answers these queries in milliseconds with the right indexes.
- One system to operate; search results are transactionally consistent with the data.
- PostGIS is the standard for polygon coverage queries; H3 would add a dependency to answer a question GIST already answers.

## Alternatives considered

| Alternative | Why not |
|---|---|
| OpenSearch or Elasticsearch | A cluster to run and sync for a listing of hundreds; revisit at a facet-heavy, multi-city search product |
| Typesense or Meilisearch container | Lighter, but still a second index to keep consistent; no measured need |
| H3 cells for retrieval (RECOMMENDATION_ENGINE.md mentions it as an option) | GIST on polygons is exact and already indexed; cells are useful for caching travel times at scale, which is not the POC |
| Google Places for geocoding at the POC | Chirag chose the OpenStreetMap stack for Raipur; pin drop is the primary input |

## Consequences

- Search relevance is basic (ranking by `ts_rank` and name); good enough for the POC's lists.
- Service-area polygons must be validated (`ST_IsValid`) at write time; the API rejects invalid geometry.

## Migration path

A search service can be fed from the outbox events; PostGIS stays as the system of record for geometry regardless.
