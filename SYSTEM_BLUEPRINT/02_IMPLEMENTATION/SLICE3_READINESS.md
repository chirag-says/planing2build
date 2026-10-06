# Plan2Build: Slice 3 readiness (package, specification decisions, Build Plan)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/SLICE3_READINESS.md` |
| Version | 1.0 (2026-10-04) |
| Status | Audit complete. Superseded in part on 2026-10-04 by Chirag's product decisions PD-01 to PD-26 (IHB_FLOW 32.6, canonical flow 34) and `PRODUCT_FLOW_RECONCILIATION.md` v2.0, which replaces the slice order in section 12 and settles D3-02, D3-10 and D3-12; D3-11 is amended by PD-24 (any qualified structural engineer may sign). The billing, specification and Build Plan findings stand otherwise. No Slice 3 code written |
| Scope | Homeowner: workspace, package, purchase, specification decisions, Build Plan, RFQ-ready scope. Operations: package management, specification issue and oversight, Build Plan review and freeze. Out of scope: contractor sourcing, RFQ issue, quotes, comparison, recommendation |
| Sources read | IHB_FLOW sections 8, 32 (CD-01 to CD-28, CQ-01 to CQ-26), 33; PROFESSIONALS_FLOW 43; STATE_MODEL 6, 7, 8, 15; DATA, API, SECURITY, EVENT, INTEGRATION, DOMAIN, AI_AND_RECOMMENDATION, COST_MODEL, README (AQ list), ARCHITECTURE_BASELINE, ADR-013, ADR-018, ADR-020, ADR-022; SLICE2_READINESS; FOUNDATION_PLAN; S03, S04, S05, S06, S07, S08, S09, S11 (SOURCE_OF_TRUTH, read only); the Slice 2 code and `spec_lines_v1.json` |
| Precedence | Client decisions (CD) and Chirag's rulings over IHB_FLOW, over PROFESSIONALS_FLOW, over the Source of Truth. Architecture documents are proposals for Chirag's review unless a ruling adopted them |
| Labels | SETTLED (a source or ruling decides it), PROPOSED (architecture default, not approved), OPEN (no decision; CQ, AQ or OQ id given), CONFLICT. Classification: BLOCKING BEFORE CODING, NON-BLOCKING, IMPLEMENTABLE NOW, DEFERRED |

## 1. Three findings that change the plan

1. **The A/B/C packages are not the commercial package.** S04 sold three packages (A Structure, B Concealed systems, C Finishes) as instalments. CD-05 replaced them: "One package holds everything: the Build Plan, quote review and comparison, and stage inspections" (IHB 32.2), and IHB 1134 says they "are no longer sold separately". A/B/C survive only as grouping and issue timing of lines. The Slice 2 code still models purchase per A/B/C (`specification/service.py` `purchased_packages()`, workspace `packages[].purchased`, the notice "once this package is purchased"). This needs correcting once decision D3-02 is made.
2. **The hidden "performance specification" is a template, not a specification.** The S04 text on every master is a list of criteria, for example A04 "Grade, exposure class, slump range". The project values (the grade, the exposure class) are filled in by the advisor and, for structural lines, specified by the engineer: "An advisor issues a line with project-specific values filled in, and the issued text is stored on the project instance" (S04 section 10). No code or table holds those values yet. What the homeowner pays to see appears when the Build Plan is issued, not at purchase.
3. **RFQ-ready scope does not need the 67 homeowner choices.** The RFQ pack is "BOQ, drawings, specification, timeline, standard quotation format" (BR-080). The specification is brand-neutral criteria (S04 R1). Choices (CHOSEN) happen at each line's lead time through construction: "lines still surface at their lead time through the decisions calendar" (IHB 1134); S04 section 8 freezes a line at CHOSEN and makes later changes variations. So the order is: package, Build Plan with issued criteria and structural sign-off, issue and freeze, RFQ pack, then choices line by line during the build. The requested order "Specification decisions → Build Plan" holds for issuing criteria, not for homeowner choices. How contractors price lines not yet chosen is decision D3-19.

## 2. Package

| Question | Finding | Status |
|---|---|---|
| What the package contains | Build Plan, quote review and comparison, stage inspections (CD-05); drawings and 3D views (CD-06); Plan2Build concept design, or an architect's design on request (CD-25); build record and variation log (C-062) | SETTLED |
| Package states | `NOT_PURCHASED, ACTIVE (first instalment captured), PAID_IN_FULL, LAPSED (instalment overdue beyond grace), CANCELLED`, derived from invoices (STATE_MODEL 15). No business source defines fee states (OQ-016). The grace period has no source | PROPOSED |
| Price | "what the single package costs" (CQ-01, not yet asked). Older figures (S03, S04 A/B/C fees, S20 to S22 price boards) are superseded | OPEN, BLOCKING |
| Instalments | "at once or in instalments, one per milestone" (CD-05). Which milestones and how much: CQ-01. These are not the construction payment milestones at stages 1, 3, 4, 6, 7, 10, 11, 13, 14, 16 | SETTLED that they exist; schedule OPEN |
| Who can purchase | API design: owner only. Household permissions are OQ-027 | PROPOSED |
| When purchase opens | After acceptance (DOMAIN: on acceptance "billing offers the package"); IHB 33.1 order: workspace, then quote decision, then package | PROPOSED |
| Homeowner who already holds a quote | Buys the full package or a review alone: CQ-02 | OPEN |
| What payment unlocks | Ruling 2.6: performance specifications. Design: project moves ACCEPTED → PLANNING; concept design starts; Build Plan issue allowed; RFQ invitation only "if the package is held". Beyond specifications: open (SLICE2_READINESS 5.3) | Partly SETTLED; D3-02 |
| Failure | Attempt FAILED; invoice stays ISSUED with a retry link; attempts older than 30 minutes checked by reconciliation; UI says "pending, do not pay again"; amount mismatch flagged, not applied (INTEGRATION) | PROPOSED |
| Refund and cancellation | "what happens to the package and its instalments if the homeowner stops" (CQ-04, not yet asked). Design default: operations-initiated refunds with reason and MFA, no automatic rule. A project cancelled after purchase follows CQ-04 | OPEN, BLOCKING for live money |
| Invoice and tax | Tax rate and invoice format not stated (MI-007); retention and numbering AQ-11; GST registration AQ-20. Plan2Build issues its own invoices; Razorpay invoices are not used | OPEN, BLOCKING for invoices |

## 3. Payment and the money boundary

**Boundary (SETTLED).** CD-01: Plan2Build "never takes, holds or releases the payments between" homeowners and professionals. CD-09: construction payments are marked paid and received, yes or no, with no amount. Plan2Build's own fee is the only money through the platform (IHB 2810, INTEGRATION). Rules for the design:

- Only the package fee ever reaches Razorpay. No endpoint accepts an amount for construction work; `payment_milestones` keeps no amount column (DATA 224).
- Billing tables carry no contractor, quote or contract reference. Construction milestone marks live in the money module and never create an invoice.
- Open at the edge: whether the architect's fee goes direct or into the package (CQ-25). Until settled, nothing about architects enters billing.
- One drift to correct when the money module is built: EVENT 182 still says "payment due with amount from the contract", which conflicts with CD-09.

**Razorpay lifecycle.** Razorpay Checkout in the app was decided by Chirag on 2026-10-03 (SYSTEM_ARCHITECTURE 3; ADR-020). IHB 32.5 still lists CQ-03 as not yet asked: the IHB register needs updating; the client has not confirmed. The rest is PROPOSED (INTEGRATION 4):

| Step | Behaviour |
|---|---|
| Purchase | Owner chooses the offering version and plan; purchase and first invoice ISSUED; idempotency key |
| Checkout | One Razorpay order per attempt (Orders API, amount in paise, `receipt` = invoice code); attempt INITIATED; public key only to the browser; 5 attempts per invoice per hour |
| Browser callback | Hint only. HMAC of order and payment id checked; never marks paid (BR-040) |
| Webhook | `POST /webhooks/razorpay`: HMAC-SHA256 of the raw body with the webhook secret, constant-time compare, before parsing; failures are security events; event id UNIQUE in `payment_events`; store, answer 200, process in a job; amount and order id checked against the invoice. Events: `payment.captured`, `payment.failed`, `order.paid`, `refund.processed`, `refund.failed`, `payment.dispute.created` |
| Capture | Attempt CAPTURED, invoice PAID, purchase ACTIVE or PAID_IN_FULL, receipt rendered, homeowner notified, `billing.package_paid` |
| Reconciliation | Daily: non-terminal attempts older than 30 minutes fetched; captures of the last 3 days matched; differences to `billing_exceptions` for operations; manual trigger for ops |
| Audit | Audit row per transition in the same transaction; events `billing.invoice_issued`, `payment_captured`, `payment_failed`, `package_paid`, `instalment_due`, `instalment_overdue`, `refunded` |

## 4. Specification lifecycle

**States (SETTLED).** `SPECIFIED → OPTIONS_ISSUED → CHOSEN → PURCHASED → INSTALLED → VERIFIED` (S04 section 2; STATE_MODEL 7; code `SpecLineState`). No LOCKED state: CHOSEN "freezes the line into the contract baseline" (S04 section 8); VERIFIED is final and never undone. PURCHASED means the material was bought for the site, not the package purchase.

| From | To | Actor | Source status |
|---|---|---|---|
| (new) | SPECIFIED | System, at acceptance | SETTLED; built |
| SPECIFIED | OPTIONS_ISSUED | Operations advisor; only lines with a brand category, never structural | SETTLED. CONFLICT on count: STATE_MODEL requires 3 to 5 options; S04 R2, BR-062 and DT-07 allow fewer "if fewer than three qualify". S04 outranks |
| OPTIONS_ISSUED | CHOSEN | Owner, with OTP; option must be in the issued set | SETTLED |
| SPECIFIED | CHOSEN | Structural or no-brand lines. STATE_MODEL lets "homeowner or operations" confirm; S04 section 8: "Each line is acknowledged by the homeowner with OTP at the Chosen state" | CONFLICT (AMB-020 open) |
| CHOSEN | PURCHASED, INSTALLED | Contractor by default, or operations | OPEN (POQ-021, AMB-022). Construction phase; not Slice 3 |
| INSTALLED | VERIFIED | Auditor at a gate, or operations | Construction phase; not Slice 3 |
| CHOSEN | CHOSEN | Variation activation | SETTLED (CD-08); window and closure CQ-12 open |
| Any | One state back | Operations override with reason and fresh MFA; audit `override = true` | SETTLED |

**Issue.** S04 section 10: an advisor issues a line with project values, and the issued text is stored on the project instance. Today `issued_criteria` holds the master template copied at acceptance; no state, event or endpoint records the advisor's issue. Proposal: the advisor writes project values inside the Build Plan draft (S05 P3: the advisor "can edit any figure or line; the edit is recorded"); issuing the Build Plan writes the issued text to each project line with a new line event, under that Build Plan version.

**Who edits.** Homeowner chooses, never edits criteria (S04 R6). Advisor edits values in the draft. Masters change only by a new version (admin with MFA; structural masters need the engineer's record; API 278). Operations do not edit data directly (SECURITY 4.2). CONFLICT, minor: DOMAIN gives operations edit rights on non-structural masters; API restricts publishing to admin.

**Versioning.** A master change never alters an issued instance (S04 section 10; BR-074). Whether a new master version reaches existing projects that have not yet had a Build Plan issued has no source.

**Changes recorded.** Append-only `spec_line_events` plus an audit row per transition (built). S06 section 7 also requires evidence and source channel on events; the built table lacks `evidence_file_id` and `source_channel` (DATA 142).

**When authoritative.** Criteria: when the Build Plan version carrying them is ISSUED (CD-05 through BR-052, DERIVED). Structural criteria: only under the engineer's sign-off (S04 section 3). A choice: at CHOSEN with OTP. Baseline value timing (Build Plan estimate or awarded quote): AMB-040, open.

**Effect of a changed decision.** Before issue: the draft changes; nothing downstream exists. After issue: the version is frozen (BR-051); a change to a CHOSEN line is a variation with cost and time (S04 section 8; CD-08); an RFQ change is a new pack version and quotes on the old one are flagged (EVENT 151). OPEN: whether a first-time choice after award changes contract value or BOQ, and whether any change re-issues the Build Plan (D3-19, D3-20).

**Decide-by.** "Weeks before the consuming stage begins" (S04 section 2): `decide_by` = planned start of the consuming stage instance minus `decide_by_weeks`. NULL until a schedule exists (ruling 2.9, built). Missed deadline consequence: OQ-044. Reminder defaults 14/7/2 days for long-lead, 7/2 otherwise (AQ-14, proposed).

**Visibility of the six states to the homeowner.** S04: the homeowner sees the first three. The client ticked step 18 (CD-24), where the homeowner sees chosen through verified. C-029 is not marked settled. NON-BLOCKING for Slice 3 (the last three states are construction).

## 5. Structural sign-off

| Question | Finding | Status |
|---|---|---|
| Meaning | "must be issued under the sign-off of a registered structural engineer, not by Plan2Build alone. Plan2Build compiles and communicates; the engineer specifies" (S04 section 3). Structural design is never AI-generated (BR-055, CD-25) | SETTLED |
| Lines | A01, A02, A04, A05, A09, A12, A13, A19 (ruling 2.4; seed marks all eight PENDING). Package C needs none | SETTLED |
| Who | A Plan2Build-retained registered structural engineer, distinct from the independent auditor (S03 7.3; PRO 494). Registration body unknown; capacity and structural drawing scope CQ-22 | Role SETTLED; person and scope OPEN |
| When | Before Build Plan issue: IN_REVIEW on request; ISSUED only when every structural line is signed (STATE_MODEL 8; API 101-102) | PROPOSED |
| Where recorded | CONFLICT. Design: `structural_signoffs` per Build Plan version and line (DATA 153). Built: `engineer_signoff` on the master version, copied to each project line. Because issued instances never change, copied PENDING values could never become SIGNED | D3-11 |
| What a sign-off records | No source (SLICE2_READINESS 5.3). `EngineerSignoff.SIGNED` in code has no source either | OPEN, BLOCKING |
| Engineer access | MFA, professionals host (SECURITY 3.3). No engineer account, onboarding or sign-off flow exists (POQ-042) | OPEN |

## 6. Build Plan

**Lifecycle (PROPOSED, STATE_MODEL 8).** `DRAFT → IN_REVIEW → ISSUED → SUPERSEDED`, plus `WITHDRAWN` for an abandoned draft. Draft by the advisor; IN_REVIEW when structural sign-off is requested; ISSUED by operations with MFA when every structural line is signed, the package is paid and a concept design or architect's pack is attached; SUPERSEDED when a later version is issued. ISSUED content never changes (trigger); a failed PDF render does not undo ISSUED. Project: ACCEPTED → PLANNING on payment, PLANNING → PLAN_ISSUED on issue. Baseline `UNLOCKED → LOCKED` on the first issue. Operations QA (rate-card version, schema version, assumptions; S07) has no state of its own and sits inside "issue". Whether the homeowner formally accepts an issued plan: OPEN (IHB 1130).

| Part | Source of truth | Authoritative or illustrative | Status |
|---|---|---|---|
| Inputs | Requirement answers (question set v1, locked), specification masters (S04 v1), stage master, rate card in force, approved drawings, advisor edits (S05 P3) | Authoritative | SETTLED as design |
| Estimate | Stored with its rate-card version, regenerable identically; stage breakdown sums to the total (S05 F2). Only a DEMO card exists, never served in production (N-05) | Authoritative once a production card exists | Production card D-16 OPEN, BLOCKING |
| BOQ | Lines: item code, quantity, unit, rate version, amount, assumptions, stage, spec line code; immutable with their version. Quantities measured from approved drawings (33.6, proposed). The DEMO card has per-square-foot rates; no item-rate card is defined anywhere | Authoritative | Item rates OPEN (D-16), BLOCKING |
| Specification extract | Issued criteria with project values; checked against Indian Standards and the structural design before issue (S04 section 10) | Authoritative | Mechanism D3-10 |
| Schedule, cash flow, decisions calendar | Payment schedule, monthly cash flow, decide-by dates (BR-054) | Authoritative when built from approved inputs | Needs D-04 values or a per-project schedule (D3-16) |
| Concept drawings | Plan2Build concept design by default, architect on request (CD-25). Method (digitise sanctioned plan, or fit a library layout in CAD) is a proposal awaiting Chirag (33.6). CONFLICT: Chirag's CD-25 wording has an image tool making 2D drawings; 33.5 and ADR-013 reject AI floor plans. Checker: CQ-26 | Authoritative once approved by the checker | OPEN, BLOCKING for issue |
| Structural drawings | Engineer. Full RCC and permit drawings in the package: CQ-22 | Authoritative | OPEN |
| 3D views | AI image generation (CD-25); "Illustrative; the drawings govern" burned in; `is_authoritative = false`; never read by BOQ or RFQ; two regeneration rounds; stale when the plan changes. Budget: S09 and S11 exclude image generation; CQ-24 not asked. Issue without views: AQ-18 (default allowed). Provider: AQ-15 | Illustrative only | OPEN; DEFERRED unless funded |
| PDF | [SUPERSEDED by ADR-023, 2026-10-05: fpdf2] WeasyPrint on the render queue; deterministic, versioned, hash stored (ADR-018; BR-056). CONFLICT: BR-057 requires Hindi and English; ADR-022 records Chirag's English-only MVP decision; client not asked (AQ-10) | Rendering of the issued version | SETTLED engine; language D3-17 |
| Share link | Expiry and revocation OQ-047 | n/a | DEFERRED |

**Regeneration and invalidation.** SETTLED: issued versions never change; a later change is a new version; an architect's pack supersedes concept artefacts, re-measures the BOQ and creates a new RFQ pack version; a changed plan marks 3D views stale. OPEN (no source): which pre-issue changes force a new draft, and whether a post-issue variation creates a new Build Plan version or only grows the baseline (D3-20).

## 7. Stage schedule

| Question | Finding | Status |
|---|---|---|
| Where durations and cost shares come from | Versioned stage master, values NULL (D-04; ruling 2.9). No source holds approved per-stage durations or shares. The S14 shares and duration formula are prototype values and live only on the DEMO rate card | Values OPEN |
| Who approves | "who approves a configuration version" is open (D-04). SLICE2_READINESS 2.9 recommended the engineer for values and an ADMIN with MFA for approval; not adopted | OPEN |
| Global or per project | Global versioned master (built). A per-project operations-entered schedule is allowed by D-04 ("planned dates come only from an approved configuration or an operations-entered schedule"); endpoint designed (API 196); who enters it is open (IHB 949) | Global SETTLED; per-project mechanism SETTLED, actor OPEN |
| How planned dates are calculated | Start date source unknown before a contractor schedule exists (IHB 980). No dependency table, no parallel-stage rule. Code observation: `construction.plan()` numbers every floor of stage 5 before stage 6, so `sequence` is display order, not build order; date maths must not rely on it | OPEN |
| Effect of a schedule change | `construction.stage_dates_changed` recomputes decide-by dates and notifies members (EVENT 173). Construction payment milestones follow actual completion and gate clearance, not planned dates. Package instalments tied to dates: CQ-01 | PROPOSED |
| Decide-by now or later | Later: NULL until a schedule exists (ruling 2.9 overrides STATE_MODEL's "computed at instantiation"). Built that way | SETTLED |
| Two homes for cost shares | `rate_cards.stage_shares_pct` (estimator, DEMO) and `stage_masters.cost_share_pct` (NULL). S05 F2 wants the estimator breakdown from the stage master | CONFLICT, D3-15 |

## 8. Security and authorization

| Actor | Package and payment | Specification | Build Plan | Schedule |
|---|---|---|---|---|
| Owner | Buys, pays, reads own invoices and receipts | Reads; chooses with OTP; never edits criteria | Reads issued versions only, PDF logged | Reads |
| Household member | None until OQ-027 (deferred) | Reads; no OTP acknowledgement (default) | Reads issued (default) | Reads |
| OPS (staff, MFA) | Reads purchases and invoices; refunds with fresh MFA and reason; reconciliation; billing exceptions | Issues options; overrides one state back with reason and MFA | Issues with MFA; reads drafts | Enters or changes a schedule with reason (actor D3-16) |
| OPS_ADVISOR (project role) | None | Writes project values in the draft | Drafts, requests sign-off | Proposes |
| ADMIN (staff, MFA) | Configures offerings and price versions | Publishes master versions; structural masters need the engineer's record | None (built rule: ADMIN does not open review routes; DOMAIN's "full" access is superseded) | Publishes stage master versions |
| Structural engineer (pro host, MFA) | None | Specifies structural lines | Signs structural lines per version | None |
| Auditor (assigned) | None ("No payment action") | Gate-relevant view, no supplier or brand | No access by default (DOMAIN) | Reads gates |
| Contractor, architect | None (construction money stays off-platform) | Later slices | RFQ-pack parts only, later slices | Later slices |

Rules: membership join on every query and 404 outside it (built and tested); fee data visible to the owner and operations only, gateway fields classed P3; the auditor and professionals never see fee data; every state change writes an audit row in the same transaction; every POST takes an `Idempotency-Key`; webhooks are idempotent by provider event id and verified before parsing; only the webhook or reconciliation can mark a payment paid; MFA for operations, admin, engineer sign-off and overrides, re-verified every 8 hours and before approvals. Auditor MFA is AQ-23 (open).

## 9. Decisions required

Each decision: why it matters, then the recommendation. Recommendations are Sakha's advice, not facts.

| ID | Decision | Blocks | Recommendation |
|---|---|---|---|
| D3-01 | Package price and instalment plan (CQ-01): amount, number of instalments, what triggers each, amounts; confirm the instalments are Plan2Build's own fee, not credit | Purchase, invoices, checkout | Ask the client. Model the price as an offering version set by an ADMIN with MFA, so the value is never in code. Limit instalment triggers to a short fixed list (on purchase, on Build Plan issue, on a named stage completion) |
| D3-02 | What the purchase unlocks, and when the specification becomes visible: all at once on first payment, per A/B/C at "before stage 3/9/13", or per instalment | Purchase effects; the Slice 2 correction | Tie visibility to issue, not payment. The homeowner sees the issued specification (with project values) when the Build Plan version is ISSUED, which already requires payment. Drop the per-A/B/C `purchased` flag; keep A/B/C as grouping and timing labels |
| D3-03 | Quote-holder path (CQ-02) | Only that path | Defer. Build the full package path first |
| D3-04 | Refund and cancellation policy (CQ-04) | Live money; legal terms | Ask the client. Mechanism: operations-initiated refunds only, with reason and fresh MFA, no automatic rule. Policy text belongs in the terms (launch gate: legal) |
| D3-05 | Invoice and tax: legal entity, GSTIN, tax rate, SAC code, numbering and retention (MI-007, AQ-11, AQ-20) | Invoices and receipts | Ask Chirag's accountant. Plan2Build's own sequential numbering per financial year; nothing invented |
| D3-06 | Who may purchase | Purchase | Owner only until household permissions (OQ-027) are decided |
| D3-07 | Package states | Purchase | Adopt the derived states in section 2, with LAPSED only if D3-01 has instalments and a grace period (value from Chirag) |
| D3-08 | Structural and no-brand lines reach CHOSEN by the homeowner's OTP acknowledgement, or operations may confirm (AMB-020) | Spec decisions | Follow S04: the homeowner acknowledges with OTP at CHOSEN for every line. Operations never choose on the homeowner's behalf except by audited override |
| D3-09 | Who curates brand options at the MVP, and how products qualify (S04 R4 test certificates, R8 annual review); fewer than three options allowed | OPTIONS_ISSUED | Operations advisor curates against S04 R1 to R9; allow a short set with the reason shown (S04 R2); Plan2Build never recommends a brand (CD-18) |
| D3-10 | Where project values are written and when the issued text becomes authoritative | Specification extract | Advisor writes values in the Build Plan draft; issuing the version writes the issued text and a line event per line under that version |
| D3-11 | Structural sign-off record: per Build Plan version and line (design) or per master; what it records; who the engineer is and how the account is created | Build Plan issue | Per Build Plan version and line. Record: engineer account, registration number (as provided), line code, version, the text signed, time, statement wording approved by Chirag. Remove the per-line copy of the master's PENDING value once this lands. Engineer account created by the staff command with MFA |
| D3-12 | Does the homeowner formally accept an issued Build Plan; how many revision rounds before issue | Lifecycle | No acceptance step after issue. Before issue, the homeowner reviews the concept drawings (accept, ask for changes, request an architect; API 106); the round limit is Chirag's number |
| D3-13 | Concept drawing method (CD-25 method), checker (CQ-26), structural scope (CQ-22), architect fee route (CQ-25) | Build Plan issue | Confirm the 33.6 method: no AI floor plans; drawings by people with CAD; checker named by Chirag |
| D3-14 | 3D views: funded in the POC (CQ-24); issue without views (AQ-18); provider (AQ-15) | Views only | Issue without views. Build views only once funded |
| D3-15 | Production rate card: values, approver, shape, item rates for the BOQ (D-16); which cost-share home governs | Estimate, BOQ | Ask Chirag for the card shape and source. One home for stage shares: the stage master, with the estimator reading it |
| D3-16 | Schedule: approved durations and approver (D-04), or a per-project schedule entered by operations; start date source; overlaps | Schedule, cash flow, decide-by dates | For the POC, a per-project schedule entered by the advisor with reason, no defaults invented; global defaults later when Chirag approves values |
| D3-17 | PDF language: English only (ADR-022) or Hindi and English (BR-057) | PDF | English only for the MVP, as Chirag decided; confirm with the client (AQ-10) |
| D3-18 | Homeowner visibility of the last three ledger states (C-029) | Construction slices | Show all six, since the client ticked step 18. Not needed for Slice 3 |
| D3-19 | How the RFQ prices lines not yet chosen | RFQ slice | Price against the issued brand-neutral criteria; a later choice within the criteria costs nothing extra; outside them it is a variation (S04 section 8) |
| D3-20 | Invalidation: which pre-issue changes force a new draft; does a post-issue variation create a new Build Plan version | Build Plan versions | Before issue every change edits the draft. After issue the version is frozen; variations grow the baseline; a new version is issued only by deliberate operations action (for example an architect's pack), which also creates a new RFQ pack version |

## 10. Classification

| Item | Class |
|---|---|
| Package price, instalments, refunds, tax, invoices (D3-01, D3-04, D3-05) | BLOCKING BEFORE CODING |
| What purchase unlocks (D3-02) | BLOCKING BEFORE CODING |
| Package states and who purchases (D3-06, D3-07) | BLOCKING BEFORE CODING (quick confirmations) |
| Razorpay mechanics, webhook verification, idempotency, reconciliation | IMPLEMENTABLE once D3-01 and D3-02 are settled; production also needs the Razorpay account (launch gate) |
| Money boundary | SETTLED; enforced by design |
| Ledger states SPECIFIED, OPTIONS_ISSUED, CHOSEN (D3-08, D3-09) | BLOCKING BEFORE CODING |
| Ledger states PURCHASED, INSTALLED, VERIFIED | DEFERRED (construction) |
| `spec_line_events.evidence_file_id` and `source_channel` (DATA 142, S06 section 7) | IMPLEMENTABLE NOW (sourced, additive) |
| Project values and issue (D3-10) | BLOCKING BEFORE CODING |
| Structural sign-off (D3-11) | BLOCKING BEFORE CODING |
| Build Plan lifecycle (D3-12) | BLOCKING BEFORE CODING |
| Drawings (D3-13) | BLOCKING for issue; the draft can exist without them |
| 3D views (D3-14) | DEFERRED |
| Estimate and BOQ with production rates (D3-15) | BLOCKING BEFORE CODING |
| Schedule (D3-16) | BLOCKING for the schedule, cash flow and decide-by parts |
| PDF engine | IMPLEMENTABLE once there is an issued version; language D3-17 NON-BLOCKING with English |
| Share links (OQ-047), quote-holder path (D3-03), six-state visibility (D3-18) | DEFERRED |
| RFQ pricing and invalidation (D3-19, D3-20) | NON-BLOCKING for the Build Plan; BLOCKING for the RFQ slice |
| Contractor sourcing, RFQ, quotes, comparison, recommendation | DEFERRED by Chirag's order |

## 11. What Slice 3 will need

**Existing code to reuse.** Transition tables (`core/state_machine.py`); outbox, jobs and notification architecture; idempotency store; audit service; rate limiting; MFA and `require_actor` roles; staff command (for engineer accounts); estimator engine with versioned rate-card schemas (`catalog/estimator.py`, a schema version 2 for item rates); stage masters and `stage_instances` with planned-date columns; spec masters with versions; `project_spec_lines` and `spec_line_events`; documents module (presigned uploads, scanning, access log) for drawings and PDFs; email provider; the workspace and operations screens and the design system.

**Likely database changes.** Billing: `offerings` and versions (price nullable until D3-01), `package_purchases` (one per project), `instalment_schedules`, `invoices`, `invoice_lines`, `payment_attempts`, `payment_events` (UNIQUE provider and event id), `refunds`, `billing_exceptions`. Specification: `spec_options`; on `project_spec_lines` add `chosen_option_id`, `chosen_at`, `otp_challenge_id`, `issued_in_version_id`; on `spec_line_events` add `evidence_file_id`, `source_channel`; drop the copied `engineer_signoff` once D3-11 lands. Build Plan: `build_plans`, `build_plan_versions` (immutable after ISSUED by trigger), `boq_lines`, `structural_signoffs`, `design_requests`, `design_artefacts` (with `is_authoritative` and `source`, missing from DATA today), `rendered_documents`. Project statuses PLANNING and PLAN_ISSUED. A schedule change log.

**Likely APIs** (API_ARCHITECTURE sections 5 to 7, 15): `GET /offerings/current`; `POST /projects/{id}/package/purchase`; `POST /invoices/{id}/checkout`; `POST /webhooks/razorpay`; `GET /projects/{id}/invoices`; `POST /ops/payments/{id}/refund`; `POST /ops/billing/reconcile`; `GET /projects/{id}/spec-lines/{code}`; `POST /projects/{id}/spec-lines/{code}/options`, `/choose`, `/override`; `GET /projects/{id}/build-plan`; `POST /ops/projects/{id}/build-plan/versions`, `/request-signoff`, `/issue`; `POST /pro/signoffs/{version_id}/lines/{code}`; `GET /projects/{id}/design`, `POST /projects/{id}/design/decide`, `POST /ops/projects/{id}/design/concept`, `POST /ops/design/artefacts/{id}/approve|reject`; `POST /ops/projects/{id}/stages/{stage_id}/reschedule`; `POST /admin/catalog/*/versions` for offerings, rate cards and stage values.

**Likely screens.** Homeowner: package offer and checkout, payment pending and result, invoices and receipts; specification line detail with options and OTP choice; Build Plan viewer and PDF; concept drawing review. Operations: purchases, invoices, billing exceptions, refunds; Build Plan editor (project values, BOQ, schedule), sign-off status, issue; option issue and override. Engineer (professionals host): sign-off queue and line sign-off. Admin: offering and price versions, rate card and stage value versions.

**Tests required.** Purchase only by the owner of an ACCEPTED project, once (idempotent, concurrent); price read from the offering version, never from the client; webhook signature bad, missing, replayed, out of order, amount or order mismatch; browser callback never marks paid; reconciliation finds and fixes a missed webhook; refund needs fresh MFA and reason; no endpoint accepts construction amounts; fee data invisible to auditors, professionals and other families. Ledger: every allowed transition, every forbidden one (options on structural lines, CHOSEN without OTP, skipping CHOSEN), override one state back with reason, events and audit rows in the same transaction. Build Plan: issue refused without payment, sign-off or drawings; issued content immutable (409 and trigger); new version supersedes; PDF hash stable; homeowner sees issued versions only; specification visible per D3-02 and never before. Schedule: decide-by recomputed on a date change; no invented values. Phone and desktop Playwright with axe on every new screen; migration up, down, up.

## 12. Next implementation slice

Not to start until Chirag approves. Proposed order, each a stop point:

1. **Slice 3a, package and payment.** Needs D3-01, D3-02, D3-04 (mechanism at least), D3-05, D3-06, D3-07, and a Razorpay test account. Builds offerings, purchase, invoices, Razorpay test-mode checkout, verified webhooks, reconciliation, refunds by operations, the visibility correction from D3-02, and the screens.
2. **Slice 3b, Build Plan draft, sign-off and issue.** Needs D3-10, D3-11, D3-12, D3-13, D3-15, D3-16, D3-17. Builds draft versions, project values, BOQ, engineer sign-off, issue and freeze, PDF.
3. **Slice 3c, specification choices.** Needs D3-08, D3-09. Builds options, OTP choice, override, decisions calendar once dates exist.
4. Then the RFQ pack (needs D3-19, D3-20), and only after that contractor sourcing, quotes and comparison.

Implementable now without any decision (not started, awaiting approval): the two ledger event columns. Everything else in Slice 3 depends on a decision above.
