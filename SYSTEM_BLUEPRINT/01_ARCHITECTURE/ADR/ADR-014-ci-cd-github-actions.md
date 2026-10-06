# ADR-014: GitHub Actions, trunk-based development, image promotion, tag-to-production with approval, expand-contract migrations

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03) |
| Deciders | Chirag (baseline: GitHub Actions), Sakha |
| Related | ENVIRONMENT_AND_DEPLOYMENT.md, TESTING_ARCHITECTURE.md, ADR-005 |

## Context

A two-person team ships to a single VPS with a staging stack beside production. Releases must be safe to roll back, migrations must not break running code, and production secrets must not live in CI.

## Decision

- Trunk-based: `main` always deployable, short branches, squash merges, pull requests with CI green and a review.
- CI on every push: lint and types, unit and service tests, authorisation matrix, S06 critical tests, contract diff, migration up and down, image build, scans, e2e smoke, push to GHCR with a `sha-` tag.
- Staging deploys automatically on merge to `main`; production deploys on a `v*` tag after manual approval in the GitHub `production` environment, promoting the same image digest.
- Deploy script over SSH: pull, migrate (one-shot, expand-only), restart worker, api, web with health waits, post-deploy checks, release annotations.
- Migrations follow expand-contract: contract steps ship one release after the code that stopped needing the old shape; `squawk` lints dangerous operations; downgrade exists or the irreversibility is documented.
- CI holds only the deploy SSH key and registry token; application secrets stay on the VPS.

## Why

- Promotion of a tested digest removes "works on staging, different build in production".
- Expand-contract makes rollback a redeploy of the previous tag with no schema action.
- Manual approval on production is the right cost for a team this size: one click, one audit line.
- Keeping application secrets out of CI shrinks the blast radius of a GitHub account compromise.

## Alternatives considered

| Alternative | Why not |
|---|---|
| GitFlow with release branches | Ceremony without benefit for two developers and continuous staging |
| Deploy from a developer laptop | No audit, no reproducibility, secrets on laptops |
| Watchtower-style auto-pull on the VPS | Loses the migration step ordering and the approval |
| A hosted CD product (Argo, Octopus) | Nothing to orchestrate beyond one Compose stack |

## Consequences

- A brief gap of seconds per service during container replacement; noted as planned maintenance for large releases; the redundant-tier stage removes it.
- Every PR carries a migration note and an `EXPLAIN` for new queries (template).
- Feature flags gate unfinished work in production.

## Migration path

The same pipeline deploys to more nodes by looping the script; the image promotion model carries over to any orchestrator later.
