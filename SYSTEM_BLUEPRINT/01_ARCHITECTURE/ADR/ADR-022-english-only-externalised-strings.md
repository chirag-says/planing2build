# ADR-022: English only at MVP with every user-facing string externalised; Hindi deferred

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03); decided by Chirag 2026-10-03 ("English only") |
| Deciders | Chirag |
| Related | SYSTEM_ARCHITECTURE.md AQ-10, EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md section 5, ADR-018 |

## Context

The D2 sources require Hindi and English from the first release, including PDFs, validation messages and notifications (BR-057, S05 §6, §7); the D1 sources assume one language. Chirag decided English only for the MVP. This is a product decision with architectural consequences.

## Decision

- All user-facing text (web, PDF templates, notification templates, reason templates, validation messages, catalog display names) is externalised: message catalogues in the web app, `locale` columns on templates and catalog display tables, a `locale` on the user profile defaulting to `en`.
- No string is hard-coded in a component, a service or a template; a lint rule flags string literals in JSX and in notification code paths.
- Hindi is added by translating catalogues and template rows, not by changing code.

## Why

- Chirag's decision reduces MVP scope; externalising strings now costs little and avoids a retrofit that the sources show will be required.
- Transliteration and Hindi typography in PDFs need font and template work that is cleaner when templates are already locale-aware.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Hindi and English from day one as the sources require | Doubles content work during the POC; Chirag chose otherwise; the gap is recorded as AQ-10 for the client conversation |
| Hard-code English and translate later | The retrofit is the expensive path; externalising is cheap now |

## Consequences

- The client must be told that BR-057 is deferred (AQ-10).
- Font bundling for Devanagari in the PDF renderer (fpdf2, ADR-023) and the web is a known later task.

## Implementation note (2026-10-04)

The strings live in `apps/web/messages/en.json` and are read through `use-intl` (`apps/web/src/lib/i18n.ts`), the core library of next-intl with the same ICU message format. next-intl itself was not used because its Next.js plugin now needs a native SWC binary (`FOUNDATION_PLAN.md` N-16). Moving to next-intl later changes the helper, not the messages. Notification templates are files under the owning module until the `notifications` module exists (N-21).

## Migration path

Add `hi` rows and catalogues; switch the default per user or per host.
