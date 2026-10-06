# Plan2Build: state model

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/01_ARCHITECTURE/STATE_MODEL.md` |
| Version | 0.2 (2026-10-04: registration timing, OTP challenge machine; earlier text 0.1 proposed) |
| Date | 2026-10-03 |
| Status | Architecture proposal for Chirag's review. This is the canonical technical state vocabulary. |
| Business authority | `IHB_FLOW.md` v1.2 sections 9, 10, 33.3 (SM-01 to SM-24, DT-05, DT-10, DT-11 revised); `PROFESSIONALS_FLOW.md` v1.2 sections 9, 13.3, 20, 21, 25, 26, 44.7, 44.8 (PSM-01 to PSM-32); `RECOMMENDATION_ENGINE.md` sections 3 and 9; client decisions CD-08, CD-09, CD-10, CD-17, CD-26, CD-27 |
| Related | DOMAIN_ARCHITECTURE.md, DATA_ARCHITECTURE.md, API_ARCHITECTURE.md, TESTING_ARCHITECTURE.md |

## 1. Rules that apply to every machine

1. State names are stable, machine-readable, upper snake case, stored as `text` columns with a CHECK constraint generated from this document; the UI shows labels from message files (S01 App B). Postgres enums are not used, because adding a value to an enum is harder to migrate than updating a CHECK constraint.
2. Every transition is a row in a transition table in code (`from`, `to`, `trigger`, `allowed_roles`, `preconditions`, `side_effects`), checked in the service layer before any write. A disallowed transition returns HTTP 409 with the code `STATE_CONFLICT` and the current state. The table is the single place where a state can change; routers never set states.
3. Every transition writes one `audit_events` row in the same transaction (actor, old state, new state, reason where given). Entities with a ledger (specification lines, variations, inspections, issues, leads) also append an event row to their own event table.
4. Overrides: operations may force a transition that the table marks `override_allowed` only with a reason; the audit row carries `override = true` (S01 §17.1, S06 §16.1). Transitions marked `never` cannot be forced by anyone.
5. Terminal states are never deleted. Important records are soft-deleted by status, never hard-deleted (S01 §17.1).
6. Record versions: every stateful row carries `version` (integer); a write that supplies a stale version fails with 409 `VERSION_CONFLICT` (S06 §8.1).
7. Scheduled transitions (expiry, escalation, due dates) run in the worker on a schedule and are idempotent: the job checks the current state before acting.
8. Where the sources leave state names open (OQ-029), this document adopts the D1 names when they fit and marks the choice `[canonical]`; where a client decision changed the machine, the decision is cited.
9. Retry behaviour: a failed side effect (notification, render, metric) never rolls back a committed transition; it retries from the outbox. A failed precondition never produces a half-transition.

## 2. User account (identity)

Sources: SM-01, PSM-01 (D1 PENDING_EMAIL renamed because the MVP verifies by email OTP or, later, SMS OTP: CD-24, Chirag 2026-10-03).

| State | Meaning |
|---|---|
| PENDING_VERIFICATION | Account created, contact not yet verified |
| ACTIVE | Normal account |
| SUSPENDED | Access restricted by policy or operations; records preserved |
| CLOSED | No longer operational; records retained per retention policy |

| From | To | Trigger | Actor | Preconditions | Side effects | Notification | Audit |
|---|---|---|---|---|---|---|---|
| (new) | PENDING_VERIFICATION | Register | User, or operations on behalf (CD-07) | Contact unique per audience. Self-registration: the contact's OTP has just been verified, and this row and the next happen in one transaction (B-03, Chirag 2026-10-04). Operations-created accounts (CD-07) wait here until the person verifies | None for self-registration (the OTP was the verification) | None | Yes |
| PENDING_VERIFICATION | ACTIVE | OTP verified | User | Valid, unexpired OTP; attempts under limit | Session created; consent recorded | Welcome | Yes |
| ACTIVE | SUSPENDED | Policy or operational action | Admin | Reason required | All sessions revoked; sensitive actions blocked | Security notice | Yes |
| SUSPENDED | ACTIVE | Reinstate | Admin | Investigation complete | None | Notice | Yes |
| SUSPENDED | CLOSED | Close | Admin | Reason | Memberships marked inactive; data retained | Notice | Yes |
| ACTIVE | CLOSED | Owner-initiated closure | User | Open obligations handled (policy open, J25 [U]) | As above | Notice | Yes |

Related machines: Session `ACTIVE → EXPIRED | REVOKED`; OTP challenge `ISSUED → VERIFIED | EXPIRED | LOCKED` (LOCKED after the configured number of wrong codes, DT-13; EXPIRED when its validity passes or when a newer challenge for the same contact, audience and purpose replaces it; VERIFIED, EXPIRED and LOCKED are terminal, so a code can never be used twice); MFA enrolment `PENDING → ENROLLED → DISABLED`.

## 3. Professional verification case (professionals)

One case per professional and category; a second case type with scope `PROJECT_ONLY` carries the basic verification of the family's own contractor (CD-27). Sources: PSM-02, PSM-03, PSM-04, 9.2 and 9.5 (PA-008 to PA-019), PC-010 reconciled by adopting the S02 names.

| State | Meaning |
|---|---|
| DRAFT | Profile and evidence being prepared |
| SUBMITTED | Evidence checklist complete, awaiting review |
| UNDER_REVIEW | Operations reviewing; reference calls and site visit recorded here |
| CHANGES_REQUESTED | Operations asked for corrections; reviewer comments preserved |
| VERIFIED | Checks passed for this category and scope |
| REJECTED | Declined; reapplication per policy (default: after six months, configuration) |
| SUSPENDED | Credential lost or policy action for this category; other categories unaffected |

| From | To | Trigger | Actor | Preconditions | Side effects | Notification |
|---|---|---|---|---|---|---|
| DRAFT | SUBMITTED | Submit | Professional, or operations on behalf | Required evidence for the category present; evidence locked after submission | Queue item for operations | To professional |
| SUBMITTED | UNDER_REVIEW | Claim | Operations | None | Reference call and site visit records open | None |
| UNDER_REVIEW | CHANGES_REQUESTED | Request changes | Operations | Reason | Evidence unlocked for the listed fields | To professional |
| CHANGES_REQUESTED | UNDER_REVIEW | Resubmit | Professional | Corrected evidence | Comments preserved | None |
| UNDER_REVIEW | VERIFIED | Approve | Operations | Identity, references and site visit recorded; for PROJECT_ONLY scope the project is named | Project-only membership granted, or Club curation may begin | To professional; to homeowner for PROJECT_ONLY |
| UNDER_REVIEW | REJECTED | Reject | Operations | Reason | Reapply date set | To professional |
| VERIFIED | SUSPENDED | Suspend | Admin | Reason | New opportunities and quotes blocked for the category; active projects preserved; parties notified | To professional and affected homeowners |
| SUSPENDED | VERIFIED | Reinstate | Admin | Investigation complete | None | To professional |

A failed PROJECT_ONLY verification is CQ-23: the machine ends in REJECTED and the homeowner is told; what Plan2Build does for the project is not decided.

## 4. Champions Club membership (professionals)

> **Superseded (2026-10-04, PD-18).** Not to be built as a membership machine. A professional has a listing state per category instead: PENDING_REVIEW, CHANGES_REQUESTED, LISTED (shown as Champions Club), SUSPENDED, REJECTED. See `02_IMPLEMENTATION/PRODUCT_FLOW_RECONCILIATION.md` section D.

Source: 44.8 (proposed, CD-27). Separate from verification: a professional is VERIFIED first, then curated.

| State | Meaning |
|---|---|
| APPLIED | Application received |
| IN_CURATION | Gates being checked, scorecard in progress |
| CHANGES_REQUESTED | Gate evidence missing or weak |
| MEMBER | Admitted; class assigned; listed, recommended, sent leads |
| WARNED | Member with an improvement plan; still listed |
| SUSPENDED | Not listed, not recommended, no leads; active projects continue with closer inspection |
| REJECTED | Not admitted; reapply after the configured wait |
| REMOVED | Removed from the Club; records kept |

| From | To | Trigger | Actor | Preconditions | Side effects |
|---|---|---|---|---|---|
| APPLIED | IN_CURATION | Start | Operations | Verification VERIFIED for the category | Scorecard opened |
| IN_CURATION | CHANGES_REQUESTED | Request | Operations | Reason | Applicant notified |
| CHANGES_REQUESTED | IN_CURATION | Resubmit | Professional | Evidence | None |
| IN_CURATION | MEMBER | Admit | Operations | All gates pass; class set from the scorecard; capacity declared | Listing projection updated; `club.admitted`; metrics seeded from the scorecard |
| IN_CURATION | REJECTED | Reject | Operations | Reason | Reapply date |
| MEMBER | WARNED | Warn | Operations (review job proposes) | Review trigger met | Improvement plan recorded |
| WARNED | MEMBER | Clear | Operations | Next review passes | None |
| MEMBER or WARNED | SUSPENDED | Suspend | Operations | Trigger: critical unrectified NC past due, dispute decided against, misrepresentation | Listing removed; open leads withdrawn; engine eligibility fails; active projects flagged for closer inspection |
| SUSPENDED | MEMBER | Reinstate | Operations | Reason | Listing restored |
| SUSPENDED | REMOVED | Remove | Admin | Repeated suspension, fraud or abandonment | Records kept; never listed |
| MEMBER | MEMBER | Class change | Operations | Review evidence | `club.class_changed`; leads outside the new class withdrawn |

Derived listing status: `LISTED` when membership is MEMBER or WARNED, the category verification is VERIFIED, and capacity is not paused; never stored, always computed, so it cannot drift.

## 5. Project (projects)

Sources: SM-04 and PSM-11 (C-018: three D1 versions; D2 has no values), DT-05 revised, 33.1. Canonical names chosen `[canonical]`, handover before completion (S01 order), QUALIFIED renamed ACCEPTED to match J07's wording "project accepted for planning".

| State | Meaning |
|---|---|
| DRAFT | Requirement being captured (J05, J06) |
| SUBMITTED | Requirement submitted, under Plan2Build review (J07) |
| NEEDS_INFO | Plan2Build asked the homeowner for more details |
| ACCEPTED | Accepted for planning; workspace instantiated (J08) |
| PLANNING | Package paid; Build Plan or quote review in progress (J09, J10; CD-04, CD-05) |
| PLAN_ISSUED | Build Plan issued, baseline locked (J10) |
| SOURCING | Contractors being found and quotes compared (J12 to J14) |
| CONTRACTED | Award recorded; contract value set (J15) |
| BUILDING | Construction in progress (J16 to J21) |
| HANDOVER_PENDING | Final snag inspection cleared; retention and record pending (J22) |
| COMPLETED | Build record issued |
| ARCHIVED | Closed for activity; record readable |
| ON_HOLD | Paused by the homeowner or operations with reason (from PLANNING to BUILDING) |
| CANCELLED | Abandoned before completion (refund policy CQ-04) |

| From | To | Trigger | Actor | Preconditions |
|---|---|---|---|---|
| DRAFT | SUBMITTED | Submit | Homeowner | Required fields; project type is new home (CD-03) |
| SUBMITTED | NEEDS_INFO | Ask | Operations | Reason |
| NEEDS_INFO | SUBMITTED | Resubmit | Homeowner | Answers |
| SUBMITTED | ACCEPTED | Accept | Operations | Review done; workspace instantiation succeeds |
| ACCEPTED | PLANNING | Package paid | System (billing event) | First payment captured |
| PLANNING | PLAN_ISSUED | Issue | Operations | Build Plan version issued; baseline locked |
| PLANNING | SOURCING | Quote review published | Operations | CD-04 path; what follows is CQ-02 (default: homeowner may proceed to RFQ) |
| PLAN_ISSUED | SOURCING | Start sourcing | Homeowner or operations | At least one contractor route chosen |
| SOURCING | CONTRACTED | Selection recorded | Homeowner (through rfq) | Selection with contract value |
| CONTRACTED | BUILDING | First stage started | Contractor update or operations | Membership for the contractor exists |
| BUILDING | HANDOVER_PENDING | Final snag cleared | System (assurance event) | Gate 6 cleared |
| HANDOVER_PENDING | COMPLETED | Record issued | System (records event) | Retention milestone settled or waived with reason |
| COMPLETED | ARCHIVED | Archive | Operations or scheduled | None |
| PLANNING to BUILDING | ON_HOLD | Hold | Homeowner or operations | Reason |
| ON_HOLD | previous state | Resume | Same | None |
| DRAFT to BUILDING | CANCELLED | Cancel | Homeowner or operations | Reason; refund handling per CQ-04 |

Invalid: any jump that skips ACCEPTED (the workspace must exist), CONTRACTED without a selection, COMPLETED without a build record. Overrides allowed with reason for ON_HOLD and for moving back one state (operations), never for COMPLETED.

Attributes rather than states: `path` (PLAN_FIRST or QUOTE_REVIEW), `contractor_route` (OWN or CLUB). **Superseded (2026-10-04, PD-17):** no single route per project; service needs and engagements are held per category (`02_IMPLEMENTATION/PRODUCT_FLOW_RECONCILIATION.md`).

> **Superseded as the professional lifecycle (2026-10-05, N-03, confirmed and closed by Chirag).** SOURCING, CONTRACTED and BUILDING do not describe professionals: no transition into them is built, and none replaces them. Professional progress is modelled as service needs, then engagements (section 9a), then the later construction and execution states. N-03 is not open and blocks nothing.

## 6. Stage instance (construction)

Source: SM-05 and PSM-13 (names unknown, OQ-029), 20.2, PC-023 (approval authority open), CD-19. Canonical names `[canonical]`.

| State | Meaning |
|---|---|
| NOT_STARTED | Instantiated with planned dates |
| IN_PROGRESS | Work started (first update or planned start reached) |
| COMPLETION_REQUESTED | Contractor requested completion with evidence (standard update) |
| COMPLETED | Completion accepted; for gate stages the gate is cleared too |
| BLOCKED | An issue or non-conformance blocks progress |
| ON_HOLD | Paused with the project |

| From | To | Trigger | Actor | Preconditions | Side effects |
|---|---|---|---|---|---|
| NOT_STARTED | IN_PROGRESS | Start | Contractor update, or scheduled at planned start | Previous dependent stages at least IN_PROGRESS | Actual start recorded |
| IN_PROGRESS | COMPLETION_REQUESTED | Request completion | Contractor | Update in the standard format with evidence | Homeowner and operations notified; for gate stages the inspection is scheduled |
| COMPLETION_REQUESTED | COMPLETED | Accept | Homeowner (default; operations may accept with reason; PC-023 open) | For gate stages: gate CLEARED | Actual end recorded; `construction.stage_completed`; payment milestone may become DUE |
| COMPLETION_REQUESTED | IN_PROGRESS | Return | Homeowner or operations | Reason (issue raised) | Notified |
| IN_PROGRESS | BLOCKED | Block | System on issue or open critical NC | Reason | Exception feed |
| BLOCKED | IN_PROGRESS | Unblock | System when the blocker closes | None | None |

Gate attribute on gate stages: `gate_status` in `NOT_INSPECTED, SCHEDULED, OPEN_NC, CLEARED` set by assurance events. Planned date changes record `construction.stage_dates_changed` and recompute specification deadlines (S05 P2).

## 7. Specification line (specification)

Source: SM-06, PSM-27, DT-07, S04 §8, S06 §7.1; six states settled in D2. Who records PURCHASED and INSTALLED is POQ-021 (default: contractor records with evidence; operations may record).

| State | Meaning |
|---|---|
| SPECIFIED | Issued criteria on the project instance |
| OPTIONS_ISSUED | 3 to 5 qualifying options presented (never on structural or no-brand lines) |
| CHOSEN | Homeowner chose and acknowledged by OTP; frozen into the baseline |
| PURCHASED | Product bought; evidence attached; switch event if different from the choice |
| INSTALLED | Applied on site; installer and date recorded |
| VERIFIED | Verified at a gate, site log or delivery check |

| From | To | Trigger | Actor | Preconditions | Side effects |
|---|---|---|---|---|---|
| (new) | SPECIFIED | Instantiate | System | Workspace instantiation | Deadline and long-lead flag computed |
| SPECIFIED | OPTIONS_ISSUED | Issue options | Operations | Line has a brand category and is not structural; 3 to 5 options, one value tier, ordered by price | Homeowner notified at lead time |
| OPTIONS_ISSUED | CHOSEN | Choose | Homeowner | OTP valid; option in the issued set | Baseline grows; `specline.chosen`; later changes are variations |
| SPECIFIED | CHOSEN | Confirm | Homeowner or operations | Structural or no-brand line (AMB-020 default: acknowledgement without an option) | As above |
| CHOSEN | PURCHASED | Record purchase | Contractor (default) or operations | Evidence file; product recorded; switch event if it differs | Switch notification to the homeowner |
| PURCHASED | INSTALLED | Record installation | Contractor or operations | Installer, date | None |
| INSTALLED | VERIFIED | Verify | Auditor (gate), operations (site log or delivery check) | Evidence reference | Build record line complete |
| CHOSEN | CHOSEN | Change by variation | Variation activation | ACTIVE variation referencing the line | New choice recorded; previous kept in events |

Invalid: skipping CHOSEN (no purchase without a choice), any transition without an event row, options on a structural line (rejected at the data layer, S05 rule 8). Overrides: operations may move a line back one state with reason; VERIFIED is never undone, a new verification record is added instead.

## 8. Build Plan version and contract baseline (buildplan)

Build Plan version: `DRAFT → IN_REVIEW → ISSUED → SUPERSEDED` plus `WITHDRAWN` (a draft abandoned). Transitions: draft by the advisor; IN_REVIEW when structural sign-off is requested; ISSUED by operations when every structural line in the plan is signed off, the package is paid and the concept design (or an architect's pack) is attached; SUPERSEDED when a later version is issued. ISSUED content never changes (S06 §16.1); the PDF render failing does not undo ISSUED (the render job retries).

Quote review (CD-04): `DRAFT → PUBLISHED`.

Contract baseline: `UNLOCKED → LOCKED` on the first ISSUED version (BR-052 as changed by CD-05, DERIVED). After LOCKED the baseline grows line by line at CHOSEN and the contract value is set at award (money); the locked items never change.

Design artefact version (design): `REQUESTED → GENERATING → GENERATED → IN_REVIEW → APPROVED | REJECTED → SUPERSEDED`; `FAILED` from GENERATING with retry. The approved plan version is the input to BOQ measurement; an architect pack enters at APPROVED directly (checked by operations) and supersedes concept artefacts.

## 8a. Build Plan version, drawing set, sign-off (buildplan; as built, Slice 3.5)

Section 8 is superseded where it differs: SLICE3_5_READINESS 0.2 is the machine as built. Version: DRAFT → IN_REVIEW (submit; content hash) → DRAFT (return; sign-offs VOID) or ISSUED (OPS with MFA, not the last editor, every structural line signed on the hash, published card, approved set, PDF stored) → ACCEPTED (owner, one-time code) or CHANGES_REQUESTED; SUPERSEDED when a later version is issued (unaccepted) or accepted (accepted); WITHDRAWN from DRAFT, IN_REVIEW or ISSUED, never ACCEPTED. Drawing set: DRAFT → SUBMITTED (professional) or IN_CHECK (the family's own) → IN_CHECK or CHANGES_REQUESTED → APPROVED or REJECTED; APPROVED → SUPERSEDED. Sign-off: SIGNED → VOID before issue; after issue a revocation is an event that blocks acceptance. No project status moves (BP-14). No date is calculated (BP-07A deferred).

## 9. Listing lead (leads)

Source: 44.7 (CD-26, proposed). Names as written there.

| State | Meaning |
|---|---|
| SENT | Delivered to an eligible contractor |
| VIEWED | Contractor opened the lead |
| ACCEPTED | Accepted within the acceptance window |
| DECLINED | Declined with a reason from the list |
| EXPIRED | Acceptance or quote window passed |
| QUOTED | Quote submitted in time |
| SELECTED | Homeowner selected this contractor |
| NOT_SELECTED | Homeowner selected another |
| WITHDRAWN | Member suspended, class no longer fits, homeowner withdrew or went inactive |

| From | To | Trigger | Actor | Preconditions | Side effects |
|---|---|---|---|---|---|
| (new) | SENT | Request Quote | Homeowner (system sends) | Project facts complete; at most three open leads on the project; contractor is a Club member, VERIFIED, class covers the project, service area covers the site, capacity free, not suspended, no conflict; no existing lead for the pair | Notification; `accept_by = now + 48 h` (configuration) |
| SENT | VIEWED | Open | Contractor | None | Response time recorded |
| SENT or VIEWED | ACCEPTED | Accept | Contractor | Before `accept_by` | Thread opened; `quote_by = now + 10 days` (configuration); RFQ invitation if the package is held |
| SENT or VIEWED | DECLINED | Decline | Contractor | Reason from the list | Replacement suggestion requested |
| SENT or VIEWED | EXPIRED | Window passed | Scheduled job | `accept_by` passed | Replacement suggestion requested; lead response metric |
| ACCEPTED | QUOTED | Quote submitted | Contractor (rfq event) | Before `quote_by` | None |
| ACCEPTED | EXPIRED | Quote window passed | Scheduled job | `quote_by` passed | Replacement |
| QUOTED | SELECTED | Selection | Homeowner (rfq event) | Selection recorded | Other leads NOT_SELECTED |
| QUOTED | NOT_SELECTED | Another selected | System | Selection recorded | Contractor told |
| any open | WITHDRAWN | Withdraw | System or operations | Trigger recorded as reason | Contractor told; replacement if the homeowner is active |

Terminal: DECLINED, EXPIRED, SELECTED, NOT_SELECTED, WITHDRAWN. If project facts change after SENT, the lead is updated in place and the contractor is told; a class mismatch withdraws it.

## 9a. Connection and engagement (engagements; as built, Slice 3.4)

Section 9 (listing lead) is **superseded** by these two machines (Connection and Lead decision, 2026-10-05).

Connection, per project, category and professional: `new to SENT` (owner, package active, need not NOT_NEEDED, no ACTIVE engagement in the category, fewer than 3 SENT in the category, none SENT to this professional, professional LISTED and shown, radius covers the plot); `SENT to ACCEPTED` (the professional, before `respond_by`, still LISTED, package active, project not cancelled, no ACTIVE engagement); `SENT to DECLINED` (the professional, with a reason; OTHER needs a note); `SENT to EXPIRED` (job every 15 minutes after `respond_by`, 48 hours by configuration); `SENT to WITHDRAWN` (the family; the system on another acceptance, the package refunded or cancelled, the project cancelled, the listing leaving LISTED; operations with a reason). Every state but SENT is terminal.

Engagement, per project and category, at most one ACTIVE: `new to ACTIVE` on acceptance (LISTED) or on recording (OUTSIDE), withdrawing the category's SENT requests; `ACTIVE to ENDED` by the family, the professional or operations, with a reason (shared files stop being visible). The package ending never ends an engagement (N-10).

## 10a. RFQ, invitation, quote version, review, comparison, selection (rfq; as built, Slice 3.6)

Section 10 is superseded where it differs: SLICE3_6_READINESS section T and 0 are the machines as built. RFQ: DRAFT → ISSUED (pack frozen) → CLOSED (selection) | CANCELLED (owner, operations, PACKAGE_ENDED, BASELINE_SUPERSEDED, PROJECT_CLOSED). Invitation: PROPOSED → SENT → ACCEPTED | DECLINED | EXPIRED; PROPOSED → ACCEPTED for an outside party at issue; PROPOSED, SENT or ACCEPTED → WITHDRAWN. Quote version: SUBMITTED → SUPERSEDED | WITHDRAWN | EXPIRED | SELECTED | NOT_SELECTED; a RENEWAL version after expiry. Review: PENDING ⇄ NEEDS_CLARIFICATION → REVIEWED, or CLOSED when the version leaves SUBMITTED. Comparison: PUBLISHED → SUPERSEDED | DECIDED. Selection: one append-only row. No project status moves and no engagement state is added: a selection creates or reuses the 3.4 engagement (origin RFQ_SELECTION, ADR-024).

## 10. RFQ, quote version, comparison and selection (rfq)

RFQ `[canonical]`: `DRAFT → ISSUED → CLOSED | CANCELLED`. ISSUED requires a pack version with drawings, BOQ, specification set, timeline and quote format (BR-080); a new pack version is an attribute change with `rfq.pack_version_changed` notifying invited contractors, not a state. CLOSED on selection; CANCELLED by operations with reason.

Invitation: `INVITED → ACCEPTED | DECLINED | EXPIRED` (D2: whether a contractor may decline an invitation was POQ-008; default from the lead design: yes, with a reason).

Quote version (CD-17; C-020 and PC-011 reconciled):

| State | Meaning |
|---|---|
| DRAFT | Being prepared by the contractor or captured by staff |
| SUBMITTED | Immutable; valid between `valid_from` and `valid_to`; the latest SUBMITTED version is the one the homeowner sees |
| SUPERSEDED | A later version was submitted |
| WITHDRAWN | Withdrawn by the contractor before selection (POQ-013 default: allowed, with reason) |
| EXPIRED | `valid_to` passed without selection (CQ-09: who sets dates; default the contractor sets within a configured maximum) |
| SELECTED | Chosen at award |
| NOT_SELECTED | Another quote was selected |

Submission precondition: every RFQ line priced or explicitly excluded (S06 §10), validity dates present, the RFQ ISSUED, the contractor VERIFIED. Transitions to SELECTED and NOT_SELECTED happen in the same transaction as the selection.

Comparison `[canonical]`: `DRAFT → NORMALISED → RECOMMENDED → PUBLISHED → DECIDED`. NORMALISED when every live quote has its adjustment list complete; RECOMMENDED when the engine's quote recommendation is approved by operations; PUBLISHED freezes the snapshot (quotes as submitted, adjustments, totals, recommendation, reasons) and renders the document; DECIDED on selection. Any later quote version after PUBLISHED creates a new comparison version.

## 11. Variation (variations)

Source: CD-08, DT-10 revised, SM-16, PSM-14, PSM-15. Names `[canonical]`; no DECLINED or REJECTED state exists.

| State | Meaning |
|---|---|
| RAISED | Raised by the homeowner or the contractor with reason, stage, line, cost and time impact, evidence |
| ASSESSED | Plan2Build qualified (valid or not) and quantified (cost, time) |
| ACTIVE | Acknowledged by OTP; contract value and completion date updated |
| ESCALATED | No acknowledgement within the window; visible to both parties |
| IN_DISCUSSION | Discussion step led by Plan2Build |
| CLOSED | Closure recorded with an outcome: APPLIED (becomes ACTIVE), WITHDRAWN, AMENDED (new variation raised) |

| From | To | Trigger | Actor | Preconditions | Side effects |
|---|---|---|---|---|---|
| (new) | RAISED | Raise | Homeowner or contractor | Required fields | Number assigned; operations queue |
| RAISED | ASSESSED | Assess | Operations | Validity, cost and time entered | Other party asked to acknowledge; `ack_by = now + window` (CQ-12; configuration) |
| ASSESSED | ACTIVE | Acknowledge | The other party | OTP valid; before `ack_by` | Contract value and completion date update; both notified |
| ASSESSED | IN_DISCUSSION | Disagree | The other party | Reason | Discussion thread |
| ASSESSED | ESCALATED | Window passed | Scheduled job | `ack_by` passed | Visible to both; exception feed |
| ESCALATED | IN_DISCUSSION | Open discussion | Operations | None | Thread |
| IN_DISCUSSION | CLOSED | Close | Operations (closure authority CQ-12) | Outcome and reason | If APPLIED: the same transaction marks ACTIVE effects; if AMENDED: new variation RAISED |
| ACTIVE | CLOSED | Mark implemented | Contractor update or operations | Work done | Record only |

Invalid: ACTIVE without an OTP acknowledgement or a CLOSED outcome APPLIED; any transition to a declined or rejected state. Delay days carry a cause category and roll up into the schedule position (S05 P5).

## 12. Payment milestone and payment marks (money)

Source: CD-09, DT-11 revised, SM-15, PSM-17, BR-108. No amounts for payments ever exist in this machine.

| State | Meaning |
|---|---|
| NOT_DUE | Stage not complete, or gate not cleared |
| DUE | Stage complete and, for gate stages, gate cleared; shown without an amount |
| SETTLED | Homeowner marked paid and professional marked received |

Marks are timestamps on the milestone (`paid_marked_at`, `received_marked_at`, each with the actor); a milestone with one mark and not the other for longer than the configured mismatch window is flagged `MISMATCH` in the exception feed (CQ-13 default; nothing is blocked). Whether the next milestone waits for SETTLED is CQ-13; default: it does not wait, since recording is optional. Retention (stage 16) follows the same machine at handover.

| From | To | Trigger | Actor |
|---|---|---|---|
| NOT_DUE | DUE | Stage COMPLETED (and gate CLEARED) | System |
| DUE | SETTLED | Both marks present | System on the second mark |
| DUE | DUE | Mark paid or mark received | Homeowner or professional |
| any | NOT_DUE | Stage reopened | Operations with reason |

## 13. Inspection, checkpoint, non-conformance (assurance)

Inspection `[canonical]` (SM-18, PSM-24, S07 §6):

| State | Meaning |
|---|---|
| SCHEDULED | Assigned to an auditor for a project and gate with a checklist version |
| PACK_DOWNLOADED | Job pack downloaded to the device |
| IN_PROGRESS | Readiness confirmed; checkpoints being recorded offline |
| SYNCED | All batches received by the server |
| LOCKED | Report content hashed and frozen; amendments are new records |
| APPROVED | Central operations approved; report rendered and shared; gate result applied |
| RETURNED | Operations returned it for an amendment record (does not unlock) |
| CANCELLED | Cancelled before sync, with reason |

Transitions: schedule (operations); download (auditor); confirm readiness (auditor); sync batches (auditor's device, idempotent per batch id); lock (server when the auditor submits as complete); approve or return (operations); cancel (operations). Checkpoint results are values, not states: `PASS, OBSERVATION, NON_CONFORMANCE, NOT_APPLICABLE`. Evidence captured before sync carries the device timestamp and location; the server adds its own receipt time and the hash; nothing is backdated because order is by device sequence and server receipt.

Non-conformance (SM-19, PSM-25; C-066: re-inspection governs, reviewer closure behind the flag `nc_reviewer_closure_allowed`, default false):

| State | Meaning |
|---|---|
| OPEN | Finding immutable; severity, owner, due date |
| RECTIFICATION_SUBMITTED | Contractor submitted evidence |
| REINSPECTION_SCHEDULED | A re-inspection is scheduled for the open set |
| CLOSED | Closed by a re-inspection record with evidence and sign-off (or by an authorised reviewer when the flag is on) |

A critical NC past its due date is a Club suspension trigger (44.8) and blocks the stage. Gate status (section 6) becomes CLEARED when an APPROVED inspection has no OPEN non-conformances.

## 14. Issue and dispute (issues)

Issue (CD-10; C-022 and PC-033 reconciled with the S01 names):

| State | Meaning |
|---|---|
| OPEN | Raised with evidence |
| ACKNOWLEDGED | Assignee acknowledged |
| IN_PROGRESS | Being fixed |
| FIXED | Fix submitted with proof |
| VERIFIED | Homeowner verified the fix |
| CLOSED | Closed by the homeowner (or operations with reason) |
| REOPENED | Homeowner rejected the fix; back to IN_PROGRESS on acknowledgement |
| ESCALATED | No fix by the due date, or escalated by the homeowner; operations handle |

Dispute (operations only, CD-10; steps per S01 names `[canonical]`): `OPEN → UNDER_REVIEW → RESOLUTION_PROPOSED → RESOLVED → CLOSED`, with `decided_against` recorded; a decision against a Club member raises `dispute.decided` for the Club review.

## 15. Plan2Build fee: invoice, payment attempt, refund (billing)

Invoice `[canonical]`: `DRAFT → ISSUED → PAID | OVERDUE → PAID | CANCELLED`; instalment invoices are separate invoices under one purchase with a schedule (CQ-01 sets the schedule; default: one invoice per milestone named in the offering).

Payment attempt (S02 §9 names): `INITIATED → PENDING → CAPTURED | FAILED | EXPIRED`; CAPTURED is set only by a verified webhook or a verified fetch during reconciliation, never by the browser callback alone. Refund: `REFUND_REQUESTED → REFUNDED | REFUND_FAILED` (operations, policy CQ-04). Package status derived: `NOT_PURCHASED, ACTIVE (first instalment captured), PAID_IN_FULL, LAPSED (instalment overdue beyond grace), CANCELLED`.

## 16. Files, rendered documents, share tokens (documents)

File object: `PENDING_UPLOAD → UPLOADED → SCANNING → AVAILABLE | QUARANTINED | FAILED → DELETED (soft)`. Rendered document: `QUEUED → RENDERING → RENDERED | FAILED` (retry with backoff, then dead letter). Share token: `ACTIVE → EXPIRED | REVOKED` (OQ-047 default: build record tokens do not expire; other documents expire per configuration).

## 17. Build record (records)

`ASSEMBLING → ISSUED → TRANSFERRED` (TRANSFERRED keeps ISSUED content; ownership changes with a new owner contact verified by OTP). Warranty entries inside the record carry `term, expiry, installer` and are values, not a machine, at the MVP (D1's warranty machine is deferred with the Improve loop).

## 18. Recommendation request (recommendation)

`REQUESTED → COMPUTING → COMPUTED → IN_REVIEW → APPROVED → SHOWN`, with `FAILED` (fallback: the operations team builds the shortlist by hand, recorded as a manual request) and `DISCARDED` (operations declined to show, with reason). Every review action is a row with actor, old value, new value and reason (BR-142).

## 19. Notification delivery and jobs

Delivery: `QUEUED → SENT → DELIVERED | FAILED | BOUNCED`; retries with backoff per channel; dead letter after the configured attempts; OTP deliveries are never retried beyond the OTP validity.

Jobs are owned by Procrastinate: `todo → doing → succeeded | failed | cancelled`; failed jobs with exhausted retries are the dead letter list (EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md).

## 20. Reconciliation of source vocabularies

| Entity | D1 names (S01, S02) | D2 names | Canonical here | Reason |
|---|---|---|---|---|
| Account | PENDING_EMAIL, ACTIVE, SUSPENDED, CLOSED | auth status, values unknown | PENDING_VERIFICATION, ACTIVE, SUSPENDED, CLOSED | OTP by email or SMS, not email verification only |
| Verification | DRAFT, SUBMITTED, UNDER_REVIEW, NEEDS_RESUBMISSION or RESUBMISSION_REQUIRED or Changes Required, VERIFIED, REJECTED, SUSPENDED | values unknown | S02 wording with CHANGES_REQUESTED | One name for the same meaning (PC-010) |
| Project | three lists (C-018) | values unknown | section 5 | S01 order of handover before completion; ACCEPTED for QUALIFIED |
| Quote | two lists (C-020, PC-011) | draft and final submission | section 10 | Versions per CD-17; SELECTED and NOT_SELECTED instead of ACCEPTED or REJECTED (PAMB-006) |
| Variation | ACCEPTED or REJECTED (D1) | Raised, Active, Escalated | section 11 | CD-08 removes rejection; discussion and closure added |
| Payment record | ALLOCATED, SETTLEMENT (D1) | recorded, acknowledged | section 12 | CD-09 marks without amounts; settlement does not exist |
| Issue | two lists (C-022) | none | section 14 | CD-10 sequence with S01 names |
| Milestone | four lists (C-021) | stage instances | section 6 | Stage instance states; payment milestone separate |

Open items that this document decides by default, each reversible by configuration or a one-line change: stage completion authority (homeowner, operations override), who records PURCHASED and INSTALLED (contractor), quote withdrawal (allowed with reason), OTP acknowledgement by household members (owner only), reviewer closure of non-conformances (off), whether the next milestone waits for marks (no), share-token expiry for the build record (none).
