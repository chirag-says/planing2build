# ADR-016: Cloudflare in front, Caddy on the VPS, origin certificate, same-origin `/api/v1` on each host

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03); Caddy and same-origin decided by Chirag 2026-10-03 (API exposure delegated: "you decide which is better") |
| Deciders | Chirag, Sakha |
| Related | CLOUD_AND_HOSTING_ARCHITECTURE.md sections 4 and 8, SECURITY_ARCHITECTURE.md section 6, ADR-001, ADR-010 |

## Context

Three browser hosts and a webhook surface sit on one VPS. The API must be reachable from the browser without CORS complexity, cookies must stay host-bound, TLS must be simple to run, and the origin should not be exposed directly to the internet.

## Decision

- Cloudflare proxies every host (DNS, TLS at the edge, WAF managed rules, static caching, rate-limiting rule on auth paths); Full (strict) mode to the origin.
- Caddy on the VPS terminates TLS with a Cloudflare Origin CA certificate (15 years, no ACME on the host), routes by host, sends `/api/v1/*` to FastAPI and everything else to Next.js, adds request ids and security headers, and only accepts connections from Cloudflare IP ranges (UFW rules refreshed weekly).
- The API is same-origin on each host: `plan2build.in/api/v1`, `professionals.plan2build.in/api/v1`, `admin.plan2build.in/api/v1`; `/api/v1/admin/*` is routed only from the admin host. No CORS for browsers. `api.plan2build.in` is reserved for non-browser clients.
- Next.js server components call FastAPI over loopback, forwarding the user's cookie.

## Why

- Same-origin removes CORS preflights and cross-site cookie issues and makes `SameSite=Lax` cookies work without exceptions.
- Caddy's configuration is a few dozen lines; no certificate renewals to babysit on the host.
- Cloudflare absorbs floods and serves static assets near users at no cost.
- Routing admin API paths only from the admin host adds a network-level check on top of the application's role check.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Nginx or Traefik | Both fine; Caddy has the simplest configuration and built-in health checks; Chirag chose it |
| A separate `api.plan2build.in` for browsers with CORS | Cross-site cookies need `SameSite=None`, which weakens CSRF defence and complicates three audiences |
| Cloudflare Tunnel instead of open 443 | Attractive (no inbound ports), but adds a daemon and a dependency on Cloudflare's tunnel for all traffic; the IP allow-list achieves most of the benefit; revisit if SSH exposure becomes a concern (AQ-25) |
| Let's Encrypt via ACME on Caddy | Works, but needs DNS tokens on the host for wildcard or Cloudflare proxy quirks; the origin certificate is simpler |

## Consequences

- Cloudflare is a dependency for all traffic; its free-plan reliability is high and its outages are visible to everyone.
- Webhook paths must be excluded from bot protection and caching (configured).
- `Full (strict)` requires the origin certificate to match the host names; wildcard origin certificates cover subdomains.

## Migration path

Add nodes behind Cloudflare load balancing; replace Caddy with any proxy; the same-origin model does not change.
