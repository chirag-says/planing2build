# Plan2Build: Slice 3.5 readiness (authoritative design and Build Plan)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/SLICE3_5_READINESS.md` |
| Version | 1.1 (2026-10-05) |
| Status | Implementation COMPLETE (approved by Chirag 2026-10-05); production readiness NOT YET READY (implementation report L). Reconciled 2026-10-05: PDF engine ADR-023; acceptance statement versioned. Implemented 2026-10-05: see `SLICE3_5_IMPLEMENTATION_REPORT.md`. Approved for implementation by Chirag on 2026-10-05 with BP-07A deferred. Reviewed by Chirag on 2026-10-05; BP-01 to BP-09 decided, BP-10 to BP-20 approved as recommended within the stated limits (section 0). Readiness only: no code, migration, API or UI changed. Where sections A to U differ from section 0, section 0 governs |
| Baseline | PD-01 to PD-27 (IHB_FLOW 32.6); PRODUCT_FLOW_RECONCILIATION v2.0 (PFR); SLICE3_READINESS (S3R); Slice 3.2 D-01 to D-11; Slice 3.3 L-01 to L-08; Slice 3.4 N-01 to N-12 (closed; N-03 confirmed and closed 2026-10-05) |
| Sources read | IHB_FLOW 8.11, 8.12, 9, 10, 32, 33, 34; PFR; S3R; SLICE2_READINESS rulings 2.1 to 2.10; PROFESSIONALS_FLOW (PRO); DATA, STATE, API, DOMAIN, EVENT, SECURITY, INTEGRATION, AI, TECH_STACK architecture; ADR-010, 013, 018, 022; ARCHITECTURE_BASELINE (BASE); IMPLEMENTATION_CONTRACT (IC); FOUNDATION_PLAN (FP); REQUIREMENT_QUESTIONS_V1 (RQ); the original documents in `SOURCE_OF_TRUTH` read as text: MVP Build Plan (MVP, 24 Sep 2026), Specification Schema (S04 / SCH, v1.0), Strategy and POC (STR), Client Product and Implementation Blueprint (CPB), Technology Product Blueprint (TPB), Transactional Verification Blueprints (FTB, TVB, older marketplace model); the code as built through Slice 3.4 |
| Markers | **[SOURCE]** a source or approved architecture settles it. **[PD]** Chirag's decision. **[REC]** Sakha's recommendation, not approved. **[OPEN]** undecided. **[SUPERSEDED]** an older design overridden |

Citation forms: `IHB:4306` is IHB_FLOW.md line 4306; `MVP:185` is line 185 of the MVP Build Plan text; S04 rules are cited by their rule number (R1 to R9) or SCH line. Where the original documents conflict, MVP:8 states it supersedes "the earlier MVP functional specification, which described a monitoring-led product"; FTB and TVB describe that older marketplace model and are cited only where nothing newer speaks. PD decisions outrank every source.

No code changed in this readiness pass.

### Governing chain

AI concept → design reference → authoritative design workflow → authoritative drawings → project specification values → BOQ → schedule → Build Plan version → structural sign-off where required → issue → homeowner acceptance → RFQ-ready scope. AI images never become authoritative. [PD] PD-05, PD-06, PD-13, PD-14, PD-15, PD-24, PD-25, PD-27

### Decision IDs

This document numbers its questions **BP-01** onward (no collision: `BP-` is unused elsewhere). Existing IDs are kept where a question already exists (F-04, F-10, CQ-22, CQ-25, CQ-26, D3-13 to D3-20, D-16). Two collisions found in the sources: F-04, F-09 and F-10 in RQ:135-163 are unrelated to PFR's F-04, F-09, F-10; D-03 and D-04 mean different things in BASE and in SLICE3_2 K0. In this document F-xx always means PFR's register and D-03/D-04 mean BASE's rulings.

---

## 0. Final decisions and readiness (Chirag, 2026-10-05)

N-03 (Slice 3.4) is confirmed and CLOSED: SOURCING, CONTRACTED and BUILDING are not the professional lifecycle; professional progress is service needs, then engagements, then later construction and execution states. It blocks nothing here.

### 0.1 Decision table BP-01 to BP-20

| ID | Decision | Marker |
|---|---|---|
| BP-01 | Plan2Build appoints a qualified checker for authoritative drawings. The checker need not be a Plan2Build employee. Structural drawings are checked and reviewed by the structural engineer who gives the structural sign-off | [PD] |
| BP-02 | An issued Build Plan contains, where applicable: site plan, floor plans, at least one elevation, at least one section, and structural drawings where structural lines apply. Permit-specific drawing packages are out of scope for 3.5. No other drawing type is mandatory | [PD] |
| BP-03 | Plan2Build does not generate drawings. 3.5 is design intake, professional drawing production, checking, approval, authoritative drawing set. No AI floor-plan generation, no CAD generation, no automated architectural drawing generation. AI concepts stay illustrative references only | [PD] |
| BP-04 | Two sign-off modes: (1) a verified engineer signs through a one-time-code flow; (2) operations upload signed documentation from an outside engineer. Every sign-off stores at least: engineer identity, professional category, verification or credential reference, Build Plan version, exact content and drawing set covered, timestamp, sign-off evidence, audit event. The one-time-code flow is a confirmation step; it is never described as a legally recognised electronic signature (no source establishes that). The statement is configurable and versioned. Baseline wording (product and legal copy; final client and legal confirmation required before production launch): "I confirm that I have reviewed the structural information and drawings identified in this Build Plan version for the stated project inputs and assumptions, and that the structural items covered by this sign-off are acceptable for issue, subject to the assumptions and conditions recorded with the project." | [PD] |
| BP-05 | Homeowner acceptance is confirmed with a one-time code. The RFQ baseline freezes at homeowner acceptance. A later accepted version supersedes the previously accepted one. Issued versions, accepted versions, signed structural records and historical PDFs are never mutated. Every acceptance identifies the exact version accepted | [PD] |
| BP-06 | For the POC, operations prepare the production rate card; an authorised ADMIN approves and publishes it. Versioned, with at least: item code, item description, unit, rate, geography, effective-from, effective-to where applicable, source or reference, status, version. No production Build Plan is issued from an unapproved or DEMO card. No Raipur rates are invented. Stage cost-share percentages never substitute for item-level BOQ rates | [PD] |
| BP-07 | The advisor may enter project-specific schedule information. Durations are stored independently of calendar dates while the start date is unknown. Dates are calculated only after a project baseline start date exists. The canonical build order is never inferred from the display order of the stages. Until the canonical execution order and dependencies are resolved, durations, explicitly entered dependencies and draft schedules may exist, and no authoritative production date is calculated | [PD] (partial); blocker BP-07A |
| BP-07A | **Canonical construction execution order and dependencies across stages and floors.** No source resolves it: S04 section 4 and MVP:42, 149 say only that stages 5, 6 and 9 repeat per floor and are instantiable N times; nothing defines how repeated instances interleave or which stages depend on which | **DEFERRED** (Chirag, 2026-10-05). 3.5 stores durations and explicitly entered dependencies with schedule versioning, and calculates no calendar dates, decide-by dates or cash-flow figures; nothing is inferred from display order or stage numbers. Date calculation is added later without changing the version and sign-off model |
| BP-08 | Only contractor RFQs require an accepted Build Plan baseline. Contractors receive the construction scope, quantities, relevant specifications and the other information needed to quote; they never receive Plan2Build's internal rate-card values, which stay internal costing and benchmark data. The full RFQ and quote comparison workflow is not built in 3.5 | [PD] |
| BP-09 | Build Plan work is package-gated where the product model requires it (PD-13). On package refund or cancellation: open connection requests may be withdrawn (N-10, built); active engagements stay under the 3.4 rules; issued and accepted Build Plan versions stay immutable and readable; new package-gated work is blocked while the package is inactive. The substantial-work rule for refunds is unchanged (N-12: a professional accepting a connection). Issuing a Build Plan is recorded operationally (history, audit, event) and never written as a refund substantial-work record | [PD] |
| BP-10 | No construction payment-percentage schedule (no source values; payments are between family and contractor). A monthly cash-flow figure appears only once authoritative dates exist (after BP-07A and a start date), computed from BOQ stage budgets | [REC] approved |
| BP-11 | Documents in English (ADR-022); client confirmation of BR-057 (Hindi and English) is a launch item | [REC] approved |
| BP-12 | No system limit on design or Build Plan revision rounds | [REC] approved |
| BP-13 | The issuer is never the person who last edited the version's content (maker and checker) | [REC] approved |
| BP-14 | PLANNING and PLAN_ISSUED project statuses do not move with the Build Plan; the Build Plan's own state is the record (N-03, PD-17) | [REC] approved |
| BP-15 | No project-only accounts for outside architects or engineers in 3.5; the owner or operations upload on their behalf (F-03 stays open) | [REC] approved |
| BP-16 | No public share link in 3.5; signed-in, logged downloads only (OQ-047 deferred) | [REC] approved |
| BP-17 | PDF wording limited to source statements plus the BP-04 statement; any further disclaimer comes from Chirag | [REC] approved |
| BP-18 | Lines may be marked not applicable with a reason; a structural line marked not applicable needs the engineer's sign-off of that applicability | [REC] approved |
| BP-19 | A master version published after a draft starts reaches the draft only when the advisor refreshes that line (recorded) | [REC] approved |
| BP-20 | A sign-off revoked after issue: an unaccepted version is withdrawn; an accepted version is replaced through a new version and acceptance; the homeowner is told | [REC] approved |

Consistency check (Chirag's rule that BP-10 to BP-20 must not contradict the product reconciliation, billing and refund decisions, the modular professional model, the versioning model or N-03): BP-09's earlier recommendation to write `BUILD_PLAN_ISSUED` into `package_service_usage` is **withdrawn** (it would have changed the refund rule). BP-09's earlier recommendation to withdraw drafts automatically on refund is **withdrawn** (not in the approved list): drafts stay, blocked, and operations may withdraw them with a reason. BP-10's cash-flow figure now waits for dates (BP-07A). No other conflict found.

### 0.1a Post-implementation reconciliation (Chirag, 2026-10-05)

| Point | Status |
|---|---|
| PDF engine | fpdf2 approved for Build Plan PDFs, invoices and credit notes (ADR-023); ADR-018 (WeasyPrint) superseded and applicable to no document type |
| Acceptance wording | Versioned configuration (`acceptance_statements`, migration 0014); v1 IMPLEMENTED / PENDING FINAL CLIENT + LEGAL CONFIRMATION |
| Sign-off wording | Versioned (BP-04); v1 IMPLEMENTED / PENDING FINAL CLIENT + LEGAL CONFIRMATION |
| Engineer notification | Known workflow gap: the sign-off works, the engineer is not emailed when a version awaits signature. Follow-up hardening task H-01 (before production, not part of 3.6) |
| Browser coverage | Architect upload and engineer sign-off paths accepted as API-tested for 3.5 |
| BP-07A | Still deferred; nothing inferred from display order |

### 0.2 Final Build Plan state machine

States: DRAFT, IN_REVIEW, ISSUED, ACCEPTED, CHANGES_REQUESTED, SUPERSEDED, WITHDRAWN.

| From | To | Trigger | Actor | Guard |
|---|---|---|---|---|
| none | DRAFT | create | Advisor | Project ELIGIBLE; package active; no other DRAFT or IN_REVIEW version; content carried forward from the latest version |
| DRAFT | IN_REVIEW | submit | Advisor | Package active; completeness (0.4 items 1 to 7); content hash stored; sign-off requests opened |
| IN_REVIEW | DRAFT | return | Advisor, OPS, or a signer declining | Reason; every sign-off on the version becomes VOID |
| IN_REVIEW | ISSUED | issue | OPS with MFA, not the last editor | Package active; every issue condition (0.4); then freeze, render, supersede the earlier unaccepted ISSUED or CHANGES_REQUESTED version |
| ISSUED | ACCEPTED | accept | Owner with one-time code | Package active; latest ISSUED; PDF rendered; acceptance record with the content hash; the previously ACCEPTED version becomes SUPERSEDED; RFQ baseline points here |
| ISSUED | CHANGES_REQUESTED | request changes | Owner | Reason; never acceptable afterwards |
| ISSUED | WITHDRAWN | withdraw | OPS with MFA | Reason; never after acceptance |
| DRAFT, IN_REVIEW | WITHDRAWN | withdraw | Advisor or OPS | Reason; open sign-offs VOID |
| ACCEPTED | SUPERSEDED | successor accepted | System | A later version accepted |
| CHANGES_REQUESTED | SUPERSEDED | successor issued | System | A later version issued |

Content is editable only in DRAFT. ISSUED, ACCEPTED, CHANGES_REQUESTED, SUPERSEDED and WITHDRAWN versions are immutable; only lifecycle columns change. ACCEPTED is never withdrawn. While the package is inactive every transition except reading and withdrawal is refused (BP-09).

Drawing set (supporting machine): DRAFT → SUBMITTED (files frozen) → homeowner review → CHANGES_REQUESTED (terminal, a new set follows) or checking → APPROVED (authoritative, immutable) or REJECTED; APPROVED → SUPERSEDED when a later set for the same request is approved.

Structural sign-off (per version and line): SIGNED → VOID (return to draft, revocation before issue with reason, operations void with reason and MFA). After issue a revocation is an event that forces BP-20.

### 0.3 Final authoritative data flow

1. **Illustrative only.** AI concepts and design references never feed anything below; a design request may list reference ids labelled illustrative (PD-05, PD-06, PD-27, BP-03).
2. **Design request** by the owner (package active): provider is a listed architect or engineer with an ACTIVE engagement, an outside professional (uploads by owner or operations), the homeowner's own drawings, or another professional Plan2Build arranges. No generation by Plan2Build.
3. **Drawing set** uploaded, classified (site plan, floor plan, elevation, section, structural, other), scanned, hashed, submitted, reviewed by the homeowner.
4. **Check** by the appointed checker (BP-01); structural drawings by the signing engineer. APPROVED set = authoritative drawings.
5. **Build Plan version (DRAFT)** references one approved set and holds:
   - specification values per S04 line: criteria from the master version, project value, basis, evidence (PD-14);
   - BOQ: quantities with their basis (measured from approved drawings, provided by a professional, or advisor estimate with reason), rates from one PUBLISHED production item card (DEMO only outside production), server-computed amounts;
   - schedule: durations and explicit dependencies per stage instance, no dates until a start date exists and BP-07A is resolved;
   - inclusions, exclusions, assumptions.
6. **Submit** computes the content hash.
7. **Structural sign-off** on that hash, covering the line values and the structural drawings of the set, under a versioned statement (BP-04).
8. **Issue** by OPS with MFA (four-eyes), freezing everything; deterministic PDF with version and hash.
9. **Homeowner acceptance** with a one-time code; the acceptance record holds the exact version and hash. This is the RFQ baseline (BP-05).
10. **RFQ scope manifest** for contractor RFQs only (BP-08): drawings, issued specification values, BOQ quantities without Plan2Build rates, schedule durations, scope lists, version id and hash. Consumed by 3.6.

Never in the flow: AI generations, design references as inputs, unapproved or superseded sets, draft values, DEMO pricing in production, Plan2Build's internal rates for contractors, stage cost-share percentages in place of item rates.

### 0.4 Issue conditions (final)

1. One APPROVED drawing set containing every BP-02 class that applies (structural drawings when any structural line is applicable).
2. Every applicable specification line has a project value, or NOT_APPLICABLE with a reason.
3. Every applicable structural line, and every structural line marked not applicable, is SIGNED on this version's content hash under the current statement version.
4. A BOQ priced from one rate card version; amounts equal quantity × rate.
5. In production, that card is PUBLISHED and not DEMO.
6. A schedule with durations for the stage instances; dependencies only as explicitly entered; no calculated dates unless BP-07A is resolved and a start date exists.
7. Inclusions, exclusions and assumptions recorded (an explicit "none" allowed).
8. Package active.
9. Issuer is OPS with MFA and not the last editor.

### 0.5 Final implementation dependency order

1. Migration and vocabulary: design requests, drawing sets and files, checker appointments, sign-off statement versions, item rate cards and lines, Build Plan, versions, values, BOQ lines, schedule entries, sign-offs, acceptances, events; guards; file purposes DRAWING, SIGNOFF_EVIDENCE, BUILD_PLAN_DOCUMENT. Up, down, up.
2. Item rate cards: operations draft, ADMIN publish with MFA, immutability, effective dates, DEMO loader for development only.
3. Checker appointments and sign-off statement versions (ADMIN, versioned; baseline wording loaded as version 1 marked "pending legal confirmation").
4. Design requests and drawing sets: intake, upload, submit, homeowner review, check, approval, supersession. Depends on 1 and 3.
5. Build Plan drafting: versions, carry-forward, drawing reference, specification values, BOQ entry and import with server amounts, schedule durations and explicit dependencies (no date calculation), scope lists, content hash. Depends on 2 and 4.
6. Review and sign-off: submit, return, one-time-code signing for verified engineers, operations upload of signed documentation with credential reference, void and revocation. Depends on 3 and 5.
7. Issue: every condition, four-eyes, events, audit; no refund usage record. Depends on 6.
8. PDF (fpdf2, ADR-023; this read WeasyPrint before the 2026-10-05 reconciliation): deterministic render, hash, TEST banner for DEMO, logged download. Depends on 7.
9. Homeowner acceptance with one-time code, changes requested, supersession, history. Depends on 8.
10. Package gating and refund behaviour (BP-09) across 4 to 9.
11. RFQ scope manifest for contractor RFQs (quantities, no internal rates). Depends on 9.
12. Accepted-value pointers on project lines. Decide-by dates and stage dates stay NULL until BP-07A and a start date.
13. Minimal functional screens to exercise the flow; no visual polish.
14. Tests for every invariant in section Q, every transition and refusal, the DEMO refusal in production, hash binding, four-eyes, acceptance evidence, package gating, the unchanged refund rule; Playwright on phone and desktop with axe; contracts; documentation.

### 0.6 Remaining blockers

| Blocker | Blocks | Does not block |
|---|---|---|
| **BP-07A canonical construction execution order and dependencies** | Authoritative schedule date calculation, decide-by dates, the monthly cash-flow figure, the stage-order fix in `construction` | Building and issuing Build Plans with durations and explicitly entered dependencies |

Production launch items (process decided; content or confirmation still to come, none blocks implementation):

| Item | Why |
|---|---|
| Raipur production item rate card content (prepared by operations, published by ADMIN) | Production refuses DEMO pricing |
| At least one appointed drawing checker | No set can be approved |
| Final client and legal confirmation of the BP-04 statement wording | Production sign-off |
| A qualified structural engineer reachable (listed or outside) | Plans with structural lines |
| A Unicode PDF font in production (fpdf2, ADR-023; no WeasyPrint libraries needed) | Rendering in production |
| Client confirmation of English-only documents (BP-11) | BR-057 conflict |

---

## A. Current implementation inventory

### A.1 What exists

| Area | As built | Relevance to 3.5 |
|---|---|---|
| AI concepts | `design_generations` with `is_authoritative` CHECK false; versioned prompt templates; image marked "Illustrative concept" | Stays exploration only [PD] PD-05, PD-27 |
| Design references | `design_references.authority` CHECK `ILLUSTRATIVE_ONLY`, reversible, one per concept; route docstring "starts no Build Plan, BOQ, RFQ or approval" | May be shown to a designer as an illustrative input, never attached to drawings or a Build Plan [PD] PD-06; [SOURCE] PFR:180 |
| Authoritative design | Nothing: no `design_requests`, `design_artefacts`, drawings | To build |
| Build Plan | Nothing: no `build_plans`, versions, BOQ, sign-offs, baselines, rendered documents, share tokens (S3R:200) | To build |
| Specification masters | `spec_groups` A/B/C; `spec_line_masters` (code, group, item, `consuming_stages[]`, `decide_by_weeks`, `verified_at`, `brand_category`, `is_structural`, `is_long_lead`; CHECK structural has no brand); `spec_line_master_versions` (`performance_specification`, `engineer_signoff` PENDING/SIGNED/NOT_REQUIRED, one ACTIVE per code). Seed v1: 67 lines, 8 structural (A01, A02, A04, A05, A09, A12, A13, A19), 9 long-lead | The criteria. Never receive project values [PD] PD-14 |
| Project spec lines | `project_spec_lines` (`issued_criteria` copied from the master at acceptance, `engineer_signoff` copied, state SPECIFIED, `decide_by` NULL, `consuming_stage_instance_id`); `spec_line_events` append-only. No value field, no signer | The per-line copy of `engineer_signoff` can never become SIGNED (S3R:95); PFR:222 moves sign-off to the Build Plan version |
| Stages | `stage_master_versions` v1 ACTIVE; `stage_masters` 16 rows, `sequence = number`, `default_duration_days` and `cost_share_pct` NULL ("not approved", D-04); `stage_instances` per project with `floor` (-1 basement, 0 ground, 1 to 3), dates NULL | The schedule source. Ordering defect below |
| Rate card | `rate_cards` (city text, version, `schema_version` 1, `rates` JSON, `is_demo`, `label`, `valid_from`, `published_by`; CHECK `is_demo OR published_by IS NOT NULL`). Only a DEMO Raipur card, loaded by a command that refuses production; rates are per square foot by tier plus S14 stage shares | Area rates only: no item rates exist anywhere (S3R:107) |
| Indicative estimate | `project_estimates` append-only per (project, requirement version), with `rate_card_id` and a result snapshot including `is_demo` | Preserved unchanged [PD] PD-04 |
| Documents | `file_objects` with sha256; purposes REQUIREMENT_UPLOAD, AI_CONCEPT, VERIFICATION_EVIDENCE, PORTFOLIO, INVOICE, QUOTE_DOCUMENT; `document_access_log` append-only; `store_generated_file` allows AI_CONCEPT and INVOICE only; links 15 minutes | Drawings, sign-off evidence and the Build Plan PDF need purposes |
| PDF | Invoices only, rendered by fpdf2 in a job; English; TTF font required in production | ADR-018 named WeasyPrint for all PDFs; resolved by ADR-023 (fpdf2, 2026-10-05) |
| Professionals | Listing per category; STRUCTURAL_ENGINEER and ARCHITECT requirements include REGISTRATION evidence; registration issuer and number in `professional_documents.details`; append-only `verification_checks` | Identity and credential for a listed signer or architect |
| Engagements (3.4) | Per category, one ACTIVE; LISTED (profile, connection) or OUTSIDE (name, firm, contact). No project membership created | Decides who may contribute drawings or sign for a project |
| Quote-holder intake (3.4) | `quote_review_requests` SUBMITTED, 1 to 5 QUOTE_DOCUMENT files | Review itself is not 3.5 (section M) |
| Package | `package_active`, `package_service_usage` (only `CONNECTION_ACCEPTED` written) | Build Plan is a package service [PD] PD-13 |
| Project status | Only DRAFT, SUBMITTED, NEEDS_INFO, ACCEPTED, CANCELLED move; PLANNING and PLAN_ISSUED exist only in the CHECK | See BP-14 |
| Language | English only, externalised strings (ADR-022) | See BP-11 |
| OTP | Login OTP built; challenge purposes for acknowledgements designed (SEC:62) but not built | Homeowner acceptance and possibly engineer signing |
| MFA | Staff only (OPS, ADMIN). Professionals have no MFA | SEC:86 asks MFA for engineer sign-off |

### A.2 Code defect to fix before any date arithmetic

`construction/service.py` builds instances by stage `sequence`, then floor inside each stage, so every floor's stage 5 precedes every stage 6. `sequence` is display order, not build order; "date maths must not rely on it" (S3R:125). [SOURCE] PFR:222: "The stage order used for dates is fixed with the schedule work." Section K proposes the fix.

### A.3 Contradictions found (none silently reconciled)

| # | Contradiction | Sources | Treatment here |
|---|---|---|---|
| X1 | Homeowner acceptance: none (STATE 8; S3R D3-12 recommended "No acceptance step") versus formal acceptance | STATE:204; S3R:162; PD-13 IHB:4306; PFR:187 | [PD] PD-13 governs: acceptance exists. [SUPERSEDED] D3-12's "no acceptance". How it is captured: BP-05 |
| X2 | Baseline lock: at Package A issue (MVP:190), per line at CHOSEN with OTP (SCH:684), at first ISSUED version (STATE:208), at acceptance (F-10 recommendation PFR:269) | as listed | [PD] BP-05: the RFQ baseline freezes at homeowner acceptance; the construction contract baseline (variations) is a later slice |
| X3 | Who signs structural lines: Plan2Build's retained engineer (PRO:322, PRO:4106, S3R:93, STR:264) versus any qualified engineer | PD-24 IHB:4317 | [PD] PD-24 governs. [SUPERSEDED] retained-engineer-only |
| X4 | Engineer sign-off record keyed on `engineer_user_id` (a platform account) versus outside signers | DATA:153; PD-24 | [SUPERSEDED] account-only key; section F |
| X5 | Who makes 2D drawings: CD-25 wording has the image tool making "the 3D views and the 2D drawings" versus no AI floor plans | IHB:4151; IHB:4491; ADR-013; PD-27 IHB:4325 | [PD] PD-27 (never floor-plan images or dimensioned drawings) governs AI. [PD] BP-03: Plan2Build generates no drawings at all in 3.5 (answers D3-13 for this slice) |
| X6 | AI design entirely out of scope (MVP:347; PLAN:391) versus AI concepts built in 3.1 | PD-05 | [PD] PD-05 governs; irrelevant to authority because AI is never authoritative |
| X7 | Build Plan in the package: CD-05 and PD-13 ("package service") versus PD-19 and SLICE3_3:55 package-service lists that omit it | IHB:4131; IHB:4306; IHB:4312 | [PD] PD-13 explicit; the lists are incomplete. Gating rule: BP-09 |
| X8 | Build Plan = three packages A/B/C issued at stages 3, 9, 13 (MVP:182; SCH:47-66) versus one Build Plan with A/B/C as groups only | PD-09 IHB:4302; PD-13 | [PD] PD-09 governs. [SUPERSEDED] three separately issued packages. Line timing inside one plan: section E |
| X9 | When PLANNING starts: on package paid (STATE:133; EVT:221) versus only for homeowners who take a planning service (PFR:249) versus activation changes no status (as built, FP:258) | as listed | BP-14 |
| X10 | PDF engine: WeasyPrint for all PDFs (ADR-018; TECH:32; INT:137) versus invoices built with fpdf2 | FP:260 | **Resolved (Chirag, 2026-10-05): ADR-023 approves fpdf2 for Build Plan PDFs, invoices and credit notes; ADR-018 superseded** |
| X11 | PDF language: Hindi and English from first release (BR-057 IHB:3221; C-028; MVP:48) versus English only (ADR-022, Chirag); budget documents "One language" | as listed | [PD] ADR-022 for the build; client confirmation BP-11 (AQ-10, D3-17) |
| X12 | Two homes for stage cost shares: `rate_cards.stage_shares_pct` (DEMO) and `stage_masters.cost_share_pct` (NULL) | S3R:128 | [REC] neither for the Build Plan: stage budgets come from BOQ lines tagged to stages (section H). The estimator keeps its own until D-16 |
| X13 | Structural lines carry brand categories in S04 (A01 testing lab, A04/A09/A12 cement/RMC, A05 steel, A13 RMC) versus "structurally impossible" to attach a brand or option (MVP:51, MVP:151) | SCH:155-238 | [SOURCE] ruling D-03 (DATA:418) and 2.4 already removed them; built CHECK enforces it |
| X14 | Option ordering: by price or alphabetically (R5) versus by price (MVP:51) | | Not 3.5 (options belong to the choices slice) |
| X15 | Package timing versus line timing: lines consumed before their group's issue point (A01 stage 1; B18, B21 stage 2; C01, C02 stage 11) | SCH; OQ-051 IHB:3551; EC-053 | Dissolved by PD-09 if one plan covers all 67 lines before construction (section E) |
| X16 | Six-milestone model (TVB:485-513) versus 16 stages | | [SUPERSEDED] TVB; 16 stages as built |
| X17 | Ratings in comparison (FTB:162) versus none (MVP:333) | D-07 | [SUPERSEDED] FTB; not 3.5 |
| X18 | Design artefact model lacks `is_authoritative` and `source` (DATA:157) while AI:23 has them | S3R:200 | Section G replaces the design-artefact model |
| X19 | STATE:194 lets operations move a structural line to CHOSEN; S04 asks homeowner OTP on every line | S3R:65 | Not 3.5 (choices slice) |
| X20 | BASE:234 still lists A01 as open under D-03; ruling 2.4 settled it | S2R:156 | Documentation correction only |

---

## B. Authoritative design workflow

### B.1 What "authoritative" means

| Rule | Marker |
|---|---|
| An AI concept is never authoritative, never a structural, permit or working drawing, never a source for BOQ or RFQ | [PD] PD-05, PD-27 |
| A liked concept is only a reference feeding the authoritative workflow | [PD] PD-06 |
| An authoritative drawing is a drawing file that (1) comes from a party with a recorded basis to provide it, (2) has been checked by the designated checker, and (3) belongs to a drawing set version that is APPROVED and therefore frozen | [REC] (no source defines the word; built from 33.6 "a qualified person checks them before they feed the BOQ", IHB:4151, and AI:25 "BOQ measurement reads only artefacts with is_authoritative = true") |
| An architect's design "replaces the concept drawings in the Build Plan and the RFQ package" | [SOURCE] CD-20 IHB:4146; PRO:4167 |
| Structural design is never by AI; "the registered structural engineer designs and signs" | [SOURCE] 33.6; BR-055; DOM:121 |
| Drawings may come from Plan2Build professionals, the homeowner, outside professionals or approved design inputs | [PD] PD-25 |

### B.2 Sources of drawings (design request kinds)

| Kind | Who provides | Upload by | Basis recorded | Marker |
|---|---|---|---|---|
| `LISTED_ARCHITECT` | A listed ARCHITECT with an ACTIVE engagement on the project (3.4) | The professional on the professionals host | Engagement id; listing; verified REGISTRATION | [REC] (uses N-02 engagements; API:107 designed `POST /pro/design/{request_id}/pack`) |
| `OUTSIDE_PROFESSIONAL` | The homeowner's own architect or engineer (OUTSIDE engagement) | The homeowner, or operations on their behalf; the outside professional has no account until F-03 | Engagement id; name, firm; registration number and certificate if supplied | [REC]; [OPEN] F-03 for direct access |
| `HOMEOWNER_PROVIDED` | Existing drawings or a sanctioned plan | The homeowner | Declared origin; sanctioned plan flag | [SOURCE] RQ:56, RQ:175 ("a sanctioned plan saves a design step"); CPB:93 |
| `PLAN2BUILD_ARRANGED` | A qualified professional Plan2Build arranges to produce the drawings (CD-25 default service, without any generation by Plan2Build) | That professional on the platform if they hold an engagement, otherwise operations on their behalf | Professional identity and qualification | [SOURCE] CD-25 IHB:4151; [PD] BP-03 |

### B.3 Workflow

1. **Initiation.** The homeowner (owner role) opens a design request for the project, choosing one kind, or operations open one on the homeowner's instruction. Package required: BP-09. [REC]
2. **Request content.** Kind; provider (engagement id or outside details); scope note; requirement version it is based on; optional illustrative inputs (design reference ids, copied as ids and labelled ILLUSTRATIVE, never as files of the drawing set). [REC]; illustrative inputs [PD] PD-06
3. **Provision.** The provider (or uploader on their behalf) uploads files into a drawing set version in DRAFT, classifying each file (section G). Files go through the existing upload checks and scan. [REC]
4. **Submission.** The uploader submits the set: DRAFT → SUBMITTED. Files are frozen from here (no add or remove). [REC]
5. **Homeowner review.** The homeowner sees the set and either approves it for checking or requests changes with a reason. Changes: the set becomes CHANGES_REQUESTED (terminal) and the provider starts a new set version, which supersedes it. Revision rounds: [OPEN] BP-12 (IHB:1120 "number of revisions UNKNOWN"). [REC]
6. **Check.** The designated checker (BP-01; CQ-26) checks the set and records APPROVED or REJECTED with a note. Structural drawings are checked by the structural engineer who gives the sign-off. The checker is appointed by Plan2Build and need not be an employee; a checker with a platform account records the check directly, otherwise operations record it with the checker's signed check note as evidence. [PD] BP-01; recording method [REC]
7. **Approved = authoritative.** An APPROVED set is immutable. It is the only kind of drawing a Build Plan version may reference. [REC]; AI:66 "Only approved drawings can be referenced by a Build Plan version" [SOURCE]
8. **Supersession.** A later approved set for the same request supersedes the earlier one (state SUPERSEDED, still readable). A Build Plan version that is ISSUED or ACCEPTED keeps pointing at the set it was issued with; using the new set needs a new Build Plan version. [REC]; [SOURCE] S3R:116 (architect pack supersedes concept, BOQ re-measured, new RFQ pack version)
9. **Architect over concept.** When a `LISTED_ARCHITECT` or `OUTSIDE_PROFESSIONAL` set is approved for the same scope as a `PLAN2BUILD_ARRANGED` set, the concept set is superseded. [SOURCE] CD-20

### B.4 What 3.5 does not build

No CAD, no drawing editor, no measurement tool, no image-to-plan conversion. Drawings are files with metadata. [SOURCE] IC:13 (no invented scope); [REC]

---

## C. Build Plan model

| Element | Definition | Marker |
|---|---|---|
| Nature | An authoritative downstream artefact and package service; not a mandatory route; inputs from Plan2Build professionals, the homeowner, outside professionals and approved design inputs | [PD] PD-13, PD-17, PD-25 |
| Cardinality | One Build Plan per project, many versions | [SOURCE] DATA:150-151 |
| Scope | The construction of the house as described by the requirement: the 67 S04 lines (A, B, C as groups only), the drawings, BOQ, schedule | [PD] PD-09, PD-13; [REC] whole-house scope |
| Lines not applicable | A line may be marked NOT_APPLICABLE with a reason (for example basement lines without a basement; a project already past stage 3, RQ:159) | [REC]; BP-18 |
| Contents of a version | Approved drawing set reference; project specification values; BOQ with rate-card version; cost estimate and stage-wise budget derived from the BOQ; schedule; decisions-calendar extract derived from the schedule; inclusions, exclusions and assumptions; structural sign-offs; issue record; homeowner acceptance | [PD] PD-13 (drawings, values, BOQ, estimate, schedule, approved design, RFQ-ready scope); [SOURCE] MVP:185 and IHB:1052-1073 (inclusions, exclusions, decisions calendar, cash-flow, payment schedule) |
| Payment schedule and cash-flow plan | In the sources (MVP:185, MVP:189). No source gives construction milestone percentages; payments between family and contractor never pass through Plan2Build | BP-10: no payment-percentage schedule; a monthly cash-flow figure only once authoritative dates exist (BP-07A) |
| Margin disclosure | MVP:56, MVP:192: Plan2Build's margin printed where it supplies material | [SOURCE]; not applicable: Plan2Build supplies no material [PD] aggregator (CD-01). Not built |
| Package | A package service; package-gated work needs an active package; refund leaves issued and accepted versions readable and blocks new work | [PD] PD-13, BP-09 |
| Who drafts | The advisor (operations staff with the OPS_ADVISOR project role or OPS staff role) | [SOURCE] MVP:187, IHB:1083, DOM:116 |
| Who issues | Operations with MFA, only when every condition in D.3 holds | [SOURCE] API:102, DOM:116 |
| Generation speed | Within 30 seconds (BR-058) applies to rendering | [SOURCE] IHB:3222 |

---

## D. Build Plan state machine

### D.1 States

| State | Meaning | Content editable | Marker |
|---|---|---|---|
| DRAFT | Being prepared by the advisor | Yes | [SOURCE] STATE:204 |
| IN_REVIEW | Submitted for checks: structural sign-off and operations review. Content frozen so signatures bind to fixed content | No | [SOURCE] STATE:204 (sign-off requested); freeze [REC] |
| ISSUED | Released to the homeowner; content, drawings references, values, BOQ, schedule, rate card and PDF immutable | No | [SOURCE] BR-051, STATE:204 |
| ACCEPTED | The homeowner formally accepted this issued version | No | [PD] PD-13 |
| CHANGES_REQUESTED | The homeowner asked for changes to this issued version instead of accepting; it can no longer be accepted | No | [REC] (the brief's proposed path; needed so a rejected version cannot later be accepted by mistake) |
| SUPERSEDED | A later version replaced this one; still readable | No | [SOURCE] STATE:204 |
| WITHDRAWN | Abandoned before acceptance (draft dropped, error found after issue, package ended) | No | [SOURCE] STATE:204 (drafts); after-issue use [REC] |

No other state is needed. `PLANNING` and `PLAN_ISSUED` are project statuses, not Build Plan states (BP-14).

### D.2 Transitions

| From | To | Trigger | Actor | Validations | Effects | Marker |
|---|---|---|---|---|---|---|
| none | DRAFT | create | Advisor (ops) | Project ELIGIBLE; package active (BP-09); no other DRAFT or IN_REVIEW version | `version_no` = previous + 1; copies the previous version's content as a starting point, each value marked "carried forward" | [REC] |
| DRAFT | IN_REVIEW | submit | Advisor | Completeness check (D.3 items 1 to 7) | Content hash computed and stored; sign-off requests opened for applicable structural lines | [SOURCE] STATE:204; hash [REC] |
| IN_REVIEW | DRAFT | return | Advisor, OPS, or a signer refusing | Reason required | Every sign-off on this version becomes VOID with the reason | [REC] |
| IN_REVIEW | ISSUED | issue | OPS with MFA | D.3 all items; issuer is not the last editor of the content (BP-13) | Freeze; render PDF job; previous ISSUED or CHANGES_REQUESTED version (if any, never ACCEPTED) → SUPERSEDED; homeowner notified; issue recorded in history, audit and events only, never as a refund usage record (BP-09) | [SOURCE] API:102, DOM:111; four-eyes [PD] BP-13 |
| ISSUED | ACCEPTED | accept | Owner, with a one-time code (BP-05) | Version is the latest ISSUED; PDF rendered; package active (BP-09) | Acceptance record; the previously ACCEPTED version (if any) → SUPERSEDED; RFQ baseline points here | [PD] PD-13; mechanics [REC] |
| ISSUED | CHANGES_REQUESTED | request changes | Owner | Reason required | Advisor notified; a new DRAFT may be created from it | [REC] |
| ISSUED | WITHDRAWN | withdraw | OPS with MFA | Reason; not accepted | Homeowner notified | [REC] |
| DRAFT or IN_REVIEW | WITHDRAWN | withdraw | Advisor or OPS | Reason | Open sign-off requests VOID. A package ending does not withdraw drafts; it blocks their progress (BP-09) | [SOURCE] STATE:204; [PD] BP-09 |
| ACCEPTED | SUPERSEDED | successor accepted | System | A later version was ACCEPTED | Old version stays readable; history keeps both | [REC] |
| CHANGES_REQUESTED | SUPERSEDED | successor issued | System | A later version was ISSUED | | [REC] |

Invariants: at most one DRAFT or IN_REVIEW version per plan; at most one ISSUED-not-yet-answered version; at most one ACCEPTED version (the RFQ baseline); ACCEPTED is never WITHDRAWN, only SUPERSEDED by a later acceptance. [REC]

### D.3 Issue conditions

1. An APPROVED drawing set is referenced (BP-02 decides the required drawing classes). [SOURCE] API:102 "a design is attached"
2. Every applicable specification line has a project value or NOT_APPLICABLE with a reason. [PD] PD-14
3. Every applicable structural line is signed on this exact version's content hash. [PD] PD-24; [SOURCE] STATE:204
4. A BOQ exists, priced only from one rate card version, every amount equal to quantity × rate. [SOURCE] MVP:153-161
5. In production the rate card is an approved production card, never DEMO. [SOURCE] BASE:215 N-05; [REC] hard check
6. A schedule exists with durations and explicitly entered dependencies; no calculated dates until BP-07A is resolved and a start date exists. [SOURCE] D-04; [PD] BP-07
7. Inclusions, exclusions and assumptions are recorded (each may be empty only with an explicit "none"). [SOURCE] MVP:185
8. Package active. [PD] PD-13, BP-09
9. Issuer holds OPS with MFA verified within the window. [SOURCE] SEC:78

### D.4 Audit and events

Every transition writes an append-only history row (from, to, actor, role, reason) and an audit row. Events (ids only): `buildplan.drafted`, `buildplan.submitted`, `buildplan.returned`, `buildplan.signed_off` (per line), `buildplan.issued`, `buildplan.accepted`, `buildplan.changes_requested`, `buildplan.withdrawn`, `buildplan.superseded`, `documents.rendered`. [SOURCE] DOM:113 for the core set; the rest [REC]. [SUPERSEDED] `baseline.locked` and the contract baseline (DOM:110, DATA:154) move to the construction slice; in 3.5 the accepted version is the RFQ baseline (X2).

---

## E. Specification value model

| Rule | Marker |
|---|---|
| S04 masters define criteria; the advisor or engineer supplies the project value in a Build Plan version; issue freezes it; the RFQ uses the issued brand-neutral values; no values are invented | [PD] PD-14 |
| The 67 lines are criteria, never sample project values; project values never go back into the masters | [PD] PD-14; [SOURCE] SCH:709 "the issued text is stored on the project instance" |
| A/B/C are groups only: never products, never separately paid, never a gate | [PD] PD-09 |
| Criteria "are indicative and must be confirmed against the applicable Indian Standards and the project's structural design before issue" | [SOURCE] SCH:712 |
| Brand never appears in a value | [SOURCE] S04 R1, R9; [PD] PD-15 (brand-neutral) |
| Changing a master does not change issued project instances | [SOURCE] MVP:152; SCH:710 |

### E.1 A project value

| Field | Meaning | Marker |
|---|---|---|
| Line code and master version | The criteria the value answers, with the criteria text copied as it stood | [REC] |
| Applicability | APPLICABLE or NOT_APPLICABLE with reason | [REC]; BP-18 |
| Value text | The project-specific specification, for example a grade, class, thickness, system type | [SOURCE] SCH:17-36 field "performance specification" |
| Basis | Where the value comes from: STRUCTURAL_DESIGN (engineer), ARCHITECT_DRAWING, HOMEOWNER_PROVIDED, ADVISOR (with reason), STANDARD_REFERENCE (an IS reference cited by the advisor) | [REC] |
| Source note and evidence | Free text and optional files (a calculation sheet, a drawing sheet, a soil report) | [REC] |
| Entered by | User, role, time; on a carried-forward value, the original entry is kept and the carry-forward recorded | [REC] |

### E.2 Who fills

| Lines | Who may enter | Who must confirm | Marker |
|---|---|---|---|
| Structural (8 lines) | The advisor may enter a value taken from the engineer's design; the engineer may enter directly on the platform when they have access | The signing engineer, by signing the line (section F) | [PD] PD-14 ("advisor or engineer"), PD-24 |
| All others | The advisor (operations) | Operations at issue (four-eyes BP-13) | [SOURCE] SCH:709, MVP:187 |
| Homeowner | Never enters or edits a value | | [SOURCE] S04 R6 "Homeowner chooses, unprompted" applies to options, not criteria; S3R:73 |

### E.3 Validation

Every applicable line valued before IN_REVIEW; value text non-empty and length-limited; no value may be entered on an ISSUED, ACCEPTED, CHANGES_REQUESTED, SUPERSEDED or WITHDRAWN version; structural values change only in DRAFT, and any change voids that line's sign-off. Brand detection is not automatic: the checker attests brand neutrality at issue. [REC]

### E.4 Versioning and changes

A new Build Plan version copies values as "carried forward"; editing creates a new value row in the new version, never edits the old one. A new master version reaches a draft only when the advisor refreshes that line (recorded); issued and accepted versions keep the master version they were issued with. Whether new master versions reach projects without an issued plan has no source (S3R:75): [REC] as described. [REC]

### E.5 Relation to construction-time line states

`project_spec_lines` (SPECIFIED → OPTIONS_ISSUED → CHOSEN → ...) is the construction-time machine and is not changed by 3.5 except: [REC] when a version is ACCEPTED, each project line records a pointer to its accepted value; the per-line `engineer_signoff` column copied from the master is [SUPERSEDED] by per-version sign-off (PFR:222) and the workspace reads sign-off from the accepted version. Options, OTP choice at CHOSEN, and how contractors price lines not yet chosen (D3-19) belong to later slices.

### E.6 Line timing

With one Build Plan covering all 67 lines before construction (PD-09, PD-13), the S04 problem of lines due before their group's issue point (X15, OQ-051, EC-053) no longer arises for values. Decide-by dates for homeowner choices come from the schedule (section K). [REC]

---

## F. Structural sign-off model

| Rule | Marker |
|---|---|
| Where structural sign-off applies, a qualified structural engineer signs before the relevant authoritative Build Plan version is issued | [PD] PD-24 |
| The signer may be Plan2Build-listed, the homeowner's own, or another qualified outside engineer where the rules permit | [PD] PD-24 |
| "Plan2Build compiles and communicates; the engineer specifies" | [SOURCE] SCH:68; STR:266; BR-055 |
| Lines requiring sign-off: A01, A02, A04, A05, A09, A12, A13, A19 (`is_structural`) | [SOURCE] S04 †; ruling 2.4 (A01); seed v1 |
| No B or C line is structural; group C "needs no engineer sign-off" | [SOURCE] SCH:711 |
| Structural lines are never brand-monetised | [SOURCE] R9 |

### F.1 Signer identity

| Signer | Identity | Credential check | Marker |
|---|---|---|---|
| Listed engineer | Profile in category STRUCTURAL_ENGINEER, LISTED, with an ACTIVE engagement on this project in that category | Verified REGISTRATION check from 3.2 (issuer, number) | [REC] |
| Outside engineer | Name, firm, registration number, issuing body; registration certificate file | Operations record a check against the certificate before the sign-off counts | [REC]; [SOURCE] F-04 recommendation PFR:263 "Registration number and certificate recorded and checked by operations" |
| Plan2Build-retained engineer | Same as listed engineer, or recorded as an engineer contact by operations | Same | [PD] PD-24 allows; not mandatory |

What counts as "qualified" beyond a registration (for example Raipur municipal licensing): [OPEN] CQ-22, F-04. No legal requirement is invented here.

### F.2 What is signed

One sign-off per (Build Plan version, structural line). The signed content is the line code, criteria text, project value, applicability, the version id, the version's content hash at IN_REVIEW, the approved drawing set id with the file hashes of its structural drawings, and the statement text with its version. [SOURCE] F-04 recommendation; [PD] BP-04 (minimum fields, configurable versioned statement, baseline wording pending final client and legal confirmation before production).

### F.3 Capture

| Mode | How | Evidence stored | Marker |
|---|---|---|---|
| On platform | A verified engineer opens the version on the professionals host and signs each line; confirmation by a one-time code to their account email. Described as a confirmation, never as a legally recognised electronic signature | Challenge id, time, account, IP hash, statement version | [PD] BP-04 |
| Signed documentation | Operations upload documentation signed by an outside engineer covering listed lines of this version, with the engineer's identity and credential reference and their own attestation | File (sha256), uploader, attestation, credential reference, time | [PD] BP-04 |

### F.4 Partial sign-off, states, revocation

- Lines are signed one by one; issue needs all applicable lines signed. Partial sign-off is a normal intermediate state, never issuable. [REC]
- States per sign-off: SIGNED, VOID. A sign-off becomes VOID when the version returns to DRAFT, when the signer revokes before issue (reason required), or when operations void it (reason, MFA). [REC]
- After ISSUE a sign-off cannot be voided silently: a revocation is recorded as an event and the version must be WITHDRAWN (if not accepted) or replaced by a new version (if accepted); the homeowner is told. [REC]
- A structural line marked NOT_APPLICABLE needs the engineer's signed confirmation of that applicability. [REC]; BP-18
- Turnaround and homeowner visibility (OQ-046): [OPEN], not blocking.

### F.5 Audit

Each sign-off, void and revocation is append-only with actor, role, reason and hash. [SOURCE] SEC:219

---

## G. Drawing model

| Question | Finding | Marker |
|---|---|---|
| Drawing types required | No MVP-line source lists drawing types; 33.6 proposes site plan, floor plans, elevations, one section (concept) and structural drawings by the engineer; AI:18-25 lists SITE_PLAN, FLOOR_PLAN, ELEVATION, SECTION, STRUCTURAL, ARCHITECT_PACK | [PD] BP-02: site plan, floor plans, at least one elevation, at least one section, structural drawings where structural lines apply; nothing else mandatory |
| Are architect drawings authoritative | Yes once checked and approved (B.1); they replace concept drawings | [SOURCE] CD-20 |
| Structural drawings separate | Yes as a class; produced by the engineer; who produces calculations is POQ-023 | [SOURCE] 33.6; [OPEN] POQ-023 |
| Permit-ready drawings required | Not asked; "Permit drawings are normally signed by a licensed architect or engineer; confirm the Raipur rule" | [PD] BP-02: permit-specific packages out of scope for 3.5; CQ-22 stays open for later |
| Who creates / checks / signs | Provider per B.2; checker appointed by Plan2Build; structural drawings checked by the signing engineer | [PD] BP-01 (answers CQ-26 for this slice) |
| Outside architect drawings importable | Yes, as `OUTSIDE_PROFESSIONAL` sets | [PD] PD-25; [SOURCE] PFR:189 |
| Revisions create a new Build Plan version | Only if the Build Plan version is ISSUED or later; a draft may switch to the newer approved set | [REC] |
| Attachment to the plan | A version references exactly one approved drawing set (which may hold several classes) | [REC] |
| 3D views | Illustrative only, never required; AQ-18 default "issue without views allowed, flagged 'to follow'" | [SOURCE] AI:62, ADR-013; [PD] PD-27 for AI views |
| CAD | Not built | [REC]; no source requires it |

### G.1 Drawing set

A drawing set version: project, design request, kind (B.2), set number, state (DRAFT, SUBMITTED, CHANGES_REQUESTED, APPROVED, REJECTED, SUPERSEDED), provider identity and basis, checker, check note and time, supersedes. Files in a set: file id with sha256, class (SITE_PLAN, FLOOR_PLAN, ELEVATION, SECTION, STRUCTURAL, MEP, SANCTIONED_PLAN, OTHER), floor where relevant, title, sheet number. Accepted file types: PDF and images through the existing scanner; CAD formats only as attachments, not rendered. [REC]

---

## H. BOQ model

| Element | Definition | Marker |
|---|---|---|
| Owner | The Build Plan version: one BOQ per version, immutable with it | [SOURCE] DATA:152 |
| Line | Line number, item code (from the rate card's item list), description, unit, quantity, rate, amount, stage number (and floor where relevant), linked spec line codes, assumptions note | [SOURCE] TPB:277, DATA:152, S3R:107 |
| Quantity basis | MEASURED_FROM_DRAWING (with the drawing file reference), PROVIDED_BY_PROFESSIONAL, ADVISOR_ESTIMATE (with reason) | [REC]; measured from approved drawings [SOURCE] 33.6 |
| No AI quantities | Never | [PD] PD-05; [SOURCE] AI:25 |
| Rate | Taken from one rate card version's item rate; the version is recorded on the BOQ; a line may carry a manual rate only with a reason and is flagged | [SOURCE] MVP:93-94 (estimate reproducible against the card in force); manual rate [REC] |
| Amount | Computed by the server as quantity × rate, rounded to the rupee rule of the card; stored | [SOURCE] MVP:153 ("stage-wise breakdown always sums to the headline total") |
| Exclusions and assumptions | Version-level lists, plus per-line assumptions | [SOURCE] MVP:185, TPB:377 |
| Entry | Advisor enters lines individually or imports a structured file; validation rejects unknown item codes and units that differ from the card | [REC] |
| Revision | A new version copies lines as carried forward; any change is a new row in the new version | [REC] |
| Totals | Version total, totals per stage (stage-wise budget), totals per group A/B/C for display only | [SOURCE] MVP:185 stage-wise budget; group display [PD] PD-09 |
| Contractor prices | Never shown to the homeowner; never part of the Build Plan | [SOURCE] MVP:201 |

No production quantities or rates are invented. Development uses DEMO item rates marked TEST (section I).

---

## I. Rate-card model

| Question | Finding | Marker |
|---|---|---|
| What exists | Area-rate cards (schema 1) for the indicative estimator; DEMO only; no item rates | [SOURCE] as built; S3R:107 |
| DEMO versus production | DEMO: `is_demo` true, no publisher, never served in production, every result flagged. Production: published by a named approver | [SOURCE] BASE:215 N-05; DATA:131 |
| Required for a Build Plan | An item-rate card with at least: item code, item description, unit, rate, geography, effective-from, effective-to where applicable, source or reference, status, version | [PD] BP-06; [SOURCE] MVP:93-94, TPB:275 |
| Who prepares and publishes | Operations prepare a DRAFT card; an authorised ADMIN approves and publishes it with MFA; a published version is immutable; status DRAFT, PUBLISHED, RETIRED | [PD] BP-06; [SOURCE] API:280 |
| Versioning and effective dates | Version per geography; effective-from, and effective-to where applicable; at most one published card in force per geography and date | [PD] BP-06; uniqueness [REC] |
| City or region | Raipur only at the POC; "Do not build tenanting" | [SOURCE] MVP:350 |
| Revision | A new card never changes an existing BOQ; a draft is re-priced only when the advisor chooses to (recorded); issued and accepted versions keep their card | [SOURCE] MVP:153-161 |
| DEMO guard | A Build Plan priced from a DEMO card can be issued only outside production and carries a TEST banner in its PDF; production issue refuses it | [SOURCE] N-05; [REC] mechanism |
| Production values | Not invented. Content still to be prepared by operations (production launch item); stage cost shares never substitute for item rates | [PD] BP-06 |
| Estimator card | Keeps schema 1 (area rates) for the indicative estimate; the item card is schema 2 or a separate catalogue | [SOURCE] BASE:246 mentions "rate card schema version 2"; [REC] separate item card so the indicative estimator is untouched |

---

## J. Estimate relationship

| Price | What it is | Stored where | Marker |
|---|---|---|---|
| A. Indicative estimate | Area-based range from the requirement and the area-rate card | `project_estimates`, append-only per requirement version; never overwritten | [PD] PD-04; [SOURCE] as built |
| B. Build Plan estimate | Sum of the BOQ of a specific version, with the item-rate card version; stage-wise budget from BOQ stage tags | On the version, immutable once issued | [PD] PD-13 (estimate in the plan); computation [REC] |
| C. Professional quote | A contractor's price in response to an RFQ | 3.6 | [PD] PD-04, PD-15 |

- B is a new authoritative calculation, not an adjustment of A. [REC]
- A stays visible as "indicative, from your requirement"; B shows its own total; the difference is shown as a figure with no explanation invented by the system; the advisor may add an explanation note on the version. [REC]
- The RFQ baseline is the accepted version's scope (drawings, values, BOQ quantities, schedule), not B's price. Contractors never see Plan2Build's rates. [PD] BP-08
- The rate card version is stored on B and never changes. [SOURCE] MVP:153-161
- Stage-wise budget from BOQ lines removes the need for stage cost-share percentages in the Build Plan (X12). [REC]

---

## K. Schedule model

| Question | Finding | Marker |
|---|---|---|
| Universal durations or cost shares | None approved; stage master values NULL | [SOURCE] D-04, ruling 2.9 |
| Source of a project schedule | An operations-entered schedule is allowed | [SOURCE] D-04; S3R:166 recommendation (advisor-entered per project) |
| Who enters | The advisor, with input from the engaged professionals where available | [PD] BP-07 |
| Dates or durations | Start date is unknown before a contractor exists (IHB:980) | [PD] BP-07: durations stored independently of dates; dates calculated only after a baseline start date exists and BP-07A is resolved |
| Units | One schedule entry per stage instance of the project (stage, floor), so basement and floor repeats follow ruling 2.2 | [SOURCE] ruling 2.2; [REC] entry per instance |
| Dependencies | No source gives a dependency rule; "configurable stages, dependencies" only | [SOURCE] CPB:337; [PD] BP-07: only explicitly entered dependencies, no default derived from any order |
| Build order (defect A.2) | Build order is not `sequence`, and no source defines how repeated per-floor instances interleave or which stages depend on which (S04 section 4; MVP:42, 149 say only that stages 5, 6 and 9 repeat per floor) | **[OPEN] BLOCKER BP-07A**; never inferred from display order; no `build_order` is set until it is resolved |
| Decisions calendar | Decide-by = consuming stage start minus decide-by weeks (S04 §8, MVP:117) | [SOURCE]; shown as "weeks before the consuming stage" until dates exist; no decide-by date is calculated until BP-07A is resolved and a start date exists |
| Revisions | A schedule change is a new Build Plan version; after acceptance, schedule changes belong to construction (variations) | [SOURCE] MVP:203-211 for variations (later slice); [REC] |
| Baseline freeze | At homeowner acceptance with the version | [PD] BP-05 |
| Gantt | Not built | [SOURCE] MVP:346 excludes Gantt charts |

---

## L. PDF model

| Item | Finding | Marker |
|---|---|---|
| Engine | fpdf2, deterministic, hash stored; rendered in the issuing request | [PD] ADR-023 (2026-10-05) supersedes ADR-018 (WeasyPrint); BR-056 |
| Determinism | Same inputs give byte-identical output; the render record keeps template version and context hash | [SOURCE] BR-056; DATA:272 |
| Timing | Rendered after ISSUE; a failed render does not undo ISSUED; acceptance waits for the rendered PDF | [SOURCE] STATE:204; acceptance wait [REC] |
| Language | English (ADR-022); BR-057 asks Hindi and English | [PD] ADR-022; BP-11 approved (client confirmation of BR-057 is a launch item) |
| Share link without login | BR-050 asks one; share tokens and expiry are deferred (OQ-047) | [SOURCE]; [REC] 3.5 provides only signed-in, logged downloads; public link later |
| Legal wording | None beyond source statements: criteria are indicative and confirmed against Indian Standards and the structural design (SCH:712); "Plan2Build compiles and communicates; the engineer specifies" (SCH:68); the illustrative label for any image | [SOURCE]; any further disclaimer [OPEN] BP-17 |

### L.1 Sections of the issued PDF [REC], each from the version only

1. Cover: project code, locality, Build Plan version number, issue date, issuer role, content hash, rate card version, "TEST" banner when DEMO.
2. Contents and how to read the plan.
3. Project facts from the requirement version used.
4. Drawings register: each drawing's class, title, sheet, provider, checker, approval date, file hash. Drawings are attached as an annex or a bundled file set (BP-02 decides).
5. Specification values by group A, B, C: code, item, criteria, project value, basis; structural lines marked with the signer's name, registration and time.
6. BOQ by stage, with item, unit, quantity, rate, amount, assumptions; totals per stage and overall.
7. Estimate: the Build Plan total and the stage-wise budget; the indicative estimate shown for reference with its card.
8. Schedule: stages with durations and dependencies, target dates only if given.
9. Decisions calendar extract.
10. Inclusions, exclusions, assumptions.
11. Sign-off register.
12. Revision history: earlier versions with dates and the reason for each new version.

Homeowner acceptance cannot be printed into the issued PDF without breaking immutability. [REC] the acceptance is stored separately and shown on the web record; a short acceptance receipt may be rendered as its own document.

---

## M. RFQ boundary

### M.1 What 3.5 outputs (the RFQ-ready scope)

An **RFQ scope manifest** for one ACCEPTED Build Plan version [REC]:

| Item | Content |
|---|---|
| Identity | Build Plan id, version id and number, content hash, accepted time |
| Drawings | The approved drawing set id and each file's id and sha256 |
| Specifications | Issued values per line, brand-neutral, with criteria and applicability |
| BOQ | Lines with item, description, unit, quantity, stage, spec links; never Plan2Build's rates or amounts (BP-08) |
| Schedule | Durations, dependencies, target start if given |
| Scope | Inclusions, exclusions, assumptions |
| Quote format | A standard quote structure version: one price per BOQ line, explicit exclusions per line, the contractor's own schedule; a quote cannot be submitted with required fields missing "without explicit exclusion" |

[SOURCE] BR-080 IHB:3246, PD-15, MVP:121-122, TPB:381; quote structure details are 3.6.

### M.2 The RFQ never depends on

AI exploration history, design references, discarded or unapproved drawings, draft specifications, DEMO pricing, or any version other than the one named. [PD] PD-05, PD-15; [SOURCE] N-05

### M.3 Open

Only contractor RFQs need an accepted Build Plan baseline [PD] BP-08 (answers F-10). API:164's "ISSUED plan for every RFQ" is [SUPERSEDED].

### M.4 Quote-holder review placement

3.4 built intake. The review (comparison of the held quote against a scope) belongs to the quote workflow in 3.6, using the same normalisation model as RFQ quotes (MVP:126 normalisation adjustments). Without a Build Plan the scope is the requirement and the criteria; with an accepted Build Plan it is that version. [SOURCE] SLICE3_4 R; S3R D3-03; [OPEN] CQ-02 (not yet asked). 3.5 builds nothing for it.

---

## N. Data model (minimum)

All tables carry `project_id` (BASE N-03 row scoping). Append-only tables refuse UPDATE and DELETE; versioned rows allow only lifecycle columns to change (`p2b_allow_only_columns`, as in 3.3 and 3.4). [REC] throughout; [SOURCE] DATA 146-159 for the shape.

| Table | Purpose | Key columns | Guard |
|---|---|---|---|
| `design_requests` | A request for authoritative design | kind (B.2), engagement id or outside provider details, requirement version, illustrative reference ids, state (OPEN, CLOSED), opened by | lifecycle columns only |
| `drawing_sets` | A drawing set version | design request, set number, state, provider identity and basis, checker, check note and time, supersedes | lifecycle columns only; APPROVED content frozen |
| `drawing_files` | Files in a set | set, file id, sha256, class, floor, title, sheet | append-only once the set is SUBMITTED |
| `build_plans` | One per project | project UNIQUE | |
| `build_plan_versions` | A version | plan, version number UNIQUE per plan, state, drawing set, rate card version, stage master version, requirement version, content hash, inclusions, exclusions, assumptions, explanation note, issued by/at, document file, template version, render state, created from version, withdrawn reason | content columns frozen from IN_REVIEW; lifecycle columns only |
| `build_plan_spec_values` | Values per version and line | version, line code, master version, criteria text, applicability, value text, basis, source note, evidence file ids, entered by, role, time, carried from | UNIQUE (version, line); frozen with the version |
| `boq_lines` | BOQ per version | version, line number, item code, description, unit, quantity, quantity basis, drawing file, rate, rate source (card item or manual with reason), amount, stage, floor, spec line codes, assumptions | frozen with the version |
| `build_plan_schedule_entries` | Schedule per version | version, stage number, floor, duration days, explicitly entered predecessor entries; no dates (BP-07, BP-07A) | frozen with the version |
| `structural_signoffs` | Sign-off per version and line | version, line code, signer kind, profile id and category or outside identity (name, registration number, issuer), credential reference (verification check id or certificate file and operations check), capture mode, challenge id or signed-document file, statement version and text, drawing set id and structural drawing hashes, signed content hash, state SIGNED/VOID, void reason, times | SIGNED rows change only to VOID |
| `signoff_statement_versions` | Configurable sign-off statement (BP-04) | version, text, status, approved by, note ("pending legal confirmation") | published rows immutable |
| `drawing_checker_appointments` | Appointed checkers (BP-01) | name, qualification and registration reference, appointed by, linked user account if any, from and to | appointments end, never deleted |
| `build_plan_acceptances` | Homeowner acceptance evidence | version UNIQUE, accepted by, role, challenge id, statement text, content hash accepted, time, IP hash | append-only |
| `build_plan_events` | History | version, from and to state, actor, role, reason (includes changes requested with the homeowner's reason) | append-only |
| `item_rate_cards`, `item_rate_card_lines` | Item rates (BP-06) | geography, version, status (DRAFT, PUBLISHED, RETIRED), is_demo, effective from, effective to, source or reference, prepared by, published by; lines: item code, description, unit, rate | published rows immutable |
| `file_objects` | New purposes: DRAWING, SIGNOFF_EVIDENCE, BUILD_PLAN_DOCUMENT | | existing |
| `project_spec_lines` | Pointer to the accepted value (E.5) | `accepted_value_id` | additive |

Not created in 3.5: `contract_baselines`, `payment_schedules`, `cashflow_plans` as tables (a cash-flow figure is computed only once dates exist, BP-10), a `build_order` column (waits for BP-07A), `share_tokens`, `rendered_documents` as a generic table (the version carries its render fields until a second document kind needs the generic table), `design_artefacts` and `generation_jobs` (replaced by drawing sets; no generation). [REC]

---

## O. API model (proposed, not implemented)

Every create and transition POST takes `Idempotency-Key`; every write is audited; refusals are 409 with a `reason`. [SOURCE] API section 1; 3.4 pattern

| Route | Actor | Rules |
|---|---|---|
| `POST /projects/{id}/design-requests` | Owner | Package rule BP-09; kind; provider; illustrative references only by id |
| `GET /projects/{id}/design-requests`, `GET .../{rid}` | Owner, household, ops; the provider | Sets with states and files |
| `POST /projects/{id}/design-requests/{rid}/sets` and file upload, complete, submit | Uploader per B.2 (listed professional on the pro host with an ACTIVE engagement; owner; ops) | Files scanned; submit freezes |
| `POST .../sets/{sid}/homeowner-decision` | Owner | APPROVE_FOR_CHECK or CHANGES with reason |
| `POST /ops/drawing-sets/{sid}/check` | Checker (BP-01) with MFA if staff | APPROVED or REJECTED with note |
| `POST /ops/projects/{id}/build-plan/versions` | Advisor | Creates DRAFT from the latest version |
| `PUT /ops/build-plan-versions/{vid}/drawing-set` | Advisor | APPROVED set only; DRAFT only |
| `PUT /ops/build-plan-versions/{vid}/spec-values/{code}` | Advisor; engineer for structural lines when on the platform | DRAFT only; E.3 |
| `PUT /ops/build-plan-versions/{vid}/boq` (lines or file import) | Advisor | DRAFT only; card items and units; server computes amounts |
| `PUT /ops/build-plan-versions/{vid}/schedule` | Advisor | DRAFT only; one entry per stage instance |
| `PUT /ops/build-plan-versions/{vid}/scope` | Advisor | Inclusions, exclusions, assumptions |
| `POST /ops/build-plan-versions/{vid}/submit`, `/return`, `/withdraw` | Advisor, OPS | D.2 |
| `GET /pro/signoffs`, `GET /pro/signoffs/{vid}`, `POST /pro/signoffs/{vid}/lines/{code}` (with one-time code), `POST .../revoke` | Listed engineer with an ACTIVE STRUCTURAL_ENGINEER engagement | IN_REVIEW only; content hash bound |
| `POST /ops/build-plan-versions/{vid}/signoffs` (signed sheet) and `/signoffs/{sid}/void` | OPS with MFA | Credential check recorded; reason for void |
| `POST /ops/build-plan-versions/{vid}/issue` | OPS with MFA, not the last editor | D.3; queues the render |
| `GET /projects/{id}/build-plan`, `GET .../versions/{vid}` | Owner, household (issued versions and later only); ops (all) | Drafts never shown to the homeowner [SOURCE] DOM:116 |
| `POST /projects/{id}/build-plan/versions/{vid}/accept` (start and confirm with one-time code) | Owner | BP-05; latest ISSUED; PDF rendered |
| `POST /projects/{id}/build-plan/versions/{vid}/request-changes` | Owner | Reason |
| `GET /projects/{id}/build-plan/versions/{vid}/document` | Owner, household, ops; later RFQ recipients | Logged link |
| `GET /projects/{id}/build-plan/history` | Owner, household, ops | All issued and later versions, events |
| `GET /ops/build-plan-versions/{vid}/rfq-scope` | Ops (3.6 consumer) | ACCEPTED only; the manifest of M.1 |
| `POST /admin/item-rate-cards`, `/publish` | ADMIN with MFA | Source note; immutable once published |

---

## P. Permissions

| Actor | Can | Cannot | Marker |
|---|---|---|---|
| Homeowner (owner) | Open design requests; upload homeowner-provided drawings and outside professionals' drawings; review drawing sets; see ISSUED and later Build Plan versions; accept; request changes; download | See drafts; edit values, BOQ, schedule; sign | [SOURCE] DOM:116 (members read issued); [PD] PD-13 (accept); rest [REC] |
| Household member | Read what the owner reads | Accept, request changes, open requests | [REC]; [OPEN] OQ-027 |
| Listed architect (ACTIVE ARCHITECT engagement) | Upload and submit drawing sets for that project's requests addressed to them; revise after changes requested | See the Build Plan draft, values or BOQ; act on other projects | [REC] |
| Listed structural engineer (ACTIVE engagement) | See the IN_REVIEW version's structural lines, values and the drawings; enter structural values when the advisor allows; sign or revoke | Issue; edit non-structural content | [PD] PD-24; [REC] scope |
| Outside professional | No platform access in 3.5; their drawings and signed sheets enter through the owner or operations | | [OPEN] F-03 |
| Advisor (OPS staff or OPS_ADVISOR project role) | Draft, enter values, BOQ, schedule, scope; submit; return; withdraw drafts | Issue a version they last edited | [SOURCE] MVP:187, DOM:116; four-eyes [REC] BP-13 |
| OPS (MFA) | Check drawings when designated (BP-01); record credential checks; upload signed sheets; issue when D.3 holds; withdraw an unaccepted issued version | Edit an issued version; accept for the homeowner | [SOURCE] API:102 |
| ADMIN (MFA) | Publish rate cards, master versions; privileged overrides only with reason and audit | Edit issued content | [SOURCE] API:280, SEC:78 |
| Nobody | Edit an ISSUED, ACCEPTED, CHANGES_REQUESTED, SUPERSEDED or WITHDRAWN version | | [SOURCE] BR-051 |

---

## Q. Security, audit and invariants

| Invariant | Enforcement | Marker |
|---|---|---|
| An issued version cannot be mutated | Database trigger allows only lifecycle columns; service checks state | [SOURCE] DATA:151; [REC] trigger |
| Issued values, BOQ, schedule cannot be mutated | Rows belong to the version; trigger refuses UPDATE and DELETE once the version leaves DRAFT | [REC] |
| A signed line cannot change silently | Sign-off stores the content hash; any draft change returns the version to DRAFT and voids sign-offs; issue recomputes the hash and requires every SIGNED hash to match | [REC] |
| An accepted plan cannot be replaced silently | Only a later version's acceptance supersedes it; never withdrawn; the homeowner is notified of every new issue | [REC] |
| Changes create a new version | No edit route for non-DRAFT versions | [SOURCE] BR-051 |
| Old versions stay readable | No deletion; SUPERSEDED and WITHDRAWN readable by the same audiences | [REC] |
| The RFQ references one explicit version | The manifest carries version id and content hash | [REC] |
| The PDF identifies its version | Cover and every page footer: version number and content hash | [REC] |
| The rate card version is immutable on the issued artefact | Stored on the version and every BOQ line; published cards immutable | [SOURCE] MVP:153-161 |
| AI never authoritative | No foreign key from any drawing, value or BOQ row to `design_generations` or AI_CONCEPT files; illustrative reference ids only on design requests; DB CHECK on file purpose for drawing files | [PD] PD-05 |
| DEMO pricing never issued in production | Issue refuses a DEMO card when the environment is production | [SOURCE] N-05 |
| Access | Project membership on every project route (404 outside); professionals only through an ACTIVE engagement in the right category; staff routes need roles and MFA | [SOURCE] SEC 4.2; 3.4 pattern |
| Evidence integrity | Every file carries sha256; signed sheets and certificates are files; acceptance stores the content hash accepted | [SOURCE] DATA:431 |
| Audit | Every transition, value entry, BOQ change, sign-off, void, credential check, issue, acceptance, download | [SOURCE] SEC:219 |
| Events carry ids only | | [SOURCE] EVT |
| PDF templates escape user text | | [SOURCE] SEC:137, IC:184 |

---

## R. Decisions register

All of BP-01 to BP-20 are decided (section 0.1). One question stays open:

| ID | Question | Blocks |
|---|---|---|
| BP-07A | What is the canonical construction execution order and the dependencies across the 16 stages and their per-floor repeats (basement, ground, upper floors), so that authoritative dates can be calculated from a start date? | Authoritative schedule dates, decide-by dates, the monthly cash-flow figure, the stage-order fix. Nothing else |

Carried, not for 3.5: CQ-02 quote-holder review (3.6), D3-19 pricing lines not yet chosen, D3-08 and D3-09 options and OTP at CHOSEN, OQ-046 sign-off turnaround, POQ-023 who produces structural calculations, F-03 outside professionals' own access, AQ-15 image provider, AQ-18 issue without views (no AI view is ever required), D-05 contractor class, OQ-027 household permissions.

---

## S. Implementation order

Section 0.5.

---

## T. Launch and production blockers

Section 0.6.

---

## U. Verdict

Every business decision needed to build 3.5 is taken (section 0.1). The only unresolved item, BP-07A (canonical build order and dependencies), blocks authoritative date calculation and nothing else; the slice builds and issues Build Plans with durations and explicit dependencies and calculates no dates until it is answered. Production launch still needs the content items in 0.6 (rate card values, an appointed checker, legal confirmation of the statement, an available engineer, fonts, client confirmation of English).

No code changed in this readiness pass.

SLICE 3.5 READINESS = READY WITH DECISIONS

The one decision still needed: BP-07A, the canonical construction execution order and dependencies, before any authoritative schedule date is calculated.
