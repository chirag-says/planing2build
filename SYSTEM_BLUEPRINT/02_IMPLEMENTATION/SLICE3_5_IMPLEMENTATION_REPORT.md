# Plan2Build: Slice 3.5 implementation report (authoritative design and Build Plan)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/SLICE3_5_IMPLEMENTATION_REPORT.md` |
| Date | 2026-10-05; reconciled the same day after Chirag's approval |
| Status | SLICE 3.5 IMPLEMENTATION = COMPLETE (approved by Chirag); SLICE 3.5 PRODUCTION READINESS = NOT YET READY (section L) |
| Rules | SLICE3_5_READINESS.md section 0 (BP-01 to BP-20, Chirag 2026-10-05); BP-07A deferred |
| Scope kept out | Ratings, ranking, professional payments, construction money, CAD, AI drawing generation, quote comparison, construction execution, visual redesign |

## A. What was implemented

- **Design intake (BP-01 to BP-03).** Design requests of four kinds: a listed professional with an ACTIVE engagement, the family's own (outside) professional, the family's own drawings, a professional Plan2Build arranges (operations only). Drawing sets with classified files (site plan, floor plan, elevation, section, structural, other), the family's review of a professional's set, and approval by an appointed checker who need not be an employee: a checker with an account records the check; otherwise operations record it with the checker's signed note. An approved set is authoritative and immutable; a later approved set supersedes it. Plan2Build generates no drawing. AI concepts can only be named on a request as illustrative references, never added as files.
- **Item rate cards (BP-06).** Operations prepare a DRAFT card (geography, version, effective from and to, source, status, lines with item code, description, unit, rate); an ADMIN publishes it with MFA; published cards never change. DEMO cards are refused for publishing and pricing in production.
- **Build Plan versions.** One plan per project, versions created DRAFT (seeded empty, or carried forward from the latest version), with the approved drawing set, a project value per S04 line (value and basis, or not applicable with a reason; criteria copied from the master and never written back), a BOQ priced by the server from one published card (no manual rates; quantity basis measured from a drawing of the set, provided by a professional, or an advisor estimate with a reason), a date-less schedule (duration per stage instance, explicitly entered predecessors, cycle check), inclusions, exclusions and assumptions. Submit computes the content hash. Line criteria refresh only by the advisor (BP-19).
- **Structural sign-off (BP-04, BP-18, BP-20).** Two modes: a verified engineer (listed STRUCTURAL_ENGINEER with a verified registration and an ACTIVE engagement on the project) confirms with a one-time code; operations record an outside engineer's signed document with the registration number, issuer, certificate and their attestation. Each sign-off stores engineer, category, credential reference, version, content hash, drawing set and structural drawing hashes, the line as signed, statement version and text, evidence, time and history. Not-applicable structural lines also need a sign-off. Revocation before issue voids; after issue it is recorded and blocks acceptance.
- **Issue (BP-13).** Operations with MFA, never the version's last editor; every structural line signed on this exact content hash; a published (never DEMO in production) card; the approved set; the content hash recomputed and compared. The PDF is rendered and stored in the same transaction. An earlier unaccepted issued version becomes SUPERSEDED. Issue is recorded in history, audit and an event, and emails the family; it writes no refund usage record.
- **Acceptance (BP-05).** The owner requests a one-time code bound to the version and confirms it; the acceptance record names the version, its content hash and the issued PDF's sha256. The owner confirms the ACTIVE acceptance statement, which is versioned configuration (`acceptance_statements`, templates with $version_no, $project_code, $content_hash); version 1 is functional wording, IMPLEMENTED / PENDING FINAL CLIENT + LEGAL CONFIRMATION, and the launch wording replaces it as a new version without changing the acceptance model. Each acceptance names its statement version. A second, separate accepted-copy PDF is stored. The previous accepted version becomes SUPERSEDED. Each project specification line points at its accepted value. Changes requested close the version for acceptance.
- **Package gating and refunds (BP-09).** Package-gated work (requests, sets, drafting, submit, sign-off, issue, acceptance, change requests) is refused while the package is inactive; reading and withdrawal are not. Drafts are not withdrawn automatically. Issued and accepted versions stay readable. The refund substantial-work rule is unchanged (N-12).
- **Contractor RFQ manifest (BP-08).** For the accepted version only: drawings with hashes, issued values, quantities, schedule durations and dependencies, scope, a quote format version; no rate, amount or rate card.
- **Minimal functional screens.** Homeowner: Build Plan section (requests, sets, uploads, review, versions), version page (content, PDFs, acceptance by code, change requests). Professional: Build Plan page (requests, sets, uploads; versions to sign) and sign-off page (lines, drawings, statement, code). Operations: setup page (rate cards, checkers, statements), project Build Plan page (requests, checks, versions, manifest), version page (JSON editors for values, BOQ and schedule, scope, submit, sign-off documents, issue, return, withdraw). No visual polish.

## B. Database and migrations

Migrations `0013_buildplan` and `0014_acceptance_statements` (the reconciliation: versioned acceptance statement, each acceptance linked to its version; earlier acceptances linked to version 1, whose text they hold).

Migration `0013_buildplan`:

- **New tables:** `item_rate_cards`, `item_rate_card_lines`, `drawing_checker_appointments`, `signoff_statements`, `design_requests`, `drawing_sets`, `drawing_files`, `build_plans`, `build_plan_versions`, `build_plan_spec_values`, `boq_lines`, `build_plan_schedule_entries`, `structural_signoffs`, `build_plan_acceptances`, `build_plan_events`.
- **Changes to existing tables:**
  - `otp_challenges`: purposes ACCEPT_BUILD_PLAN and SIGN_STRUCTURAL, with `subject_id`.
  - `project_spec_lines.accepted_value_id`.
  - `file_objects` purposes DRAWING, BUILD_PLAN_EVIDENCE and BUILD_PLAN_DOCUMENT.
- **Guards (database triggers):**
  - a version's content changes only while DRAFT;
  - child rows of a version, set or card change only while it is DRAFT;
  - set-once columns;
  - append-only requests, acceptances and history;
  - sign-offs change only from SIGNED to VOID.
- **CHECK constraints:**
  - issuer is never the last editor;
  - an issued version has a document;
  - schedule dates stay NULL.
- **Seed:** sign-off statement version 1 (the baseline wording, ACTIVE, marked pending final client and legal confirmation). No rate, duration or value is seeded.
- **Migration checks:** up, down, up, down, up on the test database for 0013 and again for 0014; `alembic check` clean; dev database at 0014.

## C. API changes

The route table is in `API_ARCHITECTURE.md` (Slice 3.5 section). Rules:

- Every create and transition POST takes `Idempotency-Key`.
- Refusals are 409 with a machine-readable `reason`.
- Families read issued versions only.
- Professionals reach only requests addressed to their ACTIVE engagement, or versions where they are the engaged structural engineer.
- Staff routes need a staff role and MFA; ADMIN publishes cards, appoints checkers and activates statements.
- Staff uploads go through the API (`POST /ops/projects/{id}/build-plan/files`, raw body): the admin host is not a storage CORS origin, and the R2 policy from 3.3 was not widened.
- Acceptance statements: `GET /ops/acceptance-statements`, `POST /admin/acceptance-statements`, `POST /admin/acceptance-statements/{id}/activate` (ADMIN with MFA; only the three placeholders are accepted).
- Contracts regenerated.

## D. State machine

Build Plan version (as built):

| From | To | Who | Guard |
|---|---|---|---|
| (new) | DRAFT | advisor | Package active; no open version |
| DRAFT | IN_REVIEW | advisor | Complete; content hash stored |
| IN_REVIEW | DRAFT | advisor or operations | Reason; sign-offs voided |
| IN_REVIEW | ISSUED | operations with MFA, not the last editor | All issue conditions |
| ISSUED | ACCEPTED | owner | One-time code; latest issued; package active; no revocation after issue |
| ISSUED | CHANGES_REQUESTED | owner | Reason |
| ISSUED, CHANGES_REQUESTED | SUPERSEDED | system | A later version issued |
| ACCEPTED | SUPERSEDED | system | A later version accepted |
| DRAFT, IN_REVIEW, ISSUED | WITHDRAWN | operations | Reason; never ACCEPTED |

Drawing set:

| From | To | Who | Guard |
|---|---|---|---|
| DRAFT | SUBMITTED | professional or operations | At least one file; files scanned; hash stored |
| DRAFT | IN_CHECK | the family, for its own set | Same as submit |
| SUBMITTED | IN_CHECK or CHANGES_REQUESTED | the family | A note is needed for changes |
| IN_CHECK | APPROVED or REJECTED | appointed checker | A signed note when the checker has no account |
| APPROVED | SUPERSEDED | system | A later set of the same request approved |

Sign-off: SIGNED → VOID before issue only.

No project status moves (BP-14). `STATE_MODEL.md` 8a records the as-built machine.

## E. Permissions

| Actor | Can |
|---|---|
| Owner | Open requests (not PLAN2BUILD_ARRANGED); provide their own and outside professionals' sets; review a professional's set; read issued versions; accept with a code; request changes; download drawings and issued PDFs |
| Household | Read what the owner reads |
| Listed professional, engaged | Provide sets for requests addressed to their engagement; download those drawings |
| Engaged structural engineer | Read versions in review on that project; sign with a code once verified; revoke |
| OPS (MFA) | Draft, edit drafts, submit, return, withdraw unaccepted versions; record checks, signed documents and staff uploads; issue other people's versions; prepare rate cards; read the manifest |
| ADMIN (MFA) | Everything OPS can, plus publish and retire rate cards, appoint and end checkers, draft and activate statements |
| Nobody | Edit a version outside DRAFT; issue their own last edit; withdraw an accepted version |

## F. PDF

- **Engine:** fpdf2. Reconciled on 2026-10-05: **ADR-023** approves fpdf2 for Build Plan PDFs (issued and accepted copies), invoices and credit notes, and supersedes ADR-018 (WeasyPrint) in full. ADR-018 applies to no document type. Later document types use fpdf2 unless a new ADR justifies HTML layout. The architecture documents, the ADR index and the baseline are updated.
- **Content:** rendered from the version's snapshot only:
  - project, version, state, issue date, content hash, requirement version, rate card;
  - drawings register with hashes, checker and provider;
  - specification values by group with criteria and basis;
  - BOQ with stage totals and total;
  - schedule (durations and dependencies, with the note that dates are not calculated, BP-07A);
  - scope; sign-off register and statement text;
  - revision history;
  - the acceptance record and statement in the accepted copy.
- **Rendering:**
  - Deterministic: creation date fixed to the issue or acceptance time; identical snapshots give identical bytes (tested).
  - A DEMO card puts a TEST banner on the PDF.
  - Rendered inside the issue and acceptance transactions (ADR-023); the issued PDF never changes.
- **Wording:**
  - the two source statements;
  - the versioned sign-off statement and acceptance statement (both IMPLEMENTED / PENDING FINAL CLIENT + LEGAL CONFIRMATION);
  - no other legal language; English only.

## G. RFQ boundary

`GET /ops/projects/{id}/build-plan/rfq-manifest` returns the accepted version's manifest: version id and number, content hash, accepted time, drawings with hashes, specification values (criteria, value, applicability), quantities (no rate, amount or card), schedule durations and dependencies, `dates_status`, scope, quote format version 1. It refuses before acceptance (`NO_ACCEPTED_VERSION`). No RFQ entity, invitation, quote or comparison was built. A test checks that the manifest JSON contains no rate key and no rate value.

## H. Schedule deferral (BP-07A)

- **What is stored:** schedule entries hold a duration and explicitly entered predecessors per stage instance; dependencies are checked for unknown keys, self-reference and cycles.
- **What is never calculated:** stage dates, decide-by dates and the monthly cash-flow figure. Snapshots, the PDF and the manifest say `NOT_CALCULATED_BP07A_DEFERRED`.
- **What is never inferred:** no order from display order or stage numbers, and no default predecessor.
- **Enforced by the database:** a CHECK keeps `planned_start` and `planned_end` NULL; a test proves a write is refused, and that no project line receives a decide-by date.
- **Later:** date calculation is added by lifting that CHECK once BP-07A is decided. The version, sign-off and acceptance model does not change.

## I. Tests

| Check | Result |
|---|---|
| API (pytest) | 484 passed (16 in `test_buildplan.py`, including the versioned acceptance statement; helpers in `buildplan_support.py`) |
| Coverage of the new code | `buildplan` 88% overall, with `item_rates` and `confirmations` included in that figure (models and views 100%, lifecycle 90%, plans 85%, PDF 94%) |
| ruff, mypy strict (src), import-linter | Clean; 4 contracts kept, `buildplan` added to every contract |
| Migration | 0013 and 0014 up, down, up twice; `alembic check` clean |
| Web: `tsc`, ESLint, Vitest 30, `next build` | Clean |
| Playwright, phone and desktop, axe on every screen | 58 passed: 32 + 10 + 8 + 6 + 2 (`buildplan.spec.ts`), production build, rate limits reset per batch; rerun after the reconciliation with the same result |

API tests cover:

- **Transitions:** draft to review, review to draft (sign-offs voided, re-sign needed), review to issued, issued to accepted, issued to changes requested, issued to withdrawn, accepted to superseded, changes requested to superseded. A withdrawn version cannot be accepted; an accepted version cannot be withdrawn.
- **Immutability, enforced by database triggers on:** version content, content hash, values, BOQ, schedule, sign-offs, acceptances, events, set hash, set files, card lines, statements, and the four-eyes CHECK.
- **Sign-off:** hash binding; a partial sign-off is not issuable.
- **Engineer sign-off:** one-time-code sign-off with credential reference and drawing hashes; the code cannot be reused; revocation before and after issue.
- **Who may sign:** an unverified or unengaged engineer is refused; an outside engineer's document needs the certificate and the evidence.
- **Issue:** the last editor cannot issue.
- **Package gating:** a refund leaves the issued version readable and the draft in place, and blocks new work; the refund rule is unchanged.
- **Rate cards:** DEMO refused in production; ADMIN-only publish; a draft card cannot price a BOQ.
- **Contractor manifest:** rates hidden.
- **Access:** strangers 404, anonymous 401, drafts invisible to the family.
- **Downloads:** authenticated and logged.
- **AI exclusion:** unknown concepts refused; an AI_CONCEPT file cannot be a drawing.
- **Schedule:** dates stay NULL; loops and unknown keys refused.
- **Codes:** a confirmation code never signs anyone in, and another user cannot use it.
- **The rest:** a listed architect's set through the family's review and a checker with an account; the issue email; PDF determinism; staff uploads through the API.

The browser test runs the whole workflow on phone and desktop:

1. The family uploads five drawings (scanned) and submits.
2. Operations record the check with a signed note.
3. Operations draft and complete a version through the screens and submit it.
4. Operations record an outside engineer's signed document.
5. The last editor is refused at issue; a second operator issues.
6. The family accepts with the emailed code.
7. The manifest shows quantities and no rate.

## J. Security

- **Authorisation:** membership or engagement on every route; 404 outside it; staff routes need a role and MFA; ADMIN for publishing and appointments.
- **Immutability:** enforced by database triggers as well as the service.
- **Confirmation codes:** argon2id hash, encrypted only until delivery, 10 minutes, 5 attempts, per-user rate limits; bound to user, purpose and subject; never usable for sign-in; recorded on the sign-off or acceptance (the acceptance challenge is UNIQUE).
- **Files:** every file passes the type check and scan before use. Staff uploads go through the API and the same scan. Downloads are short-lived, signed-in and logged. There are no share links (BP-16).
- **Data in transit to other parties:** events carry ids only. Contractors never receive internal rates.
- **Audit:** every transition, edit set, check, sign-off, void, issue, acceptance and card or statement change.

## K. Known limitations (accepted for Slice 3.5)

- **Engineer notification (workflow gap, not complete).**
  - The sign-off itself works.
  - The engineer is **not** emailed when a version awaits sign-off; they see it on their Build Plan page.
  - Placement: follow-up hardening task **H-01**, done before production and independent of 3.6. It is a notification on 3.5's own workflow, needs no RFQ concept, and reuses the notification pattern of 3.4: an event when a version enters IN_REVIEW, a template, the engaged engineer's primary email.
- **Browser coverage, accepted as API-tested:** the listed architect's upload screen and the engineer's sign-off screen. No extra UI work was done to raise browser coverage.
- **Screens:** functional only; JSON editors for values, BOQ and schedule.
- **Accounts:** household members read but do not act. Outside professionals have no accounts (F-03).
- **Other notifications:** only the family's "Build Plan issued" email was added.
- **Rendering:** synchronous rendering means a storage failure fails the issue (ADR-023).
- **Project lines:** `project_spec_lines.engineer_signoff` (from Slice 2) is left in place; sign-off is read per version.
- **Schedule:** no dates, decide-by or cash flow (BP-07A deferred).

## L. Implementation complete versus production readiness

### L.1 Implementation complete

Every Slice 3.5 item in SLICE3_5_READINESS 0.5 is built and tested: design intake, rate cards, checkers, versioned statements, drafting, review and sign-off, issue, PDF, acceptance, package gating, the contractor manifest, accepted-value pointers, functional screens. Tests, migrations and checks pass (section I). None of the items in L.2 is a defect in the implementation.

### L.2 Production readiness blockers (business inputs and launch items)

| Blocker | Why |
|---|---|
| An approved Raipur production item rate card (prepared by operations, published by an ADMIN) | Production refuses DEMO pricing; no rate was invented |
| An appointed drawing checker | No set can be approved |
| Approved sign-off wording (final client and legal confirmation of statement v1, published as a new version if it changes) | Production sign-off |
| Approved acceptance wording (same) | Production acceptance |
| An available qualified structural engineer (listed and verified, or outside with a certificate) | Plans with structural lines |
| A production Unicode PDF font (`P2B_INVOICE_FONT_PATH`) | Rendering beyond Latin-1 |
| Client confirmation of English-only documents (BP-11) | BR-057 |
| BP-07A canonical build order | Before any authoritative schedule date, decide-by date or cash flow |
| H-01 engineer notification | So engineers learn of pending sign-offs without checking |

## M. Final status

SLICE 3.5 IMPLEMENTATION = COMPLETE

SLICE 3.5 PRODUCTION READINESS = NOT YET READY
