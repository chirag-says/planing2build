# ADR-001: Next.js with TypeScript for every web surface, one application serving three hosts

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03) |
| Deciders | Chirag (host split decided 2026-10-03), Sakha (proposal) |
| Related | SYSTEM_ARCHITECTURE.md, PERFORMANCE_ARCHITECTURE.md, ADR-016, ADR-021 |

## Context

Four audiences use Plan2Build in a browser: homeowners and household members, professionals (contractors, architects, engineers, auditors), operations staff and administrators. The public pages must render on low-end Android over 3G (BR-150), the estimator must be interactive within 3 seconds (BR-152), authenticated dashboards must be usable within 2 seconds on 4G (BR-153), and auditors need an offline inspection module. Chirag decided that homeowners use `plan2build.in`, professionals use `professionals.plan2build.in` and operations use `admin.plan2build.in`.

## Decision

One Next.js (App Router) application in TypeScript serves all three hosts. Middleware reads the host and routes to the `(ihb)`, `(pro)` or `(ops)` route group; a request for a route group that does not match the host is a 404. Marketing and content pages are statically generated; listings and profiles use incremental static regeneration; authenticated pages are server-rendered with data fetched from FastAPI over loopback; the auditor module under `/inspections` on the professional host is a client-rendered PWA with a service worker.

## Why

- Server rendering with streaming gives the fastest first paint on slow networks; static generation makes public pages free to serve.
- One codebase shares components, the generated API client, forms and validation across audiences; three deployables would triple the release work for a two-person team.
- The host split still gives the audience separation that matters (separate cookies, separate route groups, separate CSP), without separate applications.
- Next.js is Chirag's baseline and the most widely known React framework, which helps future developers and AI agents.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Three separate Next.js applications | Three builds, three deploys, duplicated components; no benefit at this team size; can be split later because route groups are already separate |
| Remix or SvelteKit | Comparable capabilities; smaller hiring pool and fewer AI-agent priors; no reason to leave the baseline |
| A single-page application (Vite plus React) with FastAPI serving JSON | Public pages would need a separate static site for performance and indexing; SSR solves both in one place |
| Native apps (React Native) for homeowners or auditors | BR-151: a native app is justified by repeat usage; the PWA covers the POC (ADR-021) |

## Consequences

- The middleware is the one place where host-to-audience mapping lives; tests cover cross-host access.
- A bug in a shared component affects all audiences; the e2e suite covers each host.
- The server-rendering work happens on the VPS (no Vercel); CLOUD_AND_HOSTING_ARCHITECTURE.md sizes it.
- Bundle budgets (PERFORMANCE_ARCHITECTURE.md section 2) are enforced in CI because one application makes accidental bloat easy.

## Migration path

Route groups can be extracted into separate applications without rewriting pages; the API client and components move to `packages/`. Static pages can move to a CDN-hosted static export if the VPS becomes a bottleneck for public traffic.
