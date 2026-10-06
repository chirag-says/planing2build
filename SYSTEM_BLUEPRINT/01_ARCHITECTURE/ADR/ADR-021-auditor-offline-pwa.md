# ADR-021: Auditor inspections as an offline-capable PWA module on the professional host, not a native app

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03); decided by Chirag 2026-10-03 |
| Deciders | Chirag, Sakha |
| Related | API_ARCHITECTURE.md section 13, STATE_MODEL.md section 13, SECURITY_ARCHITECTURE.md section 6, ADR-001 |

## Context

S05 P6 requires offline, geotagged, timestamped photos that cannot be backdated, non-conformance closure only by re-inspection, and that the auditor never sees supplier or brand. S06 and S09 proposed a React Native (Expo) auditor app with push notifications. The POC has a handful of auditors in Raipur and a two-person development team.

## Decision

The auditor module is a route group (`/inspections/*`) on `professionals.plan2build.in` built as a PWA: a service worker precaches the app shell; the job pack (checklist, project facts without supplier or brand, reference drawings) is downloaded before the visit; checkpoints, acknowledgements and evidence references are stored in IndexedDB; evidence files upload directly to R2 by presigned URL when a network exists; a sync endpoint accepts ordered batches with device id and sequence (idempotent); the server assigns timestamps and the client's capture time and GPS are stored as claims; the report is locked server-side with a hash.

## Why

- One codebase and one release pipeline; no app store accounts or review cycles.
- Modern Android browsers provide camera, geolocation, IndexedDB and background sync; the POC's needs fit.
- Server-side timestamps and hashes provide the "cannot be backdated" property regardless of the client.
- A native app can be added later for a measured reason (BR-151's repeat-usage test) without changing the API.

## Alternatives considered

| Alternative | Why not |
|---|---|
| React Native (Expo) app as S06 proposed | A second codebase, store distribution and native build tooling for a few auditors; not justified at the POC |
| Online-only web module | Sites often lack signal; the sources require offline capture |
| Capacitor wrapper around the PWA | Adds store distribution without adding capability the POC needs; possible later for push and background upload reliability |

## Consequences

- iOS Safari's PWA limits (background sync, storage eviction) mean Android is the supported auditor device at the POC; stated in the auditor onboarding.
- Storage eviction risk is handled by syncing as soon as a network exists and by warning when unsynced data is older than a day.
- No push notifications at the POC; assignments arrive by email and the in-app inbox; web push can be added later.

## Migration path

The sync contract and the pack format are client-agnostic; a native client would reuse them.
