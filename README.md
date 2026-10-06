# Plan2Build

Decision-and-evidence platform for families building a new house (POC: Raipur).

| Read first | Why |
|---|---|
| `SYSTEM_BLUEPRINT/01_ARCHITECTURE/00_APPROVAL/ARCHITECTURE_BASELINE.md` | What is fixed, what is open, what blocks what |
| `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/IMPLEMENTATION_CONTRACT.md` | The rules every change follows |
| `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/FOUNDATION_PLAN.md` | What exists, how it was verified, what comes next |

Business ambiguity is never resolved by invention: when the blueprint does not say, stop and ask.

## Layout

| Path | Contents |
|---|---|
| `apps/api` | FastAPI API and Procrastinate worker (one image), Alembic migrations, tests |
| `apps/web` | Next.js app serving `plan2build.in`, `professionals.plan2build.in`, `admin.plan2build.in` |
| `packages/contracts` | TypeScript client and types generated from the API (never edit by hand) |
| `infra/local` | Local Compose stack and Caddy routing |
| `tools` | Blueprint prose and table checks |
| `SYSTEM_BLUEPRINT` | Product and architecture authority |

## Local development

Prerequisites: Docker, Node 22 or later with pnpm, Python 3.12 or later with [uv](https://docs.astral.sh/uv/).

```bash
pnpm install
pnpm local:up
pnpm dev:web
```

Open http://ihb.localhost:8080, http://pro.localhost:8080 and http://admin.localhost:8080. Sign-in codes arrive in Mailpit at http://localhost:8025. `pnpm local:demo-rates` loads the DEMO rate card (prototype values, never served in production).

| Task | Command |
|---|---|
| API tests (needs the Compose database) | `pnpm test:api` |
| API lint, types, module boundaries | `pnpm lint:api` |
| Web unit tests, lint, types | `pnpm test:web`, `pnpm lint:web` |
| End-to-end (needs the stack and `pnpm dev:web`) | `pnpm test:e2e` |
| Regenerate the API contract | `pnpm contracts` |
| New migration | `cd apps/api && uv run alembic revision -m "..."` (hand-review it) |
| Stop the stack | `pnpm local:down` |
