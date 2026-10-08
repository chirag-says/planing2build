# Plan2Build: Slice 3.7 implementation report (execution, assurance, handover, Build Record)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/SLICE3_7_IMPLEMENTATION_REPORT.md` |
| Date | 2026-10-06 |
| Rules | `SLICE3_7_READINESS.md` v1.1, section 0 (EX-01 to EX-24, H-07 first, three checkpoints) |
| Status | SLICE 3.7 IMPLEMENTATION = COMPLETE (section P); production readiness depends on section N |

## A. Scope

Built in three checkpoints, each green before the next started:

- **H-07** first: the recorded file hash is the hash of the final stored bytes.
- **3.7A execution:**
  - progress updates in the standard format with scanned photos;
  - completion request, owner confirm or return, operations confirm or return with a reason;
  - informational payment marks;
  - the contractor's execution page with the accepted drawings;
  - contractor transition with history;
  - operations entry for an outside contractor;
  - the completion-request exception.
- **3.7B assurance:**
  - auditor appointments;
  - versioned gate checklists (version 1 seeded from S04);
  - one inspection per gate stage instance;
  - readiness, results with findings, submission with a one-time code;
  - staff capture from a signed report;
  - approval with an fpdf2 report, return for amendment, cancellation;
  - findings with severity, rectification, re-inspection and closure;
  - report corrections as new versions, later test results;
  - the operations queue with thresholds, package gating and package-end cancellation.
- **3.7C handover and Build Record:**
  - the handover with documents and warranties;
  - the owner's acknowledgement with a code against a versioned statement;
  - the operations issue without acknowledgement;
  - the Build Record assembled from the records, issued with a snapshot hash, a deterministic PDF and a JSON export, versioned and immutable.
- Notifications, minimal functional screens on the three hosts, API and browser tests, and the documentation corrections (H-10).

Not built, by decision:
- Variations, specification choices, the issue log, disputes and change orders (EX-24).
- Capped remedy (EX-13).
- Offline inspection (EX-10).
- Behind-plan, delay attribution, planned dates and percentages (EX-04, BP-07A).
- Payment amounts or a settled state (EX-05).
- Share links and record transfer (EX-17).
- Reminders and digests (EX-12, EX-20).

## B. Decisions implemented

| ID | Implemented as |
|---|---|
| EX-01 | No project status moves. Stage instances carry execution; inspections, handovers and Build Records are their own records |
| EX-02 | `stage_updates`: stage, kind (PROGRESS, COMPLETION_REQUEST), note, 1 to 10 scanned photos (configurable), optional materials and open problems, the engagement it was made under. No percentage field anywhere (key scans in tests). Operations enter updates only for an OUTSIDE contractor, with how they received them |
| EX-03 | The owner confirms or returns with a reason; operations confirm or return with a recorded reason; a gate stage's confirmation is refused (GATE_NOT_CLEARED) until its gate is CLEARED; nothing completes automatically. `version` on the stage refuses stale decisions (STALE) |
| EX-04 | CHECK `dates_not_calculated_bp07a` keeps planned dates NULL; no ordering guard; no behind-plan or delay calculation |
| EX-05 | `payment_marks` (module `money`): append-only YES or NO per payment-milestone stage, PAID by the owner, RECEIVED by the contractor or by operations for an OUTSIDE contractor. No amount column, no settled state, never read to allow or refuse anything |
| EX-06 | Inspections are scheduled for listed or outside contractors alike |
| EX-07 | Partial UNIQUE index: one live INITIAL inspection per stage instance; each per-floor slab and floor instance has its own |
| EX-08 | Version 1 seeded PUBLISHED from S04 "verified at" for Gates 1 to 5 (6, 3, 3, 13, 2 checkpoints, with the named test as expected evidence); operations draft new versions, ADMIN publishes; inspections keep their version |
| EX-09 | ADMIN appoints auditors with a unique ID (AUD-nnnnn), qualification, registration reference, optional credential file and optional professionals-host account; submission with a SUBMIT_INSPECTION code; without an account, operations capture from the signed report |
| EX-10 | Online screens only |
| EX-11 | Severity MINOR, MAJOR, CRITICAL; finding text set once; a finding closes only when an approved re-inspection records PASS for it (CHECK: closed only with the closing inspection); a failed re-inspection keeps it OPEN |
| EX-12 | `completion_request_exception_days` = 3 and `inspection_open_exception_days` = 7 (configuration, [PD NEW]); calendar days in Raipur; operations queue flags only |
| EX-13 | Not built |
| EX-14 | Plain-language report with a technical appendix, fpdf2, rendered at approval from the frozen content, deterministic; a correction is a new report version with its reason |
| EX-15 | Handover opens only with Gate 6 CLEARED and no finding open on the project; READY needs documents and a warranty entry for each warranty document; the owner acknowledges with ACKNOWLEDGE_HANDOVER against the ACTIVE statement; operations may issue without acknowledgement with a reason, which a CHECK keeps apart from any acknowledgement field |
| EX-16 | No specification lifecycle; the Build Record shows inspection results per line; product, purchase and installation are NOT RECORDED |
| EX-17 | OWNER and HOUSEHOLD read; PDF and JSON behind logged links; no share link or transfer; a correction is a new version with a reason, the earlier version SUPERSEDED and readable |
| EX-18 | Package required to schedule and approve inspections and to issue the Build Record. Everything else is free. When the package ends, SCHEDULED inspections are cancelled (PACKAGE_ENDED); in-progress and submitted ones stay but cannot be approved |
| EX-19 | Every update records its engagement; a different engagement posting on a stage writes a CONTRACTOR history event; an ended engagement loses access; the next contractor continues the same stages |
| EX-20 | Notifications as in section J; no reminders, digests or countdowns |
| EX-21 | Household members read everything the owner reads and act on nothing (403) |
| EX-22 | Images are re-encoded (metadata stripped); `file_objects.capture_claim` holds the device's capture time and location claims; the hash is of the stored bytes (H-07) |
| EX-23 | A finding past its due date is an operations queue exception only |
| EX-24 | Not built |

## C. H-07 correction

- **Defect:** the image pipeline hashed the uploaded bytes and then stored re-encoded bytes, so `file_objects.sha256` did not match the stored object.
- **Fix:** `documents/service.py process_file` sets `sha256` from the final stored content (the re-encoded image), and from the stored bytes in the quarantine branch.
- **Test:** `test_the_recorded_hash_is_of_the_final_stored_bytes` uploads an image, lets processing re-encode it, reads the stored object back and checks the recorded hash and size against it.
- **Documentation:** INTEGRATION_ARCHITECTURE (images row), SECURITY_ARCHITECTURE (malicious uploads row) and DATA_ARCHITECTURE section 4 (objects and capture claims).

## D. 3.7A execution

- **Module `construction`:**
  - `execution.py` holds the transitions: start on the first update, request, confirm, return.
  - `router.py` serves the homeowner and contractor routes; `ops_router.py` the operations routes.
  - Transitions go through `STAGE` TransitionTable entries.
- **Guards and history:**
  - Row locks on the stage for every decision.
  - Every transition writes a `construction_events` row and an audit row.
- **Contractor:**
  - Reaches only its ACTIVE CONTRACTOR engagement and sees only its own updates.
  - Its execution page lists the accepted Build Plan's drawings with logged links.
- **Module `money`:** payment marks (EX-05) with routes on all three hosts. An advisory lock serialises marks per stage and side, so a repeated mark is refused as UNCHANGED.
- **Operations queue:** completion requests oldest first, flagged after 3 calendar days (EX-12).

## E. 3.7B assurance

- **Module `assurance`:**
  - `appointments`, `checklists`, `inspections`, `ncs`, `pdf`, `views`;
  - `router.py` for the homeowner, contractor and auditor; `ops_router.py` for operations and ADMIN; `handlers.py` for package end and project cancel.
- **Gate status:** derived from the records only (`refresh_gate`) and written through `construction.interface.set_gate_status`, which records a GATE history event:
  - findings not closed → OPEN_NC;
  - an approved initial inspection → CLEARED;
  - a live inspection → SCHEDULED;
  - otherwise NOT_INSPECTED.
- **Submission:**
  - Freezes the content and stores `content_sha256` over every checkpoint result and the evidence hashes.
  - Approval recomputes the hash and refuses CONTENT_CHANGED.
  - The trigger `p2b_inspection_frozen` keeps the content columns fixed from SUBMITTED.
- **Findings:** open at approval with the contractor of record; rectification evidence is the contractor's own scanned photos; operations can send a rectification back or move a due date, each with a reason.
- **Auditor view:** checklist criteria from the issued specification; the accepted value only for lines without a brand category; drawings; no supplier, brand, product, price or homeowner contact (a key-scan test).
- **Correction found:** S04 maps C24 External works to Gate 6. The readiness said no line maps to Gate 6. Version 1 follows EX-08 (Gates 1 to 5) and names C24 in its note as a sourced input for the Gate 6 draft. The readiness carries a correction note.

## F. 3.7C handover

- **Module `records`:** `service.py` (handover and Build Record), `pdf.py`, `views.py`, `router.py`, `ops_router.py`.
- **Handover flow:**
  - The handover opens with Gate 6 cleared and no open finding (GATE6_NOT_CLEARED, OPEN_FINDINGS).
  - The contractor (presigned upload) or operations (raw upload) record documents; warranties carry item, term, expiry and installer.
  - Operations confirm READY or reopen it with a reason.
  - The owner requests a code, reads the filled-in statement, and acknowledges. The challenge, statement version and filled text are stored.
  - Operations may instead issue without acknowledgement, with a reason; the homeowner sees it labelled as such.
- **Statement:** version 1 is functional wording, IMPLEMENTED / PENDING FINAL CLIENT + LEGAL CONFIRMATION. It says the acknowledgement is not a completion certificate or an approval of quality. ADMIN can draft and activate new versions.

## G. Build Record

- **Assembly:** automatic, at acknowledgement or operations issue (DRAFT). Operations can re-assemble a DRAFT; after an issued version, a new DRAFT needs a correction reason.
- **Snapshot (schema version 1):**
  - identity and plan: version, hash, accepted time;
  - drawings with hashes;
  - the 67 specification lines with accepted value, gate verification results, and NOT RECORDED for product, purchase and installation;
  - contractor history, with "chosen by the family" for an outside party;
  - execution per stage instance (actual dates, update counts);
  - approved inspections with auditor ID, outcome and report hashes, and findings with closure;
  - payment marks (YES or NO with times);
  - handover documents with hashes, warranties, and the acknowledgement or the operations issue.
- **Excluded:** no quote price, amount or contract value (key-scan test).
- **Issue:**
  - Requires the package.
  - Stores the snapshot sha256, a deterministic fpdf2 PDF (creation date = issue time) and a canonical JSON export with the same snapshot and hash.
  - The previous ISSUED version becomes SUPERSEDED.
  - The trigger `p2b_records_frozen` keeps issued and superseded versions unchanged.
- **Access:** OWNER and HOUSEHOLD only. The contractor and other families get nothing.

## H. Documents and PDF

| Purpose | Producer | Notes |
|---|---|---|
| STAGE_EVIDENCE | Contractor (presigned) or operations (raw body) | Images only; capture claims; also used for rectification evidence |
| INSPECTION_EVIDENCE | Auditor (presigned) or operations (raw body) | Images and PDF (the signed report for staff capture) |
| INSPECTION_REPORT | Server at approval | fpdf2; versions on correction |
| HANDOVER_DOCUMENT | Contractor or operations | PDF, JPG, PNG; up to 20 MB |
| BUILD_RECORD_DOCUMENT, BUILD_RECORD_EXPORT | Server at issue | PDF and JSON |

Every file is project-scoped, scanned before use, served through logged links, and never overwritten. The production Unicode font remains a 3.5 blocker (section N).

## I. Permissions and security

- **Project boundary:** membership join; another project's ids return 404 (sweeps in each test module).
- **Roles:**
  - Owner acts; household reads (403 on every write).
  - Contractor: only its ACTIVE CONTRACTOR engagement.
  - Auditor: only its active appointment's inspections.
  - Operations and ADMIN: MFA. ADMIN alone appoints, publishes checklists and activates statements.
- **Write guards:**
  - `Idempotency-Key` on transitions; `version` on stage decisions.
  - Row locks on stage, inspection, finding, handover and Build Record transitions.
  - Concurrency tests (two decisions, three marks, two approvals, two issues) each have exactly one winner.
- **Database guards:** lifecycle-column triggers, append-only triggers, child-editable triggers, freeze triggers, and the CHECKs listed in DATA 4.21 to 4.23.
- **Money:** the import-linter forbids billing from importing `money`, `construction`, `assurance` or `records`. Schema and key scans show no amount column or field.
- **Audit:** each transition writes a history row and an audit row; tests compare their counts.

## J. Notifications

| Audience | Sent on |
|---|---|
| Homeowner | Completion requested; payment milestone due (no amount); inspection scheduled or cancelled; inspection report ready; handover opened; handover ready; Build Record issued |
| Contractor (listed) | Completion confirmed or returned; payment marked paid; inspection scheduled; re-inspection scheduled; findings to correct; corrections confirmed; gate cleared; handover opened; handover acknowledged |
| Auditor (with an account) | Inspection assigned, returned, cancelled |
| Operations mailbox | Gate stage completion requested; inspection submitted; rectification submitted; handover acknowledged; Build Record draft assembled |

- Outbox payloads carry ids only (tested).
- No email contains a finding's text or an amount (tested).
- Wording is a draft awaiting approval.

## K. UI

Minimal functional screens, axe-clean on phone and desktop:

- **Homeowner:** the construction page now shows stages with states, actual dates, gate status and update counts. It also offers:
  - confirm and return;
  - the stage updates page with photos;
  - payment marks;
  - inspections with outcomes and report downloads, and findings;
  - the handover with documents, warranties and code acknowledgement;
  - Build Record versions with PDF and data file.
- **Contractor:** the execution page from the engagement, with:
  - drawings and the update form (photo upload with scan wait);
  - received marks;
  - findings with the correction form;
  - the handover document and warranty forms.
- **Auditor:** `/inspections` and the inspection page (readiness, results with findings and photos, submission with a code).
- **Operations:**
  - `/execution` (queue and project);
  - `/assurance` (queue, project page with approve, return, cancel, capture, report correction and finding actions);
  - `/assurance/config` (appointments, checklists);
  - `/handover/{project}` (handover and Build Record).
  - JSON editors where acceptable (H-06).

## L. Database and migrations

| Migration | Content |
|---|---|
| 0016_execution | `stage_updates`, `construction_events`, `payment_marks`; `stage_instances` lifecycle guard (H-09 closed) and BP-07A CHECK; `completion_requested_at`; STAGE_EVIDENCE; `capture_claim` |
| 0017_assurance | Appointments with `auditor_code_seq`, checklists with version 1 seed, inspections, results, findings, reports, test results, history; triggers; INSPECTION_* purposes; SUBMIT_INSPECTION; GATE history subject |
| 0018_records | Statements with version 1 seed, handovers, documents, warranties, Build Records, history; triggers; HANDOVER_DOCUMENT and BUILD_RECORD_* purposes; ACKNOWLEDGE_HANDOVER |

- Each migration was run upgrade, downgrade, upgrade twice on a test database, and `alembic check` reported no drift.
- Downgrades remove the feature's data, files and codes, lifting append-only guards only for those deletes.
- The dev database is at 0018.

## M. Tests

### M.1 Results (final run, 2026-10-06)

| Check | Result |
|---|---|
| API suite (pytest, full) | 533 passed (499 before 3.7; new: H-07 1, execution 15, assurance 12, records 6) |
| Coverage of the 3.7 modules (`construction`, `money`, `assurance`, `records`) | 89% lines and branches combined (3,548 statements) |
| Migrations 0016, 0017, 0018 | Each upgrade, downgrade, upgrade twice; `alembic check`: no drift; test and dev databases at 0018 |
| ruff format and check, mypy strict (src and tests), import-linter | Clean; 4 contracts kept |
| Web: TypeScript, ESLint, production build | Clean |
| Playwright on the production build, phone and desktop, axe on every screen | 66 passed: hosts 18, sign-in 6, requirement 8, designs 2, ops 8, professionals 4, engagements 4, build plan 2, RFQ 2, billing 6, execution 2, assurance 2, records 2 (each spec run alone; larger batches hit sign-in rate limits, as in 3.6) |

Each checkpoint was green before the next started:
- **3.7A:** API 516, Playwright 62.
- **3.7B:** API 527, Playwright 64. One vocabulary-against-database check failed only because of the next checkpoint's added confirmation purpose; it passed with that value held back.
- **3.7C:** the final run above.

### M.2 Required tests and where they are

| Requirement | Test |
|---|---|
| H-07 final-byte hashing | `test_documents::test_the_recorded_hash_is_of_the_final_stored_bytes` |
| Execution permissions, unauthorized isolation | `test_execution::test_only_the_engaged_contractor_reaches_the_project`, `test_an_update_needs_its_own_scanned_photos_on_the_project`; assurance and records sweeps |
| Stage completion, owner return, operations confirmation | `test_execution::test_the_contractor_reports_and_the_owner_confirms`, `test_the_owner_returns_with_a_reason_and_the_household_only_reads`, `test_operations_confirm_with_a_reason_and_a_gate_waits_for_clearance` |
| No percentage, no dates | `test_execution::test_no_dates_no_percentages_and_the_record_is_append_only` (key scans, a refused field, BP-07A CHECK) |
| Payment mark non-blocking, no amount | `test_execution::test_payment_marks_inform_and_never_block` |
| Contractor transition | `test_execution::test_a_new_contractor_continues_and_history_stays_with_the_old` |
| Operations entry for an outside contractor, execution free of the package | `test_execution::test_operations_enter_only_for_an_outside_contractor_and_need_no_package` |
| Completion-request threshold | `test_execution::test_an_unanswered_request_becomes_an_operations_exception` |
| Auditor appointment and permissions | `test_assurance::test_admin_appoints_and_ends_auditors`, `test_return_amendment_cancel_and_isolation` (another auditor, the contractor), auditor key scan |
| One inspection per gate stage instance | `test_assurance::test_one_inspection_per_gate_stage_instance` |
| Checklist versioning | `test_assurance::test_version_1_holds_gates_1_to_5_from_the_s04_mapping`, `test_checklists_are_versioned_and_published_by_admin` |
| Inspection immutability, defect severity, re-inspection-only closure | `test_assurance::test_an_inspection_opens_findings_and_only_a_reinspection_closes_them` |
| Staff capture | `test_assurance::test_operations_capture_a_signed_report_for_an_auditor_without_an_account` |
| Assurance package gating and package cancellation | `test_assurance::test_the_package_gates_scheduling_and_approval_and_its_end_cancels`; `test_records::test_issuing_needs_the_package_and_acknowledging_does_not` |
| Thresholds and overdue findings | `test_assurance::test_thresholds_make_operations_exceptions_only` |
| PDF determinism, report versions, test results | `test_assurance::test_reports_are_deterministic_and_corrections_are_new_versions`; `test_records::test_the_build_record_is_issued_versioned_and_immutable` |
| Handover conditions | `test_records::test_the_handover_waits_for_gate_6_and_closed_findings` |
| OTP acknowledgement, household read-only | `test_records::test_documents_warranties_and_the_owners_acknowledgement` |
| Operations forced handover | `test_records::test_an_operations_issue_is_never_an_acknowledgement` |
| Build Record immutability, versioning, JSON/PDF consistency, document authorization, historical access | `test_records::test_the_build_record_is_issued_versioned_and_immutable` |
| Concurrent transitions | `test_execution::test_concurrent_decisions_and_marks_have_one_winner`, `test_assurance::test_concurrent_approvals_have_one_winner`, `test_records::test_concurrent_issues_have_one_winner` |
| Audit history | Event-row and audit-row counts compared in execution and assurance tests |
| Notifications | Mapping tests per module; mailbox subjects in the flow tests; ids-only outbox payloads |
| Browser flows | `e2e/execution.spec.ts`, `e2e/assurance.spec.ts`, `e2e/records.spec.ts` |
| Previous suites | All earlier API tests and browser specs, unchanged except: `ops.spec` (the construction page now shows execution, no schedule column) and shared helpers moved into `e2e/support.ts` |

### M.3 Defects found and fixed during the slice

| Defect | Fix |
|---|---|
| Ending an auditor appointment autoflushed half-updated columns into a CHECK | Read the time before changing the row |
| `checklist_versions` referenced `users`, so test cleanup (`TRUNCATE users CASCADE`) emptied the seeded checklist | Plain user ids, as for other reference data |
| The assurance interface lacked two imports in a path no 3.7B test reached | Imports added; exercised by the 3.7C tests |
| The handover upload sent a capture claim its schema rejects | Capture claims only for photos |
| The browser retry for scanned files ignored `file_id` errors | Retries on `file_ids` and `file_id` |
| The warranty form fixed its warranty document at first render, before the document existed | The document is chosen at submission |
| axe measured a button mid-transition | The axe helper waits for running animations |


## N. Production blockers

- Approved gate checklist content, including Gate 6 (EX-08); C24 is the one sourced Gate 6 line.
- At least one appointed independent auditor (EX-09, CQ-15: person or firm).
- Approved wording:
  - the acknowledgement statement v1 (pending final client and legal confirmation);
  - the inspection report text;
  - every new email template.
- Client answers CQ-11 (update format) and CQ-13 (marks).
- The 3.6 items: selection statement approval, RFQ email approvals, real listed Raipur contractors, English-only contractor screens, H-04, H-05, H-06.
- The 3.5 items:
  - Raipur production rate card;
  - appointed drawing checker;
  - approved sign-off and acceptance wording;
  - an available structural engineer;
  - a production Unicode PDF font (now also for inspection reports and the Build Record);
  - English-only documents;
  - BP-07A;
  - H-01.
- `P2B_OPS_NOTIFICATION_EMAIL` must be configured or operations notices are skipped (by design, logged).

## O. Hardening gaps

| ID | Gap |
|---|---|
| H-02, H-04, H-05, H-06 | Unchanged from 3.5 and 3.6 |
| H-08 | `spec_line_events` still append-only by grant only; 3.7 did not touch lines (EX-16) |
| H-11 (new) | The completion-request and inspection-open exceptions are computed when the queue is read; there is no stored exception or alert beyond the queue (by EX-12 design; revisit if operations want history of exceptions) |
| H-12 (new) | The contractor and auditor upload screens wait for the virus scan by retrying the post for about 30 seconds; a slower scan shows an error and the user retries |
| H-13 (new) | Operations screens for capture, re-inspection, checklists, appointments and warranties are JSON editors (H-06 pattern) |
| H-14 (new) | The Build Record's identity section has no owner name: the account has no reliable legal name field, so it is not recorded rather than guessed |

## P. Final verdict

All three checkpoints passed (sections D to G, M). The decisions EX-01 to EX-24 are implemented as section B describes; H-07 is fixed with a test; H-09 is closed; H-10 is corrected in the architecture documents with marked notes.

Production readiness is a separate question: the blockers in section N stand (approved checklist content including Gate 6, an appointed auditor, approved wording for the acknowledgement statement, reports and emails, and the open 3.5 and 3.6 items).

SLICE 3.7 IMPLEMENTATION = COMPLETE
