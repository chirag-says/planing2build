# ADR-002: FastAPI and Python for the API and the worker

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03) |
| Deciders | Chirag (baseline), Sakha (proposal) |
| Related | DOMAIN_ARCHITECTURE.md, API_ARCHITECTURE.md, ADR-008, ADR-009, ADR-018 |

## Context

The backend owns every business rule: state machines for a dozen entities, the recommendation engine, document rendering, file processing, image-generation orchestration and provider integrations. S06 recommended NestJS; Chirag's baseline is FastAPI with Python.

## Decision

FastAPI (async) on Python 3.12 for the HTTP API, and the same codebase run as a Procrastinate worker for jobs. Pydantic v2 models define every request, response, event payload and engine contract. SQLAlchemy 2 (async) with asyncpg for data access; Alembic for migrations. One Docker image, two commands.

## Why

- Python carries the libraries this product needs with the least friction: fpdf2 (PDF, ADR-023; WeasyPrint was proposed in ADR-018), Pillow and pikepdf (files), the scientific stack for the engine (numpy now, LightGBM later), ezdxf and OR-Tools for the later layout engine.
- FastAPI's dependency injection expresses the authorisation chain (session, role, membership, state) as composable, testable dependencies.
- Pydantic gives one source of truth for validation and the OpenAPI document, from which the TypeScript client is generated (ADR-019).
- Async request handling with a transaction-mode pooler keeps connection counts low on a small database.

## Alternatives considered

| Alternative | Why not |
|---|---|
| NestJS (S06 recommendation) | One language across web and API is attractive, but the rendering, file and engine libraries are weaker in Node; the team's stated baseline is Python |
| Django with DRF | Mature, but synchronous by default and heavier; the ORM's migration tooling is good, yet the project needs explicit transition tables and shaped queries more than an admin site |
| Go | Fast and simple, but the PDF, image and scientific libraries would have to be replaced or shelled out to Python anyway |

## Consequences

- Two languages in the repository (TypeScript and Python); the contract package bridges them.
- Python's CPU-bound work (rendering, image handling) runs in the worker container with its own CPU share.
- `mypy --strict` and `ruff` are mandatory to keep a dynamically typed codebase safe for future developers.

## Migration path

Modules are plain Python packages behind interfaces; any module can be extracted into its own FastAPI service (ADR-008). The worker can run on a separate host without code change.
