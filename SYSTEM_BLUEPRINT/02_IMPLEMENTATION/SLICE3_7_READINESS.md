# Plan2Build: Slice 3.7 readiness (execution, assurance, handover, Build Record)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/SLICE3_7_READINESS.md` |
| Version | 1.1 (2026-10-06) |
| Status | **APPROVED FOR IMPLEMENTATION** (Chirag, 2026-10-06). EX-01 to EX-24 decided (section 0); EX-12's two day counts are new product and operations decisions. Where sections A to X differ from section 0, section 0 governs. Version 1.0 was readiness only. Slices 3.5 and 3.6 are CLOSED and not reopened; their production and hardening items stay tracked (section V) |
| Scope asked | Selected professional → execution and construction progress → assurance and inspections → handover → Build Record |
| Baseline | PD-01 to PD-27 (IHB 32.6); IHB 34 (PD-26); PRODUCT_FLOW_RECONCILIATION v2.0 (PFR); L-01 to L-08 and O-01 to O-10 (3.3); N-01 to N-12 (3.4); BP-01 to BP-20 with BP-07A deferred (3.5); QD-01 to QD-26 (3.6, QD-02 a new product decision); ADR-023, ADR-024 |
| Sources read | IHB_FLOW 8.9, 8.16 to 8.22, 9, 10, 12 to 15, 19, 22, 24 to 27, 32 to 34; PROFESSIONALS_FLOW (PRO) 6.7, 13 to 22, 28 to 30, 42 to 44; RECOMMENDATION_ENGINE (RE); STATE, DATA, API, DOMAIN, EVENT, SECURITY, INTEGRATION, TESTING, SYSTEM architecture; ADR-006, 008, 011, 018, 021, 023, 024; ARCHITECTURE_BASELINE (BASE); IMPLEMENTATION_CONTRACT (IC); FOUNDATION_PLAN (FP); SLICE3_READINESS (S3R), SLICE3_3 to SLICE3_6 readiness (S33 to S36) and the 3.5 and 3.6 implementation reports (S35IR, S36IR); every `SOURCE_OF_TRUTH` document read as text: Strategy and POC (STR, 21 Sep), MVP Build Plan (MVP, 24 Sep), Specification Schema (SCH), Technology Product Blueprint (TPB), Client Product and Implementation Blueprint (CPB), POC budget plans (POCB, PLAN), site copy (WEB), budget plans of 19 Sep (BUD), Transactional Verification Blueprints (TVB, FTB; older marketplace), meeting notes of 1 Oct (GEM); `PLAN2BUILD_USER_FLOWS.html` (FLOWS, 2 Oct), Client Review Changes (CRC, 3 Oct), Client Questions Round 2 (CQ2, 3 Oct, answers blank); the code as built through Slice 3.6 |
| Markers | **[SOURCE]** a source or approved architecture settles it. **[PD]** Chirag's decision (EX-01 to EX-24 decided 2026-10-06). **[PD NEW]** a new product or operations decision with no source value (EX-12 day counts). **[REC]** Sakha's recommendation, not approved. **[OPEN]** undecided. **[SUPERSEDED]** an older design overridden |

Citation forms: `IHB:1599` is IHB_FLOW.md line 1599; `STATE:330`, `DATA:234`, `API:214`, `DOM:217`, `EVENT:192`, `SEC:171`, `PRO:4126`, `PFR:270`, `S36:44` likewise. Original documents are cited by section (`MVP P6`, `SCH §4`, `CRC step 19`). MVP states that it supersedes "the earlier MVP functional specification"; TVB, FTB and BUD (19 and 20 Sep) describe the older marketplace and monitoring model and are cited only where nothing newer speaks. PD decisions outrank every source; the slice decisions outrank the architecture documents.

### Decision IDs

Questions in this document are **EX-01** onward; contradictions are **XC-01** onward (both prefixes unused elsewhere). Existing IDs are kept: CQ-11 to CQ-16, F-03, F-11, POQ-017, POQ-018, POQ-020, POQ-021, POQ-024, POQ-025, POQ-029, POQ-034, POQ-039, POQ-040, POQ-041, C-029, C-066, C-071, OQ-018, OQ-027, OQ-047, AQ-23, D-05, D3-08, D3-09, D3-19, D3-20. New hardening gaps are **H-07** onward.

### Governing chain

ACCEPTED Build Plan (3.5) and the CONTRACTOR engagement (3.4, or from a 3.6 selection) → stage-by-stage progress in the standard update format → gate inspections by an appointed independent auditor → findings, rectification, re-inspection → gate cleared → payment marks without amounts → final snag gate → handover with the homeowner's acknowledgement → an issued, versioned Build Record. Plan2Build records and assures; the contractor builds, supervises and is paid directly by the homeowner. [SOURCE] STR §8.3, CPB §4.5, MVP P5 to P8, SCH §4 and §9, CD-01, CD-05, CD-09, CD-11, CD-19, CD-21; [PD] PD-01, PD-17, N-02, N-03

---

## 0. Final decisions (Chirag, 2026-10-06)

### 0.1 Decision table EX-01 to EX-24

| ID | Decision | Marker |
|---|---|---|
| EX-01 | No project-level status movement during construction. Execution, stage, inspection, handover and Build Record states are separate records. SOURCING, CONTRACTED and BUILDING are not revived as the professional lifecycle | [PD] |
| EX-02 | A progress update holds the stage instance, the update type, a note and photos; optionally materials information and open problems. No percentage. For an OUTSIDE contractor, operations may enter the update. Updates are evidence and history, never a promise of schedule completion | [PD] |
| EX-03 | The owner confirms completion or returns the stage with a reason; operations may confirm with a recorded reason. A gate stage cannot complete until its gate is cleared. No automatic completion | [PD] |
| EX-04 | Until BP-07A: no authoritative stage ordering, behind-plan calculation, automatic delay attribution, calendar-based variance or authoritative construction dates. Progress is still recorded against stage instances | [PD] |
| EX-05 | An informational payment mark YES or NO per payment-milestone stage (the owner's "paid" and the contractor's "received"). No amount, contract value, milestone percentage, mismatch calculation or automatic block; no effect on stage completion or inspection; external payment-position information only | [PD] |
| EX-06 | Assurance is an optional package service, usable with a Plan2Build-selected contractor or the homeowner's outside contractor (answers F-11 for 3.7). Plan2Build stays an assurance and coordination layer | [PD] |
| EX-07 | One inspection per gate stage instance: Gate 3 one per slab instance, Gate 4 one per floor instance; never one global Gate 3 or Gate 4 inspection | [PD] |
| EX-08 | Gates 1 to 5: version 1 derived from the S04 "verified at" mapping. Gate 6: the appointed auditor and operations draft it, ADMIN publishes. Checklists are versioned configuration data, never text inside inspection logic | [PD] |
| EX-09 | ADMIN appoints auditors: unique identifier, appointment status, qualification and credential information, optional professional-site account. With an account: authenticated submission and a fresh confirmation where required. Without: operations capture the signed or submitted evidence. Auditors need not be Plan2Build professionals | [PD] |
| EX-10 | Offline capability is out of 3.7: online inspection screens only, no synchronisation | [PD] |
| EX-11 | Severity MINOR, MAJOR, CRITICAL. A defect closes only after an approved re-inspection confirms closure; never closed without that record. The original defect is immutable; corrections are separate records | [PD] |
| EX-12 | Two operations thresholds, configurable: a completion request unanswered for 3 calendar days; an inspection open for 7 calendar days. They create operations queue exceptions only; no reminders or countdowns | [PD NEW] |
| EX-13 | Capped remedy out of 3.7 | [PD] |
| EX-14 | Inspection report: plain-language main report plus technical appendix; fpdf2 (ADR-023); rendered only at operations approval; no AI findings; published reports immutable; a correction creates a new report record | [PD] |
| EX-15 | Handover requires Gate 6 cleared, zero open defects, required handover documents, warranties where applicable, and the owner's acknowledgement by one-time code. If the owner does not respond, operations may issue the handover record with reason, actor, time and audit event, never represented as the owner's acknowledgement | [PD] |
| EX-16 | No new specification lifecycle in 3.7. The Build Record may show inspection results relevant to lines; product, purchase and installation show NOT RECORDED. Completion is never inferred from inspection alone | [PD] |
| EX-17 | Build Record read by the OWNER and HOUSEHOLD only; deterministic PDF and JSON; no share link, no transfer; any correction is a new version; earlier versions stay readable | [PD] |
| EX-18 | Package required for scheduling an inspection, approving an inspection, issuing the Build Record. Free: progress updates, stage completion, payment marks, reading, the owner's acknowledgement. No new substantial-work trigger (QD-02 stays separate). Package inactive: inspections not yet started are cancelled; history and evidence stay readable; no new scheduling or approval | [PD] |
| EX-19 | History stays attached to the previous engagement and professional; a new contractor continues the same project and stages; nothing is recreated or rewritten; the transition is auditable | [PD] |
| EX-20 | The notification list of section O; no reminders, digests, countdowns or marketing; transactional and privacy-safe | [PD] |
| EX-21 | HOUSEHOLD is read-only; only the OWNER performs formal stage acknowledgement and handover acknowledgement | [PD] |
| EX-22 | Stored images have location metadata stripped; capture time and, where the device gives it, capture location are separate structured claims; EXIF is never authoritative; the file hash is of the final stored bytes | [PD] |
| EX-23 | An overdue defect creates an operations exception only: no automatic stage block, professional suspension or project status change | [PD] |
| EX-24 | Variations, specification choices, the issue log as a workflow, disputes and change orders are out of 3.7 (the following change and exception slice) | [PD] |

### 0.2 H-07 first

The file pipeline must persist the SHA-256 of the final stored bytes (after re-encoding). This is the first task, before 3.7A, with a regression test (upload, processing, storage, read back, recompute, equal) and updated documentation. [PD]

### 0.3 Structure

Three checkpoints, each green before the next starts (compile, migrations, API tests, browser tests, type, lint and import checks, previous-slice suites): 3.7A execution (with H-07), 3.7B assurance and inspections, 3.7C handover and Build Record. Only informational payment marks; no construction money path of any kind. Minimal functional UI. [PD]

---

## A. Current inventory

### A.1 What exists

| Area | As built | Use in 3.7 |
|---|---|---|
| Stage instances (`construction`) | Created at project ACCEPTED from the active stage master: 16 stages, stages 5, 6 and 9 once per floor (basement, ground, upper floors); `is_gate` and `gate_status` NOT_INSPECTED on gates (stages 3, 4, 6, 9, 10, 16); `is_payment_milestone` copied (stages 1, 3, 4, 6, 7, 10, 11, 13, 14, 16); `planned_start`/`planned_end` NULL; states declared NOT_STARTED, IN_PROGRESS, COMPLETION_REQUESTED, COMPLETED, BLOCKED, ON_HOLD; the transition table has only `instantiate`. No routes; read through `GET /projects/{id}/workspace`. No lifecycle trigger on the table | The execution backbone (sections D, E) |
| Stage masters (`catalog`) | Version 1 ACTIVE; durations and cost shares NULL (D-04) | Read only |
| Specification lines (`specification`) | 67 lines SPECIFIED; `consuming_stage_instance_id`; `accepted_value_id` (3.5); `decide_by` never set; `spec_line_events` append-only by grant only (no trigger); masters carry S04 `verified_at` text, which names the gate for 26 lines (Gate 1: 6, Gate 2: 3, Gate 3: 3, Gate 4: 13, Gate 5: 2) and the site log, delivery challan or second-fix check for the rest | Gate checklist source (F.4); no state change in 3.7 (EX-16) |
| Project status | Only DRAFT, SUBMITTED, NEEDS_INFO, ACCEPTED, CANCELLED are set; PLANNING through ARCHIVED are declared and never set | N-03, BP-14, QD-12: no move (EX-01) |
| Memberships | Only OWNER rows; roles CONTRACTOR, ARCHITECT, OPS_ADVISOR, OPS_FIELD, AUDITOR_ASSIGNED declared, unused | Not used (section N) |
| Engagements | One ACTIVE per category; origin CONNECTION, OUTSIDE, RFQ_SELECTION; contacts; `/pro/engagements/{id}` with contact, pin, shared files | The contractor of record for progress (D.2) |
| RFQ selection | `selections` (no contract value); `quote_versions.duration_days` and `stage_durations`; nothing exported through `rfq.interface` | Read-only reference for the contractor's own durations (E.3) |
| Build Plan | Accepted version and manifest through `buildplan.interface`; schedule entries per stage instance with durations, dates CHECK NULL; drawings readable by a contractor only through the RFQ pack route | The contractor's reference documents (J) |
| Documents | Purposes include DRAWING, BUILD_PLAN_*, QUOTE_ATTACHMENT, COMPARISON_DOCUMENT; scan pipeline; images re-encoded by Pillow (EXIF stripped); logged links; `store_generated_file` for server PDFs | New purposes for evidence, reports, handover and the Build Record (J) |
| Billing | `package_active`, `package_state`; usage kinds CONNECTION_ACCEPTED and RFQ_SELECTION (closed CHECK) | Gating (L) |
| Identity | StaffRole OPS and ADMIN only; OTP purposes LOGIN, ACCEPT_BUILD_PLAN, SIGN_STRUCTURAL, SELECT_QUOTE; versioned statements pattern (sign-off, acceptance, selection) | Auditor access (EX-09); handover acknowledgement (EX-15) |
| Operations | Queues REQUIREMENT_REVIEW and PROFESSIONAL_REVIEW (CHECK); the ops project page has no stages | New queue kinds (EX-12) |
| Not existing | Any table, route or code for progress updates, inspections, checkpoints, findings, non-conformances, payment marks, variations, issues, handover, warranties, Build Record | Built here or deferred (C.3) |

### A.2 Gaps found in passing

| ID | Gap | Placement |
|---|---|---|
| H-07 | `documents.process_file` stores `sha256` of the uploaded bytes, while the stored object for an image is the re-encoded file: for images the recorded hash does not match the stored bytes | **A dependency of 3.7** (inspection evidence, report and Build Record hashes rely on file hashes): fix in 3.7 step 1, not deferred (section W) |
| H-08 | `spec_line_events` is append-only only by grant; no trigger | Fix with 3.7 if lines are touched (EX-16); otherwise hardening |
| H-09 | `stage_instances` has no lifecycle guard trigger | Added in 3.7 when stages start moving |
| H-10 | Architecture drift: EVENT:182 "payment due with amount" (contradicts CD-09); API §19 and DOM §6.4 move projects to CONTRACTED/BUILDING (contradicts N-03); DOMAIN lists `variation_discussions` and `payment_marks` tables absent from DATA; DOM:183 cites STATE §7 for stage authority (it is §6) | Documentation correction when 3.7 is implemented |

---

## B. Source reconciliation

### B.1 Precedence used

PD decisions → slice decisions (L-, O-, N-, BP-, QD-) → IHB 34 → PFR v2.0 → client decisions CD-01 to CD-24 (CD-25 to CD-28 proposed) → CRC and CQ2 (3 Oct, newest client notes; CQ2 answers blank) → architecture documents → original sources (MVP and later) → TVB, FTB, BUD. [SOURCE] IHB:4116, IHB:4117, IHB:4290

### B.2 Contradictions (none silently resolved)

| ID | Contradiction | Governs now | Consequence for 3.7 |
|---|---|---|---|
| XC-01 | **Project status during execution.** STATE §5 moves CONTRACTED → BUILDING ("first stage started") → HANDOVER_PENDING ("Gate 6 cleared") → COMPLETED ("record issued") → ARCHIVED; API §19, DOM §6.4 and EVENT 4.5 rely on it. N-03 supersedes SOURCING, CONTRACTED and BUILDING as the professional lifecycle; BP-14 and QD-12 move no project status | N-03, BP-14, QD-12 for SOURCING to BUILDING. HANDOVER_PENDING and COMPLETED are not professional states and are not addressed by N-03 | EX-01: whether any project status moves in 3.7. [REC] none; the stage, handover and Build Record states are the record |
| XC-02 | **Who records progress.** IHB A-J16-01 (L1454): UNKNOWN; MVP C1 "Deliberately thin" (no progress posting); FLOWS Path A has no update step; PRO POQ-020 narrowed (PRO:4015) and PRO 44.2 P22: the professional posts updates in the standard format (CD-19); PLAN includes "project updates" | CD-19 (one standard format set by Plan2Build) with PRO 43.3 narrowing; format CQ-11 open | EX-02 |
| XC-03 | **Stage completion approval.** PRO 44.2 P24: "the homeowner approves it or raises an issue [S]"; IHB 13.1 (L2647): approve milestones "Not present" in D2; PRC-10 superseded optional milestone approval; STATE §6 default: homeowner confirms, operations may with reason (PC-023 open) | No decision (POQ-034 open) | EX-03 |
| XC-04 | **Dates and order.** STATE §6, EVENT `sweep_schedule`, `stage_behind_plan`, decide-by deadlines and variations updating completion dates all need planned dates; BP-07A defers the canonical order and all date calculation; S35 A.2: `sequence` is display order, not build order | BP-07A [PD] | No planned dates, no behind-plan feed, no ordering guard from `sequence` (EX-04) |
| XC-05 | **Payment recording.** MVP P7 and CPB §12: amounts, "paid to date", "due now"; CD-09 and CRC step 20: optional, yes or no, no amount; CQ2 Q1 asks to confirm; EVENT:182 "with amount" | CD-09 [SOURCE, client decision]; IC §6.8 and §23.8 forbid any homeowner-to-professional payment amount | Marks only (EX-05); EVENT:182 is drift (H-10) |
| XC-06 | **Contract value.** CQ-13 asks to confirm the money position shows the contract value and approved change costs; MVP P5/P7 update a running contract value; QD-12 records none in 3.6; IC:91 forbids "a payment amount between homeowner and professional" | QD-12 for selection; CQ-13 open; whether a contract value is a forbidden "payment amount" is unresolved (IC:36, IC:39 stop-and-report) | Not recorded in 3.7 (EX-05) |
| XC-07 | **Assurance in the package.** CD-05: "Stage inspections are part of the single package"; CRC step 9 (newest client note): "Quote review, comparison, stage checks and assurance are offered separately"; PD-17/PD-20: no service mandatory; IHB 34 row 15 "Where applicable"; F-11 (outside contractor) open | PD-19 (assurance is a package service), PD-20 (never mandatory); F-11 open; CRC vs CD-05 on separate sale is a commercial question (one package, PD-09) | EX-06 |
| XC-08 | **Number of inspections.** "Six gates" (STR, MVP, WEB, CD-24 tick) vs Gate 3 "each slab" (SCH §4) and Gate 4 on stage 9, which repeats per floor (IHB:972 DERIVED); POQ-040 open | No decision | EX-07 |
| XC-09 | **Checkpoint lists.** No source gives a checkpoint list (MI-027, D-05); SCH §1: the schema "is the audit checklist at each inspection gate", and each line's "Verified at" names a gate (26 lines map to Gates 1 to 5; none names Gate 6) | SCH §1 [SOURCE] for Gates 1 to 5; nothing for Gate 6 | EX-08 |
| XC-10 | **Auditor identity and channel.** Sources: an independent consultant retained per inspection (STR §7.3, FLOWS), unique ID as an entity (CD-21; CQ-15 open), a native React Native app (TPB §1, PRO:344); ADR-021: an offline PWA on the professionals host; README default "Category AUD profile" (no such category exists, PD-18 categories) | ADR-021 (architecture, proposed) over the channel; CQ-15 open | EX-09, EX-10 |
| XC-11 | **Non-conformance closure.** MVP P6, CPB §6, PLAN §3: only by a re-inspection record with evidence and sign-off; TPB §5.3: "closed by authorised reviewer"; FLOWS: both, "rule still to be confirmed"; STATE: re-inspection, reviewer closure behind a flag, default off | C-066 open | EX-11 |
| XC-12 | **Result vocabulary.** MVP: pass, observation, non-conformance; TPB: plus not-applicable; FLOWS: pass or not applicable, observation, defect; FTB (older): Scheduled, Completed, Failed, Passed, Follow-up | TPB and STATE §13 (the newest complete list) | PASS, OBSERVATION, NON_CONFORMANCE, NOT_APPLICABLE [SOURCE] |
| XC-13 | **Severity scale.** None in any source for non-conformances; TVB's low to critical is for issues; DATA design MINOR, MAJOR, CRITICAL; PRO 44.8 "critical structural non-conformance" | No decision | EX-11 |
| XC-14 | **Evidence metadata.** MVP P6: "Photographs are geotagged and timestamped at capture, and the sequence cannot be backdated"; DATA: inspection evidence "EXIF kept" (P3); INTEGRATION and as built: images re-encoded, EXIF stripped | The pipeline (privacy) as built; MVP P6 for the integrity requirement | Capture metadata stored as separate claims, the file stays stripped (EX-22) |
| XC-15 | **Handover acceptance.** IHB A-J22-02: "D2 has no formal homeowner handover acceptance"; TVB §15.1 and FLOWS §2 step 16: the homeowner accepts; CQ2 Q4 asks whether both parties confirm the final payment | No decision | EX-15 |
| XC-16 | **Build Record access.** MVP P8 and FLOWS step 24: "readable without a Plan2Build account and transferable to a new owner"; BP-16 and QD-23: no public share link so far; OQ-047 (token expiry) open | No decision for the Build Record | EX-17 |
| XC-17 | **Build Record line content.** SCH §9 per line: product chosen, purchase evidence, installation date, verification result, warranty, installer; these need the CHOSEN, PURCHASED and INSTALLED states, whose options flow (D3-08, D3-09), OTP at CHOSEN and recorder (POQ-021) are open, and CQ2 Q8 drops material supply | SCH §9 for content; D3-08, D3-09, POQ-021 open | EX-16: the record shows what exists and leaves the rest blank, labelled |
| XC-18 | **Six-state visibility.** SCH §2 and STR §3.4: the homeowner sees only the first three line states; TPB matrix and FLOWS 18: the homeowner sees all six | C-029 open | Only relevant if EX-16 brings line states into 3.7 |
| XC-19 | **Variations.** CD-08 and CRC step 19 (newest): Plan2Build qualifies and quantifies, OTP acknowledgement, no decline, discussion then closure; MVP P5: the raiser states impact, the running contract value and completion date update; CQ-12 (window, closure authority, acknowledge before work) and C-071 open | CD-08 for the shape; CQ-12 open; contract value and dates blocked by XC-04 and XC-06 | EX-24: variations out of 3.7 |
| XC-20 | **Issue log.** CD-10 and CRC step 22: the homeowner issue log at the MVP (raise, fix with proof, verify, close); its states (C-022) and dispute steps (C-023) open | CD-10 for inclusion in the product | EX-24: placement |
| XC-21 | **Capped remedy.** STR §3.3, FLOWS step 21: Plan2Build pays to fix a structural defect it cleared, capped; terms OQ-018 open; TPB §18.1 founder decision | Not decided | EX-13: not in 3.7 |
| XC-22 | **Substantial work.** S33 E and O-04 [REC] and S34 N recommendation name "first inspection"; decided N-12 and QD-02 are a closed set without it | N-12, QD-02 [PD] | No inspection usage record unless Chirag adds one (EX-18) |
| XC-23 | **Inspection reports and AI.** TPB §12, CPB §20: AI may draft plain-language wording only under human review; never pass or fail decisions; IC §18.6: no language model at the POC | IC §18.6 | No AI in 3.7 |
| XC-24 | **Club consequences.** STATE §13, DOM 3.8, EVENT: a critical NC past due or a lost dispute triggers a Club review; PD-18: the Club is a label | PD-18 | No automatic listing consequence in 3.7 (EX-23) |
| XC-25 | **Retention.** SCH §4: stage 16 "retention release"; FLOWS step 23: "The retention, the last stage payment, falls due here"; no percentage or hold period anywhere | CD-09 (no amounts) | The stage 16 milestone is the retention mark, without amount |

---

## C. Product model

### C.1 Boundary

| Rule | Marker |
|---|---|
| The contractor executes, supervises and carries execution risk and liability; Plan2Build never takes the contract, never becomes the contractor and never guarantees execution | [SOURCE] STR §8.3, CPB §4.5, WEB, FLOWS A9; [PD] PD-01 |
| Plan2Build records progress the parties report, assures gate stages through an independent auditor, records payment marks without amounts, coordinates handover and issues the Build Record | [SOURCE] MVP P6 to P8, CD-05, CD-09, CD-11, CD-19 |
| Construction money moves directly between homeowner and contractor; no amount, gateway, escrow, settlement or milestone payment processing exists | [SOURCE] CD-01, CD-09; [PD] PD-01; IC §23.8 |
| Commercial terms are the parties'; Plan2Build changes none of them and records no contract value in 3.7 | [PD] QD-12; [PD] EX-05 |
| An inspection reports what was inspected at a gate; it is not a certificate of the whole building, and no legal completion certificate is issued | [SOURCE] MVP P6 ("a pass status against the gate"); [REC] wording rule |
| Every service stays optional and per category; a family may use an outside contractor | [PD] PD-17, PD-20 |

### C.2 What 3.7 builds [REC, subject to section U]

1. **Execution tracking:**
   - the stage instances begin to move;
   - progress updates in the standard format, from the engaged contractor (or operations for an outside contractor);
   - completion requests and the completion decision.
2. **Payment marks** without amounts on the payment-milestone stages.
3. **Assurance:**
   - auditor appointments;
   - versioned gate checklists;
   - inspections scheduled by operations and performed by the auditor;
   - findings and non-conformances;
   - rectification and re-inspection;
   - operations approval;
   - a deterministic report PDF;
   - gate clearance.
4. **Handover:**
   - after the final snag gate clears;
   - handover documents and warranty entries;
   - the homeowner's acknowledgement with a one-time code.
5. **The Build Record:** assembled from existing records, issued as an immutable version with a PDF and a JSON export, corrected only by a new version.

### C.3 Not in 3.7 [REC]

| Item | Why | Marker |
|---|---|---|
| Variations | Window and closure authority CQ-12, acknowledge-before-work C-071, contract value XC-06 and completion dates XC-04 open | EX-24 |
| Specification choices (options, OTP at CHOSEN) and PURCHASED/INSTALLED recording | D3-08, D3-09, POQ-021, AMB-020 open; CQ2 Q8 drops supply | EX-16 |
| Homeowner issue log and disputes | CD-10 decided for the product; states C-022 and dispute steps C-023 open; a separate "change and exception" workflow | EX-24 |
| Offline auditor PWA (ADR-021) | Large separate capability; 3.7 proves the inspection model online first | EX-10 |
| Capped remedy | Terms OQ-018 open | EX-13 |
| Post-handover back office, transfer to a new owner, renovation and resale opt-ins | CQ-16 open; transfer OTP TRANSFER not built | EX-17 |
| Recommendation signals from audit data (RE) | QD-10 deferral | [PD] QD-10 |
| Exception feed items that need dates (stage behind plan, overdue decisions) | BP-07A | [PD] BP-07A |

---

## D. Execution lifecycle

### D.1 Records

| Question | Answer | Marker |
|---|---|---|
| Separate execution record | No new execution entity. The project's stage instances (created at ACCEPTED) are the execution record; their states move in 3.7. No project status moves | [PD] EX-01; [PD] N-03 |
| Engagement lifecycle | Unchanged: ACTIVE → ENDED. No execution state is added to engagements | [PD] N-02, N-03, ADR-024 |
| Who the contractor of record is | The ACTIVE CONTRACTOR engagement at the time of each action; every progress update, completion request and rectification records that engagement id | [REC]; [SOURCE] PFR:227 ("updates ... reference an engagement or a category") |
| Starting execution | The first progress update on a stage moves it NOT_STARTED → IN_PROGRESS; nothing else "activates" a project | [SOURCE] STATE §6; [REC] |
| Contractor changes mid-build (POQ-018, POQ-029) | Ending the engagement (3.4) stops that contractor's access; history stays with its engagement id; a new CONTRACTOR engagement continues on the same stages | [PD] EX-19 |
| No contractor engaged | Stages stay readable; no update can be posted; inspections can still be scheduled where the homeowner uses assurance (F-11) | [PD] EX-06 |

### D.2 Who acts

| Actor | Execution actions | Marker |
|---|---|---|
| Engaged LISTED contractor | Post progress updates, request completion, mark payments received, submit rectification evidence | [SOURCE] CD-19, CD-09, PRO 44.2; [PD] EX-02 |
| Engaged OUTSIDE contractor | No account (F-03); operations post updates and rectification evidence on its behalf, with the evidence it supplies, as in QD-22 | [PD] QD-22 pattern; [REC] |
| Owner | Read; confirm or return a completion request (EX-03); mark payments paid; acknowledge handover | [PD] EX-03; [SOURCE] CD-09 |
| Household | Read only | [REC]; OQ-027 open |
| Operations | Post on behalf; confirm completion with a reason where the owner does not (EX-03); schedule and approve inspections; open handover; issue the Build Record | [SOURCE] IHB 13.1a "Configure / monitor", "Assign / approve / audit" |
| Auditor | Perform assigned inspections only | [SOURCE] IHB 13.1a "Assigned gate" |

---

## E. Progress tracking

### E.1 The standard update (CD-19; contents CQ-11 open)

| Field | Rule | Marker |
|---|---|---|
| Stage instance | Required (MVP rule 1: every log entry carries a stage instance) | [SOURCE] MVP rule 1 |
| Kind | PROGRESS or COMPLETION_REQUEST | [SOURCE] STATE §6, DATA:222 |
| Note | Required free text | [REC] |
| Photos and documents | Up to a configured number of scanned files (STAGE_EVIDENCE); at least one for a completion request | [SOURCE] STATE §6 ("with evidence"); [REC] count |
| Materials used | Optional free text | [SOURCE] CQ2 Q4 proposed contents; [PD] EX-02 (CQ-11 stays a client question) |
| Open problems | Optional free text (not an issue log, EX-24) | [REC] |
| Progress percentage | Not collected. No percentage is computed or shown | [REC] (no source defines milestone weights; TVB's "never manually editable without an audit record" is the older model) |
| Dates | The server time of the update; the stage's actual start is the first update and actual end the completion | [SOURCE] STATE §6 |

[PD] EX-02 approves this format for 3.7. CQ-11 (the client's view of the contents) stays a client question; an answer becomes a new decision, not an edit of history.

### E.2 Planned versus actual

- **Planned:** no planned date exists (BP-07A). The planned side is the accepted Build Plan's durations and dependencies, plus the contractor's quoted total and stage durations (3.6, QD-18). Both are shown as durations, never converted to dates. [PD] BP-07, BP-07A, QD-18.
- **Actual:** actual start and end dates come from updates and the completion. [SOURCE] STATE §6.
- **Behind plan:** no "behind plan" flag or exception exists, and no delay attribution. Delay cause categories are undefined (MI-024) and belong with variations. [PD] BP-07A; [PD] EX-04.

### E.3 Order between stages

No ordering guard: any stage may start. Stage `sequence` is display order, not build order (S35 A.2), and the canonical order is BP-07A. Explicitly entered predecessors from the accepted Build Plan are shown, not enforced. [PD] BP-07A; [PD] EX-04

### E.4 Delays, exceptions, revisions

- **Delays:** an update may say the stage is delayed, as free text only. [REC]
- **Exceptions in 3.7:**
  - a completion request waiting longer than a configured number of days;
  - an inspection IN_PROGRESS longer than a configured number of days;
  - a non-conformance past its due date.
- The configured values come from Chirag. [PD] EX-12.
- **Revisions:** an update is never edited. A correction is a new update that names the one it corrects. [SOURCE] STATE rule 1 ("ledger"), TPB §3.2 (tamper-evident).
- **Audit:** every update and every transition writes an audit row and an execution event row. [SOURCE] STATE rule 4.

---

## F. Assurance and inspection model

### F.1 Scope and availability

| Question | Answer | Marker |
|---|---|---|
| What assurance is | Independent inspection of gate stages against a versioned checklist, with a plain-language report and a tracked non-conformance register | [SOURCE] MVP P6, CPB §6 |
| Package | Scheduling an inspection needs an ACTIVE package; the family may choose not to use assurance | [PD] PD-19, PD-20; [PD] EX-06 |
| Outside contractor (F-11) | Available whoever the contractor is | [PD] EX-06 (answers F-11 for 3.7) |
| Gates | Gate 1 stage 3 (pre-pour), Gate 2 stage 4 (plinth beam), Gate 3 stage 6 (pre-pour, each slab), Gate 4 stage 9 (pre-plaster, concealed services), Gate 5 stage 10 (waterproofing, ponding test), Gate 6 stage 16 (snag) | [SOURCE] SCH §4 |
| Inspections per gate | One per gate stage instance: Gate 3 per slab and Gate 4 per floor, as the stage instances already exist | [PD] EX-07 (answers POQ-040) |

### F.2 Triggers

- **Gate stages:** a completion request on a gate stage puts the stage in the operations assurance queue. Operations schedule the inspection: appointed auditor, checklist version, date as free text or a date the auditor agrees. [SOURCE] STATE §6, EVENT:171, FLOWS auditor step 1.
- **Earlier inspections:** operations may also schedule an inspection before a completion request, for example at the contractor's readiness notice. [SOURCE] FLOWS auditor step 3, "confirms the stage is ready"; POQ-024 open (who declares readiness).
- **Homeowner requests:** the homeowner cannot book or schedule inspections. [SOURCE] IHB 13.1 "Book or schedule inspections … No (operations schedule gates)".

### F.3 The auditor

| Question | Answer | Marker |
|---|---|---|
| Who | An independent engineer retained by Plan2Build, paid per inspection, unconnected to local business partners; not the structural engineer who signs the Build Plan | [SOURCE] STR §7.3, FLOWS auditor box, S3R:93 |
| Record | An auditor appointment (like the 3.5 drawing checker, BP-01): name, qualification and registration reference, unique auditor ID (CD-21), optional linked account, appointed and ended by ADMIN | [PD] EX-09; (answered for 3.7) CQ-15 (person or firm, where the ID appears) |
| Account | A linked account on the professionals host, with access only to the inspections assigned to the appointment | [PD] EX-09; [SOURCE] ADR-021 (professionals host) |
| Confirmation | A fresh one-time confirmation code (purpose SUBMIT_INSPECTION) for an auditor with an account; the professionals host has no authenticator | [PD] EX-09 (answers AQ-23 for 3.7) |
| Blindness | Never sees supplier, brand, product, homeowner contact, prices or any commercial data | [SOURCE] MVP rule 9, BR-122, SEC:171 |
| Without an account | Operations enter the inspection from the auditor's signed report (evidence file), recorded as staff capture | [REC]; BP-01 and QD-22 pattern |

### F.4 Checklists

- **Configuration:** a versioned gate checklist, prepared by operations and published by ADMIN, like rate cards (BP-06). Each checkpoint has a gate, text, an expected evidence type, a critical flag, and an optional specification line code. [SOURCE] TPB §10 ("Gate checklist templates are versioned"), DATA `checkpoint_masters`; [REC] process.
- **Version 1, sourced part:** each specification line whose S04 "verified at" names a gate becomes a checkpoint of that gate. Its criteria come from the accepted value, plus the named test where given (cube test, mill test certificate, ponding test, resistance test, pressure test, against drawing). [SOURCE] SCH §1 ("is the audit checklist at each inspection gate").
- **Version 1, missing part:** Gate 6 (snag) has no sourced checkpoint, and no source gives further checkpoints for any gate. Without approved content there is no production inspection. [PD] EX-08.
- **Evidence the auditor never sees:** brand categories and chosen products. [SOURCE] BR-122.

### F.5 Inspection, findings, outcome

| Step | Rule | Marker |
|---|---|---|
| Readiness | The auditor confirms the stage is ready and the checklist version | [SOURCE] FLOWS auditor step 3, TPB §5.3 |
| Checkpoints | Each result PASS, OBSERVATION, NON_CONFORMANCE or NOT_APPLICABLE (with a reason); a note; photos and measurements | [SOURCE] TPB §5.3, STATE §13 |
| Non-conformance | Severity, description, corrective action required, owner (the contractor of record), due date, evidence | [SOURCE] TPB §7, FLOWS auditor step 4; severity scale [PD] EX-11 |
| Tests | Cube test results at 7 and 28 days attach later to the right pour, as a later record on the same inspection's checkpoint, never by editing it | [SOURCE] MVP P6; [REC] mechanism |
| Concealed services (Gate 4) | Photos tagged by room, kept for the Build Record's as-built concealed services map | [SOURCE] MVP P8, SCH §9 |
| Submission | The auditor submits; the server freezes the inspection and hashes its content (checkpoints, findings, evidence hashes); later corrections are new amendment records | [SOURCE] MVP P6, TPB §5.3, BR-123 |
| Approval | Operations (MFA) approve or return; approval opens the non-conformances, renders the plain-language report PDF with the technical appendix, shares it with the homeowner, and gives the contractor its findings | [SOURCE] FLOWS auditor step 7, IHB:1668 |
| Gate outcome | Gate CLEARED when an approved inspection of the stage instance has no OPEN non-conformance; "passed with observations" clears | [SOURCE] STATE §13, IHB:1692 |
| Conditional pass | Not a separate state: observations do not block, non-conformances do | [SOURCE] IHB:1692 |
| Acknowledgement | No homeowner or contractor acknowledgement of findings in 3.7 | [REC] within EX-20 and EX-21 (F-113, AMB-046 stay for later) |
| Escalation | A non-conformance past its due date goes to the operations exception list; no automatic stage block and no listing consequence | [PD] EX-23; [SUPERSEDED] Club triggers (PD-18) |
| AI | None | [PD] IC §18.6 |

---

## G. Corrective actions

| Step | Rule | Marker |
|---|---|---|
| Owner | The contractor of record (or operations for an OUTSIDE contractor) submits rectification evidence (photos, note) per non-conformance | [SOURCE] IHB 13.1a "Respond to findings", DOM 3.13 |
| Re-inspection | Operations schedule a re-inspection of the open set (a new inspection record that names the original) | [SOURCE] STATE §13, MVP P6 |
| Closure | Only by an approved re-inspection whose checkpoint result for that finding is PASS, with evidence and the auditor's submission; reviewer closure off | (answered for 3.7) C-066; [PD] EX-11 (MVP governs) |
| Original finding | Immutable; the closure is a separate record | [SOURCE] TPB §5.3, STATE §13 |
| Homeowner | Cannot close a non-conformance | [SOURCE] NP-10 |
| Failed re-inspection | The finding stays OPEN with the new evidence; another rectification cycle follows | [REC] |
| Due date | Set by the auditor at the finding; extended by operations with a reason (recorded) | [REC] |

---

## H. Handover

| Question | Answer | Marker |
|---|---|---|
| What handover is | The close of the project's execution record after the final snag gate: Gate 6 (stage 16) CLEARED, handover documents recorded, the homeowner's acknowledgement | [SOURCE] SCH §4, FLOWS step 23, MVP P8; [PD] EX-15 |
| Snag list | The Gate 6 inspection's findings are the snag list; they close by re-inspection like any non-conformance | [SOURCE] SCH §4 (Gate 6 snag); [REC] |
| Outstanding items | Non-conformances still OPEN block handover; observations are listed in the handover | [PD] EX-15 |
| Documents | Warranties (item, term, expiry, installer; optional line code), manuals, final drawings, certificates the contractor holds, completion photos: uploaded by the contractor or operations (HANDOVER_DOCUMENT) | [SOURCE] MVP P8 ("Every warranty carries its term, expiry and installer"), TVB §15.1, FTB §13; [PD] EX-15: operations confirm that the documents required for the project are recorded (a contractor-specific list, POQ-025, stays a client question) |
| Retention payment | The stage 16 milestone's marks, yes or no, no amount; never blocks handover | [SOURCE] CD-09, FLOWS step 23; [PD] EX-05 |
| Homeowner acknowledgement | The owner confirms with a one-time code a versioned acknowledgement statement ("I acknowledge handover of project $code ... recorded by Plan2Build; this is not a completion certificate ...") | [PD] EX-15 (D2 defines none; D1 and FLOWS §2 have acceptance); [REC] |
| Contractor confirmation | None required; the contractor is told | [PD] EX-15 |
| Legal completion certificate | None | Chirag's instruction; [REC] |
| Project status | No move (EX-01) | [REC] |

---

## I. Build Record

### I.1 Authoritative content (issued, frozen) [SOURCE] MVP P8, SCH §9, CPB §13

| Section | Content | Source of truth |
|---|---|---|
| Identity | Project code, locality, plot facts, owner name as on the account | projects |
| Plan | The accepted Build Plan version(s) with version numbers and content hashes, and the accepted document references | buildplan |
| Drawings | The drawing set of the last accepted version with file hashes | buildplan |
| Specification | The 67 lines with the accepted values and, where recorded, verification results from inspections; product, purchase evidence and installation fields shown as "not recorded" until the choices slice exists | specification, assurance (EX-16) |
| Contractor | The CONTRACTOR engagements (names, firm, start and end, origin); "Chosen by the family" label for an OUTSIDE party | engagements; [SOURCE] PRO 44.8 |
| Execution | Each stage instance's actual start and completion; update count and evidence references (not every photo inline) | construction |
| Assurance | Every approved inspection (gate, date, auditor ID, result, report hash), non-conformances with closure records | assurance |
| Concealed services | Gate 4 room-tagged photos per floor | assurance |
| Payment marks | Per milestone: marked paid and received, yes or no, with times; no amounts | money |
| Handover | Documents, warranties (term, expiry, installer), the acknowledgement record | records |

### I.2 Linked history (not frozen into the record, reachable through links)

- RFQ invitations, quote versions and comparisons (commercial, P1).
- Every progress update photo.
- Clarifications.
- Ops notes and audit events.

[REC]: the record names the selected quote version only, without prices, because quote prices are the homeowner's commercial data and not part of a transferable house record.

### I.3 Form

- **What is issued:** a snapshot JSON (schema-versioned) and its sha256, a deterministic fpdf2 PDF, and a JSON export file. [SOURCE] MVP P8 ("PDF plus structured data"); [PD] ADR-023.
- **Assembly:** automatic from records. There is no manual compilation step, only an issue action by operations with MFA. [SOURCE] MVP P8.
- **Never sold separately; free.** [SOURCE] MVP P8, SCH §9, C-062 narrowed.

---

## J. Documents and evidence

| Document | Purpose (new unless noted) | Producer | Rules | Marker |
|---|---|---|---|---|
| Progress evidence | STAGE_EVIDENCE | Contractor (presigned, pro host) or operations (raw-body route) | Project-scoped; scanned; logged links; never edited | [REC] |
| Inspection evidence | INSPECTION_EVIDENCE (P3) | Auditor (pro host) or operations | Scanned; EXIF stripped in the stored file; capture time and location stored as claims beside it (EX-22); links 5 minutes; frozen with the inspection | [SOURCE] DATA P3, SEC; [PD] EX-22 |
| Rectification evidence | STAGE_EVIDENCE | Contractor or operations | As progress evidence | [REC] |
| Inspection report | INSPECTION_REPORT | Server, at approval | fpdf2, deterministic, sha256; never re-rendered; amendments produce a new report version | [PD] ADR-023; [SOURCE] BR-123 |
| Drawings used during execution | DRAWING (existing) | Build Plan | The engaged contractor and the assigned auditor get logged links to the accepted version's drawings (the auditor's without brand data) | [REC]; closes the gap in A.1 |
| Handover documents | HANDOVER_DOCUMENT | Contractor or operations | Scanned; part of the Build Record | [REC] |
| Build Record | BUILD_RECORD_DOCUMENT (PDF) and BUILD_RECORD_EXPORT (JSON) | Server, at issue | fpdf2 PDF; JSON export; sha256; immutable per version | [PD] ADR-023; [REC] |

Every file:
- has a project scope and an owner;
- is accessed only through authenticated, logged short links;
- is scanned before it is available;
- is never overwritten.

Generated documents are stored once. H-07 is fixed first, so that recorded hashes equal the stored bytes. [SOURCE] ADR-006, ADR-011, IC §11

---

## K. Versioning and immutability

| Record | Changes | Frozen | Marker |
|---|---|---|---|
| Progress updates | Never edited; corrections are new updates | From creation | [SOURCE] DATA:222 append-only |
| Stage instances | Lifecycle columns only (state, actual dates, version) | COMPLETED is terminal; operations may move one state back with a reason (STATE rule) | [SOURCE] STATE §1, §6 |
| Inspections | Draft content while IN_PROGRESS | From SUBMITTED (hash); amendments are new records | [SOURCE] BR-123, MVP P6 |
| Checkpoint results, findings, evidence links | Written while IN_PROGRESS | With the inspection | [SOURCE] STATE §13 |
| Non-conformances | State, due date (by operations with reason) | The finding text, severity and evidence never change | [SOURCE] STATE §13 |
| Payment milestones | Marks are set once each (paid, received) | SETTLED is terminal; a mistaken mark is reversed only by operations with a reason, recorded | [REC] |
| Checklists, statements | DRAFT editable | PUBLISHED or ACTIVE immutable | [SOURCE] BP-06 pattern |
| Handover | Documents added until acknowledged | ACKNOWLEDGED freezes it | [REC] |
| Build Record | DRAFT re-assembled at will | ISSUED immutable; a correction issues a new version and the earlier becomes SUPERSEDED, still readable | [PD] EX-17; [SOURCE] DATA:252 |

---

## L. Package and refund behaviour

| Question | Answer | Marker |
|---|---|---|
| Substantial work | Unchanged: N-12 (connection accepted) and QD-02 (RFQ selection). No inspection or Build Record usage kind | [PD] N-12, QD-02; [PD] EX-18 if Chirag wants inspections to count |
| Package-gated in 3.7 | Scheduling inspections, approving inspections, issuing the Build Record | [PD] PD-19 (assurance a package service); [PD] EX-18 |
| Not gated | Progress updates, completion decisions, payment marks, reading anything, the homeowner's acknowledgement | [PD] EX-18 (the family's own project record, PD-03 free dashboard; recording continues after a refund as engagements do, N-10) |
| Package REFUNDED or CANCELLED | SCHEDULED inspections not yet started are cancelled (PACKAGE_ENDED); IN_PROGRESS ones may be submitted and approved; approved records, reports and an issued Build Record stay readable; open non-conformances stay open and visible; no new inspection | [PD] EX-18; QD-14 and BP-09 patterns |
| Active engagement | Continues (N-10) | [PD] N-10 |
| Build Record after a refund | [REC] the last issued version stays readable; a new version is not issued while inactive | [PD] EX-18 |
| Late instalment | No effect (no LAPSED state) | [SOURCE] S33 O-03 as built |

---

## M. Money boundary

| Rule | Marker |
|---|---|
| No construction payment collection, settlement, escrow or milestone payment processing; no gateway call | [SOURCE] CD-01, INTEGRATION:33; IC §23.8 |
| No amount column for any homeowner-to-contractor payment; no contract value in 3.7; no "paid to date" or "due now" | [SOURCE] CD-09; [PD] QD-12; [PD] EX-05 |
| Payment milestones are the stage master's flags (stages 1, 3, 4, 6, 7, 10, 11, 13, 14, 16); a milestone shows as due (derived, informational) once its stage is COMPLETED | [SOURCE] SCH §4, MVP P7, BR-108 |
| Marks: the owner's "paid" and the contractor's "received" mark, each YES or NO with actor and time, recorded as append-only entries (the latest is current); recording is optional and never blocks anything; no SETTLED state | [SOURCE] CD-09, CRC step 20; (answered for 3.7) CQ-13 (whether it waits; mismatch); [PD] EX-05 |
| Outside contractor: the owner's mark only, or operations record the contractor's confirmation | [REC] |
| Mismatch: no calculation or flag | [PD] EX-05 |
| Billing tables never reference a milestone or stage (L-06, import linter) | [PD] L-06 |

---

## N. Permissions and security

### N.1 Matrix

| Action | Owner | Household | Engaged contractor | Auditor (assigned) | Operations | Admin |
|---|---|---|---|---|---|---|
| Read stages, updates, inspections (approved), handover, Build Record | Yes | Yes | Own project's stages, own updates, own findings, handover | Assigned inspection's stage and checklist only | Yes | Yes |
| Post update, request completion | No | No | Yes (engaged CONTRACTOR, ACTIVE) | No | On behalf, with reason | Same |
| Confirm or return completion | Yes (EX-03) | No | No | No | With reason (EX-03) | Same |
| Mark paid / received | Paid | No | Received | No | Correct with reason | Same |
| Schedule, cancel inspection | No | No | No | No | Yes (MFA), package active | Same |
| Perform, submit inspection | No | No | No | Yes (MFA, EX-09) | Staff capture from a signed report | Same |
| Approve or return inspection | No | No | No | No | Yes (MFA) | Same |
| Submit rectification | No | No | Yes | No | On behalf | Same |
| Close non-conformance | Never | Never | Never | Through re-inspection | Through approval of the re-inspection | Same |
| Open handover, add documents | No | No | Add documents | No | Yes | Same |
| Acknowledge handover | Yes (code) | No | No | No | No | No |
| Issue Build Record | No | No | No | No | Yes (MFA) | Same |
| Publish checklists, appoint auditors, statements | No | No | No | No | Prepare | Yes |

### N.2 Invariants

- **Project boundary:** membership join; another project's resources return 404.
- **Contractor:** acts only while its CONTRACTOR engagement is ACTIVE on that project, and only on that project's stages; never sees the auditor's internal notes before approval, other categories' data, or Plan2Build's rates.
- **Auditor:** reaches only its assigned inspections. Its response model has no supplier, brand, product, price or homeowner contact field (a test scans the keys). It cannot read the Build Record or payment marks.
- **Immutability:** submitted inspections, findings, evidence links, reports and issued Build Records refuse writes in the service and by trigger.
- **Write rules:**
  - every transition is audited;
  - `Idempotency-Key` on transitions and `version` on mutable rows;
  - row locks on the stage instance for completion, and on the inspection for submission and approval.
- **Files:** scanned before use; logged short links (5 minutes for P3 evidence).
- **Gating and money:** package gating is server-side; no route accepts a construction payment amount.

[SOURCE] SEC 4.2, IC §8, §9, §11, BR-122

---

## O. Notifications

Pattern as 3.4 to 3.6: outbox notice, then a job, then a plain-text template. Ids only, one email per event. No reminders or digests in 3.7 (AQ-12, AQ-13 open). Wording is draft until approved. [REC]; [SOURCE] N-11 pattern

| Recipient | Event | Marker |
|---|---|---|
| Homeowner | Completion requested (needs a decision); inspection scheduled; inspection report approved (with outcome); non-conformance raised (plain language); gate cleared; payment milestone due (no amount); handover ready to acknowledge; Build Record issued | [SOURCE] IHB 14.2, EVENT:171-201; [REC] selection |
| Contractor | Completion confirmed or returned; inspection scheduled on its stage; findings (non-conformances with due dates); re-inspection scheduled; non-conformance closed; payment marked paid; handover opened | [SOURCE] PNOT-38 to 41, IHB 14.2 |
| Auditor | Inspection assigned; inspection returned for amendment | [SOURCE] PNOT-38, EVENT:192 |
| Operations | Gate stage completion requested (schedule an inspection); inspection submitted (approve); rectification submitted (schedule re-inspection); non-conformance past due; completion request unanswered past the configured days; handover acknowledged | [SOURCE] EVENT:171-201; [REC] |

Not sent: every progress update (the homeowner reads them on the dashboard), payment-mark mismatches, warranty expiry.

---

## P. State machines

Common rules:
- transition tables in code;
- 409 `STATE_CONFLICT` for a disallowed pair, and every pair is tested;
- terminal states never change;
- every row writes an event row and an audit row in the same transaction.

[SOURCE] STATE §1, IC §9

### P.A Stage instance (execution) and payment milestone

| From → To | Actor | Guard | Side effects | Notify | Audit | Reversal |
|---|---|---|---|---|---|---|
| NOT_STARTED → IN_PROGRESS | Contractor or operations (first update) | ACTIVE CONTRACTOR engagement (or operations); project not CANCELLED | `actual_start`; update stored | None | `stage.in_progress` | Operations, one state back, with reason |
| IN_PROGRESS → COMPLETION_REQUESTED | Contractor or operations | Update of kind COMPLETION_REQUEST with at least one evidence file | Gate stage: assurance queue item | Owner; operations | `stage.completion_requested` | Owner or operations return |
| COMPLETION_REQUESTED → COMPLETED | Owner, or operations with reason (EX-03) | Gate stage: gate CLEARED | `actual_end`; payment milestone DUE if flagged | Contractor; owner (milestone due) | `stage.completed` | Operations one state back with reason (STATE rule) |
| COMPLETION_REQUESTED → IN_PROGRESS | Owner or operations | Reason | None | Contractor | `stage.returned` | None |
| Gate status NOT_INSPECTED → SCHEDULED → OPEN_NC or CLEARED | System from assurance | Section P.B | Completion may proceed when CLEARED | As P.B | `stage.gate_*` | Never by hand |
| Payment mark (no state machine, EX-05) | Owner (paid) or the contractor of record (received), or operations for an OUTSIDE contractor | Payment-milestone stage; YES or NO | Append-only entry; latest is current | The other party | `payment_mark.recorded` | A new entry |

BLOCKED and ON_HOLD: not used in 3.7 [REC]. No source gives a trigger other than issues and critical non-conformances, which do not block in 3.7 (EX-23).

### P.B Inspection

| From → To | Actor | Guard | Side effects | Notify | Audit | Immutable | Reversal |
|---|---|---|---|---|---|---|---|
| none → SCHEDULED | Operations (MFA) | Package active; gate stage instance; ACTIVE appointment; PUBLISHED checklist version | Gate status SCHEDULED | Auditor, owner, contractor | `inspection.scheduled` | Stage, gate, checklist version | Cancel |
| SCHEDULED → IN_PROGRESS | Auditor | Readiness confirmed | None | None | `inspection.in_progress` | As above | Operations cancel with reason |
| IN_PROGRESS → SUBMITTED | Auditor (MFA, EX-09) or operations (staff capture) | Every checkpoint answered; every finding with severity and due date; evidence files AVAILABLE | Content hash | Operations | `inspection.submitted` | Everything recorded | Return creates an amendment |
| SUBMITTED → APPROVED | Operations (MFA) | Package active | Non-conformances OPEN; report PDF rendered and stored; gate CLEARED if none open | Owner (report), contractor (findings) | `inspection.approved` | Report and hash | None; corrections by amendment |
| SUBMITTED → RETURNED | Operations (MFA) | Reason | A replacement inspection (amendment) may be scheduled, naming this one | Auditor | `inspection.returned` | The returned record | None |
| SCHEDULED or IN_PROGRESS → CANCELLED | Operations (reason) or system (PACKAGE_ENDED, PROJECT_CLOSED) | Not SUBMITTED | Gate status back to NOT_INSPECTED if nothing else applies | Auditor, owner | `inspection.cancelled` | None | None |

### P.C Non-conformance and re-inspection

| From → To | Actor | Guard | Side effects | Notify | Audit | Reversal |
|---|---|---|---|---|---|---|
| none → OPEN | System at inspection approval | Finding of an approved inspection | Gate OPEN_NC | Contractor (due date), owner (plain language) | `nc.open` | None |
| OPEN → RECTIFICATION_SUBMITTED | Contractor or operations | Evidence | Operations queue | Operations | `nc.rectification_submitted` | Operations back to OPEN with reason |
| RECTIFICATION_SUBMITTED → REINSPECTION_SCHEDULED | Operations | A re-inspection SCHEDULED naming the finding | None | Contractor, auditor | `nc.reinspection_scheduled` | Cancelling the re-inspection returns it |
| REINSPECTION_SCHEDULED → CLOSED | System at the re-inspection's approval | Its checkpoint for the finding PASS | Closure record; gate CLEARED if the last | Owner, contractor | `nc.closed` | None |
| REINSPECTION_SCHEDULED → OPEN | System at the re-inspection's approval | Not PASS | New evidence linked | Contractor | `nc.open` | None |

Reviewer closure: absent [PD] EX-11 (answers C-066 for 3.7).

### P.D Handover

| From → To | Actor | Guard | Side effects | Notify | Audit | Immutable |
|---|---|---|---|---|---|---|
| none → OPEN | Operations (MFA) | Gate 6 inspection approved with no OPEN non-conformance | Handover record | Owner, contractor | `handover.open` | None |
| OPEN → READY | Operations | Documents recorded (warranty entries complete for what was supplied) | Acknowledgement statement filled in | Owner | `handover.ready` | None |
| READY → ACKNOWLEDGED | Owner with one-time code (EX-15) | ACTIVE acknowledgement statement | Build Record DRAFT assembled | Operations, contractor | `handover.acknowledged` | Whole record |
| READY → OPEN | Operations | Reason (a document correction) | None | Owner | `handover.reopened` | None |

### P.E Build Record version

| From → To | Actor | Guard | Side effects | Notify | Audit | Immutable |
|---|---|---|---|---|---|---|
| none → DRAFT | System (on acknowledgement) or operations | Handover ACKNOWLEDGED (or operations with reason when the owner cannot acknowledge, EX-15) | Snapshot assembled | Operations | `build_record.draft` | None |
| DRAFT → ISSUED | Operations (MFA) | Package active (EX-18) | Snapshot hash, PDF and JSON stored; the previous ISSUED version SUPERSEDED | Owner | `build_record.issued` | Snapshot, hash, files |
| ISSUED → SUPERSEDED | System | A newer version issued | None | None | `build_record.superseded` | Everything; still readable |

---

## Q. Data model (minimum)

Module ownership uses names in the ADR-008 list (`construction`, `money`, `assurance`, `records`), so no new ADR is needed. The guards follow 3.3 to 3.6: lifecycle columns only, set-once fields, append-only tables, and child rows editable only while their parent is open. [REC]

| Module | Table | Purpose | Key columns | Guard |
|---|---|---|---|---|
| construction | `stage_instances` (existing) | Execution states | Add `completion_requested_at`, `completed_by_role`; states move | Lifecycle columns only (H-09) |
| construction | `stage_updates` | The standard update | project, stage instance, engagement (nullable for operations), kind, note, materials, open problems, file ids, corrects (update id), posted by and role, posted at | Append-only |
| construction | `construction_events` | History of stage transitions | subject, from, to, actor, reason | Append-only |
| money | `payment_marks` | Informational marks (EX-05) | project, stage instance (payment milestone), side PAID or RECEIVED, value YES or NO, engagement, marked by and role, at; **no amount column** | Append-only |
| assurance | `auditor_appointments` | Appointed auditors | name, qualification, registration reference, auditor ID (UNIQUE), linked user, appointed/ended by and at | Ends, never deleted |
| assurance | `checklist_versions`, `checkpoint_masters` | Versioned gate checklists | version, status DRAFT/PUBLISHED/RETIRED; checkpoint: gate, sequence, text, expected evidence, critical flag, spec line code | Published immutable |
| assurance | `inspections` | One per gate stage instance visit | project, stage instance, gate number, appointment, checklist version, state, readiness at, submitted at, content hash, approved by/at, report file, amends (inspection id), reinspection (boolean), captured by staff with evidence | Content frozen from SUBMITTED |
| assurance | `inspection_results` | Per checkpoint | inspection, checkpoint, result, note, measurements jsonb, NA reason, room tag | Frozen with the inspection |
| assurance | `inspection_evidence` | File links with capture claims | inspection, result (nullable), file, claimed capture time, claimed location (optional, consent), server receipt time, file sha256 | Frozen with the inspection |
| assurance | `test_results` | Later results on a checkpoint (cube tests) | result id, test kind, value text, recorded by, file | Append-only |
| assurance | `non_conformances`, `nc_events` | Findings and their cycle | finding: inspection, result, severity, description, corrective action, due date, owner engagement; state; closure inspection | Finding columns set once; lifecycle; events append-only |
| assurance | `assurance_events` | History | | Append-only |
| records | `handovers` | One per project | state, gate 6 inspection, opened by, acknowledged by, challenge id, statement id and text | Lifecycle; frozen at ACKNOWLEDGED |
| records | `handover_documents`, `warranties` | Documents and warranty values | kind (WARRANTY, MANUAL, DRAWING, CERTIFICATE, PHOTO, OTHER), file; warranty: item, term, expiry, installer, line code | Frozen with the handover |
| records | `acknowledgement_statements` | Versioned handover wording | as `acceptance_statements` | Active immutable |
| records | `build_records` | Versions | version no, state DRAFT/ISSUED/SUPERSEDED, snapshot jsonb, sha256, PDF file, JSON file, issued by/at | Frozen from ISSUED |
| documents | `file_objects` purposes | | STAGE_EVIDENCE, INSPECTION_EVIDENCE, INSPECTION_REPORT, HANDOVER_DOCUMENT, BUILD_RECORD_DOCUMENT, BUILD_RECORD_EXPORT | CHECK widened |
| identity | `otp_challenges` purpose | | ACKNOWLEDGE_HANDOVER | CHECK widened |
| operations | `ops_queue_items` kinds | | COMPLETION_REVIEW, INSPECTION_APPROVAL, RECTIFICATION_REVIEW (EX-12) | CHECK widened |

Not created [REC]:
- `variations`, `contract_values` (EX-24, EX-05);
- `issues`, `disputes` (EX-24);
- `inspection_sync_batches` (offline, EX-10);
- `material_records` and line state changes (EX-16);
- `share_tokens`, `record_transfers`, `post_handover_optins` (EX-17);
- an execution entity or project status moves (EX-01);
- membership rows (access through engagements and appointments).

---

## R. API model (proposed, not implemented)

Conventions as before:
- `Idempotency-Key` on transitions and `version` on mutable rows;
- 409 with `details.reason`, 422 for fields, 404 outside visibility;
- operations routes need OPS or ADMIN with MFA.

| Host | Route | Purpose |
|---|---|---|
| Homeowner | `GET /projects/{id}/execution` | Stages with states, actual dates, updates (paged), gate status, milestones with marks, open non-conformances in plain language |
| Homeowner | `GET /projects/{id}/stages/{sid}/updates`, `GET .../updates/{uid}/files/{fid}/url` | Updates and logged evidence |
| Homeowner | `POST /projects/{id}/stages/{sid}/confirm`, `.../return` | Completion decision (EX-03) |
| Homeowner | `POST /projects/{id}/milestones/{mid}/mark-paid` | Mark |
| Homeowner | `GET /projects/{id}/inspections`, `GET .../inspections/{iid}/report` | Approved inspections and the report PDF |
| Homeowner | `GET /projects/{id}/handover`, `POST .../handover/acknowledgement-code`, `POST .../handover/acknowledge` | Handover |
| Homeowner | `GET /projects/{id}/build-record`, `GET .../build-record/versions/{v}`, `GET .../build-record/versions/{v}/pdf`, `.../json` | Build Record |
| Contractor | `GET /pro/engagements/{eid}/execution` | Its project's stages, drawings of the accepted version, its own updates and findings, milestones |
| Contractor | `POST /pro/engagements/{eid}/stages/{sid}/updates` (+ evidence uploads) | Update or completion request |
| Contractor | `POST /pro/engagements/{eid}/milestones/{mid}/mark-received` | Mark |
| Contractor | `POST /pro/engagements/{eid}/non-conformances/{nid}/rectification` | Evidence |
| Contractor | `POST /pro/engagements/{eid}/handover/documents` (+ uploads) | Handover documents |
| Auditor | `GET /pro/inspections`, `GET /pro/inspections/{iid}` | Assigned inspections, checklist, drawings without brand data |
| Auditor | `POST /pro/inspections/{iid}/readiness`, `PUT .../results`, evidence uploads, `POST .../submit` (MFA) | Perform and submit |
| Operations | `GET /ops/execution`, `GET /ops/projects/{id}/execution` | Queues and project view |
| Operations | `POST /ops/stages/{sid}/updates` (raw-body evidence), `.../confirm`, `.../return`, `.../reopen` | On behalf and overrides with reason |
| Operations | `POST /ops/projects/{id}/inspections`, `POST /ops/inspections/{iid}/cancel`, `.../approve`, `.../return`, `.../capture` | Assurance |
| Operations | `POST /ops/non-conformances/{nid}/due-date`, `.../schedule-reinspection` | Corrective actions |
| Operations | `POST /ops/projects/{id}/handover`, `.../ready`, `.../reopen`, `.../documents` | Handover |
| Operations | `POST /ops/projects/{id}/build-record/assemble`, `POST /ops/build-records/{rid}/issue` | Build Record |
| Admin | `GET/POST /admin/auditor-appointments`, `.../end`; `GET /ops/checklists`, `POST /ops/checklists`, `PUT .../checkpoints`, `POST /admin/checklists/{id}/publish`; `GET/POST /admin/acknowledgement-statements`, `.../activate` | Configuration |

Events are internal outbox notices (section O). Read-only interfaces are added between modules, such as `construction.interface.stage_facts` and `assurance.interface.gate_cleared`. Import-linter contracts are extended for `money`, `assurance` and `records`.

---

## S. UI scope (functional only)

No redesign, visual polish, animation, marketing or final responsive pass. [PD] Chirag's instruction

| Host | Screens |
|---|---|
| Homeowner | The existing "Construction stages" page gains states, updates, evidence links, the confirm and return actions, milestones with the paid mark, inspections with reports, and open findings. New pages: "Handover" (documents, acknowledgement with code) and "Build Record" (versions, PDF, JSON) |
| Contractor | An execution page from the engagement: stages, accepted drawings, update form, completion request, received marks, findings with rectification, handover documents |
| Auditor | "Inspections" list and inspection page (readiness, checkpoint results, findings, evidence upload, submit) |
| Operations | Execution queue; project execution page; inspection scheduling, approval, return, staff capture; non-conformance actions; handover; Build Record assemble and issue; checklists and auditor appointments (JSON editors acceptable, H-06) |

---

## T. Test strategy

| Area | Tests |
|---|---|
| Execution authorization | Only the ACTIVE CONTRACTOR engagement's professional posts on that project; an ENDED engagement is refused; another project 404; household read only; owner cannot post updates |
| Execution transitions | Every allowed and disallowed stage pair; completion of a gate stage refused until CLEARED; return needs a reason; operations override needs a reason and MFA |
| Progress integrity | Updates never change (trigger); corrections link; evidence files scanned and project-scoped; no percentage anywhere; no planned date written (BP-07A) |
| Inspection permissions | Auditor sees only assigned inspections; no supplier, brand, product, price or contact key in any auditor response (key scan); contractor never sees an inspection before approval |
| Signed inspection immutability | After SUBMITTED, results, findings and evidence refuse writes (service and trigger); recomputed hash equals the stored one; amendment is a new record |
| Corrective actions | Rectification by the contractor of record; re-inspection names the finding; PASS closes; a non-PASS keeps it OPEN; homeowner and contractor can never close; gate CLEARED only when the last closes |
| Reinspection | A re-inspection is a separate inspection; the original stays unchanged |
| Payment marks | DUE only after completion (and clearance); marks once each; SETTLED on both; no amount field in any request or response; mark never blocks the next milestone |
| Handover | Refused while Gate 6 has an OPEN finding; acknowledgement needs the code and the ACTIVE statement version; ACKNOWLEDGED freezes documents |
| Build Record integrity | Snapshot hash stable; PDF deterministic; ISSUED immutable; new version supersedes and the old stays readable; quote prices absent |
| Historical document access | Logged links; 5-minute P3 evidence links; access after engagement end limited as defined |
| Package cancellation | Scheduled inspections cancelled (PACKAGE_ENDED); approved records readable; no new inspection or Build Record issue; progress and marks continue; no usage row |
| Engagement integration | Contractor change mid-build keeps history with each engagement id; the new contractor continues; no engagement state added |
| Concurrent updates | Two completion decisions or two marks race: one wins; inspection submission and cancellation race |
| Audit history | Audit rows equal event rows for every transition |
| Unauthorized access | Foreign-membership sweep over every new route |
| No construction-money path | Schema scan: no amount column on milestones; no route accepts an amount |
| Hash fix | H-07: a re-encoded image's recorded sha256 equals the stored object |
| Browser (phone and desktop, axe) | Contractor posts and requests completion; operations schedule; auditor inspects and submits; operations approve; contractor rectifies; re-inspection closes; owner confirms; marks; Gate 6; handover acknowledgement; Build Record issue and download |

---

## U. Open decisions

None for 3.7: EX-01 to EX-24 are decided (section 0). Questions still open outside 3.7, unchanged: CQ-11 and CQ-13 (client answers may refine the update format and the marks as new decisions), CQ-15 (auditor registered as person or firm), CQ-16 (back office), F-03, C-022, C-023, C-071, CQ-12, D3-08, D3-09, D3-19, D3-20, POQ-021, OQ-018 (capped remedy), OQ-047, AQ-12, AQ-13, the offline PWA (EX-10).

---

## V. Production blockers

| Blocker | Why |
|---|---|
| Approved gate checklist content, including Gate 6 (EX-08) | No production inspection |
| At least one appointed independent auditor with an ID (EX-09, CQ-15) | No inspection |
| Final wording: handover acknowledgement statement, inspection report wording, the new emails | Production handover and notices |
| Client answers CQ-11 (update format) and CQ-13 (marks) | The provisional format and mark rules become final |
| The 3.6 items: selection statement approval, RFQ email approvals, real listed Raipur contractors, English-only contractor screens, H-04, H-05, H-06 | Execution starts from a selection |
| The 3.5 items: Raipur production rate card, appointed drawing checker, approved sign-off and acceptance wording, an available structural engineer, a production Unicode PDF font (also for reports and the Build Record), English-only documents, BP-07A, H-01 | The accepted Build Plan is the execution baseline |
| H-02 | Hardening |
| Offline auditor PWA (ADR-021) if EX-10 (a) | Field connectivity |
| Documentation drift H-10 corrected | Architecture consistency |

---

## W. Implementation order (after the decisions)

1. Record Chirag's answers. Fix H-07: the file hash must equal the stored object, with a test. Add the `stage_instances` guard (H-09).
2. Vocabulary and configuration:
   - new states, kinds, purposes and queue kinds;
   - the auditor MFA rule;
   - the two day counts from EX-12.
3. Modules `money`, `assurance`, `records` and their interfaces, plus the construction extensions and import-linter contracts.
4. Migration 0016: tables, triggers, CHECK widenings, grants, and a seed of the acknowledgement statement v1 (functional wording pending legal confirmation). Then up, down, up twice.
5. **3.7a, execution:**
   - updates;
   - completion request, confirm and return;
   - milestones and marks;
   - the contractor's execution view with accepted drawings;
   - operations on behalf.
6. **3.7b, assurance:**
   - appointments and checklists (version 1 from the S04 mapping);
   - scheduling, readiness, results, findings, evidence and submission (hash);
   - approval with the report PDF; return and amendment; staff capture;
   - non-conformances, rectification, re-inspection, closure, gate clearance;
   - package-end handling.
7. **3.7c, handover and Build Record:**
   - handover with documents, warranties and the acknowledgement code;
   - Build Record assembly, issue (PDF and JSON), versions.
8. Notifications and templates.
9. Functional screens on the three hosts; contracts regenerated.
10. Tests (section T), Playwright on the production build, migration checks, the documentation drift fix (H-10), SLICE3_7_IMPLEMENTATION_REPORT.

Each of 3.7a, 3.7b and 3.7c ends with its tests passing before the next starts. This keeps one slice with three checkpoints, given the size. [REC] (PACT 8)

---

## X. Final verdict

The sources and the decisions of 2026-10-06 (section 0) settle every question 3.7 needs:
- execution without project status moves (EX-01);
- the update format (EX-02) and completion authority (EX-03);
- no dates (EX-04);
- informational marks (EX-05);
- optional assurance with any contractor (EX-06);
- one inspection per gate stage instance (EX-07);
- versioned checklists (EX-08) and appointed auditors (EX-09), online only (EX-10);
- re-inspection-only closure (EX-11);
- the two thresholds (EX-12);
- reports (EX-14), handover (EX-15) and the Build Record (EX-16, EX-17);
- package behaviour (EX-18) and contractor changes (EX-19);
- notices (EX-20), household rights (EX-21), photo metadata (EX-22) and overdue defects (EX-23);
- the boundary of the slice (EX-24).

H-07 is the first task. The checklist content for Gate 6 and an appointed auditor remain production blockers, not implementation blockers. No [OPEN] marker remains for a 3.7 decision.

SLICE 3.7 READINESS = READY
