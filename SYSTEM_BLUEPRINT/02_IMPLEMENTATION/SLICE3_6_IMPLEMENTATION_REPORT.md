# Plan2Build: Slice 3.6 implementation report (accepted Build Plan to contractor selection)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/SLICE3_6_IMPLEMENTATION_REPORT.md` |
| Date | 2026-10-06 |
| Rules | `SLICE3_6_READINESS.md` v1.1, section 0 (QD-01 to QD-26, implementation-safety decisions) |
| Status | SLICE 3.6 IMPLEMENTATION = COMPLETE (section T); production readiness depends on section R |

## A. Scope

Built:
- The contractor RFQ on the ACCEPTED Build Plan version, with its manifest frozen at issue.
- Invitations to listed contractors (and the family's outside contractor through operations capture).
- Contractor quotes as immutable versions, with withdrawal, expiry and validity renewal.
- Structured clarifications, Plan2Build's review with internal adjustments.
- A neutral, versioned comparison with a deterministic fpdf2 PDF.
- The homeowner's selection with a one-time code and a versioned statement.
- The engagement created or reused through the engagements module, and the RFQ_SELECTION substantial-work record.
- Notifications, minimal functional screens on the three hosts, API and browser tests.

Not built, by decision:
- Recommendation engine output (QD-10, deferred to a future slice).
- RFQ pack amendments (QD-16).
- Non-contractor RFQs (QD-26).
- Review of homeowner-held quotes (QD-25).
- Contract values (QD-12).
- Countdowns and reminders (QD-05).
- Any calendar date (BP-07A).

## B. Decisions implemented

| ID | As implemented |
|---|---|
| QD-01 | `rfq_invitations` is a separate record; accepting it creates no engagement or connection; the selection creates or reuses the engagement through `engagements.interface.engage_for_selection` |
| QD-02 | `PackageServiceKind.RFQ_SELECTION` written by the selection through `billing.interface.record_service_usage`; the kinds are a closed set (CHECK); N-12 untouched. Recorded as a new product decision in the readiness, DATA 4.18 and an annotation beside N-12 in SLICE3_4_READINESS |
| QD-03 | Owner request with nominations; operations introduce with a required reason; operations set the deadline and issue |
| QD-04 | `rfq_max_recipients` (default 3) copied onto each RFQ; live invitations counted |
| QD-05 | `rfq_invitation_response_hours` (48); deadline per RFQ; late submissions refused (`DEADLINE_PASSED`); audited extension with the same notice to every recipient; N-06 reasons; no countdown |
| QD-06 | Contractor dates; expiry job; selection refuses a quote not valid today (Raipur date); RENEWAL versions must keep the content hash |
| QD-07 | Family views carry status and version identity only until a comparison is published |
| QD-08 | No contractor response model has an adjustment, review or comparison field (tested by key scan) |
| QD-09 | Brief at SENT; frozen pack and drawing links after accepting; contacts exchanged only at selection |
| QD-10 | No recommendation, rank, score or label anywhere (tested); the requirement is kept for a future slice |
| QD-11 | Order from a stored per-version seed and the version ids only |
| QD-12 | Code bound to the quote version; ACTIVE statement version must match; immutable; engagement ACTIVE at once; no contract value; statement v1 functional wording, pending final client and legal confirmation |
| QD-13 | With an ACTIVE CONTRACTOR engagement only that party is invited (`ENGAGED`); an OUTSIDE party is added for capture |
| QD-14 | Handler on `billing.package_changed`: open RFQs CANCELLED (PACKAGE_ENDED), history kept, no usage record |
| QD-15 | Handler on `buildplan.accepted`: open RFQs on another version CANCELLED (BASELINE_SUPERSEDED); the old manifest never changes |
| QD-16 | No pack versions |
| QD-17 | Structured questions and answers through Plan2Build; shared answers carry no asker identity |
| QD-18 | Unit rate or exclusion with reason per line; server amounts; additional items outside the comparable total; GST choice and note; durations; free-text terms; attachments |
| QD-19 | Withdrawal with a reason until selection; resubmission before the deadline |
| QD-20 | Not-selected email names no winner, price or ranking (tested) |
| QD-21 | No enlistment class |
| QD-22 | OUTSIDE invitation, staff capture with evidence, never a platform professional |
| QD-23 | fpdf2 PDF at publication, stored with the version, never re-rendered; owner, household and operations only |
| QD-24 | One or more reviewed quotes; zero refused (`NO_REVIEWED_QUOTES`); counts shown |
| QD-25 | 3.4 intake unchanged |
| QD-26 | CHECK `category_code = 'CONTRACTOR'` |

## C. Architecture and module changes

- **ADR-024 (H-03 resolved):** `engagements` replaces `leads` in the ADR-008 module list; README, baseline, tech stack, SYSTEM and DOMAIN updated.
- **New module `rfq`** (name from DOM 3.10):
  - `models`, `common` (state tables, history, notices, access);
  - `rfqs`, `quotes`, `review`, `comparison`, `pdf`, `selection`, `views`, `schemas`;
  - `router` (homeowner and contractor), `ops_router`, `handlers`, `jobs`, `interface`.
- **Import linter:** `rfq` is in all four contracts. Billing may not import it. Modules reach it only through `rfq.interface` (used by notifications). 4 contracts kept.
- **Interfaces added:**
  - `buildplan.interface.accepted_manifest`, `accepted_version_id`;
  - `engagements.interface.lock_category`, `active_engagement`, `engage_for_selection`;
  - billing usage typed with `PackageServiceKind`.
- **Engagements:**
  - origin and contacts on engagements;
  - a professional's engagement routes for any origin (`/pro/engagements/{id}`, end, shared file links);
  - the family's view reads the professional's contact from the engagement when there is no connection.
- **Documents:** purposes QUOTE_ATTACHMENT (project upload limits) and COMPARISON_DOCUMENT (server generated); both readable by staff.
- **Identity:** purpose SELECT_QUOTE.
- **Configuration:** `rfq_max_recipients`, `rfq_invitation_response_hours`, `rfq_quote_attachments_max`.

## D. Database and migration

Migration `0015_rfq`:
- Creates `rfqs`, `rfq_invitations`, `quote_drafts`, `quote_versions`, `quote_lines`, `quote_adjustments`, `rfq_clarifications`, `comparisons`, `selection_statements`, `selections` and `rfq_events`, with CHECKs, partial unique indexes, grants and guards:
  - lifecycle-only columns;
  - set-once frozen pack and closing times;
  - append-only lines, selections and history;
  - adjustments editable only while the review is open.
- Seeds selection statement v1.
- Backfills `project_engagements.origin` (LISTED→CONNECTION, OUTSIDE→OUTSIDE) with the lifecycle guard lifted for the backfill only, then widens the party CHECK.
- Adds the usage-kind CHECK and the new OTP and file purposes.
- Downgrade removes RFQ data and the engagements it created, then restores 0014's constraints.

Checks: - Up, down, up, down, up on the test database.
- `alembic check`: no new operations.
- The dev database migrated to 0015 by the Compose `migrate` service.
- `test_migrations_produce_exactly_the_model_schema` passes.

## E. RFQ lifecycle

DRAFT (owner request or operations) → ISSUED (deadline set, package active, the version still the accepted one, at least one invitation, every listed contractor still eligible; manifest and sha256 frozen) → CLOSED (selection) or CANCELLED (owner, operations, PACKAGE_ENDED, BASELINE_SUPERSEDED, PROJECT_CLOSED). One open RFQ per project and category. Cancelling withdraws unanswered invitations, discards drafts, closes open questions and reviews, and keeps quotes and comparisons readable.

## F. Invitation lifecycle

PROPOSED on a DRAFT, SENT at issue (or when introduced after issue) with `respond_by`. Then:
- ACCEPTED: agreeing to quote, before the deadline, still LISTED, package active.
- DECLINED: N-06 reason; OTHER needs a note.
- EXPIRED: job every 15 minutes.
- WITHDRAWN: removed before issue, operations, RFQ cancelled or closed, contractor not LISTED.

An OUTSIDE party moves PROPOSED → ACCEPTED at issue for staff capture. Eligibility:
- LISTED and not hidden;
- radius covers the plot;
- not the owner;
- one per contractor;
- within the limit;
- the QD-13 rule.

## G. Quote lifecycle

- **Drafts:** private and deletable.
- **Submission:** validates every line, the dates (`valid_to` not in the past), the stage keys and the attachments (the contractor's own, scanned, of this project). It computes amounts and totals and hashes the content. It supersedes the previous version and opens the review.
- **Staff capture:** the same path with an evidence file.
- **Withdrawal:** with a reason.
- **Expiry:** the job compares against the Raipur date.
- **Renewal:** only after expiry; identical content hash. A finished review carries over with its adjustments.
- **At selection:** SELECTED, NOT_SELECTED.

Rows and lines refuse changes in the database (tested).

## H. Clarifications

Contractors ask about the pack. Operations answer, optionally shared with every accepted invitation without identity. Operations ask a contractor (the quote's review goes to NEEDS_CLARIFICATION until answered or closed). The contractor answers. Questions can be closed with a reason. A clarification never changes the RFQ or a quote.

## I. Review and adjustments

Operations replace the adjustment list while the review is open, then mark it REVIEWED. Adjustments name a quantity line or specification line, a deviation type, a rupee impact and a basis. After REVIEWED they are frozen in the service and by trigger. Contractors never receive them.

## J. Comparison

Publishing:
- Snapshots every current SUBMITTED and REVIEWED version: quotes as submitted, adjustments, totals (as submitted, adjustments, same scope), the RFQ's lines, counts (invited, received, compared) and neutral notes.
- Orders the quotes from a stored random seed.
- Hashes the snapshot.
- Renders and stores the PDF.
- Supersedes the previous version.

A later quote version makes the published one stale for selection; a new comparison version is needed. Nothing ranks, scores or recommends.

## K. Selection

Code request: the guards, the ACTIVE statement filled in for the quote, the code sent.

Selection:
1. Lock the RFQ, then the category (engagements' lock order).
2. Check the statement version and verify the code.
3. Create or reuse the engagement.
4. Write the selection row.
5. SELECTED and NOT_SELECTED.
6. Comparison DECIDED, RFQ CLOSED.
7. Contractor notices, clean-up, RFQ_SELECTION usage, family and operations notices.

Immutable: a second attempt is refused.

## L. Engagement and billing integration

- **New engagement:** origin RFQ_SELECTION with the contacts exchanged at selection (N-08 after acceptance); the family's open contractor connections withdrawn (ANOTHER_ENGAGED).
- **Existing engagement with the same party:** reused, with a history row (an outside contractor's capture path; a listed engaged contractor).
- **Engagement with anyone else:** `ENGAGED`.
- **N-02 under concurrency:** a selection racing a connection acceptance leaves exactly one ACTIVE engagement (tested).
- **Usage:** RFQ_SELECTION only at selection. No usage from invitation, submission, review or publication; Build Plan issue still writes none (tested).

## M. Documents

- **Pack drawings:** logged 15-minute links, only while the contractor's invitation is accepted and the RFQ open, or once selected.
- **Quote attachments:**
  - presigned upload from the professionals host;
  - staff evidence through the raw-body API route;
  - the homeowner may open attachments of compared quotes only.
- **Comparison PDF:** fpdf2 (ADR-023), deterministic for a given snapshot and publication time (tested), stored once per version, for the owner, household and operations.

## N. Notifications

Outbox notices `rfq.family_notice`, `rfq.contractor_notice` (one invitation per event) and `rfq.ops_notice`, with ids only. Twenty plain-text templates; wording is a draft awaiting approval.

| Audience | Notices |
|---|---|
| Homeowner | RFQ issued, comparison published, selection confirmed, RFQ cancelled by operations or the system |
| Contractor | Invitation, RFQ closed or withdrawn, deadline extended, question, answer, shared answer, quote captured, quote expired, selected, not selected |
| Operations | Quotes requested, quote submitted, quote withdrawn, clarification, deadline reached (once), selection confirmed |

No reminders.

## O. Security

- **Own invitation only:** every contractor route is keyed by the contractor's own invitation (404 otherwise, including PROPOSED ones).
- **Separate response models:** one per audience. The pack model forbids extra keys, and a test scans every contractor response for rates, totals, adjustments, reviews and comparison keys.
- **Hidden before publication:** the homeowner sees no prices until a comparison is published.
- **Access checks:**
  - foreign projects 404;
  - household reads only;
  - staff routes need OPS or ADMIN with MFA;
  - ADMIN only for statements.
- **Request handling:**
  - `Idempotency-Key` on transitions;
  - row locks on the RFQ and the category;
  - session rate limits on quotes, questions and uploads.
- **Audit and immutability:**
  - audit rows equal history rows for every transition (tested);
  - database triggers on immutable records.
- **Money:** no construction money and no contract value anywhere.

## P. UI

Functional only, no visual work:
- **Homeowner:** "Contractor quotes" (search listed contractors by name, nominate, status, comparison, PDF, selection with code).
- **Contractor:** "Requests to quote" list and detail (brief, accept or decline, pack, drawings, quote form, versions, withdraw, renew, questions), and the engagement page.
- **Operations:** "RFQs" list with selection statements, and the RFQ detail (deadline, issue, introduce, withdraw, capture with upload, adjustments, reviewed, publish, questions, history).

## Q. Tests

| Check | Result |
|---|---|
| API (pytest), full suite | 499 passed (484 earlier plus 15 in `tests/test_rfq.py`; helpers in `tests/rfq_support.py`; the `rfq_worker` fixture in `conftest.py`). One ResourceWarning at teardown (an unclosed connection after the concurrent test), no failure |
| Coverage of `p2b.rfq` (branch) | 85% |
| Lint, format, types | `ruff check` and `ruff format` clean on `src` and `tests`; `mypy src` clean (182 files) |
| Import linter | 4 contracts kept, 0 broken |
| Migration | Section D |
| Web | `tsc --noEmit` and `eslint .` clean; production build succeeds |
| Playwright on the production build, phone and desktop, axe on every screen | 60 passed in batches with rate limits reset between them: 34 (hosts, sign-in, requirement, designs) + 4 (professionals) + 8 (operations) + 6 (billing, one worker) + 4 (engagements) + 2 (Build Plan) + 2 (`rfq.spec.ts`, new) |

Two batching notes, neither a code defect:
- A first attempt that grouped more specs into one batch hit the OTP rate limit per address (20 per 10 minutes): 7 sign-in waits timed out. Smaller batches passed.
- The billing spec pauses the shared worker container. Its phone and desktop runs raced on that pause, so the spec ran with one worker.

The 3.6 tests named in the instruction, and where they are:

| Requirement | Test |
|---|---|
| RFQ baseline requires the ACCEPTED Build Plan; manifest frozen at issue; baseline supersession | `test_an_rfq_needs_the_accepted_build_plan_and_names_it`, `test_accepted_build_plan_to_selection_with_competing_quotes`, `test_a_newer_accepted_build_plan_cancels_the_open_rfq` |
| Competing invitations, max 3, eligibility, engaged category | `test_recipients_limit_eligibility_and_the_engaged_category` |
| Invitation expiry, decline reasons | `test_invitations_expire_and_declines_need_a_reason` |
| Contractor isolation, no internal rates, no competitor inference, adjustment privacy | `test_accepted_build_plan_to_selection_with_competing_quotes` (key and value scans), `test_clarifications_review_states_and_adjustment_privacy`, `test_isolation_document_access_audit_and_transition_tables` |
| Line completeness, server amounts, version immutability, withdrawal, validity, expiry, renewal, late refusal | `test_accepted_build_plan_to_selection_with_competing_quotes`, `test_quote_versions_are_immutable_withdrawable_and_expire_into_renewal` |
| Clarification isolation, review states | `test_clarifications_review_states_and_adjustment_privacy` |
| Neutral order, no price ranking, no recommendation, versions, deterministic PDF, one-quote comparison | `test_the_comparison_is_neutral_versioned_and_its_pdf_deterministic`, the whole-path test |
| One-time code, statement versioning | `test_selection_needs_the_code_and_the_current_statement` |
| Engagement creation and reuse, RFQ_SELECTION billing trigger | the whole-path test, `test_the_familys_outside_contractor_quotes_through_staff_capture` |
| N-02 concurrency | `test_n02_holds_when_a_selection_races_a_connection_acceptance` |
| Package cancellation, no usage before selection | `test_a_refund_cancels_the_open_rfq_and_keeps_its_history` |
| Suspension and listing loss | `test_a_contractor_leaving_listed_loses_invitations_and_cannot_be_selected` |
| Losing-contractor notification | the whole-path test (email checked for no winner and no price), `test_rfq_notices_map_to_their_emails` |
| Outside-contractor staff capture | `test_the_familys_outside_contractor_quotes_through_staff_capture` |
| Document authorization, audit trail, invalid transitions, historical immutability, foreign isolation | `test_isolation_document_access_audit_and_transition_tables`, the immutability test |

## R. Production blockers

| Blocker | Why |
|---|---|
| Final client and legal confirmation of the selection statement (v1 is functional wording) | Production selection (QD-12) |
| Approval of the twenty RFQ email texts | Production notifications |
| Listed, verified CONTRACTOR professionals in Raipur | Invitations |
| The 3.5 production items: Raipur production rate card, appointed checker, approved sign-off and acceptance wording, available structural engineer, production Unicode PDF font (also used by the comparison PDF), client confirmation of English-only documents, BP-07A, H-01 | An ACCEPTED production Build Plan is the RFQ baseline |
| Client confirmation that contractor screens may be English only (PBR-040 asks for Hindi on the quote form) | BR-057, ADR-022 |

## S. Known hardening gaps

| ID | Gap |
|---|---|
| H-01 | Engineer sign-off notification (3.5), unchanged |
| H-02 | A household member cannot open quote-holder review files (3.4), unchanged |
| H-04 | The contractor's drawing link re-reads the whole invitation view to authorise; correct, but heavier than needed |
| H-05 | Homeowner nomination searches the public directory by name; the directory has no plot-coverage filter, so an out-of-area pick is refused at request (`OUTSIDE_AREA`) rather than hidden |
| H-06 | Operations screens use JSON editors (deadline, introductions, capture, adjustments, questions), as in 3.5 |

## T. Final verdict

Every Slice 3.6 item in SLICE3_6_READINESS v1.1 section 0 is built and tested. The required checks pass:
- API suite (499) and coverage;
- lint, types and import contracts;
- migration cycles and `alembic check`;
- web type-check, lint and production build;
- Playwright on phone and desktop with axe (60).

Production readiness is a separate matter (section R): the selection statement and email wording, real listed contractors and the 3.5 production items.

SLICE 3.6 IMPLEMENTATION = COMPLETE
