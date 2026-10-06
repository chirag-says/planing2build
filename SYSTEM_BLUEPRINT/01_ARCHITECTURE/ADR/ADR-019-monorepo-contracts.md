# ADR-019: One repository with apps, packages and infra; generated contracts from OpenAPI; module boundaries enforced by lint

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03) |
| Deciders | Sakha (proposal) |
| Related | ENVIRONMENT_AND_DEPLOYMENT.md section 3, API_ARCHITECTURE.md section 20, ADR-008 |

## Context

Two languages (TypeScript, Python), two deployable images, one infrastructure definition, one blueprint. The web app must never drift from the API's request and response shapes; the state vocabulary must be identical in Python, SQL CHECK constraints and TypeScript.

## Decision

- A single repository: `apps/web`, `apps/api` (API and worker), `packages/contracts` (generated TypeScript types and client, enums and state vocabulary exported from Python), `infra/` (Compose, Caddyfile, scripts), `tools/`, `.github/workflows/`.
- FastAPI emits OpenAPI 3.1; CI generates `packages/contracts` and fails on an unmarked breaking change; the web app imports types only from there.
- Enums and state names are defined once in Python (`core/vocabulary.py`), used to build CHECK constraints in migrations and exported to TypeScript.
- `import-linter` enforces: modules talk through `interface.py`; `core` imports no module; `integrations` import no module; `recommendation/core` imports nothing from the application.

## Why

- One pull request can change the API, the migration and the screen together, with CI proving they agree.
- Generated contracts remove a class of runtime bugs (field renamed on one side).
- One vocabulary source ends the "state spelled three ways" problem that the source documents themselves show.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Separate repositories per app | Cross-cutting changes need coordinated PRs and version pinning; no benefit for one team |
| Hand-written TypeScript types | Drift is certain; generation is cheap |
| A shared schema language (Protobuf, JSON Schema first) | OpenAPI from Pydantic already is the schema; another layer adds work |

## Consequences

- CI runs both toolchains; caching keeps it under 15 minutes.
- Developers need both Node and Python locally (`make up` provides containers).
- A monorepo tool (Nx, Turborepo) is not needed at this size; plain workspaces and a Makefile suffice.

## Migration path

Packages can be published separately if a second team or an external client needs them; the structure already separates them.
