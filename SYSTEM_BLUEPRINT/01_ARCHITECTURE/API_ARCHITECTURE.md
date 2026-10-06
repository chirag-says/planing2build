# Plan2Build: API architecture

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/01_ARCHITECTURE/API_ARCHITECTURE.md` |
| Version | 0.3 (2026-10-04: section 22, the endpoints built for Handover 1). 0.2 the same day: B-03 registration, CSRF on every state change, OTP rows, demo rate cards; earlier text 0.1 proposed |
| Date | 2026-10-03 |
| Status | Architecture proposal for Chirag's review. Design only; no implementation. |
| Business authority | `IHB_FLOW.md` v1.2 sections 13, 14, 33; `PROFESSIONALS_FLOW.md` v1.2 sections 17, 28, 29, 44; `RECOMMENDATION_ENGINE.md` |
| Related | DOMAIN_ARCHITECTURE.md (module interfaces), STATE_MODEL.md (transitions), DATA_ARCHITECTURE.md (tables), SECURITY_ARCHITECTURE.md (authn and authz), EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md (side effects) |

## 1. Conventions

| Topic | Rule |
|---|---|
| Base path | `/api/v1/` on every host (`plan2build.in`, `professionals.plan2build.in`, `admin.plan2build.in`), proxied by Caddy to the same FastAPI. Non-browser clients may use `api.plan2build.in` with the same paths. |
| Versioning | Additive changes (new optional fields, new endpoints) never bump the version. A breaking change ships as `/api/v2/` with both versions served for at least six months. The OpenAPI document is the contract; the web client is generated from it (ENVIRONMENT_AND_DEPLOYMENT.md section 4). |
| Resource style | Nouns, plural, project-scoped resources under `/projects/{project_id}/...`; professional-scoped under `/pro/...`; operations under `/ops/...`; admin under `/admin/...`. Transitions are verbs as sub-resources (`/choose`, `/acknowledge`, `/approve`), never PATCH of a `state` field. |
| Authentication | Session cookie per host (`p2b_ihb_session`, `p2b_pro_session`, `p2b_ops_session`): HttpOnly, Secure, SameSite=Lax, path `/`. The audience in the session must match the host. Public endpoints are marked `public`. Machine endpoints (webhooks) use provider signatures, never cookies. |
| CSRF | SameSite=Lax plus, for every state-changing request, the header `X-Requested-With: plan2build` and an `Origin` header that matches the host. Missing either returns 403 `CSRF_REJECTED`. Provider webhooks (`/api/v1/webhooks/*`) are exempt and verified by signature instead. Version 0.1 required the check only when a session cookie was present; 0.2 applies it to public writes too, because `/auth/otp/verify` sets a session and would otherwise allow login CSRF (a hostile page signing the visitor into the attacker's account). |
| Authorisation | A FastAPI dependency chain: session, user status, audience, role, then object ownership or project membership (`projects.assert_membership`), then the state precondition from STATE_MODEL.md. Failures are 401 `UNAUTHENTICATED`, 403 `FORBIDDEN` (never 404 for objects the actor could know exist; 404 for objects outside the actor's visibility to avoid enumeration), 409 `STATE_CONFLICT`. |
| Request and response | JSON, UTF-8; Pydantic v2 models `…Request` and `…Response`; field names `snake_case`; times in ISO 8601 UTC; money as strings with two decimals and a `currency` field; ids as UUID strings; codes (project code, line code) as strings. Responses are shaped per screen; no endpoint returns a whole project. |
| Validation | At the boundary: types, ranges, enums (from the catalog), file limits; 422 `VALIDATION_ERROR` with a `fields` map. Business preconditions are checked in the service and return 409. |
| Errors | `{"error": {"code": "...", "message": "...", "details": {...}, "request_id": "..."}}`. Codes: `VALIDATION_ERROR` 422, `UNAUTHENTICATED` 401, `FORBIDDEN` 403, `CSRF_REJECTED` 403, `NOT_FOUND` 404, `STATE_CONFLICT` 409, `VERSION_CONFLICT` 409, `IDEMPOTENCY_MISMATCH` 409, `OTP_INVALID` 400, `OTP_LOCKED` 423, `RATE_LIMITED` 429, `PROVIDER_UNAVAILABLE` 503, `INTERNAL` 500 (no internals leaked). |
| Idempotency | Every POST that creates or transitions accepts `Idempotency-Key` (UUID, per session). The key, request hash and response are stored in `idempotency_keys` (core; 24 hours). A replay returns the stored response; a different body under the same key returns 409 `IDEMPOTENCY_MISMATCH`. Webhooks are idempotent by provider event id. |
| Optimistic locking | Mutating requests on stateful resources send `version`; a stale version returns 409 `VERSION_CONFLICT` with the current version. |
| Pagination | Keyset: `?limit=` (default 20, max 100) and `?cursor=`; responses carry `next_cursor`. Lists are ordered by `created_at desc, id desc` unless stated. Filters are explicit query parameters; no free-form query language. |
| Rate limits (Redis token buckets, fallback to Postgres counters) | T0 public: 60 requests per minute per IP. T1 authentication: 5 OTP sends per contact per 10 minutes, 10 OTP verifications per challenge, 20 per IP per 10 minutes, then `OTP_LOCKED` or `RATE_LIMITED`. T2 authenticated: 300 per minute per session. T3 uploads and heavy writes: 60 per minute per session. T4 webhooks: 120 per minute per provider IP range. Limits return 429 with `Retry-After`. |
| Audit and events | Every transition endpoint writes an audit row and an outbox event in the same transaction (marked A and E below). Notifications (N) and jobs (J) are triggered from events in the worker, never inline. |
| Request id | `X-Request-Id` generated at Caddy, echoed in responses and logs. |
| Health | `GET /healthz` (process up), `GET /readyz` (database reachable, migrations current), both unauthenticated, not proxied beyond Cloudflare's health checks. |

Legend for the tables: Actor shows who may call; Authz the rule beyond the role; Side effects use A (audit), E (outbox event), N (notification), J (job); Limits give the rate tier; `IK` means `Idempotency-Key` required.

## 2. Authentication and identity

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Idempotency, limits, notes |
|---|---|---|---|---|---|---|
| `POST /auth/otp/start` | Start an OTP challenge for sign-in, which is also registration for a new contact | public | `email` (phone when SMS is enabled); audience from the host; purpose `LOGIN` | `challenge_id`, `expires_at`, masked contact | Earlier open challenges for the same contact, audience and purpose EXPIRED; OTP ISSUED; E `otp.issued` (job `deliver_otp` on `priority`); security event `OTP_ISSUED` | T1 (5 sends per contact per 10 minutes, 60 starts per IP per hour); identical response for known and unknown contacts; no user row is created (B-03) |
| `POST /auth/otp/verify` | Verify the code; create the user on first sign-in; create the session | public | `challenge_id`, `code`; `consents` once the privacy notice and terms exist (launch blocker, baseline D-12) | `user`, `audience`, `is_new`, `mfa_required` | OTP VERIFIED; on first sign-in the user and its verified contact are created and moved `(new) → PENDING_VERIFICATION → ACTIVE` in the same transaction (B-03); session ACTIVE; A `user.registered`, `user.contact_verified`, `session.created`; E `user.registered` on first sign-in; security events `LOGIN_SUCCEEDED`, `OTP_FAILED`, `OTP_LOCKED` | T1 (20 verifications per IP per 10 minutes); sets the cookie; a wrong code counts against the challenge (5) and the contact (10 per hour, then a 1 hour lock, `OTP_LOCKED` 423); a used, replaced or expired challenge returns `OTP_INVALID`. Self-registration is open on the homeowner host only in slice 1; professional and operations accounts arrive with their slices |
| `POST /auth/mfa/enrol` | Enrol TOTP (operations and admin) | ops, admin | none | `otpauth_uri`, recovery codes (shown once) | MFA PENDING | T2; requires an active session |
| `POST /auth/mfa/verify` | Confirm TOTP, mark the session MFA-verified | ops, admin | `code` | `mfa_verified_until` | MFA ENROLLED on first verify; session flag; A | T1 |
| `POST /auth/logout` | Revoke the current session | any | none | 204 | Session REVOKED; A | T2 |
| `GET /auth/sessions` | List own sessions and devices | any | none | sessions with device, last seen | none | T2 |
| `DELETE /auth/sessions/{id}` | Revoke one session | self | none | 204 | REVOKED; A; N security notice | T2 |
| `GET /me` | Current user, audience, roles, consents due | any | none | `user`, `memberships` summary, `pending_consents` | none | T2 |
| `PATCH /me` | Display name, locale, notification preferences | self | fields, `version` | updated user | A | T2 |
| `POST /me/contacts` | Add a phone or email and start its verification | self | `kind`, `value` | contact (unverified) | E `otp.issued` | T1 |
| `POST /me/contacts/{id}/verify` | Verify the added contact | self | `code` | contact (verified) | A | T1 |
| `POST /me/consents` | Accept or withdraw a consent version | self | `document`, `version`, `action` | consent record | A | T2 |
| `POST /me/close` | Request account closure (flow details open, J25) | self | reason | 202 | Ops queue item; A; N | T2; closure is executed by operations until the policy is decided |

## 3. Public pages and enquiries (host `plan2build.in`)

| Route | Purpose | Actor | Request | Response | Side effects | Notes |
|---|---|---|---|---|---|---|
| `POST /public/estimate` | Free cost estimate (J02) | public | `city`, `built_up_area_sqft` (300 to 12,000), `floors` (1 to 4: G to G+3), `finish_level` | cost range, per sq ft range, months, stage breakdown, `rate_card` (`city`, `version`, `is_demo`, `label`) | `enquiries` row (no identity) once the enquiry fields are decided | T0; demo rate cards are never served in production, and every estimate from one carries `is_demo = true` |
| `POST /public/estimate/{id}/pdf` | Send the estimate PDF against a mobile number or email (F-005) | public | `contact`, `consent_marketing` | 202 | J render, N email (SMS later); E `enquiry.contact_captured` | T1 on the contact; consent stored |
| `POST /public/enquiries` | "Start your build plan" or "Talk to an expert" (J03) | public | `kind`, `plot`, `area`, `start_window`, `contact` | 202 | Ops queue; E `enquiry.created`; N | T1 |
| `GET /public/listing` | Contractor listing (CD-22; members only; no price, no rating) | public | filters: `category`, `class`, `locality` or `near` (lat, lng, km), `services`, `q`; cursor | listing entries (projection fields only) | none | T0; ISR-cached page in Next.js; ordered by relevance then name |
| `GET /public/listing/{profile_id}` | Public profile | public | none | profile projection, portfolio image URLs (public bucket), audit summary counts (POQ-051 pending) | none | T0 |
| `GET /public/share/{token}` | Open a shared document or build record without login (S05 rule 4) | public with token | none | document metadata and a short-lived file URL, or the build record view | `document_access_log`; view count | T0; token hashed; expiry and revocation checked |

## 4. Projects, requirements, memberships (homeowner host)

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Idempotency, limits, notes |
|---|---|---|---|---|---|---|
| `POST /projects` | Create a project (J05) | homeowner | `project_type` (NEW_HOME; others return the coming-soon flag) | project (DRAFT) | Project DRAFT; A; E `project.created` | IK; T2 |
| `GET /projects` | Own projects and memberships | homeowner, members | cursor | list with status and next action | none | T2 |
| `GET /projects/{id}` | Project summary for the dashboard | member | none | status, path, next actions, counts (open leads, due milestones, open issues) | none | T2; one shaped query set |
| `PUT /projects/{id}/requirement` | Save the requirement draft (J06) | owner | `answers` (MCQ, `schema_version`), `priorities` (ranking), plot pin, uploads list, `version` | requirement | A on submit only | T2; saved as a draft any number of times |
| `POST /projects/{id}/requirement/submit` | Submit (J07) | owner | `version` | project (SUBMITTED) | Project SUBMITTED; A; E `requirement.submitted`; N ops queue | IK; T2; 422 if required fields missing |
| `POST /projects/{id}/requirement/respond` | Answer a needs-info request | owner | answers | project (SUBMITTED) | A; E | IK; T2 |
| `GET /projects/{id}/members` | Members and roles | member | none | list | none | T2 |
| `POST /projects/{id}/members` | Add a household member (F-041) | owner | `contact`, `role` HOUSEHOLD, `permissions` | membership (pending until the member verifies) | A; E `project.member_added`; N invitation | IK; T2; OTP acknowledgement rights stay with the owner (OQ-027 default) |
| `DELETE /projects/{id}/members/{membership_id}` | Revoke | owner, ops | `version` | 204 | Revoked; A; E | T2 |
| `POST /projects/{id}/hold` and `/resume` and `/cancel` | Status changes (STATE_MODEL §5) | owner, ops | `reason`, `version` | project | Transition; A; E; N | IK; T2 |

## 5. Workspace: stages, specification lines, decisions calendar

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Idempotency, limits, notes |
|---|---|---|---|---|---|---|
| `GET /projects/{id}/workspace` | Stages with dates and gate status, line counts by state, due decisions, open items (J08, J16) | member | none | shaped workspace view | none | T2 |
| `GET /projects/{id}/stages` | Stage instances | member | none | list ordered by sequence | none | T2 |
| `GET /projects/{id}/spec-lines` | The 67 lines with state and deadline; auditor role gets no supplier or brand fields | member | filters `state`, `stage`, `due_before` | list | none | T2; response shaping by role (BR-122) |
| `GET /projects/{id}/spec-lines/{code}` | Line detail with events, options, material record | member | none | detail | none | T2 |
| `POST /projects/{id}/spec-lines/{code}/options` | Issue qualifying options (3 to 5, ordered by price) | ops advisor | options[], `version` | line (OPTIONS_ISSUED) | Transition; A; E `specline.options_issued`; N homeowner at lead time | IK; T2; 409 on structural lines (S05 rule 8) |
| `POST /projects/{id}/spec-lines/{code}/choose` | Choose and acknowledge by OTP (J11) | owner | `option_id`, `otp_challenge_id`, `otp_code`, `version` | line (CHOSEN) | CHOSEN; event; baseline grows; A; E `specline.chosen`; N contractor and ops | IK; T1 for the OTP part; 409 if the option is not in the issued set |
| `POST /projects/{id}/spec-lines/{code}/purchase` | Record purchase with evidence (J17) | contractor member (default, POQ-021), ops | `product`, `brand`, `evidence_file_id`, `is_switch`, `switch_reason`, `version` | line (PURCHASED) | Transition; switch event; A; E; N homeowner on switch | IK; T2 |
| `POST /projects/{id}/spec-lines/{code}/install` | Record installation | contractor, ops | `installer`, `installed_at`, `evidence_file_id`, `version` | line (INSTALLED) | A; E | IK; T2 |
| `GET /projects/{id}/decisions-calendar` | Lines by decide-by date with long-lead flags | member | `from`, `to` | calendar | none | T2 |
| `POST /projects/{id}/spec-lines/{code}/override` | Operations override of a line state with reason (S06 §16.1) | ops with MFA | `to_state`, `reason`, `version` | line | Override transition; A with `is_override`; E | IK; T2; only transitions marked `override_allowed` |

## 6. Build Plan, concept design, quote review

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Idempotency, limits, notes |
|---|---|---|---|---|---|---|
| `GET /projects/{id}/build-plan` | Current issued version and history for the homeowner; drafts for ops | member (issued only), ops (drafts) | none | version list, share link, PDF URL (presigned) | `document_access_log` on PDF | T2 |
| `POST /ops/projects/{id}/build-plan/versions` | Create or update a draft | ops advisor | `content` sections, BOQ lines, schedules, `version` | draft version | A | IK; T2; large bodies allowed (1 MB) |
| `POST /ops/projects/{id}/build-plan/versions/{v}/request-signoff` | Request structural sign-off | ops advisor | `version` | version (IN_REVIEW) | A; E; N structural engineer | IK; T2 |
| `POST /pro/signoffs/{version_id}/lines/{code}` | Sign off a structural line | structural engineer with MFA | `note` | signoff | A; E `buildplan.signed_off` when all lines are signed | IK; T2; the engineer's host is `professionals.` |
| `POST /ops/projects/{id}/build-plan/versions/{v}/issue` | Issue the version (J10) | ops with MFA | `version` | version (ISSUED) | ISSUED; baseline LOCKED; A; E `buildplan.issued`, `baseline.locked`; J render PDF; N homeowner | IK; T2; 409 unless the package is paid, structural lines are signed and a design is attached |
| `GET /projects/{id}/design` | Current design request, artefacts, views, review state (33.6) | member | none | artefacts with URLs | access log | T2 |
| `POST /ops/projects/{id}/design/concept` | Start the concept design pipeline | ops | inputs, `sanctioned_plan_file_id` or `library_layout_id` | design request | A; E `design.requested`; J generation when the plan is approved | IK; T2 |
| `POST /ops/design/artefacts/{id}/approve` and `/reject` | Checker approves a plan or the team reviews a view (CQ-26) | ops | `reason` | artefact | Transition; A; E | IK; T2 |
| `POST /projects/{id}/design/decide` | Homeowner accepts the concept, asks for changes, or requests an architect (CD-25) | owner | `decision` (ACCEPT, CHANGES, ARCHITECT), `notes` | design request | A; E `design.plan_approved` or `design.architect_requested` (recommendation request for architects once CQ-25 is settled) | IK; T2 |
| `POST /pro/design/{request_id}/pack` | Architect attaches the design pack (CD-20, CD-25) | architect engaged on the project | file ids, `version` | artefacts | A; E `design.architect_pack_attached` | IK; T3 |
| `POST /ops/projects/{id}/quote-review` | Create the quote review for a homeowner holding a quote (CD-04) | ops | external quote file, contractor details, comments | quote review (DRAFT) | A | IK; T2 |
| `POST /ops/projects/{id}/quote-review/publish` | Publish | ops | `version` | quote review (PUBLISHED) | A; E `quote_review.published`; J render; N homeowner | IK; T2 |

## 7. Billing (Plan2Build's own fee)

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Idempotency, limits, notes |
|---|---|---|---|---|---|---|
| `GET /offerings/current` | The package, price and instalment plans (CQ-01) | homeowner | none | offering | none | T2; price null until configured |
| `POST /projects/{id}/package/purchase` | Choose the package and plan (J09) | owner | `offering_version`, `plan` | purchase, first invoice | Purchase created; invoice ISSUED; A; E `billing.invoice_issued` | IK; T2; 409 if a purchase exists |
| `POST /invoices/{id}/checkout` | Create a Razorpay order for an invoice | owner | `version` | `order_id`, amount, `checkout_key_id` (public key only) | Attempt INITIATED; A | IK; T2 |
| `POST /webhooks/razorpay` | Payment webhook | Razorpay (signature) | provider payload | 200 always after storing | `payment_events` insert (UNIQUE event id); attempt CAPTURED or FAILED; invoice PAID; purchase ACTIVE or PAID_IN_FULL; A; E `billing.payment_captured`, `billing.package_paid`; J receipt render; N receipt | T4; signature verified before parsing; amount and order id checked against the invoice; replay returns 200 without effect |
| `GET /projects/{id}/invoices` | Invoices, receipts, instalment schedule | owner | none | list with PDF URLs | access log | T2 |
| `POST /ops/payments/{id}/refund` | Refund (CQ-04 policy) | ops with MFA | `amount`, `reason` | refund (REQUESTED) | A; E; J provider call; N | IK; T2 |
| `POST /ops/billing/reconcile` | Trigger reconciliation (also scheduled) | ops | none | summary | J | T2 |

## 8. Professionals: registration, verification, Club, listing (host `professionals.plan2build.in`)

> **Superseded in part (2026-10-04, PD-18).** The `/pro/club/*` and `/ops/club/*` routes are not to be built. Approval for listing replaces them; "Champions Club" is the label for listed professionals. See `02_IMPLEMENTATION/PRODUCT_FLOW_RECONCILIATION.md`.

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Idempotency, limits, notes |
|---|---|---|---|---|---|---|
| `POST /pro/profile` | Create the profile and choose the category (P02, P03) | professional (new) | `kind`, `category`, `subtype`, firm and principal, base pin, radius | profile (draft) | A; E `professional.profile_created` | IK; T2 |
| `GET /pro/profile` and `PATCH /pro/profile` | Read and edit own profile | self | fields, `version` | profile | A | T2; evidence fields lock after submission |
| `POST /pro/profile/evidence` | Upload evidence references (PF-009 to PF-013) | self | `kind`, `file_id` | evidence row | A | T3 |
| `POST /pro/profile/service-areas` | Add a polygon or radius | self | geometry | area | A | T2; validated geometry, max area per configuration |
| `POST /pro/verification/submit` | Submit for verification (P06) | self | `category`, `scope` FULL | case (SUBMITTED) | A; E `verification.submitted`; N ops queue | IK; T2; 422 if the checklist is incomplete |
| `GET /pro/verification` | Own cases and requested corrections | self | none | cases | none | T2 |
| `POST /pro/club/apply` | Apply to the Champions Club (44.8) | self, VERIFIED | `category` | membership (APPLIED) | A; E `club.applied` | IK; T2 |
| `GET /pro/club` | Own membership, class, metrics, review history | self | none | membership, `professional_metrics` (own only) | none | T2; never ranks |
| `PUT /pro/capacity` | Declare capacity and pause | self | `max_concurrent_sites`, `paused_until` | capacity | A; E `capacity.changed` | T2 |
| `GET /pro/dashboard` | Leads, invitations, quotes, active projects, inspections (auditor) | self | none | shaped view | none | T2 |
| `POST /ops/professionals/accounts` | Create an account and profile for a contractor who wants help (CD-07) | ops | contact, firm, category | user and profile | A; E `professionals.account_requested`; N invitation | IK; T2 |
| `POST /ops/verifications/{id}/claim`, `/request-changes`, `/approve`, `/reject` | Verification decisions (PA-010 to PA-014) | ops (approve and reject with MFA) | `reason`, records | case | Transitions; A; E; N professional | IK; T2 |
| `POST /ops/verifications/{id}/reference-calls` and `/site-visits` | Record the D2 checks | ops field | details, checklist | rows | A | IK; T2 |
| `POST /ops/projects/{id}/own-contractor/invite` | Invite the family's contractor by link and OTP; opens a PROJECT_ONLY case (CD-27) | ops, owner | contact, firm | invitation, case | A; E; N (project link and OTP) | IK; T1 |
| `POST /ops/club/{membership_id}/curate` | Record gates, scorecard, decision, class (44.8) | ops with MFA | gates, scorecard, `decision`, `class`, `reason` | membership | Transition; A; E `club.admitted` or others; listing rebuild | IK; T2 |
| `POST /ops/club/{membership_id}/warn`, `/suspend`, `/reinstate`, `/remove` | Review outcomes (44.8) | ops with MFA (remove: admin) | `reason`, `plan` | membership | Transition; A; E; N; open leads withdrawn on suspension | IK; T2 |
| `GET /ops/club/reviews/due` | Six-monthly review queue with computed metrics | ops | none | list | none | T2 |

## 9. Leads (44.7)

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Idempotency, limits, notes |
|---|---|---|---|---|---|---|
| `POST /projects/{id}/leads` | Request quotes from up to three listed contractors | owner, project ACCEPTED or later with a complete requirement | `profile_ids[]` (1 to 3) | per pick: lead (SENT) or `not_sent_reason` with suggestions | Eligibility per pick (reasons stored); leads SENT; A; E `lead.sent`; N contractors; recommendation request if fewer than three passed | IK; T2; 409 if open leads would exceed three |
| `POST /projects/{id}/leads/suggest` | Ask Plan2Build to suggest contractors (engine shortlist after team review) | owner | none | request id (202) | E `recommendation.requested`; J compute; N ops review queue | IK; T2 |
| `GET /projects/{id}/leads` | Lead states for the homeowner (no contractor internals) | owner | none | list | none | T2 |
| `GET /pro/leads` | Leads for the contractor (privacy-shaped brief; no name, phone or exact address) | contractor | `state` filter, cursor | list | VIEWED on first open of a lead detail | T2 |
| `GET /pro/leads/{id}` | Lead detail | recipient | none | brief, windows, reasons it was sent | Lead VIEWED; A | T2 |
| `POST /pro/leads/{id}/accept` | Accept | recipient, before `accept_by` | `version` | lead (ACCEPTED) | Transition; thread opened; RFQ invitation if the package is held; A; E `lead.accepted`; N homeowner | IK; T2 |
| `POST /pro/leads/{id}/decline` | Decline with reason | recipient | `reason_code`, `version` | lead (DECLINED) | Transition; A; E; replacement request | IK; T2 |
| `POST /ops/leads/{id}/withdraw` | Withdraw with reason | ops | `reason`, `version` | lead (WITHDRAWN) | A; E; N | IK; T2 |

## 10. RFQ, quotes, comparison, selection

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Idempotency, limits, notes |
|---|---|---|---|---|---|---|
| `POST /ops/projects/{id}/rfqs` | Issue the standard RFQ pack (J13) | ops advisor | pack contents, invitations (nominated, introduced, accepted leads), `architect_pack_artefact_id` | rfq (ISSUED) | RFQ ISSUED; invitations INVITED; A; E `rfq.issued`, `rfq.invitation_sent`; N contractors | IK; T2; 409 unless a Build Plan version is ISSUED |
| `POST /ops/rfqs/{id}/pack-version` | New pack version (for example an architect pack) | ops | changes, `version` | rfq | A; E `rfq.pack_version_changed`; N invited contractors | IK; T2 |
| `GET /pro/invitations` and `POST /pro/invitations/{id}/accept` or `/decline` | RFQ invitations | invited contractor | `reason_code` on decline | invitation | Transition; A; E; N | IK; T2 |
| `GET /pro/rfqs/{id}` | The pack for an invited contractor | invited, VERIFIED, not suspended | none | pack with presigned file URLs; never other quotes | access log | T2 |
| `POST /pro/rfqs/{id}/quotes` | Start a quote (DRAFT) | invited | none | quote with draft version | A | IK; T2 |
| `PUT /pro/quotes/{id}/draft` | Save lines and terms in the draft | owner of the quote | lines, `valid_from`, `valid_to`, terms, attachments, `version` | draft | none | T2 |
| `POST /pro/quotes/{id}/submit` | Submit a version (CD-17) | owner of the quote | `version` | quote version (SUBMITTED) | Previous version SUPERSEDED; lead QUOTED; A; E `rfq.quote_version_created`; N homeowner and ops | IK; T2; 422 unless every line is priced or excluded and dates are valid |
| `POST /pro/quotes/{id}/withdraw` | Withdraw (POQ-013 default) | owner of the quote | `reason`, `version` | version (WITHDRAWN) | A; E; N | IK; T2 |
| `POST /ops/quotes/{id}/capture` | Staff capture on behalf (S05 P4) | ops | lines, dates, terms, `on_behalf_of` | version (SUBMITTED, `captured_by_staff`) | A; E; N contractor copy | IK; T2 |
| `POST /ops/quote-versions/{id}/adjustments` | Add or edit the adjustment list (J14) | ops advisor | adjustments[], `version` | adjustments | A (S06 §11); E `rfq.adjustments_complete` when complete | IK; T2 |
| `POST /ops/rfqs/{id}/clarifications` | Ask a contractor a clarification (routed) | ops | `quote_id`, question, `share_answer_with_all` | clarification and thread | A; E; N contractor | IK; T2 |
| `POST /ops/rfqs/{id}/comparison/finalise` | Freeze the comparison with the approved recommendation | ops with MFA | `version` | comparison (PUBLISHED) | PUBLISHED; snapshot; A; E `rfq.comparison_finalised`; J render; N homeowner | IK; T2; 409 unless adjustments are complete and the recommendation is APPROVED |
| `GET /projects/{id}/comparison` | The comparison for the homeowner: quotes as submitted, adjustment list first, totals, recommendation with reasons and fit labels, risk flags | owner, household | none | comparison view | access log; `recommendation.shown` recorded | T2; contractor internals never included |
| `GET /pro/quotes/{id}` | Own quote and versions; never the comparison or others' prices | owner of the quote | none | quote detail | none | T2 |
| `POST /projects/{id}/comparison/select` | Record the selection (J15) | owner | `quote_version_id`, `contract_value`, `start_date`, `end_date`, `otp_challenge_id`, `otp_code`, `version` | selection | Selection; quote versions SELECTED and NOT_SELECTED; rfq CLOSED; leads updated; contract value recorded; project CONTRACTED; A; E `rfq.selection_recorded`; N all parties | IK; T1 for the OTP; 409 if the selected version is EXPIRED. [SUPERSEDED] H-10: as built in 3.6 (QD-12) the selection records no contract value or dates and moves no project status (N-03, EX-01) |

## 11. Recommendations (operations review; homeowner reads through sections 9 and 10)

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Idempotency, limits, notes |
|---|---|---|---|---|---|---|
| `GET /ops/recommendations` | Review queue | ops | `state`, `use` filters, cursor | requests with candidates, scores, reasons, failed rules | none | T2 |
| `POST /ops/recommendations/{id}/review` | Approve, or remove or reorder a candidate with reason (BR-142) | ops | `action`, `candidate_id`, `reason`, new order | request | Transition; A with `is_override` for changes; E `recommendation.approved` or `recommendation.review_needed` | IK; T2; reasons required for remove and reorder |
| `POST /ops/recommendations/{id}/discard` | Decline to show, with reason | ops | `reason` | request (DISCARDED) | A; E; manual shortlist path | IK; T2 |
| `GET /admin/engine/configs` and `POST /admin/engine/configs` | Versioned configuration with validation (RE §10) | admin with MFA | config document | validation report, version | A; E `catalog.version_published`; validator rejects brand item types and paid signals (422) | IK; T2 |
| `POST /ops/recommendations/recompute-metrics` | Trigger the nightly metrics job | ops | none | 202 | J | T2 |

## 12. Construction tracking, variations, money

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Idempotency, limits, notes |
|---|---|---|---|---|---|---|
| `POST /pro/projects/{id}/stages/{stage_id}/updates` | Post a standard update (CD-19) | contractor member | `type`, `schema_version`, `payload`, `file_ids` | update | Stage IN_PROGRESS on first update; COMPLETION_REQUESTED if `type` is completion; A; E `construction.update_posted` or `construction.completion_requested`; N homeowner and ops | IK; T3 |
| `GET /projects/{id}/stages/{stage_id}/updates` | Updates with evidence | member | cursor | list | access log for private files | T2 |
| `POST /projects/{id}/stages/{stage_id}/complete` | Accept completion | owner (ops with reason) | `version`, `reason` (ops) | stage (COMPLETED) | COMPLETED; milestone DUE if applicable and gate cleared; A; E `construction.stage_completed`; N | IK; T2; 409 if a gate stage is not CLEARED |
| `POST /projects/{id}/stages/{stage_id}/return` | Return a completion request with an issue | owner | `issue_id`, `version` | stage (IN_PROGRESS) | A; E; N | IK; T2 |
| `POST /ops/projects/{id}/stages/{stage_id}/reschedule` | Change planned dates with reason | ops | dates, `reason`, `version` | stage | A; E `construction.stage_dates_changed`; deadlines recomputed | IK; T2 |
| `GET /projects/{id}/schedule` | Planned versus actual, completion date, exceptions | member | none | schedule view | none | T2 |
| `POST /projects/{id}/variations` | Raise a change (J18) | owner or contractor member | description, `reason_code`, stage, line, cost and time impact, evidence, `delay_cause_code` | variation (RAISED) | Number assigned; A; E `variation.raised`; N ops | IK; T2 |
| `GET /projects/{id}/variations` | Register | member | cursor, `state` | list | none | T2 |
| `POST /ops/variations/{id}/assess` | Qualify and quantify (CD-08) | ops advisor | `is_valid`, `cost_impact`, `time_impact_days`, notes, `version` | variation (ASSESSED) | A; E `variation.assessed`; N other party with the OTP request; `ack_by` set | IK; T2 |
| `POST /projects/{id}/variations/{vid}/acknowledge` | Acknowledge by OTP | the other party | `otp_challenge_id`, `otp_code`, `version` | variation (ACTIVE) | ACTIVE; contract value and completion date updated; A; E `variation.activated`; N both | IK; T1 |
| `POST /projects/{id}/variations/{vid}/disagree` | Disagree (opens discussion) | the other party | `reason`, `version` | variation (IN_DISCUSSION) | A; E; thread; N ops | IK; T2 |
| `POST /ops/variations/{id}/close` | Close with outcome (CQ-12 default: operations) | ops with MFA | `outcome`, `reason`, `version` | variation (CLOSED, or ACTIVE when APPLIED) | A; E `variation.closed`; N both | IK; T2 |
| `GET /projects/{id}/money` | Money position (CD-09): contract value, approved changes, current value, projected final cost, milestones with due and mark states; shaped by role (contractor view pending CQ-13) | member | none | money view | none | T2; no payment amounts exist |
| `POST /projects/{id}/milestones/{mid}/mark-paid` | Homeowner marks paid | owner | `version` | milestone | Mark; SETTLED if both; A; E `milestone.paid_marked` or `milestone.settled`; N | IK; T2 |
| `POST /pro/projects/{id}/milestones/{mid}/mark-received` | Professional marks received | contractor member | `version` | milestone | as above | IK; T2 |

## 13. Assurance (auditor PWA and operations)

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Idempotency, limits, notes |
|---|---|---|---|---|---|---|
| `POST /ops/projects/{id}/inspections` | Schedule a gate inspection and assign an auditor | ops | `stage_instance_id`, `auditor_profile_id`, `scheduled_for`, `checklist_version` | inspection (SCHEDULED) | A; E `inspection.scheduled`; N auditor | IK; T2 |
| `GET /pro/inspections` | Auditor's assignments | auditor | `state` | list | none | T2 |
| `GET /pro/inspections/{id}/pack` | Offline job pack: checklist, project and gate facts, no supplier or brand (BR-122) | assigned auditor | none | pack (JSON) plus presigned URLs for reference drawings | PACK_DOWNLOADED; A | T2; cacheable by the PWA for the offline session |
| `POST /pro/inspections/{id}/readiness` | Confirm readiness and checklist version | assigned auditor | `checklist_version` | inspection (IN_PROGRESS) | A; E | IK; T2 |
| `POST /pro/inspections/{id}/sync` | Upload a batch of checkpoint results, acknowledgements and evidence references | assigned auditor | `device_id`, `batch_seq`, checkpoints[], evidence refs (file ids completed through section 15), `is_final` | applied counts, server receipt time | Batch stored (UNIQUE device and seq); results applied; SYNCED when final; A | IK by batch; T3; replays return the stored result (PNP-26) |
| `POST /pro/inspections/{id}/lock` | Submit as complete; server locks | assigned auditor | `version` | inspection (LOCKED), `report_hash` | LOCKED; A; E `inspection.locked`; J render report | IK; T2; 409 if evidence files are still processing |
| `POST /ops/inspections/{id}/approve` and `/return` | Central approval or amendment request | ops with MFA | `reason` (return) | inspection (APPROVED or RETURNED) | APPROVED: non-conformances OPEN, gate CLEARED if none, lines VERIFIED; A; E `inspection.report_approved`, `assurance.gate_cleared`; N homeowner (plain-language report) and contractor (findings) | IK; T2 |
| `GET /projects/{id}/inspections` | Reports for the homeowner; findings for the contractor | member (role-shaped) | none | list with report URLs | access log | T2 |
| `POST /pro/non-conformances/{id}/rectification` | Submit rectification evidence | contractor member | evidence file ids, note | nc (RECTIFICATION_SUBMITTED) | A; E `nc.rectification_submitted`; N ops | IK; T3 |
| `POST /ops/non-conformances/{id}/schedule-reinspection` | Schedule the re-inspection | ops | inspection details | nc (REINSPECTION_SCHEDULED), inspection (SCHEDULED, `reinspection_of`) | A; E | IK; T2 |
| `POST /ops/non-conformances/{id}/close` | Close on re-inspection pass (or reviewer, flag) | ops with MFA | `basis`, `closure_inspection_id`, `reason` | nc (CLOSED) | A; E `nc.closed`; gate CLEARED if last; N | IK; T2; 409 when the basis is REVIEWER and the flag is off (C-066) |
| `POST /projects/{id}/inspections/{iid}/acknowledge` | Homeowner or contractor acknowledgement (F-113) | member | `otp_challenge_id`, `otp_code` (optional per configuration) | acknowledgement | A | IK; T2 |

## 14. Issues and disputes

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Idempotency, limits, notes |
|---|---|---|---|---|---|---|
| `POST /projects/{id}/issues` | Raise (CD-10) | member | title, description, severity, stage, line, evidence | issue (OPEN) | A; E `issue.raised`; N assignee and ops | IK; T2 |
| `GET /projects/{id}/issues` | Issue log | member | `state`, cursor | list | none | T2 |
| `POST /pro/issues/{id}/acknowledge` and `/fix` | Acknowledge; submit fix with proof | assignee | proof file ids, note | issue | Transitions; A; E `issue.fixed`; N homeowner | IK; T3 |
| `POST /projects/{id}/issues/{iid}/verify`, `/reopen`, `/close` | Homeowner verification and closure | owner | `reason` on reopen | issue | Transitions; A; E; N | IK; T2 |
| `POST /projects/{id}/issues/{iid}/escalate` | Escalate to operations | owner | reason | issue (ESCALATED) | A; E; N ops | IK; T2 |
| `POST /ops/disputes` and `POST /ops/disputes/{id}/decide` | Operations open and decide disputes | ops with MFA | details, `decision`, `decided_against_profile_id`, `reason` | dispute | Transitions; A; E `dispute.decided` (Club trigger); N parties | IK; T2 |

## 15. Documents and uploads (all hosts)

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Idempotency, limits, notes |
|---|---|---|---|---|---|---|
| `POST /uploads` | Request a presigned upload | any authenticated user with rights on the purpose's context | `purpose`, `context` (project id, inspection id, case id), `declared_mime`, `size_bytes`, `original_name` | `file_id`, presigned PUT URL (15 minutes), required headers | File PENDING_UPLOAD; A | IK; T3; 422 if type or size is outside the purpose's limits (JPG, PNG, PDF, 10 MB for homeowner uploads; larger limits for drawings and evidence by purpose) |
| `POST /uploads/{file_id}/complete` | Mark uploaded; start processing | uploader | `sha256` (client-computed, optional) | file (UPLOADED) | J sniff, scan, variants; A; E `documents.upload_completed` | IK; T3 |
| `GET /files/{file_id}/url` | Short-lived download URL | user with rights on the file's context | `variant` | presigned GET URL (15 minutes; 5 for P3) | `document_access_log` for private documents | T2; never a raw path; 404 outside visibility |
| `GET /documents/{id}` | Rendered document metadata and URL | rights holder | none | metadata, URL | access log | T2 |
| `POST /documents/{id}/share` and `DELETE /share-tokens/{id}` | Create or revoke a share token | owner of the document's context, ops | `expires_in` | token (shown once as a URL) | A; E | IK; T2 |
| `DELETE /files/{file_id}` | Soft delete where allowed (drafts, own uploads not yet referenced) | uploader | `reason` | 204 | DELETED; A | T2; 409 if referenced by a locked record |

## 16. Notifications and messaging

| Route | Purpose | Actor and authz | Request | Response | Side effects | Notes |
|---|---|---|---|---|---|---|
| `GET /notifications` | In-app inbox | self | `unread`, cursor | list with deep links | none | T2; polled every 60 seconds by the web app; no WebSocket at the POC |
| `POST /notifications/{id}/read` and `/read-all` | Mark read | self | none | 204 | none | T2 |
| `PUT /me/notification-preferences` | Channel preferences | self | per channel | preferences | A | T2 |
| `GET /threads` and `GET /threads/{id}` | Own threads and messages | participant | cursor | threads, messages | none | T2 |
| `POST /threads/{id}/messages` | Post | participant | body, attachment file ids | message | E `message.posted`; N members | IK; T3 |
| `GET /ops/threads/{id}` | Operations read with audit | ops | none | messages | A (S02 §12.2) | T2 |

## 17. Records and handover

| Route | Purpose | Actor and authz | Request | Response | Transition and side effects | Notes |
|---|---|---|---|---|---|---|
| `POST /ops/projects/{id}/handover/start` | Start handover after the final snag inspection | ops | none | handover | A; E `handover.started`; N | IK; T2 |
| `POST /ops/projects/{id}/build-record/assemble` | Assemble (also triggered by events) | ops | none | 202 | J assemble; E `build_record.assembled` | IK; T2 |
| `POST /ops/projects/{id}/build-record/issue` | Issue the record (CD-11) | ops with MFA | `version` | record (ISSUED), share URL | ISSUED; project COMPLETED; A; E `build_record.issued`; J exports; N homeowner | IK; T2 |
| `GET /projects/{id}/build-record` | The record for the owner (and members) | member | none | record view, export URLs | access log | T2 |
| `POST /projects/{id}/build-record/transfer` | Transfer to a new owner by OTP | owner | `to_contact`, `otp_challenge_id`, `otp_code` | transfer | TRANSFERRED; A; E; N both | IK; T1 |
| `POST /projects/{id}/post-handover/optin` | Opt in to coming-soon services (CD-12) | owner | `service` | optin | A; E; N back office | IK; T2 |

## 18. Operations console and admin (host `admin.plan2build.in`, MFA required)

| Route | Purpose | Actor | Notes |
|---|---|---|---|
| `GET /ops/queues/{kind}` | Work queues: requirements, verifications, curations, recommendations, inspections, variations, disputes, refunds, closures | ops | Keyset lists; `claim` and `resolve` as sub-resources; every resolve maps to a module endpoint above |
| `GET /ops/exceptions` | The exception feed (S05 O1) | ops | Filters by project, kind, severity |
| `GET /ops/projects` and `GET /ops/projects/{id}` | Every project with status and timeline | ops | Read-only composites; writes go through module endpoints |
| `GET /ops/professionals` and `GET /ops/professionals/{id}` | Every professional with cases, membership, metrics, leads | ops | Includes rank-free metrics; no ranking view exists |
| `POST /admin/users/{id}/suspend`, `/reinstate`, `/close` | Account administration | admin with MFA | A; sessions revoked |
| `GET /admin/catalog/*` and `POST /admin/catalog/*/versions` | Stages, specification masters, checkpoints, rate cards, class rules, offerings, configuration values, templates | admin with MFA (structural masters require the engineer's sign-off record) | New versions only; never edit in place; E `catalog.version_published` |
| `GET /admin/feature-flags` and `PUT /admin/feature-flags/{key}` | Flags | admin | A |
| `GET /admin/audit` | Audit search by entity, actor, project, time | admin, ops read | Keyset; export as CSV through a job |
| `GET /ops/kpis` | KPI views | ops | Daily aggregates |

## 19. State transitions by endpoint (cross-reference)

| Machine (STATE_MODEL.md) | Endpoints that move it |
|---|---|
| Account (§2) | `/auth/otp/verify`, `/admin/users/{id}/*`, `/me/close` |
| Verification (§3) | `/pro/verification/submit`, `/ops/verifications/{id}/*`, `/ops/projects/{id}/own-contractor/invite` |
| Club membership (§4) | `/pro/club/apply`, `/ops/club/{id}/curate`, `/ops/club/{id}/*` |
| Project (§5) | `/projects`, `/projects/{id}/requirement/submit`, requirement review in `/ops/queues`, webhook (PLANNING), build plan issue (PLAN_ISSUED), leads or RFQ (SOURCING), selection (CONTRACTED), first update (BUILDING), gate 6 clearance (HANDOVER_PENDING), record issue (COMPLETED), `/hold`, `/resume`, `/cancel`. [SUPERSEDED] H-10, N-03, EX-01: no project status moves during construction; execution, inspection, handover and Build Record states are their own records (Slice 3.7) |
| Stage instance (§6) | updates, `/complete`, `/return`, `/reschedule`, inspection approval |
| Specification line (§7) | `/options`, `/choose`, `/purchase`, `/install`, inspection approval (VERIFIED), `/override` |
| Build Plan and baseline (§8) | draft versions, `/request-signoff`, signoffs, `/issue` |
| Lead (§9) | `/projects/{id}/leads`, `/pro/leads/{id}/*`, `/ops/leads/{id}/withdraw`, scheduled expiry, quote submission, selection |
| RFQ, quote, comparison (§10) | `/ops/projects/{id}/rfqs`, invitations, `/submit`, `/withdraw`, `/capture`, adjustments, `/comparison/finalise`, `/comparison/select`, scheduled expiry |
| Variation (§11) | `/variations`, `/assess`, `/acknowledge`, `/disagree`, scheduled escalation, `/close` |
| Milestone (§12) | stage completion and gate clearance (DUE), `/mark-paid`, `/mark-received`, scheduled mismatch check |
| Inspection and NC (§13) | `/ops/projects/{id}/inspections`, `/pack`, `/readiness`, `/sync`, `/lock`, `/approve`, `/return`, rectification, re-inspection, `/close` |
| Issue and dispute (§14) | `/issues`, `/acknowledge`, `/fix`, `/verify`, `/reopen`, `/close`, `/escalate`, `/ops/disputes/*` |
| Invoice and payment (§15) | `/package/purchase`, `/checkout`, webhook, `/refund`, reconciliation |
| Files and documents (§16) | `/uploads`, `/complete`, worker processing, render jobs, share tokens |
| Build record (§17) | `/handover/start`, `/assemble`, `/issue`, `/transfer` |
| Recommendation (§18) | `/leads/suggest`, adjustments complete (quote recommendation), `/ops/recommendations/{id}/*` |

## 20. Contract generation and client use

- FastAPI emits the OpenAPI 3.1 document at build time; CI stores it as an artefact and diff-checks it against the previous release (a removed field or endpoint fails the build unless the change is marked breaking).
- `packages/contracts` in the monorepo holds the generated TypeScript types and a typed fetch client, plus the state vocabulary and enums exported from the Python source (ENVIRONMENT_AND_DEPLOYMENT.md section 4). The web app never hand-writes request or response types.
- Schemathesis runs against the OpenAPI document in CI to fuzz every endpoint for contract and validation faults (TESTING_ARCHITECTURE.md).

## 21. Amendment to DATA_ARCHITECTURE.md

`idempotency_keys` (core): `key`, `session_id`, `request_hash`, `response_status`, `response_body jsonb`, `created_at`; UNIQUE (`session_id`,`key`); retention 24 hours. Required by the conventions above; carried in DATA_ARCHITECTURE.md section 4.15.

## 22. As built for Handover 1 (2026-10-04)

The tables in sections 3, 4 and 15 are the design. These endpoints exist now, with these shapes; where they differ, this section governs for them. All are under `/api/v1`, return the error envelope, and need the CSRF headers on every state change.

| Route | Actor | Request | Response | Side effects | Limits and notes |
|---|---|---|---|---|---|
| `GET /public/requirement-questions` | public | none | the ACTIVE question set (`version`, `locale`, `sections`, `questions`, `review_flags`) | none | T0. The form is rendered from it |
| `POST /public/enquiries` | public | `kind` (COMING_SOON_HELP, OTHER_CITY), `email`, `work_type` (required for COMING_SOON_HELP, forbidden for OTHER_CITY) | 202 `{received: true}` | `enquiries` row; E `enquiry.created` | 20 per IP per 10 minutes; 5 per email per 10 minutes. Replaces the design row (R-1, R-2 capture only these fields) |
| `POST /projects` | homeowner | `city` (an active city), `project_type` (NEW_HOME); header `Idempotency-Key` (UUID, required) | 201 project and requirement (DRAFT) | Project DRAFT with OWNER membership; status history; A; E `project.created` | Replay returns the stored response; same key, other body: 409 `IDEMPOTENCY_MISMATCH` |
| `GET /projects`, `GET /projects/{id}` | owner | none | summaries; detail with `requirement` (`question_set_version`, `answers`, `version`, `submitted_at`) | none | Another family's project is 404. Review flags are never returned to the homeowner |
| `PUT /projects/{id}/requirement` | owner, DRAFT only | `answers` (keys of the set), `version` | requirement | none | Partial answers allowed; unknown keys and invalid values 422 with per-field messages; stale `version` 409 `VERSION_CONFLICT`; after submission 409 `STATE_CONFLICT`. Answers to hidden questions are dropped |
| `POST /projects/{id}/requirement/submit` | owner | `version`; header `Idempotency-Key` | project (SUBMITTED) and requirement | DRAFT to SUBMITTED; project columns filled from the answers; A; E `requirement.submitted` with review flags | Complete validation (422 lists every missing answer). Nothing qualifies automatically (B-01) |
| `GET /geo/locality?lat&lng` | homeowner | coordinates | `{locality}` or `{locality: null}` | `geocode_cache` row | 30 per session per 10 minutes; provider limit 1 per second. A provider outage returns `null`, never an error |
| `POST /uploads` | owner, DRAFT only | `project_id`, `file_name`, `content_type`, `size_bytes`; header `Idempotency-Key` | 201 `file`, `upload_url` (PUT, 15 minutes), `headers` | File PENDING_UPLOAD | 60 per session per minute. Type, size and count (at most 10 open files) come from the set's `uploads` question. The URL signs type and length |
| `POST /uploads/{id}/complete` | uploader | none | file: UPLOADED, or FAILED when the stored size differs from the declared size | E `documents.upload_completed`; job `process_file` (sniff, PDF checks, image re-encode without EXIF, ClamAV; then AVAILABLE or QUARANTINED) | 409 before the object arrives |
| `GET /projects/{id}/files` | owner | none | files except DELETED | none | |
| `GET /files/{id}/url` | owner | none | `url` (15 minutes, attachment), `expires_in_seconds` | `document_access_log` | 409 until AVAILABLE |
| `DELETE /files/{id}` | owner, DRAFT only | none | 204 | DELETED (soft) | |

Slice 2 foundation (2026-10-04), admin host only. "Staff" means an operations account holding OPS or ADMIN.

| Route | Actor | Request | Response | Side effects | Limits and notes |
|---|---|---|---|---|---|
| `GET /me` | any | none | adds `staff` (`roles`, `mfa_enrolled`, `mfa_verified`) on the admin host | none | Additive |
| `GET /auth/mfa` | staff | none | `enrolled`, `verified`, `recovery_codes_left` | none | Works before MFA |
| `POST /auth/mfa/enrolment` | staff, not enrolled | none | `secret`, `otpauth_uri`, `qr_svg_data_uri` | pending secret; A | 409 `MFA_ALREADY_ENROLLED` |
| `POST /auth/mfa/enrolment/confirm` | staff | `code` (6 digits) | `recovery_codes` (once) | enabled; session rotated and MFA-verified; A; security event | 5 per session per 10 min, 15 per account per hour; 400 `MFA_INVALID` |
| `POST /auth/mfa/verify` | staff | `code` (TOTP or recovery code) | `method`, `recovery_codes_left` | session rotated and MFA-verified; security event | Same limits; a recovery code in use is a warning event |
| `GET /admin/staff` | ADMIN with MFA | none | staff accounts with roles and MFA state | none | Read-only account administration view |
| `GET /ops/queues/requirement-review` | OPS with MFA | `cursor` | entries (item, project with review flags), `next_cursor` | none | Oldest first, 50 per page |
| `POST /ops/queue-items/{id}/claim`, `/release` | OPS with MFA | none | item | claim state; A with the project id | 409 when another person holds it; claiming your own is a no-op |
| `GET /ops/projects/{id}` | OPS with MFA | none | project, review flags, answers, owner email, files, queue item | none | Read-only (API 18) |
| `GET /ops/files/{id}/url` | OPS with MFA | none | `url`, `expires_in_seconds` | `document_access_log` | Requirement uploads only; 409 until AVAILABLE |

Slice 2 review and workspace (2026-10-04, rulings 2.1 to 2.10). Decisions need the reviewer's own claim on a SUBMITTED project and an `Idempotency-Key`; a replay returns the stored response.

| Route | Actor | Request | Response | Side effects | Limits and notes |
|---|---|---|---|---|---|
| `POST /ops/projects/{id}/accept` | OPS with MFA, holding the claim | header `Idempotency-Key` | detail | `SUBMITTED → ACCEPTED`; stage instances and 67 lines in the same transaction; item RESOLVED; history; A; E `project.accepted` | Already ACCEPTED: no-op. CANCELLED or NEEDS_INFO: 409 `STATE_CONFLICT`; not claimed by the caller: 409 |
| `POST /ops/projects/{id}/request-information` | OPS with MFA, holding the claim | `message` (1 to 2000 characters); header | detail | `SUBMITTED → NEEDS_INFO`; item RESOLVED; history with the message; A; E `project.needs_info` | |
| `POST /ops/projects/{id}/cancel` | OPS with MFA; claim needed when SUBMITTED | `reason` (1 to 2000 characters); header | detail | `→ CANCELLED`; item RESOLVED; history with the reason; A; E `project.cancelled` | Already CANCELLED: no-op. Final |
| `GET /ops/projects/{id}` | OPS with MFA | none | adds `history` (from, to, actor email, reason, time) | none | |
| `GET /projects/{id}` | owner | none | adds `review_message` (`status`, `message`, `at`: the ask message while NEEDS_INFO, the cancel reason once CANCELLED) | none | Never internal notes or flags |
| `PUT /projects/{id}/requirement`, `POST .../submit`, `POST /uploads`, `DELETE /files/{id}` | owner | as before | as before | Allowed in DRAFT and NEEDS_INFO; submit from NEEDS_INFO is the resubmission (new `requirement.submitted`, new queue item) | |
| `GET /projects/{id}/workspace` | owner (members) | none | `project`, `stages` (number, name, floor, gate, state, planned dates), `groups` (code, name, issued, lines: code, item, state, long lead, structural, `engineer_signoff`, `performance_specification`), `criteria_visible` | none | 409 before ACCEPTED; 404 for non-members and staff sessions. Changed in Slice 3.0: `packages` became `groups`, `purchased` removed; criteria only when `criteria_visible` (package active, or the F-09 setting) |

Slice 3.0 (2026-10-05):

| Route | Actor | Request | Response | Side effects | Limits and notes |
|---|---|---|---|---|---|
| `GET /projects/{id}` | owner | none | adds `package` (`availability`: NOT_SUBMITTED, UNDER_REVIEW, ELIGIBLE, NOT_ELIGIBLE; `purchasable`: false) | none | ELIGIBLE means the initial review passed (ACCEPTED), nothing more |
| `POST /projects/{id}/requirement/submit` | owner | as before | as before | also stores the indicative estimate | |
| `GET /projects/{id}/designs` | members | none | `quota` (`free_total`, `free_used`, `in_progress`, `free_remaining`, `can_generate`, `block`, `paid_generations_available` false) and `items` (newest first) | expires stale in-flight generations; logs each signed image link | Slice 3.1 |
| `POST /projects/{id}/designs` | owner | `view` (EXTERIOR, INTERIOR) only, unknown fields 422; header `Idempotency-Key` | 202 design (QUEUED) | generation row; A; E `design.generation_requested`; job on `ai` | 409 `QUOTA_EXHAUSTED` (`details.block`) or `STATE_CONFLICT`; 503 when no provider; 20 per session per 10 minutes |
| `GET /projects/{id}/designs/{design_id}` | members | none | design: `sequence`, `view`, `state`, `funding`, dates, `failure_reason`, `image_url` (inline signed link when SUCCEEDED), `is_authoritative` false, `reference` | logged link | Never provider, model, prompt or cost |
| `POST /projects/{id}/designs/{design_id}/reference` | owner | header `Idempotency-Key` | design with `reference` (ILLUSTRATIVE_REFERENCE) | reference row; A | 409 unless SUCCEEDED, or when the project is closed; idempotent |
| `DELETE /projects/{id}/designs/{design_id}/reference` | owner | none | design with `reference` null | reference marked removed (history kept); A | Same 404 and 409 rules; idempotent. Changes nothing else |
| `GET /projects/{id}/estimate` | owner (members) | none | `status`, `unavailable_reason`, `created_at`, `inputs`, `figures` (totals, per sq ft, duration, stages with names, rate card) | stores an estimate on first read for projects submitted before 3.0 | 409 before the first submission; 404 for non-members; DEMO cards never in production |

Slice 3.2 (2026-10-05). Professional routes need a professionals-host session; operations routes need MFA.

| Route | Actor | Request | Response | Side effects | Limits and notes |
|---|---|---|---|---|---|
| `GET /pro/profile` | professional | none | profile (with `missing` fields, `names_locked`), categories (state, requirements with provided counts, missing, message, dates, `public`), documents, references, portfolio, available categories | creates the empty profile on first use; A | Own data only |
| `PATCH /pro/profile` | professional | any of name, firm, bio, experience, team size, locality, `base_point`, radius; unknown fields 422 | dashboard | A | Name and firm 409 once a category is submitted |
| `POST /pro/categories`, `PUT /pro/categories/{code}/subtypes` | professional | `category`, `subtypes` | dashboard | DRAFT category; history; A | Subtypes only for categories that have them |
| `POST /pro/categories/{code}/submit` | professional | header `Idempotency-Key` | dashboard | PENDING_REVIEW; requirement version frozen; case opened; history; A; E `professional.category_submitted` | 422 with missing profile fields and requirements; 409 before `reapply_after`, or re-verification before it is due |
| `POST /pro/categories/{code}/hide`, `/show` | professional | none | dashboard | `hidden` flag; history; A | LISTED only; showing a listing past its re-verification date is 409 |
| `POST /pro/uploads`, `/pro/uploads/{id}/complete`, `GET /pro/files/{id}/url` | professional | purpose VERIFICATION_EVIDENCE or PORTFOLIO, file facts | upload ticket; file; signed link | file row; worker checks; link logged | jpg, png, pdf (evidence) or jpg, png (portfolio), 10 MB, 30 files |
| `POST /pro/documents`, `/pro/references`, `/pro/portfolio`; `DELETE` each | professional | kind and file, or name, phone and project note, or file and caption | dashboard | rows; A | 409 while a category is in review |
| `GET /public/professional-categories` | anyone | none | categories with subtypes | none | Public |
| `GET /public/professionals` | anyone | `category`, `subtype`, `q`, `locality`, `cursor` | `items` (D-01 fields, categories with verified kinds and registrations, cover image link), `next_cursor`, `order` = `daily_shuffle` | none | Public; 120 per minute per address; LISTED and not hidden only |
| `GET /public/professionals/{id}` | anyone | none | card fields plus bio and approved portfolio | none | Public; same rate limit; 404 unless at least one category is public |
| `GET /projects/{id}/professionals` | project members | as the directory, without `locality` | as the directory, limited to professionals whose radius covers the plot | none | 404 for non-members |
| `GET /ops/queues/professional-review` | OPS with MFA | none | entries | none | Oldest first |
| `GET /ops/professionals?state=` | OPS or ADMIN with MFA | `state` | entries | none | |
| `GET /ops/professional-categories/{id}` | OPS or ADMIN with MFA | none | profile, email, requirements and unmet ids, documents, references, portfolio, checks with internal notes, history, queue item | none | |
| `POST /ops/professional-categories/{id}/checks` | OPS with MFA, holding the claim | `kind`, `subject`, `outcome`, `note` | detail | append-only check; A | Kind must be one the requirements accept |
| `POST /ops/professional-categories/{id}/approve`, `/request-changes`, `/reject` | OPS with MFA, holding the claim | `message` (required except approve); header `Idempotency-Key` | detail | state; case decided; item RESOLVED; history; A; E `professional.listing_changed` | Approve is 409 with `unmet` and missing profile fields until every requirement is satisfied and the profile is complete |
| `POST /ops/professional-categories/{id}/suspend`, `/reinstate` | OPS or ADMIN with MFA | `reason` | detail | LISTED and SUSPENDED; history; A; E | |
| `POST /ops/portfolio-items/{id}/approve`, `/reject` | OPS with MFA | none | item | review state; A | |
| `POST /ops/professionals` | OPS with MFA | `email`, `display_name`; header `Idempotency-Key` | user, profile, `created` | account PENDING_VERIFICATION and empty profile; A | Same review as self-registration |

Slice 3.3 (2026-10-05). Requests carry versions and choices, never an amount; creating and transition POSTs take `Idempotency-Key`.

| Route | Actor | Notes |
|---|---|---|
| `GET /projects/{id}/package` | owner | Availability, package state, entitlement, the offer with the server's price and tax per payment mode (`buyer_state` optional), open order, orders, GST state list |
| `POST /projects/{id}/package/orders` | owner | `offering_version_id`, `payment_mode`, `buyer`, `accept_terms_version`; 409 not eligible, active package, open order or changed offer; 422 price unavailable; 503 billing not configured |
| `GET /me/ai-credits`, `POST /ai-credits/orders` | account | Balance, ledger, the credit offer; a single-credit order |
| `GET /me/billing`, `GET /orders/{id}`, `POST /orders/{id}/cancel` | buyer | Orders with dues, attempts, invoices, refund requests; cancel an unpaid order |
| `POST /payment-dues/{id}/checkout` | buyer | Attempt and provider order for the due's amount (reused while open); 5 new attempts per due per hour |
| `POST /payment-attempts/{id}/confirm` | buyer | The checkout callback: signature checked, a verified fetch queued; never applies anything; 401 when forged |
| `POST /orders/{id}/refund-requests`, `GET /invoices/{id}/document` | buyer | A refund request with a reason; a logged invoice link |
| `POST /webhooks/razorpay` | provider | HMAC on the raw body, event id header, 256 KB, 120 per minute per address; stored once, processed by a job |
| `POST /dev/fake-gateway/attempts/{id}/pay` | buyer | Local development and tests only (fake gateway); stands in for the shopper and the provider |
| `POST /projects/{id}/designs` | owner | Adds `use_credit`: spends one credit only when chosen and the free generations are used up; 409 `NO_CREDIT` |
| `POST /ops/projects/{id}/accept` | OPS with MFA, claim | Adds `checks` (every item of the ACTIVE checklist, PASSED); `GET /ops/projects/{id}` adds `eligibility` |
| `GET /ops/billing/orders`, `/ops/billing/orders/{id}`, `/ops/billing/invoices/{id}/document` | OPS or ADMIN with MFA | Orders with payments (applied or not), refunds, history, refund requests |
| `POST /ops/billing/orders/{id}/refund-requests` | OPS or ADMIN with MFA | Staff-raised request, optional amount |
| `GET /ops/billing/refund-requests`, `/{id}`; `POST .../approve`, `.../decline`, `.../retry` | OPS or ADMIN with MFA | Decision with reason; approve takes the amount, `ends_package`, `credits_revoked` |
| `POST /ops/billing/packages/{project_id}/cancel` | ADMIN with MFA | ACTIVE to CANCELLED with a reason |
| `GET /ops/billing/exceptions`, `POST .../{id}/resolve` | OPS or ADMIN with MFA | Resolution with a reason; nothing applied |
| `GET`, `POST /admin/billing/{pricing-rules, instalment-plans, tax-configurations, offerings}`, `POST .../{id}/publish`, `POST /admin/billing/pricing-rules/{id}/preview`, `POST /admin/billing/reconcile` | ADMIN with MFA | Drafts, publish (refuses TEST in production and incomplete tax), preview, manual reconciliation |
| `GET`, `POST /admin/eligibility-checklists`, `POST .../{id}/publish` | ADMIN with MFA | Checklist versions |

Slice 3.4 (2026-10-05). Creating and transition POSTs take `Idempotency-Key`. Refusals are 409 `PACKAGE_REQUIRED`, or `STATE_CONFLICT` with `details.reason` (NOT_ELIGIBLE, NOT_OWNER, NOT_NEEDED, ENGAGED, DUPLICATE, OPEN_LIMIT, NOT_LISTED, OUTSIDE_AREA, NO_LOCATION, SELF, IN_USE, EXPIRED, PACKAGE_ENDED, PROJECT_CLOSED).

| Route | Actor | Notes |
|---|---|---|
| `GET /projects/{id}/services` | owner or household | Per category: need, open count and cap, active engagement (contact after acceptance), requests (no decline reason), past engagements; requirement files; quote reviews |
| `PUT /projects/{id}/services/{code}/need` | owner | `state`, `subtypes`; NOT_NEEDED refused with an active engagement or open requests |
| `GET /projects/{id}/connection-target` | owner or household | `category`, `profile_id`: the professional, `blocked` reason or null, open count, response hours |
| `POST /projects/{id}/connections` | owner, package | `category`, `profile_id`, `contact_name`, `contact_phone`, `site_address`; 20 per 10 minutes per session |
| `POST /projects/{id}/connections/{cid}/withdraw` | owner | SENT only |
| `POST /projects/{id}/engagements` | owner | Outside professional: `category`, `name`, `firm`, `contact`; no package; withdraws open requests in the category |
| `POST /projects/{id}/engagements/{eid}/end` | owner | `reason` |
| `POST /projects/{id}/engagements/{eid}/files`, `DELETE .../files/{file_id}` | owner | Share or unshare requirement files with an ACTIVE listed engagement |
| `POST /projects/{id}/quote-reviews/uploads`, `.../uploads/{file_id}/complete`, `GET .../uploads/{file_id}`, `GET .../files/{file_id}/url` | owner | QUOTE_DOCUMENT uploads (scanned) and their state; logged links |
| `POST /projects/{id}/quote-reviews` | owner, package | `category`, `quoted_by`, `note`, `file_ids` (1 to 5) |
| `GET /pro/connections`, `GET /pro/connections/{id}` | professional | Brief only until ACCEPTED; then the family's contact; the pin and shared files while the engagement is ACTIVE |
| `POST /pro/connections/{id}/accept`, `/decline`, `/end` | professional | Accept with optional `phone`; decline with `reason` (and `note` for OTHER); end with `reason` |
| `GET /pro/connections/{id}/files/{file_id}/url` | professional | Shared file of an ACTIVE engagement; logged |
| `GET /ops/projects/{id}/engagements` | OPS or ADMIN with MFA | Needs, connections with decline and withdrawal reasons and the family's request contact, engagements, quote reviews, history |
| `POST /ops/connections/{id}/withdraw`, `POST /ops/engagements/{id}/end` | OPS or ADMIN with MFA | `reason` |

Slice 3.5 (2026-10-05). Creating and transition POSTs take `Idempotency-Key`; refusals are 409 with `details.reason` (PACKAGE_REQUIRED, NOT_ELIGIBLE, OPEN_VERSION, INCOMPLETE with `missing`, LAST_EDITOR, UNSIGNED with `lines`, CONTENT_CHANGED, SET_NOT_APPROVED, CARD_NOT_PUBLISHED, DEMO_CARD, NOT_VERIFIED, ALREADY_SIGNED, NOT_LATEST, SIGNOFF_REVOKED, NO_ACCEPTED_VERSION, OPS_ONLY, NO_ENGAGEMENT, NO_CHECKER, FILES_NOT_READY, NO_STATEMENT).

| Route | Actor | Notes |
|---|---|---|
| `GET /projects/{id}/build-plan`, `GET .../build-plan/versions/{vid}` | owner, household | Design requests and sets; issued versions only (drafts are 404) |
| `POST /projects/{id}/design-requests`, `.../design-requests/{rid}/sets` | owner, package | Kinds except PLAN2BUILD_ARRANGED; AI concepts by id only, illustrative |
| `POST /projects/{id}/build-plan/uploads`, `.../uploads/{fid}/complete`, `GET .../build-plan/files/{fid}` | owner | Drawing uploads (scanned) and their state |
| `POST /projects/{id}/drawing-sets/{sid}/files`, `DELETE .../files/{dfid}`, `POST .../submit`, `POST .../decision` | owner | Own and outside professionals' sets; review of a professional's set |
| `POST /projects/{id}/build-plan/versions/{vid}/acceptance-code`, `.../accept`, `.../request-changes` | owner, package | One-time code bound to the version |
| `GET /projects/{id}/build-plan/files/{fid}/url` | owner, household | Drawings of the project's sets and issued or accepted PDFs; logged |
| `GET /pro/build-plan/design-requests`, `POST .../{rid}/sets`, `.../{rid}/uploads`, `/pro/build-plan/uploads/{fid}/complete`, `/pro/build-plan/drawing-sets/{sid}/files`, `.../submit` | listed professional with the ACTIVE engagement | Their requests only |
| `GET /pro/build-plan/signoffs`, `GET .../{vid}`, `POST .../{vid}/code`, `POST .../{vid}/sign`, `POST /pro/build-plan/signoffs/{sid}/revoke`, `GET /pro/build-plan/files/{fid}/url` | engaged STRUCTURAL_ENGINEER (verified to sign) | Sign-off by one-time code |
| `GET /ops/item-rate-cards`, `POST /ops/item-rate-cards`, `PUT .../{id}/lines`, `POST /admin/item-rate-cards/{id}/publish`, `.../retire` | OPS prepares, ADMIN publishes (MFA) | DEMO refused in production |
| `GET /ops/drawing-checkers`, `POST /admin/drawing-checkers`, `.../{id}/end`; `GET /ops/signoff-statements`, `POST /admin/signoff-statements`, `.../{id}/activate`; `GET /ops/acceptance-statements`, `POST /admin/acceptance-statements`, `.../{id}/activate` | staff, ADMIN | Statements are versioned; acceptance templates may use only $version_no, $project_code, $content_hash |
| `GET /ops/projects/{id}/build-plan`, `POST .../design-requests`, `POST /ops/design-requests/{rid}/sets`, `POST /ops/projects/{id}/build-plan/files` (raw body), `POST /ops/drawing-sets/{sid}/files`, `.../submit`, `.../check` | OPS or ADMIN with MFA | Staff uploads go through the API (the admin host is not a storage CORS origin) |
| `POST /ops/projects/{id}/build-plan/versions`, `GET /ops/build-plan-versions/{vid}`, `PUT .../drawing-set`, `.../values`, `POST .../values/{code}/refresh`, `PUT .../boq`, `.../schedule`, `.../scope`, `POST .../submit`, `.../return`, `.../withdraw`, `.../issue`, `.../signoffs`, `POST /ops/signoffs/{id}/revoke` | OPS or ADMIN with MFA | Issue never by the last editor |
| `GET /ops/projects/{id}/build-plan/rfq-manifest` | OPS or ADMIN with MFA | Accepted version only; no rate, amount or rate card (BP-08) |

Slice 3.6 (2026-10-06). Creating and transition POSTs take `Idempotency-Key`; refusals are 409 with `details.reason` (PACKAGE_REQUIRED, NO_ACCEPTED_VERSION, OPEN_RFQ, NOT_NEEDED, ENGAGED, NOT_LISTED, OUTSIDE_AREA, NO_LOCATION, SELF, DUPLICATE, LIMIT, NO_DEADLINE, BASELINE_CHANGED, NO_RECIPIENTS, NOT_ELIGIBLE, EXPIRED, RFQ_CLOSED, DEADLINE_PASSED, NOT_EXPIRED, CONTENT_CHANGED, NO_QUOTE, NO_REVIEWED_QUOTES, NO_COMPARISON, STALE, STATEMENT_CHANGED, NO_STATEMENT); 422 names the quote lines to fix. Section 10 is [SUPERSEDED] where it differs.

| Route | Actor | Notes |
|---|---|---|
| `GET /projects/{id}/rfqs`, `GET .../rfqs/{rid}` | owner, household | Status, contractors and quote versions; prices only in a published comparison (QD-07) |
| `POST /projects/{id}/rfqs` | owner, package | `profile_ids` nominated (QD-03); the ACCEPTED version is named |
| `POST /projects/{id}/rfqs/{rid}/cancel` | owner | No package needed |
| `GET /projects/{id}/rfqs/{rid}/comparisons/{cid}/document`, `GET .../rfqs/{rid}/files/{fid}/url` | owner, household | Comparison PDF; attachments of compared quotes only; logged |
| `POST /projects/{id}/rfqs/{rid}/selection-code`, `.../select` | owner, package | Code bound to the quote version; the response carries the statement; `select` takes the code, `statement_id` and the contact to share |
| `GET /pro/rfq-invitations`, `GET .../{iid}` | the invited contractor | Brief until accepted; then the frozen pack (no rate, amount or card), own versions and visible clarifications; never adjustments, reviews, comparisons or other contractors |
| `POST /pro/rfq-invitations/{iid}/accept`, `/decline` | the invited contractor | Agreeing to quote is not an engagement (QD-01) |
| `GET .../{iid}/drawings/{fid}/url`, `PUT`/`DELETE .../quote-draft`, `POST .../quotes`, `.../quote/renew`, `.../quote/withdraw`, `.../clarifications`, `.../clarifications/{cid}/answer`, `.../attachments`, `.../attachments/{fid}/complete`, `.../files/{fid}/url` | the invited contractor | Pack drawings while accepted; quote versions; questions to Plan2Build |
| `GET /pro/engagements/{eid}`, `POST .../end`, `GET .../files/{fid}/url` (engagements) | the engaged professional | Any origin (ADR-024): the family's contact, and pin and shared files while ACTIVE |
| `GET /ops/rfqs`, `GET /ops/projects/{id}/rfqs`, `POST /ops/projects/{id}/rfqs`, `GET /ops/rfqs/{rid}` | OPS or ADMIN with MFA | Queue, detail with every version, review, adjustment, clarification, comparison and history |
| `PUT /ops/rfqs/{rid}/deadline`, `POST .../deadline/extend`, `.../invitations`, `.../issue`, `.../cancel`, `POST /ops/rfq-invitations/{iid}/withdraw`, `.../capture` | OPS or ADMIN with MFA | Introductions and extensions need a reason; capture needs the contractor's document |
| `POST /ops/projects/{id}/rfq-files` (raw body), `GET /ops/rfq-files/{fid}/url` | OPS or ADMIN with MFA | Quote documents received outside the portal; logged downloads |
| `PUT /ops/quote-versions/{qid}/adjustments`, `POST .../reviewed`, `POST /ops/rfqs/{rid}/clarifications`, `POST /ops/rfq-clarifications/{cid}/answer`, `.../close`, `POST /ops/rfqs/{rid}/comparisons` | OPS or ADMIN with MFA | Review, questions, publication with the PDF |
| `GET /ops/selection-statements`, `POST /admin/selection-statements`, `.../{id}/activate` | OPS reads, ADMIN | Versioned selection statement |

## 23. As built for the concept floor plan, Checkpoint 1 (2026-10-06)

Owner `houseplans` (ADR-025, PD-28). Homeowner audience; owner writes, members read (AD-12). Behind the `houseplans_enabled` setting, off in production until the ruleset is PUBLISHED and AD-06 is decided. Full contracts: `02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_1.md` section D.

| Endpoint | Who | Notes |
|---|---|---|
| `GET /projects/{id}/house-plans` | owner, members | Plans with generation state and head validity |
| `POST /projects/{id}/house-plans` | owner (members 403) | `Idempotency-Key`; body `{design_inputs}` (PROVISIONAL, CP1-03); 202 QUEUED; 409 `STATE_CONFLICT`, `GENERATION_IN_PROGRESS`, `RULESET_NOT_PUBLISHED`; 422 `DESIGN_INPUT_REQUIRED` with the missing inputs, `PLAN_UNSUPPORTED`, `VALIDATION_ERROR` |
| `GET /projects/{id}/house-plans/{plan_id}` | owner, members | Head document, `PlanGeometry`, validation report, or the infeasibility explanation |
| `GET /ops/projects/{id}/house-plans`, `GET /ops/house-plans/{plan_id}` | OPS or ADMIN with MFA | Read only |
