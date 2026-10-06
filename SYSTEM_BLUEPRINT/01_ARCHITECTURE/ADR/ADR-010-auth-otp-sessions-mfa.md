# ADR-010: Email OTP now and SMS later; server-side sessions in HttpOnly cookies per host; TOTP MFA for operations

| Item | Value |
|---|---|
| Status | Proposed (2026-10-03); sessions and OTP channel decided by Chirag 2026-10-03 |
| Deciders | Chirag, Sakha |
| Related | SECURITY_ARCHITECTURE.md section 3, API_ARCHITECTURE.md section 2, ADR-004 |

## Context

The sources require OTP or email verification (CD-24), OTP acknowledgements for specification choices, variations and selection (BR-070, BR-100), MFA for administrators and consultants (BR-144), rate limits and lockouts (BR-011, BR-012), and forbid long-lived tokens in the browser (Chirag's baseline). Contractors are phone-first; SMS needs DLT registration in India, which takes time and money. Chirag: "start with email for mvp and then we'll be using sms too".

## Decision

- OTP: 6-digit codes by email at MVP, hashed at rest, bound to contact, audience, purpose and (for acknowledgements) the object; attempt and send limits with lockouts; phone numbers are collected and verified from day one so SMS can be switched on without a data migration; MSG91 is added behind the same `MessageProvider` interface once DLT is done.
- Sessions: 256-bit random tokens stored hashed in Postgres; one HttpOnly, Secure, SameSite=Lax, host-only cookie per host (`__Host-p2b_ihb_session`, `__Host-p2b_pro_session`, `__Host-p2b_ops_session`); audience bound to host; idle and absolute lifetimes per audience; immediate revocation.
- MFA: TOTP for operations, admin and the structural engineer's sign-off; recovery codes; re-verification every 8 hours and before privileged actions.
- No JWT access tokens in the browser, no localStorage tokens, no Supabase Auth.

## Why

- Server-side sessions give instant revocation and audit of devices; JWTs in the browser would need refresh rotation and still be hard to revoke.
- Per-host cookies plus audience binding make cross-audience confusion structurally impossible.
- Email OTP gets the MVP live without waiting for DLT; verified phones from day one keep the SMS switch a configuration change.
- TOTP is standard, free and offline; SMS as a second factor would be weaker and costlier.

## Alternatives considered

| Alternative | Why not |
|---|---|
| Supabase Auth or Auth0 or Clerk | Project-level authorisation and OTP-for-acknowledgement semantics still have to be ours; an external identity provider adds a dependency and a data flow for little gain; magic links from a third party complicate the three-host model |
| Passwords plus OTP | Passwords add reset flows and breach risk for users who would mostly use OTP anyway; the sources describe OTP-first access |
| Magic links instead of codes | Links open in a different browser than the one holding the challenge on many Android mail apps; codes are more reliable; AQ-03 keeps the option |
| JWT with short expiry and refresh rotation | Workable, but revocation and device listing are harder; no benefit without multiple services |
| SMS OTP from day one | Blocked on DLT registration; email first is the pragmatic order Chirag chose |

## Consequences

- Contractors without reliable email need help at onboarding (CD-07 account creation by operations) until SMS exists; this is an honest limitation of the MVP.
- Every request reads a session row (sub-millisecond); a Redis cache exists behind a flag.
- The acknowledgement OTP is a separate challenge per action; the audit row stores which challenge acknowledged what.

## Migration path

SMS and WhatsApp OTP are channels on the same challenge model; passkeys (WebAuthn) can be added as a second factor or a password-less login later without changing sessions.
