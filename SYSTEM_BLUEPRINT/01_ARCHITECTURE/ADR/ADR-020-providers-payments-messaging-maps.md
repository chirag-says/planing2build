# ADR-020: Provider choices: Razorpay Checkout in-app, Resend email, MSG91 SMS later, WhatsApp later, OpenStreetMap stack for maps, ClamAV for scanning

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03); Razorpay Checkout, Resend and OpenStreetMap decided by Chirag 2026-10-03 |
| Deciders | Chirag, Sakha |
| Related | INTEGRATION_ARCHITECTURE.md, EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md section 5, ADR-010, ADR-015 |

## Context

The sources name Razorpay for fee collection with webhook reconciliation (S06 §9, S08 §5), Resend for transactional email (S10 §5), email plus SMS first with WhatsApp later (S07 §16.7), Google Maps "if needed" (S06). Construction money never passes through Plan2Build (CD-01). Raipur is the only city at the POC.

## Decision

| Need | Provider | Notes |
|---|---|---|
| Package fee collection and refunds | Razorpay Checkout embedded in the app; orders created server-side; signed webhooks; daily API reconciliation; our own invoice numbers | No payment links at MVP (CQ-03 answered); no Route or escrow (CD-01); subscriptions not used (instalments are our invoices) |
| Email (OTP, notices, digests) | Resend with our own versioned templates, idempotency keys and status webhooks | Free tier during the build; Pro when the daily cap is reached |
| SMS | MSG91 after DLT registration, behind the same `MessageProvider` interface | Switch-on date is Chirag's; phones verified from day one |
| WhatsApp | Cloud API through a BSP, when pilot data shows it changes response rates (S07 §16.7) | Opt-in and template approval needed |
| Map tiles, geocoding, routing | OpenStreetMap data: MapTiler free tier (or self-hosted Protomaps) for tiles, Nominatim with caching for geocoding, PostGIS for distance, OSRM container only if road time is needed; Google behind the same interfaces later | Pin drop is the primary location input |
| File scanning | ClamAV container on the VPS | No files to third parties |
| Image generation | ADR-013 | |

## Why

- Each choice is the lowest-cost provider that meets the rule, with an adapter so the choice is reversible.
- Razorpay in-app keeps the homeowner in the flow and the server in control of amounts; links and subscriptions would hand schedule control to the gateway.
- Resend's idempotency and webhooks map directly onto the delivery model.
- OpenStreetMap costs nothing for a single city and avoids Google billing setup; the honest trade is address quality, mitigated by pin drop and homeowner confirmation.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Stripe India, PayU, Cashfree | Razorpay is named in the sources, has broad UPI support and a 0% new-merchant offer; nothing to gain by switching |
| Amazon SES, SendGrid, Postmark | Fine products; Resend is named in the sources, has a free tier and a simple API |
| Google Maps Platform at the POC | Billing setup and per-request cost for one city; Chirag chose OpenStreetMap for Raipur |
| Firebase Cloud Messaging for push (named by S06 for the auditor app) | The auditor module is a PWA; web push can be added later; not needed for the POC's assignment and sync model |

## Consequences

- DLT registration (about ₹11,800 one-time plus per-template approvals) must start early if SMS is wanted within months.
- Address search quality in Raipur on Nominatim is variable; the UI leads with the map pin.
- Razorpay's 24-hour webhook retry window means a long outage needs the reconciliation job (daily) or a manual replay.

## Migration path

Adapters per provider; recipient rules in data choose channels; tiles and geocoding are URL and adapter changes.
