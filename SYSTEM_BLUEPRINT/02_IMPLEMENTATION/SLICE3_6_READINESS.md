# Plan2Build: Slice 3.6 readiness (accepted Build Plan to contractor selection)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/SLICE3_6_READINESS.md` |
| Version | 1.1 (2026-10-06) |
| Status | Implemented 2026-10-06: see `SLICE3_6_IMPLEMENTATION_REPORT.md`. **APPROVED FOR IMPLEMENTATION** (Chirag, 2026-10-06). QD-01 to QD-26 decided (section 0); QD-02 is a new product decision that extends the substantial-work triggers. Where sections A to AB differ from section 0, section 0 governs. Version 1.0 was readiness only. Slice 3.5 is CLOSED (implementation COMPLETE, production readiness NOT YET READY) and is not reopened here |
| Scope | Accepted Build Plan → RFQ → contractor invitation → contractor quote → quote review → structured comparison → homeowner selection → the existing engagement (3.4) |
| Baseline | PD-01 to PD-27 (IHB 32.6); IHB 34 (canonical flow, PD-26); PRODUCT_FLOW_RECONCILIATION v2.0 (PFR); Slice 3.2 D-01 to D-11; Slice 3.3 L-01 to L-08 and O-01 to O-10; Slice 3.4 N-01 to N-12 (closed); Slice 3.5 BP-01 to BP-20 (closed; BP-07A deferred); ADR-023 |
| Sources read | IHB_FLOW 8.13 to 8.16, 9, 10, 13, 14, 19, 22, 24 to 26, 32, 33, 34; PROFESSIONALS_FLOW (PRO) 9.7, 11 to 18, 22, 43, 44; RECOMMENDATION_ENGINE (RE); DATA, API, STATE, DOMAIN, EVENT, SECURITY, INTEGRATION, AI, SYSTEM, TESTING architecture; ADR-006, 008, 009, 011, 012, 018, 019, 020, 023; ARCHITECTURE_BASELINE (BASE); IMPLEMENTATION_CONTRACT (IC); FOUNDATION_PLAN (FP); SLICE3_READINESS (S3R); SLICE3_3 (S33), SLICE3_4 (S34), SLICE3_5 (S35) readiness and SLICE3_5_IMPLEMENTATION_REPORT (S35IR); every document in `SOURCE_OF_TRUTH` read as text: MVP Build Plan (MVP), Client Product and Implementation Blueprint (CPB), Technology Product Blueprint (TPB), Strategy and POC (STR), Specification Schema (SCH), POC budget plans (POCB, PLAN), budget plans of 19 Sep (BUD), Transactional Verification Blueprints (TVB, FTB), site copy (WEB), meeting notes of 1 Oct (GEM); `PLAN2BUILD_USER_FLOWS.html` (FLOWS, 2 Oct), Client Review Changes (CRC, 3 Oct), Client Questions Round 2 (CQ2, 3 Oct, answers blank); the code as built through Slice 3.5 |
| Markers | **[SOURCE]** a source or approved architecture settles it. **[PD]** Chirag's decision (QD-01 to QD-26 decided 2026-10-06). **[PD NEW]** a new product decision that extends an earlier closed decision without changing it (QD-02). **[REC]** Sakha's recommendation, not approved. **[OPEN]** undecided. **[SUPERSEDED]** an older design overridden |

Citation forms: `IHB:4306` is IHB_FLOW.md line 4306; `PRO:4240`, `RE:168`, `DATA:197`, `API:178`, `STATE:273`, `DOM:155`, `EVENT:158`, `SEC:121`, `AI:101`, `PFR:288`, `S34:31`, `S35:42` likewise. Original documents are cited by section (`MVP P4`, `CPB §11`) or by line of their text extraction (`MVP:170`). MVP states that it supersedes "the earlier MVP functional specification"; TVB, FTB and BUD describe the older marketplace model and are cited only where nothing newer speaks. PD decisions outrank every source; the N-, BP- and L- decisions outrank the architecture documents.

### Decision IDs

Questions in this document are **QD-01** onward; contradictions are **RC-01** onward (both prefixes unused elsewhere). Existing IDs are kept where a question already exists (CQ-02, CQ-07, CQ-09, CQ-13, CQ-17, CQ-23, D-05, F-03, F-10, POQ-008, POQ-011, POQ-012, POQ-013, POQ-015, POQ-016, D3-19, D3-20, O-04, O-10). Hardening gaps found in passing are **H-02** onward (H-01 is the 3.5 engineer notification).

### Governing chain

ACCEPTED Build Plan version (3.5) → RFQ with a frozen copy of that version's contractor manifest → invitations to eligible contractors → each contractor's immutable quote versions → Plan2Build review (adjustments, clarifications) → a published, frozen comparison version → the homeowner's selection, confirmed with a one-time code → the single engagement of 3.4 for the CONTRACTOR category. Plan2Build never becomes the contractor, never receives construction money, never guarantees a price. [PD] PD-01, PD-04, PD-13, PD-15, PD-17, PD-19, BP-05, BP-08, N-02; [SOURCE] CD-01, CD-09, IHB:1394

---

## 0. Final decisions (Chirag, 2026-10-06)

Slice 3.6 readiness is APPROVED FOR IMPLEMENTATION with these decisions. Each replaces the recommendation or open point it answers; sections A to AB below are updated to match.

### 0.1 Decision table QD-01 to QD-26

| ID | Decision | Marker |
|---|---|---|
| QD-01 | Option A. A separate RFQ invitation record. An invitation means "this contractor is being asked to quote"; accepting it means "I agree to prepare and submit a quote". Accepting an invitation creates no 3.4 engagement and reuses no connection. The 3.4 engagement stays the professional relationship record; the homeowner's selection creates or reuses the engagement through the engagements module. No second professional lifecycle. Resolves RC-01 | [PD] |
| QD-02 | Option B, recorded as a **new product decision**. An engagement created by an RFQ selection counts as substantial Plan2Build work for refunds: usage kind `RFQ_SELECTION`. N-12 is not reinterpreted: connection acceptance stays its trigger, and RFQ_SELECTION is an additional, explicitly approved trigger. Not substantial work: invitation acceptance, RFQ creation, quote submission, quote review, comparison publication, Build Plan issue. Before an RFQ selection, refunds follow the existing rules; after it, the package has entered substantial work. Written through the billing interface (`rfq` never imports billing internals); the usage kind is part of billing's versioned vocabulary | [PD NEW] |
| QD-03 | The owner requests contractor quotes and nominates contractors from the listed directory. Operations may introduce an additional contractor by hand with a written reason. Operations prepare and issue the RFQ | [PD] |
| QD-04 | At most 3 recipients per RFQ: a configuration value, initialised to 3 for the POC; never a literal in business logic | [PD] |
| QD-05 | Invitation response window 48 hours (configuration). Quote deadline set by operations per RFQ; no universal default. Late submissions refused; operations may extend the deadline with a reason; the extension is audited and every affected recipient receives the same notice. Decline reasons: the N-06 set (unavailable or capacity, outside service area, scope mismatch, schedule mismatch, compliance or verification issue, already engaged, other with an explanation). No countdown UI | [PD] |
| QD-06 | The contractor supplies `valid_from` and `valid_to`; `valid_to` after `valid_from`. Expired quotes cannot be selected. After expiry, a validity renewal may be submitted only with unchanged commercial content; the renewal is an explicit version (kind RENEWAL) and cannot change prices, lines, exclusions or terms | [PD] |
| QD-07 | Option A. Before publication the homeowner sees status only, never raw prices. After a comparison is published the homeowner sees quoted prices in it. Contractor internal costs, margins and rates stay private (RC-06) | [PD] |
| QD-08 | No. Contractors never see Plan2Build's adjustments; questions go through structured clarifications | [PD] |
| QD-09 | Invitation SENT: the connection-style brief (category, locality, basic project facts), the deadline, the existence of an accepted Build Plan; no name, phone, email, address, pin, drawings or private documents. Invitation ACCEPTED: the frozen pack (drawings, specifications, BOQ quantities, scope, schedule durations and dependencies, quote format) and shared clarifications. Before selection the homeowner's identity and contact stay hidden; communication goes through Plan2Build; site visits are arranged offline by operations; no direct-contact feature. After selection the 3.4 engagement sharing rules apply | [PD] |
| QD-10 | Option A for 3.6: no recommendation output (no "best fit", "lowest", score, rank, algorithmic winner or label). This **defers** the source and client requirement for a recommendation engine (CD-18, CD-28, RE §6) to a future slice; those requirements are kept, not deleted or rewritten | [PD] deferred decision, future slice |
| QD-11 | A neutral order fixed per comparison version from a stored deterministic seed; never dependent on price, contractor identity, commercial importance, internal preference or sponsorship. No rank numbers, no "lowest", "best" or "recommended" | [PD] |
| QD-12 | Selection requires: owner permission, the current published comparison, an explicit quote version, a still-valid quote, a still-LISTED contractor, an ACTIVE package, a one-time code, the ACTIVE versioned selection statement. Immutable within the RFQ. No second contractor confirmation (the contractor already submitted the quote). At selection: the engagement is ACTIVE immediately (an existing ACTIVE engagement with that contractor is reused, otherwise one is created with origin RFQ_SELECTION); losing quotes NOT_SELECTED; remaining invitations closed; pending CONTRACTOR connections withdrawn as N-02; the RFQ CLOSED and the comparison DECIDED. No construction contract value recorded. The statement says Plan2Build is not the contractor, is not a party to the construction contract, receives no construction money and does not guarantee the quoted price; wording IMPLEMENTED / PENDING FINAL CLIENT + LEGAL CONFIRMATION | [PD] |
| QD-13 | With an ACTIVE CONTRACTOR engagement, only that contractor may be invited; no competitors; an OUTSIDE contractor through operations capture; competition resumes only after the engagement ends. N-02 not weakened | [PD] |
| QD-14 | Package REFUNDED or CANCELLED during an open RFQ: the RFQ is CANCELLED with PACKAGE_ENDED; outstanding invitations withdrawn; no new contractor actions; submitted quotes and published comparisons stay as read-only history; no selection; no usage record unless a separate approved trigger applies. After reactivation, a new RFQ; old quotes are history and are not carried over. No pause and resume | [PD] |
| QD-15 | A newer Build Plan version accepted during an open RFQ: the RFQ is CANCELLED with BASELINE_SUPERSEDED; open invitations withdrawn; quotes and published comparisons kept as history; operations create a new RFQ on the new version when they proceed. The old baseline is never mutated; a CLOSED RFQ is never rewritten | [PD] |
| QD-16 | No RFQ pack amendments and no pack versions. A material scope change is a new Build Plan version, its acceptance, then a new RFQ. Informational points that do not alter scope go through clarifications, shared when operations decide they affect everyone | [PD] |
| QD-17 | No direct homeowner and contractor chat. Contractors ask operations; operations answer and may share the answer with all active invitees without the asker's identity. Clarifications are structured records; they never change the RFQ; a price or scope change needs a new quote version or a new Build Plan and RFQ | [PD] |
| QD-18 | Each RFQ quantity line: unit rate or explicit exclusion with a reason; amount calculated by the server. Also: alternate specification text, additional items (outside the comparable total), GST inclusive or exclusive choice and note, total duration, optional stage durations, payment terms, warranty and materials responsibility as free text, assumptions and exclusions, attachments. No structured payment milestones, percentages or amounts | [PD] |
| QD-19 | A contractor may withdraw a submitted quote until selection, with a reason; audited; earlier versions immutable; may submit again before the deadline under the normal rules | [PD] |
| QD-20 | Losing contractors receive a not-selected notice that discloses no winner, price, ranking, homeowner reasoning or other contractor's information | [PD] |
| QD-21 | No enlistment class, no placeholder. LISTED in the CONTRACTOR category (which carries the 3.2 verification) and service-area coverage are enough | [PD] |
| QD-22 | The homeowner's OUTSIDE contractor may take part without an account; operations capture its quote in the standard structure. Capture never makes it a platform professional. Kept distinct from the listed invitation flow | [PD] |
| QD-23 | A deterministic fpdf2 comparison PDF at publication (ADR-023), for the homeowner, household and operations; no public share link; comparison version, content hash and PDF object reference persisted; a published comparison is never re-rendered | [PD] |
| QD-24 | No numeric minimum: one or more REVIEWED quote versions may be published; zero cannot. The comparison shows how many invitations were sent and how many quotes were received | [PD] |
| QD-25 | The 3.4 quote-holder capability stays intake only; no review or normalisation of homeowner-held quotes in 3.6; the two capabilities stay separate | [PD] |
| QD-26 | Contractor RFQs only. Architect, structural engineer, site or civil engineer, MEP, interior designer and specialist RFQs are a later decision and slice | [PD] |

### 0.2 Implementation-safety decisions

| Point | Decision | Marker |
|---|---|---|
| H-03 | Resolved before implementation: ADR-024 records `engagements` as the module that replaces `leads` in the ADR-008 list (the count stays 24), owning service needs, connections, engagements and quote-holder intake, plus the RFQ selection entry point added by 3.6 | [PD] |
| Billing | Billing supports the explicit `RFQ_SELECTION` usage kind; `rfq` calls the billing interface only; import-linter contracts kept | [PD NEW] QD-02 |
| Closed 3.4 decisions | Not changed silently. Extensions are recorded where they apply: QD-02 (an added substantial-work trigger), QD-01 and QD-12 (an engagement may start from an RFQ selection, origin RFQ_SELECTION) | [PD] |
| H-01, H-02 | Production hardening, outside the core 3.6 scope unless a dependency appears | [PD] |
| BP-07A | Still deferred: no calendar dates, decide-by dates or cash-flow dates | [PD] |

### 0.3 Implementation order (adjusted)

Documentation and ADR reconciliation; vocabulary and configuration; `rfq` module, interfaces and import-linter contracts; billing support for RFQ_SELECTION; engagement integration; migration; RFQ lifecycle; invitations; contractor pack; quote drafts, submission and versions; clarifications; review and adjustments; comparison; fpdf2 comparison document; selection with code and statement; engagement creation or reuse; package and baseline handlers; notifications; minimal functional UI; full tests; browser tests on the production build; migration checks; final documentation and report. [PD]

---

## A. Current implementation inventory

### A.1 What exists and what 3.6 uses

| Area | As built | Use in 3.6 |
|---|---|---|
| Accepted Build Plan | `build_plans.accepted_version_id`; `lifecycle.accepted_version(project_id)`; at most one ACCEPTED version (`uq_build_plan_versions_one_accepted`); a later acceptance moves the earlier one to SUPERSEDED; `buildplan.accepted` is published and has no subscriber | The RFQ baseline (BP-05, BP-08). 3.6 subscribes to `buildplan.accepted` (section E.4) |
| Contractor manifest | `buildplan/views.manifest(view)` behind `GET /ops/projects/{id}/build-plan/rfq-manifest` (OPS or ADMIN, MFA; 409 `NO_ACCEPTED_VERSION`); `RfqManifestOut` with `extra="forbid"`; content: version id, number, content hash, accepted time, project code, drawings with sha256 and set hash, specification values (code, item, criteria, applicability, value, not-applicable reason), quantities (line, item code, description, unit, quantity, stage, floor, spec line codes, assumptions), schedule durations and predecessors, `dates_status = NOT_CALCULATED_BP07A_DEFERRED`, scope lists, `quote_format` version 1; excluded: rate, amount, rate card, BOQ and stage totals, basis notes, sign-offs. A test asserts no rate key or value | The RFQ pack (section E). Not exported in `buildplan/interface.py`; 3.6 needs an interface function |
| Engagements (3.4) | `project_service_needs`; `connections` (SENT, ACCEPTED, DECLINED, EXPIRED, WITHDRAWN; at most 3 SENT per project and category; one SENT per professional); `project_engagements` (party LISTED or OUTSIDE; ACTIVE or ENDED; one ACTIVE per project and category; CHECK: LISTED needs `profile_id` and `connection_id`); `engagement_documents`; `engagement_events`; accept writes `package_service_usage` CONNECTION_ACCEPTED (N-12) | Selection creates or reuses the engagement (section N). No interface function returns the ACTIVE engagement of a (project, category); 3.6 needs one. The LISTED CHECK needs a change for an engagement that starts from a selection |
| Quote-holder review (3.4) | `quote_review_requests`: intake only, state SUBMITTED, 1 to 5 family-owned QUOTE_DOCUMENT files; operations email; staff download; no review output | Kept distinct (section O) |
| Billing | `package_active`, `package_state`, `record_service_usage` in `billing/interface.py`; entitlement ACTIVE, CANCELLED, REFUNDED; `billing.package_changed`; refunds decided by OPS or ADMIN, never automatic; the only usage kind written is CONNECTION_ACCEPTED; billing may not import engagements or buildplan | Package gating (section P); no new usage kind without a decision (QD-02) |
| Professionals | `professional_categories.listing_state` (DRAFT, PENDING_REVIEW, CHANGES_REQUESTED, LISTED, REJECTED, SUSPENDED) plus `hidden`; one base point and radius per profile; `connection_candidate(profile, category, point)` returns listed, hidden, covers; no enlistment class (D-05 OPEN); "contractor" is the category code CONTRACTOR | Invitation eligibility (section F) |
| Documents | `file_objects` purposes REQUIREMENT_UPLOAD, AI_CONCEPT, VERIFICATION_EVIDENCE, PORTFOLIO, INVOICE, QUOTE_DOCUMENT, DRAWING, BUILD_PLAN_EVIDENCE, BUILD_PLAN_DOCUMENT; scanning pipeline (type check, ClamAV, quarantine); `_logged_link` writes `document_access_log`; staff uploads through the API raw-body route (the admin host is not a storage CORS origin); contractors can read Build Plan drawings only as the drawing provider or an engaged structural engineer | New purposes and a contractor read rule for the RFQ's drawings (section Q) |
| Notifications | Outbox event → `notifications:send_notification` job → plain-text template `{kind}.en.txt`; ops kinds to `P2B_OPS_NOTIFICATION_EMAIL`; family and professional kinds to the account's primary email through the owning module's notice function; 15 templates; wording of all is draft | Same pattern (section R) |
| One-time codes | `identity/confirmations.py`: purposes LOGIN, ACCEPT_BUILD_PLAN, SIGN_STRUCTURAL; a code binds (user, purpose, subject); one code serves one action through a unique `challenge_id` | A new purpose for selection (section M) |
| Versioned statements | `signoff_statements`, `acceptance_statements`: versioned text, one ACTIVE, ADMIN drafts and activates, templates validated against allowed placeholders | Same shape for the selection statement (section M) |
| Audit | `audit.record(action="{entity}.{state}")` in the caller's transaction | Every transition (section S) |
| Vocabulary | `ProjectStatus` declares SOURCING and CONTRACTED; no code sets them (N-03) | 3.6 never sets them |
| Import linter | Four contracts (core, integrations, billing isolation, interface-only independence) | A new module joins all four |
| Web | Homeowner: services (needs, connections, engagements, quote review), Build Plan. Professional: connections, Build Plan sign-off. Ops: project engagements, Build Plan, a raw JSON manifest button | No RFQ, quote, comparison or selection screen exists |

Nothing named rfq, quote version, comparison, selection, bid, tender or award exists in code, tables, routes, events or templates. `billing/orders.Quote` is the package price, unrelated.

### A.2 Gaps found in passing (not 3.6 scope, not fixed here)

| ID | Gap | Where | Placement |
|---|---|---|---|
| H-02 | A HOUSEHOLD member sees the quote-holder review request but not its files: the view resolves files through the owner's personal files | `engagements/views.py` (quote review files) | Hardening with H-01, before production; 3.4 stays closed |
| H-03 | The `engagements` module is not in ADR-008's module list, DOMAIN or the architecture baseline; IC §4 requires an ADR for a new module | ADR-008:15, IC §4 | **Resolved by ADR-024** (section 0.2) before implementation. 3.6 uses the listed module name `rfq` (DOM:155) |

---

## B. Source reconciliation

### B.1 Precedence used

PD decisions (IHB 32.6) → Chirag's slice decisions (L-, O-, N-, BP-, D-) → IHB 34 → PFR v2.0 → client decisions CD-01 to CD-24 (CD-25 to CD-28 are proposed answers until reviewed, IHB:4117) → architecture documents → original sources (MVP and later) → TVB, FTB, BUD (older marketplace). [SOURCE] IHB:4290, IHB:4116, IHB:4117

### B.2 Contradictions (none silently resolved)

| ID | Contradiction | Governs now | Consequence for 3.6 |
|---|---|---|---|
| RC-01 | **One ACTIVE engagement per category versus several competing quotes.** N-02 allows one ACTIVE engagement per category, and accepting one connection withdraws the others (S34 0.1). The sources send one standard scope "to several contractors" (MVP P4, CPB §4.4) and select after comparison (IHB 34 rows 11, 13). S34:156 says the RFQ is "sent to engaged professionals", which with N-02 means one contractor | N-02 (built, closed) with [PD] QD-01 | A separate invitation record; the engagement is created or reused at selection (resolved) |
| RC-02 | **Pre-acceptance privacy (N-08) versus the RFQ pack.** N-08: before acceptance no documents, exact address or pin. The pack carries drawings | N-08 for connections; [PD] QD-09 for invitations | Brief at SENT; pack after the invitation is accepted; identity and contact only after selection |
| RC-03 | **Substantial work.** S33 E [REC] listed "first RFQ issued, first comparison delivered"; S34 E.2 wrote it on connection SENT; S34 N recommended "delivered services such as a comparison". N-12 decided: a professional accepting a connection; BP-09 confirmed it unchanged | N-12, extended by [PD NEW] QD-02 | N-12 unchanged; RFQ_SELECTION is an added trigger; no other 3.6 action writes usage |
| RC-04 | **Quote-holder review placement.** PFR G:286 put it in 3.4; S3R D3-03 deferred it; S34 0 built intake only; S35 M.4 placed the review in 3.6 "using the same normalisation model"; CQ-02 (terms) is "Not yet asked" | S34 0 (intake only) and [PD] QD-25 | Not built in 3.6 (section O) |
| RC-05 | **F-10 register not updated.** PFR:189 and F-10 still read open; BP-08 answered them for contractors only | BP-08 | 3.6 covers CONTRACTOR RFQs only ([PD] QD-26). Other categories' RFQ scope (PFR F-10 recommendation: the requirement brief) is a later decision and slice |
| RC-06 | **"Contractor prices: never shown to the homeowner"** (S35 H:454, citing MVP:201) versus a homeowner comparison of quotes. MVP:200 reads "The contractor sees cost booked against revenue by stage; the homeowner never does"; MVP:170 reads "Contractor input costs, margins and internal rates are never visible to a homeowner" | The MVP text. S35 H paraphrased it wrongly | Quoted prices are shown to the homeowner; contractor input costs, margins and internal rates are never collected or shown. S35 is closed and not edited; this row records the correction |
| RC-07 | **Price ranking.** IC §23.9 forbids "price-ranked or price-sorted listings"; IC §18.3 "no price ranking"; MVP §9 forbids "any 'lowest quote wins' mechanic"; PFR D:143 says only "never hidden price ranking" | IC and MVP (stricter); [PD] QD-11 | No price sort, no rank, no "lowest" label in the comparison |
| RC-08 | **Engine recommendation at comparison.** CD-18 (client decision): the comparison "comes with a recommendation from an engine"; CD-28 (proposed answer) and RE §6 name one "Best fit" quote by TOPSIS; PFR G:288 lists "recommendation" in 3.6. Chirag's 3.6 instruction: no algorithmic "best contractor" scoring, no automatic winner unless a source explicitly requires it | [PD] QD-10: no recommendation in 3.6; the CD-18, CD-28 and RE §6 requirement is deferred to a future slice, not deleted | A neutral comparison without a recommendation |
| RC-09 | **Architecture RFQ design built on superseded concepts.** API §10, STATE §10, EVENT 4.5, DATA 4.9 and DOM 3.10 assume: leads (superseded by connections, DATA:181); project SOURCING and CONTRACTED (N-03); Club membership (PD-18); "409 unless a Build Plan version is ISSUED" (API:164; the baseline is ACCEPTED, BP-05, S35 M.3); a recommendation APPROVED before finalise (API:175); `contract_value`, start and end dates at selection (API:178); one `contract_values` row per project (DATA:224); invitation source LEAD | PD-17, PD-18, N-03, BP-05, BP-08, S34 I:240 | Those parts are [SUPERSEDED]. Kept from the architecture: immutable quote versions, lines priced or excluded, staff capture, adjustments never shown to contractors, frozen comparison versions, one selection per RFQ, contractor isolation tests |
| RC-10 | **Contract value at selection.** API:178 and DATA:201 record contract value and dates with the selection; CQ-13 (contract value visible to the contractor) is open; the final commercial agreement is between homeowner and contractor (CPB §4.5, FLOWS step 16) | [PD] QD-12 | 3.6 records no contract value. The construction slice records it (CQ-13) |
| RC-11 | **Payment terms and milestones in a quote.** TVB §9.2 and FLOWS B6 ask for payment terms and a payment schedule; RE §6 scores "payment schedule fit"; IC §6.8 "No column ever holds a payment amount between homeowner and professional (CD-09)"; BP-10 "No construction payment-percentage schedule" | CD-09, IC §6.8, BP-10; [PD] QD-18 | Payment terms are the contractor's free text only; no structured milestone amounts or percentages |
| RC-12 | **Quote dates.** CD-17: every quote has a start and end validity date. CQ-09 (who sets them, what happens on expiry) is "Not yet asked" | CD-17; [PD] QD-06 | Contractor sets both dates; expired quotes cannot be selected; renewal only with unchanged content |
| RC-13 | **Deadlines and reminders.** PRO:1432 (D2) forbids a countdown; PNOT-14: "No deadline reminder in any source"; N-07: "no repeated re-notification"; EVENT:151 adds a reminder "at half the window"; CD-26 windows (48 hours, 10 days) are proposals (S34:12) | [PD] QD-05 | 48-hour response window (configuration); deadline per RFQ; no countdown, no reminder emails |
| RC-14 | **Clarification timing.** PRO:1254 places D2 clarifications after submission; PRO 44.2 and 44.3 place "review the brief and clarify" before quoting | Neither | Both allowed: a contractor may ask about the pack before or after submitting (section J) |
| RC-15 | **Number of contractors.** FLOWS step 8: "compares up to three"; CD-26: at most three, "configuration, not fixed rules"; PRO:972: "A maximum is not stated for the RFQ itself"; STR Gate 2: 15 hand-picked contractors (a pilot supply figure, not per house); MVP §11 and CPB §22: "three real quotes" (definition of done) | [PD] QD-04 | Configuration, initialised to 3 |
| RC-16 | **Quoting without the package.** CD-26 and PRO 44.7 step 8: without the package the contractor quotes on a standard template | PD-08, PD-19 (RFQ is package-gated) | [SUPERSEDED]; not built |
| RC-17 | **Champions Club membership in eligibility.** RE:63, RE config `club_member`, AI:130, STATE:234 | PD-18: read as LISTED for the category | Eligibility uses `listing_state = LISTED` (section F) |
| RC-18 | **Who creates the RFQ.** TVB §9.1: the homeowner creates it; IHB:1307: "The IHB does not fill the RFQ; Plan2Build issues it"; AMB-031 suggested reading: Plan2Build creates and issues, the homeowner invites | IHB:1307, PD-17, [PD] QD-03 | The owner requests and nominates; operations may introduce with a reason; operations prepare and issue |
| RC-19 | **Selection confirmation.** API:178 and SEC:62 design a one-time code with purpose SELECTION; no source (IHB, PRO) specifies a code for award | [PD] QD-12 | One-time code of purpose SELECT_QUOTE |
| RC-20 | **Event names.** DOM:161 `rfq.quote_submitted`; API:170 and EVENT:152 `rfq.quote_version_created` for the same moment | Neither | [REC] `rfq.quote_submitted` (one name; matches the state) |
| RC-21 | **Lines not yet chosen (D3-19).** S3R recommended pricing against the issued brand-neutral criteria; later choices within the criteria cost nothing extra, outside them a variation | [PD] QD-18 (lines priced against the manifest) | Contractors price against the issued criteria and values; choices and variations stay in later slices |
| RC-22 | **Timeline in the RFQ.** BR-080 puts a timeline in the pack; BP-07A defers dates; the manifest carries durations and `NOT_CALCULATED_BP07A_DEFERRED` | BP-07A | The contractor states its own durations; no calendar date is computed (section H) |
| RC-23 | **Who sees normalisation adjustments.** DATA:199 "never shown to contractors"; PRO:1639 marks the contractor seeing adjustments on its own quote as AMBIGUOUS | DATA:199; [PD] QD-08 | Contractors never see adjustments, including on their own quote |
| RC-24 | **Commission from contractors.** BUD and TVB allow commission, subscription and lead fees; WEB: "Listing is free for the contractors we invite"; PRO:4288 "Nothing in this flow charges the contractor"; POQ-028 open | PD-01, PD-08 and the money boundary | Nothing in 3.6 charges a contractor or records a fee |
| RC-25 | **One contractor per house.** PRO:1684 (D2) derives one contractor per house; PD-17 and IHB 34 rows 9 and 13 allow per-category selection | PD-17 | 3.6 runs per category; only CONTRACTOR in this slice |

---

## C. Product model

| Rule | Marker |
|---|---|
| Plan2Build is a coordination layer. It never becomes the contractor, architect or engineer, never receives construction money, never guarantees a quoted price and is never a party to the construction contract | [PD] PD-01; [SOURCE] CD-01, CPB §4.5, FLOWS step 16, IHB:1396 |
| Every service is optional and per category. A homeowner may use a Plan2Build contractor, an outside contractor, or neither through Plan2Build. 3.6 never makes an RFQ or a Plan2Build contractor mandatory | [PD] PD-17, PD-20 |
| Discovery (directory, profiles) stays free. The RFQ, quote collection and coordination, structured comparison and review are package services | [PD] PD-08, PD-19 |
| Three prices never merge: Plan2Build's indicative estimate and Build Plan BOQ (internal costing), the contractor's quote, and any later commercial agreement between homeowner and contractor (outside the platform; recorded later as a contract value, CQ-13) | [PD] PD-04; [REC] for the third |
| The RFQ is built only from authoritative information: the ACCEPTED Build Plan version's contractor manifest. Never AI history, design references, drafts or DEMO pricing | [PD] PD-05, PD-15, BP-08; [SOURCE] S35 M.2 |
| The comparison is a specification audit, not a price grid: quotes as submitted, the adjustment list first, the normalised total; never a price ranking, never a "lowest" headline, never paid or sponsored order | [SOURCE] MVP P4, CPB §11, BR-083, BR-084, BR-087, BR-149; [PD] PD-08 |
| The homeowner chooses. Selection means "this contractor is engaged for this category through Plan2Build", nothing more | [SOURCE] CD-18, FLOWS step 15; [PD] PD-17 |
| 3.6 covers the CONTRACTOR category only. Architect, engineer, MEP, interior and specialist RFQs are a later slice | [PD] BP-08, QD-26 |
| No recommendation engine output in 3.6; the requirement is deferred to a future slice, not removed | [PD] QD-10 (RC-08) |

---

## D. RFQ model

| Question | Answer | Marker |
|---|---|---|
| Who starts it | The project OWNER requests contractor quotes for the CONTRACTOR category from the dashboard. Operations may also start one at the owner's direction (recorded) | [PD] QD-03; [SOURCE] IHB:1307, AMB-031 |
| Who prepares and issues it | Operations (OPS or ADMIN, MFA). They confirm the recipients, set the quote deadline and issue. The pack is never typed by hand: it is a frozen copy of the manifest | [SOURCE] IHB:1305, IHB:1307, CPB §4.4; [REC] |
| Package | `package_active(project)` for request, recipient changes, issue, invitations, staff capture, review actions, publishing and selection. Reading and withdrawal are never gated | [PD] PD-19, BP-09 pattern |
| Build Plan state | The project has an ACCEPTED Build Plan version. The RFQ names that version; DRAFT, IN_REVIEW, ISSUED, CHANGES_REQUESTED, SUPERSEDED or WITHDRAWN versions are refused | [PD] BP-05, BP-08 |
| Service category | CONTRACTOR only in 3.6. The project's need for CONTRACTOR must not be NOT_NEEDED (as for connections) | [PD] BP-08; [REC] |
| Per category | Yes. At most one open RFQ (DRAFT or ISSUED) per project and category | [REC] |
| Recipients | Several contractors per RFQ, each an invitation. Sources of recipients: nominated by the owner from the free directory; introduced by operations by hand with a written reason; the contractor already engaged for the category (section N.3) | [SOURCE] CD-26, IHB:4352 (introductions), CD-07; [PD] QD-03 |
| Maximum recipients | A configuration value initialised to 3 for the POC (sources: CD-26, FLOWS step 8, N-05 for connections) | [PD] QD-04 |
| Response window | An invitation not answered within 48 hours (configuration, a setting separate from connections) EXPIRES | [PD] QD-05 |
| Quote deadline | Set by operations per RFQ at issue (`quotes_due_at`); no universal default. After it, new submissions are refused (a validity renewal, QD-06, is the only exception); operations may extend it with a reason (audited; every affected recipient gets the same notice) | [PD] QD-05; [SOURCE] TVB §20 "do not mark quote as zero" |
| Expiry of the RFQ | No automatic RFQ expiry. After the deadline the RFQ waits for review, comparison and selection, or cancellation | [REC] |
| Withdrawal (cancellation) | The owner, before a selection, with a reason code; operations with a reason; the system on package end (QD-14) or baseline superseded (QD-15). CANCELLED is terminal; quotes and comparisons stay readable as history | [REC]; [SOURCE] STATE:257 (CANCELLED by operations with reason) |
| Reopening | No reopening. A cancelled or closed RFQ stays as history; a new RFQ is created (operations may copy the recipient list) | [REC] |
| Amendment and versioning | The pack is immutable for the life of the RFQ. Clarifications that do not change scope are shared answers (section J). A scope change is a new Build Plan version, its acceptance, and a new RFQ; there are no RFQ pack versions in 3.6 | [PD] QD-16; [SUPERSEDED] `rfq.pack_version_changed` (EVENT:150) for 3.6 |
| Adding recipients after issue | Allowed until the quote deadline, within the maximum; each passes eligibility | [REC] |
| Audit events | `rfq.draft`, `rfq.issued`, `rfq.deadline_extended`, `rfq.closed`, `rfq.cancelled`; `invitation.{state}`; `quote_version.{state}`; `quote_review.{state}`; `clarification.{state}`; `comparison.{state}`; `selection.confirmed`. Each in the same transaction as the change, with actor, role and reason | [SOURCE] API:29, STATE:16; [REC] names |

---

## E. RFQ baseline

### E.1 What 3.6 consumes

| Item | From the ACCEPTED version (manifest) | Marker |
|---|---|---|
| Identity | Build Plan version id, number, content hash, accepted time | [SOURCE] S35 M.1, S35IR G |
| Drawing set | Approved set hash; each drawing's file id, class, floor, title, sheet, sha256 | [SOURCE] S35IR G; CD-20, CD-25 (the architect's pack is part of the RFQ) |
| Specification values | Code, item, criteria, applicability, issued value, not-applicable reason; brand-neutral | [PD] PD-14 |
| BOQ | Line, item code, description, unit, quantity, stage, floor, spec line codes, assumptions; no rate, amount, rate card or total | [PD] BP-08 |
| Scope | Inclusions, exclusions, assumptions | [SOURCE] S35 M.1 |
| Schedule | Durations and explicitly entered predecessors; `dates_status` NOT_CALCULATED_BP07A_DEFERRED | [PD] BP-07, BP-07A |
| Project and location | Project code, locality, plot facts from the connection brief (`projects` facts). Never the owner's name, contact, plot pin or address before the stage QD-09 allows | [REC]; [PD] N-08 by analogy |
| Quote format | `quote_format` version 1: one price per quantity line, explicit exclusion per line, the contractor's own schedule | [SOURCE] S35IR G; BR-081 |

### E.2 Freezing

The RFQ stores the manifest JSON at issue with its sha256 and the Build Plan version id (FK). Contractors and the comparison read the stored copy, never a live rebuild. The drawing files are immutable objects already (ADR-006). [REC]; [SOURCE] DATA:194 (pack version on the RFQ), S35 Q:657

### E.3 A later Build Plan version never changes an RFQ

The RFQ's version id, manifest copy and hash never change. A new ISSUED version does nothing to an RFQ. [PD] BP-05 (issued and accepted versions never mutate)

### E.4 When a new version is accepted while an RFQ is open

`buildplan.accepted` for a project with an open RFQ on the older version:

| Option | Effect |
|---|---|
| (a) [REC] | The system cancels the open RFQ with reason BASELINE_SUPERSEDED; open invitations are withdrawn; submitted quotes and comparisons stay readable; contractors and the owner are told; operations may create a new RFQ on the new version and copy the recipients |
| (b) | Flag only (EVENT:151 "quotes against the old version flagged"); the owner may still select a quote priced on the old scope |

[PD] QD-15: option (a). A CLOSED RFQ (selection made) is not touched: a later scope change is a construction variation (later slice). [SOURCE] S3R:81

### E.5 New RFQ after a material change

Yes: a material scope change goes through a new Build Plan version and acceptance, then a new RFQ. 3.6 has no in-place amendment (section D). [PD] QD-16; [SOURCE] S3R:116 (architect pack, BOQ re-measured, new RFQ pack)

---

## F. Contractor eligibility

| Check at invitation | Rule | Marker |
|---|---|---|
| Category and listing | `professional_categories` row for CONTRACTOR with `listing_state = LISTED` and not hidden | [PD] PD-18 (LISTED, not membership), D-01 to D-11 |
| Verification | LISTED already means the 3.2 listing review (identity, business, registration, portfolio, reference, site visit checks as configured) passed; no second verification | [SOURCE] 3.2 as built; [PD] PD-18 |
| Service area | The profile's radius covers the plot point (`connection_candidate(...).covers`); no location means refused | [PD] N-04 by analogy |
| Not self | The owner's own professional profile is refused | [SOURCE] 3.4 SELF |
| Suspended | A SUSPENDED or otherwise not-LISTED category is refused; leaving LISTED later withdraws the open invitation (section T.2) | [SOURCE] STATE:68; [PD] N-10 pattern |
| Enlistment class | Not required; no fake or placeholder class values (D-05 and CQ-07 stay open for the class itself) | [PD] QD-21 |
| Capacity and conflict of interest | Not checked: no capacity or conflict data exists (AI:134, DATA:302 are designs, not built) | [REC] later; POQ-053, POQ-054 open |
| Package | Active | [PD] PD-19 |
| Connection required first | No. An invitation is a separate request to quote; it neither needs nor creates a connection | [PD] QD-01 (RC-01) |
| Existing ACTIVE engagement in CONTRACTOR | While one exists, the RFQ may go only to the engaged party (LISTED: invited; OUTSIDE: staff capture). Inviting others is refused (`ENGAGED`) until the family ends the engagement, as 3.4 refuses new connections | [PD] QD-13; [PD] N-02 |
| Open connections | An open connection to the same contractor does not block an invitation. At selection, open CONTRACTOR connections are withdrawn (ANOTHER_ENGAGED) as on acceptance | [REC] |
| Outside (own) contractor | Not invited (no account; F-03 open). When engaged as OUTSIDE, operations capture its quote in the standard format on its behalf | [SOURCE] BR-082, PBR-036, CD-07; [PD] QD-22 (F-03 and CQ-23 stay open for platform access) |
| Duplicate | One invitation per (RFQ, profile) | [SOURCE] DATA:195 |

No second contractor lifecycle: the invitation and the quote are a sourcing record; the professional relationship is still only the 3.4 engagement. [PD] N-03, PD-17; [SOURCE] S34 0 "Connection and lead" ("a later operational representation of an opportunity ... no lead entity that duplicates a connection")

---

## G. Contractor visibility and privacy

### G.1 By stage

| Stage | Contractor sees | Marker |
|---|---|---|
| Invitation SENT | The connection-style brief (category, locality, plot size, built-up area, floors, basement, budget band, start window, services), the quote deadline, that a Build Plan exists. No name, contact, pin, address, drawings or documents | [PD] N-08 by analogy; [SOURCE] S34 E.2 |
| Invitation ACCEPTED (quoting) | The frozen pack: specification values, BOQ quantities, scope, schedule durations, drawings through logged 15-minute links, the quote format, the deadline, clarifications addressed to it and answers shared with all | [SOURCE] BR-080, IHB:1227; [REC] |
| Before selection, family identity | Owner's name and contact withheld; questions go through Plan2Build | [PD] QD-09; [SOURCE] IHB:4353 "clarifications go through Plan2Build" |
| Site visit | No system feature; on request, operations arrange it offline | [PD] QD-09 |
| After NOT_SELECTED, WITHDRAWN, DECLINED, EXPIRED, or RFQ CANCELLED | Its own invitation, its own quote versions and their outcome; drawing links stop | [REC] |
| After SELECTED | The 3.4 engagement view (N-08 after acceptance: name, phone, email, location, pin where appropriate, shared documents) plus the RFQ pack and its quote | [PD] N-08 |

### G.2 Never visible to a contractor

Plan2Build's rate card, rates, amounts, BOQ and stage totals, the Build Plan estimate and band; any other contractor's identity, quote, price, line, version count, status or attachment; the number of other invitations and quotes (PC-015 "number of competitors" is [SUPERSEDED] by D2 isolation); normalisation adjustments and reviewer notes (QD-08 for its own); the comparison and its order; the selection statement and the homeowner's reasons; private operational data (verification evidence, ops notes, refunds, package details beyond "package active"). [PD] BP-08; [SOURCE] BR-088, DATA:199, SEC:121, CPB §5 "What is not exposed", AI:155 to 158, RE:170

### G.3 Inference protections

| Channel | Protection | Marker |
|---|---|---|
| API | Contractor routes are keyed by its own invitation id and filter by `profile_id = current`; every other id returns 404; response models have no field for other quotes, rates or totals (`extra="forbid"`) | [SOURCE] SEC:121, SEC:131, SEC:139 |
| URLs and ids | UUIDv7 ids; no sequential numbers in contractor-visible data (no "quote 2 of 3") | [SOURCE] SEC:139; [REC] |
| Documents | Logged, 15-minute, single-object links; only the RFQ's frozen drawing ids; attachment links only for the contractor's own files | [SOURCE] ADR-006, ADR-011 |
| Metadata | Shared clarification answers carry no asker identity; deadline extensions are announced to all recipients with the same text | [REC] |
| Timing and errors | Submitting, withdrawing or revising never reveals whether others have; refusals use the contractor's own state only | [REC] |
| Frontend | The professional host has no comparison route; the comparison exists only on the homeowner and ops hosts | [SOURCE] SEC:121 |

---

## H. Quote model

### H.1 Fields

| Field | Rule | Marker |
|---|---|---|
| Lines | One per manifest quantity line: unit rate entered by the contractor, amount = rate × the RFQ quantity (server-computed), or excluded with a short reason. Every line priced or explicitly excluded before submission | [SOURCE] BR-081, IHB:1298, DT-09; [REC] rate × quantity |
| Alternate specification | Per line, optional: the contractor states a deviation from the issued value (text). Never changes the RFQ | [SOURCE] F-082, IHB:1299 |
| Additional items | Optional extra lines the contractor proposes (description, unit, quantity, rate). Shown separately; never in the comparable total | [PD] QD-18; [SOURCE] WEB demo (unrequested false ceiling) |
| Total | Comparable total = sum of priced line amounts; stored with the version | [REC] |
| Exclusions and assumptions | Two lists of short texts for the quote as a whole | [SOURCE] TVB §9.2, TPB §7 |
| Taxes | A required choice: prices INCLUDE or EXCLUDE GST, plus an optional note. Plan2Build computes no tax | [PD] QD-18; [SOURCE] BUD (S10 "taxes"), PRO:1571 |
| Validity | `valid_from`, `valid_to` (CD-17); `valid_to` after `valid_from`; set by the contractor | [SOURCE] CD-17; [PD] QD-06 (answers CQ-09 for 3.6) |
| Schedule | The contractor's proposed total duration in days and optional durations per Build Plan schedule entry; no calendar dates | [SOURCE] S35 M.1 "the contractor's own schedule"; [PD] BP-07A |
| Payment terms | Free text from the contractor; no structured milestones, percentages or amounts | [SOURCE] CD-09, IC §6.8; [PD] BP-10; QD-18 |
| Warranty | Optional free text | [SOURCE] TVB §9.2 (category dependent) |
| Materials responsibility | Optional free text (who supplies materials) | [SOURCE] FLOWS B6, PRO:1611 |
| Attachments | Up to a configured number of scanned files (contractor's quote letter, method statement) | [SOURCE] PRO:1570; [REC] |
| Comment | One short note to Plan2Build | [REC] |
| Captured by staff | Flag plus the operations user and the evidence file (the contractor's own document), for staff capture | [SOURCE] BR-082, API:172 |
| Never collected | Contractor input costs, margins, purchase costs | [SOURCE] MVP:170, CPB §8 |

### H.2 Three prices, kept apart

| Price | Owner | Who sees it | Where |
|---|---|---|---|
| Plan2Build estimate and Build Plan BOQ amounts | Plan2Build (internal costing) | Homeowner and operations; never contractors | `buildplan` |
| Contractor quote | The contractor | The contractor (own), operations, the homeowner (in the published comparison) | `rfq` |
| Final commercial agreement | Homeowner and contractor, outside Plan2Build | Recorded later (contract value, CQ-13) | Later construction slice |

[PD] PD-04, BP-08; [REC] the third row

---

## I. Quote versioning

| Rule | Marker |
|---|---|
| One quote per invitation; each submission is a new version with `version_no` 1, 2, 3 | [SOURCE] CD-17, TVB-F §7.1, FLOWS §2 step 9 |
| A SUBMITTED version and its lines are immutable (trigger); later states change only lifecycle columns | [SOURCE] DATA:197, DATA:198, BR-085 |
| One DRAFT at a time per invitation, private to the contractor; discarded drafts are deleted (they were never submitted) | [REC] |
| A new submission moves the previous SUBMITTED version to SUPERSEDED in the same transaction | [SOURCE] DATA:473 |
| Revision allowed while the RFQ is ISSUED and before the deadline. A validity renewal (kind RENEWAL: identical lines, totals, exclusions and terms, new validity dates) may be submitted after the latest version expired, also after the deadline, until selection | [PD] QD-06 |
| Withdrawal: allowed until selection, with a reason; the version becomes WITHDRAWN; the contractor may submit again before the deadline | [PD] QD-19 (answers POQ-013) |
| EXPIRED when `valid_to` passes without selection (job) | [SOURCE] STATE:269, EVENT:256 |
| The comparison references explicit version ids; a published comparison never changes when a later version arrives (a new comparison version is needed) | [SOURCE] STATE:275, AI:101 |
| The homeowner sees the latest reviewed version of each quote, always with its version number and submission time; never an unlabelled "latest" | [SOURCE] CD-17; Chirag's 3.6 instruction |
| Superseded, withdrawn and expired versions stay stored and auditable; operations see all versions | [SOURCE] CD-17 |

---

## J. Clarifications

| Question | Answer | Marker |
|---|---|---|
| Who can ask | A contractor with an ACCEPTED invitation (about the pack, before or after submitting); operations (about a contractor's quote) | [SOURCE] CPB §5 "Clarify", FLOWS A6; RC-14; [REC] |
| Who answers | Operations answer contractor questions; the contractor answers operations' questions | [SOURCE] IHB:4353 (through Plan2Build) |
| Homeowner | No direct channel to contractors in 3.6 and no clarification role; operations may answer using the owner's input gathered off-system | [PD] QD-17; [SOURCE] IHB:1309 |
| Shared with all | Operations choose per item; a shared answer goes to every ACCEPTED invitation without the asker's identity | [PD] QD-17 (answers POQ-012) |
| Does it change the quote | Never. A clarification is text. A price or line change needs a new quote version (section I) | [SOURCE] BR-085; [REC] |
| Does it change the RFQ | Never. A scope change needs a new Build Plan version and a new RFQ | [PD] QD-16, QD-17 |
| Shape | Structured items, not chat: one question, one answer, state OPEN → ANSWERED, or CLOSED without answer with a reason; bounded length; no attachments in 3.6 | [REC] (avoids an unstructured private channel) |
| Audit | Every item and answer is a row with actor and time; audit `clarification.{state}` | [SOURCE] API:29 |
| Notifications | Contractor: a question addressed to it; an answer to its question; a shared answer. Operations: a contractor question | [REC] section R |
| Effect on review | A quote with an OPEN clarification can still be reviewed; the unresolved point is recorded as an adjustment with clarification status OPEN | [SOURCE] DATA:199 (`clarification_status`) |

---

## K. Quote review

### K.1 Four separate facts

| Fact | Record |
|---|---|
| Quote received | Quote version SUBMITTED |
| Quote structurally reviewed | Review state REVIEWED on that version (adjustment list complete) |
| Quote shown in comparison | The version id is in a PUBLISHED comparison snapshot |
| Contractor selected | A `selections` row; quote version SELECTED |

None collapses into another. [SOURCE] STATE:261 to 275; Chirag's 3.6 instruction

### K.2 Review states (per quote version)

| State | Meaning | Marker |
|---|---|---|
| PENDING | Submitted, not yet reviewed | [REC] |
| NEEDS_CLARIFICATION | Operations asked the contractor a question; the version stays as submitted | [REC]; [SOURCE] CPB §5 |
| REVIEWED | Adjustment list complete (it may be empty); operations recorded it | [SOURCE] STATE:275 ("adjustment list complete"), RE:69 |
| CLOSED | The version left SUBMITTED (superseded, withdrawn, expired) before review finished | [REC] |

Not introduced: REJECTED or RETURNED (no source lets Plan2Build reject a contractor's quote; non-conforming points become adjustments and clarifications), UNDER_REVIEW as a separate state (no behaviour differs from PENDING), ACCEPTED_FOR_COMPARISON (REVIEWED is that fact). [REC]

### K.3 Adjustments (normalisation)

| Rule | Marker |
|---|---|
| Each adjustment: the quote version, the specification line or BOQ line, the deviation type (EXCLUDED, GRADE, QUANTITY, ADDITIONAL, OTHER), a description, the rupee impact (positive or negative), the basis note, the clarification status, the author | [SOURCE] MVP P4, MVP §5 `normalisation_adjustment`, DATA:199 |
| The rupee impact is Plan2Build's figure (it may use the Build Plan's rates, which the homeowner already sees); it never overwrites the contractor's price | [SOURCE] TVB §9.3, CPB §11, BR-085 |
| Editable while the version is PENDING or NEEDS_CLARIFICATION; frozen when REVIEWED | [REC] |
| Maker and checker: the reviewer who marks REVIEWED is recorded; publication (section L) is by OPS or ADMIN with MFA | [SOURCE] API:175; [REC] four-eyes not required (no source) |
| AI may later draft adjustment text with human review; not in 3.6 (no language model at the POC) | [SOURCE] CPB §20, IC §18.6 |

### K.4 Homeowner visibility before review

The homeowner sees that a contractor accepted, declined, submitted (with version number and time) or withdrew. Prices appear only in the published comparison. [PD] QD-07; [SOURCE] STR §3.2 (a raw price grid drives contractors away), API:176 (quotes are shown in the comparison)

---

## L. Comparison

| Question | Answer | Marker |
|---|---|---|
| What it is | A structured, Plan2Build-reviewed, frozen snapshot of the REVIEWED quote versions of one RFQ | [SOURCE] DATA:200, STATE:275 |
| Line-by-line | Yes: each BOQ line with each quote's amount or "excluded", the alternate specification, then the adjustment list per quote, then totals | [SOURCE] MVP P4, IHB:1378 (D1 map to common lines) |
| Normalised | Yes: normalised total = comparable total + the sum of adjustments, shown beside the submitted total | [SOURCE] IHB:1337 to 1353, WEB demo |
| Operations-reviewed | Yes: built only from REVIEWED versions; published by OPS or ADMIN with MFA | [SOURCE] API:175, POCB "QA ... comparison outputs" |
| Calculated or entered | Totals calculated; adjustments entered by operations | [SOURCE] TPB §11.1 "reproducible from stored rules" |
| Presentation order | The adjustment list first; quotes in a neutral order from a stored deterministic seed per comparison version, independent of price, identity, commercial importance and preference; no sort by price; no "lowest", "cheapest", "best" or "recommended" label; no rank number | [SOURCE] BR-083, MVP §9, IC §23.9; [PD] QD-11 |
| Recommendation | None in 3.6; deferred to a future slice | [PD] QD-10 (RC-08) |
| Risk flags | None in 3.6; deferred with the recommendation engine (thresholds AQ-17 belong to that future slice) | [PD] QD-10 |
| Minimum quotes | No numeric minimum: one or more REVIEWED quote versions; zero cannot be published; the homeowner sees how many invitations were sent and how many quotes were received | [PD] QD-24 |
| Versions | `version_no` per RFQ; a later quote version, withdrawal or expiry after publication needs a new comparison version by operations; the earlier one becomes SUPERSEDED, never edited | [SOURCE] STATE:275, AI:101 |
| Document | A deterministic fpdf2 PDF rendered at publication (ADR-023), stored with sha256; homeowner (owner and household) and operations only; no share link | [SOURCE] F-084, IHB:1352; [PD] ADR-023, QD-23 |
| Shown where | Homeowner dashboard (functional screen) and the PDF | [REC] |
| Contractors | Never see any comparison | [SOURCE] SEC:121, RE:170 |
| Homeowner notes | Out of 3.6 | [REC] |

Neutrality guards: no paid placement, no sponsored or commercial order, no algorithmic contractor scoring, no automatic winner. A test asserts the response has no rank, score or "lowest" field and that order is independent of price. [PD] PD-08; [SOURCE] IC §18.3, ADR-012:11

---

## M. Contractor selection

| Question | Answer | Marker |
|---|---|---|
| Who selects | The project OWNER. Household members read only | [SOURCE] DOM:385; [REC] OQ-027 unchanged |
| Confirmation | A one-time code of a new purpose (`SELECT_QUOTE`) bound to the quote version, as Build Plan acceptance | [PD] QD-12 (RC-19); [SOURCE] API:178, SEC:62 design |
| Statement | The owner confirms the ACTIVE selection statement: versioned configuration like the acceptance statement, saying Plan2Build is not the contractor, is not a party to the construction contract, receives no construction money and does not guarantee the quoted price; wording IMPLEMENTED / PENDING FINAL CLIENT + LEGAL CONFIRMATION | [PD] QD-12; [SOURCE] CPB §4.5, CD-01, WEB "We never take your contract" |
| What is selected | One quote version in the current PUBLISHED comparison of the RFQ | [SOURCE] DATA:201 |
| Guards | Package active; the RFQ ISSUED; the comparison PUBLISHED and current; the version SUBMITTED, REVIEWED and not past `valid_to`; the contractor's CONTRACTOR listing still LISTED; no ACTIVE CONTRACTOR engagement with another party; no earlier selection on the RFQ | [SOURCE] API:178 ("409 if EXPIRED"); [REC] |
| One contractor | One selection per RFQ (UNIQUE), one contractor for the category | [SOURCE] DATA:201; [PD] N-02 |
| Revocable | No. The selection is an immutable record. If the family changes its mind, it ends the engagement under 3.4 and may start a new RFQ | [PD] QD-12 |
| Effect on losing quotes | Every other SUBMITTED version of the RFQ becomes NOT_SELECTED in the same transaction; drafts are discarded | [SOURCE] DATA:474, STATE:273 |
| Other invitations | SENT invitations are withdrawn (reason RFQ_CLOSED); ACCEPTED ones end with their quote's outcome | [REC] |
| Open connection requests | The family's SENT CONTRACTOR connections are withdrawn by the system with reason ANOTHER_ENGAGED, as on acceptance | [PD] N-02; [SOURCE] S34 0.1 |
| Existing engagement | See section N | |
| RFQ | CLOSED; the comparison DECIDED | [SOURCE] STATE:257, STATE:275 |
| Contractor declines after selection | No second confirmation step (the contractor already submitted the quote): the engagement is ACTIVE at selection; the contractor may end it under 3.4 with a reason | [PD] QD-12 |
| Never means | Plan2Build becomes the contractor, receives money, guarantees the price or execution, or signs anything; no project status moves | [PD] PD-01, N-03, BP-14; [SOURCE] CD-01 |
| Contract value | Not recorded in 3.6 | [PD] QD-12 (RC-10) |

---

## N. Engagement integration

### N.1 Principle

The engagement of 3.4 stays the only professional relationship record. The RFQ adds a sourcing path into it; it adds no state to engagements and no second lifecycle. [PD] N-02, N-03, PD-17; [SOURCE] S34 D.1:121 ("RFQs, quotes ... reference it")

### N.2 Rules

| Question | Answer | Marker |
|---|---|---|
| Invitation requires an engagement | No; accepting an invitation creates no engagement | [PD] QD-01 |
| Selection creates an engagement | Yes, when none is ACTIVE: a LISTED engagement for (project, CONTRACTOR, profile) with origin RFQ_SELECTION and the selection id, created through a new `engagements.interface` function in the same transaction. The family's contact is then shared as on connection acceptance (N-08) | [PD] QD-01 |
| Schema impact on engagements | `project_engagements` gains `origin` (CONNECTION, OUTSIDE, RFQ_SELECTION) and `selection_id`; the party CHECK accepts LISTED with `connection_id` or `selection_id` | [REC] (additive migration in the engagements module) |
| Existing ACTIVE engagement with the selected contractor | Reused: no new row; an engagement event records the selection | [PD] QD-13 |
| Existing ACTIVE engagement with someone else | Selection refused (`ENGAGED`); by QD-13 the RFQ could not have invited others anyway | [PD] N-02; [REC] |
| Engagement state change at selection | None beyond creation; ACTIVE and ENDED stay the only states | [PD] N-03 |
| Losing contractors | No engagement, no connection; their invitation and quote record the outcome | [REC] |
| Pending connection requests | Withdrawn (ANOTHER_ENGAGED) at selection | [PD] N-02 |
| Selected contractor no longer LISTED at selection | Selection refused (`NOT_LISTED`); the owner may select another quote | [SOURCE] 3.4 accept rule |
| Professional suspended after selection | The engagement continues (3.4: listing changes never end engagements; N-10 pattern); operations may end it with a reason | [PD] N-10; [SOURCE] S34 R |
| Package ends after selection | The engagement continues (N-10) | [PD] N-10 |
| Substantial work | Selection writes usage `RFQ_SELECTION` through `billing.interface.record_service_usage` in the selection transaction, whether the engagement is created or reused (the selection is the delivered outcome). N-12 (CONNECTION_ACCEPTED) is unchanged | [PD NEW] QD-02 |
| Interface additions | `engagements.interface.active_engagement(project_id, category)`, `engage_from_selection(...)`, `withdraw_open_connections(project_id, category, reason)`; `buildplan.interface.accepted_manifest(project_id)`; `professionals.interface.connection_candidate` reused | [REC] |

---

## O. External quote-holder review (3.4) integration

| Point | Decision | Marker |
|---|---|---|
| Distinct capabilities | 3.4 = a homeowner uploads an outside quote for Plan2Build's review (intake built). 3.6 = a structured RFQ and contractor quote workflow. They stay separate records, routes and screens | [PD] S34 0 "Quote-holder review"; Chirag's 3.6 instruction |
| Review output for held quotes | Not built in 3.6. Its terms (full package or review alone, what follows, whether the contractor must join) stay CQ-02 for a later decision | [PD] QD-25 |
| Shared model later | The held-quote review may later reuse the adjustment shape of section K.3 against the requirement (no Build Plan) or the accepted version (S35 M.4); it never writes into RFQ tables | [SOURCE] S35 M.4; [REC] |
| Bridging | A holder whose contractor is LISTED may invite it to the RFQ; one engaged as OUTSIDE is captured by staff in the standard format (QD-22). The uploaded file itself is never turned into an RFQ quote | [REC] |
| Not replaced | The 3.4 intake routes, files and operations email stay as built | [PD] S34 0 |

---

## P. Package and refund interaction

| Question | Answer | Marker |
|---|---|---|
| Gating | Request, issue, invitations, staff capture, review actions, publication and selection need `package_active`. Reading and withdrawal never do. Contractor actions (accept invitation, submit, revise) are refused while the package is inactive because the RFQ is cancelled (below) | [PD] PD-19, BP-09 pattern |
| N-12 | Unchanged: connection acceptance writes CONNECTION_ACCEPTED. 3.6 writes no usage row for RFQ creation, invitation acceptance, submission, review or comparison publication; Build Plan issue still writes none | [PD] N-12, BP-09, QD-02 |
| RFQ selection | Writes usage `RFQ_SELECTION` (an added, explicitly approved trigger). Before it, refunds follow the existing pre-substantial-work rules; after it, the package has entered substantial work | [PD NEW] QD-02 |
| Package REFUNDED or CANCELLED during an open RFQ | The system cancels the open RFQ (reason PACKAGE_ENDED), withdraws SENT invitations, closes drafts; no new contractor actions; submitted quotes and published comparisons stay readable as history; no selection; no usage record. No pause and resume | [PD] QD-14; N-10 pattern |
| After reactivation (a new order) | A new RFQ on the ACCEPTED version; operations may copy the recipients. Old quotes stay history; they are not carried over (prices may no longer be valid) | [PD] QD-14 |
| Late instalment | No effect: the package stays ACTIVE (no LAPSED state) | [SOURCE] S33 O-03 as built |
| Can contractors still respond | Not to a cancelled RFQ | [PD] QD-14 |
| Can existing quotes be viewed | Yes, by the owner and operations; by the contractor (its own) | [REC] |
| Billing tables | Carry no RFQ, quote or contractor reference; the import linter forbids billing importing `rfq` | [SOURCE] S33 G.1, S3R:40 |
| Fees from contractors | None | [SOURCE] PRO:4288; RC-24 |

---

## Q. Documents

| Document | Model | Marker |
|---|---|---|
| RFQ pack | The frozen manifest JSON on the RFQ with its sha256; drawings by file id (already immutable). No rendered pack PDF in 3.6 | [REC] |
| RFQ manifest | Read from `buildplan.interface`; ops keep the 3.5 route | [SOURCE] S35IR G |
| Contractor quote | Rows (version, lines, terms); its content hash stored at submission | [SOURCE] DATA:197; [REC] hash |
| Quote attachments | New purpose `QUOTE_ATTACHMENT`, project-scoped, owned by the contractor's user; presigned upload from the professional host (a storage CORS origin); scanned before AVAILABLE; size and count limits as configuration | [SOURCE] ADR-011; [REC] |
| Staff capture evidence | Same purpose, uploaded through the API raw-body route (admin host) | [SOURCE] S35IR C:56 pattern |
| Comparison document | New purpose `COMPARISON_DOCUMENT`; fpdf2, deterministic, rendered at publication, sha256 stored; never re-rendered for a published version | [PD] ADR-023; [PD] QD-23 |
| Selected quote | No separate document: the selection points at the immutable version and the comparison | [REC] |
| Accepted commercial record | Not in 3.6 (construction slice; CQ-13) | [REC] |
| Access | Logged 15-minute links (`document_access_log`); contractor: the RFQ's drawings while its invitation is ACCEPTED and the RFQ open, its own attachments always; owner and household: the comparison document and attachments of quotes in a published comparison; operations: all, logged | [SOURCE] ADR-006, ADR-011; [REC] |
| Versioning and retention | Objects never overwritten; PROJECT retention class (life of the record) | [SOURCE] DATA:517 |
| No WeasyPrint | ADR-018 applies to no document type | [PD] ADR-023 |

---

## R. Notifications

Pattern: outbox event → notification job → plain-text template; ops kinds to the ops mailbox; family and professional kinds to the account's primary email through an `rfq.interface` notice function; payloads carry ids only; nothing private before the stage that allows it; one email per event; no reminders, no countdowns, no marketing. Template wording is draft until approved. [SOURCE] FP 4e, IC §10.4, §12.2; [PD] N-07, N-11 by analogy

| Recipient | Event | Email | Marker |
|---|---|---|---|
| Homeowner | RFQ issued (covers "created" and "contractors invited") | Yes | [REC] |
| Homeowner | Contractor accepted, declined, quote received, quote reviewed | No email; dashboard status | [REC] (avoids several emails per RFQ) |
| Homeowner | Clarification needed | No (the owner has no clarification role, QD-17) | [REC] |
| Homeowner | Comparison published | Yes | [SOURCE] IHB:2757 "Comparison ready" |
| Homeowner | Selection confirmed | Yes | [SOURCE] IHB:2758 |
| Homeowner | RFQ cancelled by operations or the system | Yes (not when the owner cancelled) | [REC]; [SOURCE] 3.4 pattern |
| Contractor | Invitation received | Yes | [SOURCE] PNOT-10 |
| Contractor | Invitation withdrawn or RFQ cancelled | Yes | [SOURCE] 3.4 pattern |
| Contractor | Question addressed to it; answer to its question; shared answer | Yes | [SOURCE] PNOT-13 |
| Contractor | Deadline extended | Yes | [REC] |
| Contractor | Submission confirmation | No email (the screen confirms); yes when staff captured a quote on its behalf | [SOURCE] API:172 |
| Contractor | Review status | No (not visible to contractors) | [REC] |
| Contractor | Selected / not selected | Yes, both; the not-selected email names no winner and no price | [SOURCE] PRO:4246; [PD] QD-20 (answers POQ-015) |
| Contractor | Quote expired | Yes, one email | [SOURCE] EVENT:153 |
| Operations | RFQ requested by the owner | Yes | [REC] |
| Operations | Quote submitted; contractor question | Yes | [SOURCE] EVENT:152 |
| Operations | Quote deadline reached | Yes, one per RFQ (job) | [REC] |
| Operations | Selection confirmed | Yes | [REC] |
| Operations | Exceptions and failures | Existing alerting (job failures, outbox retries); no new email kind | [SOURCE] EVENT §2 |
| Owner, contractor | One-time code | Existing `otp_confirm` template with the purpose label | [SOURCE] 3.5 pattern |

---

## S. Security and permissions

| Invariant | Enforcement | Marker |
|---|---|---|
| A homeowner reaches only their own project | Membership join; 404 outside visibility; foreign-membership sweep test over every new route | [SOURCE] SEC:120, BR-013 |
| Only the OWNER writes; HOUSEHOLD reads | `family_access(write=)` pattern | [SOURCE] 3.4, 3.5 |
| A contractor sees only its own invitations | Every pro route keyed by its invitation, filtered by its profile; 404 otherwise | [SOURCE] SEC:121, IHB:1227 |
| No competitor quote, line, file, count or status | Response models per audience with no such fields; isolation test over every route | [SOURCE] BR-088, TESTING:44 |
| No Plan2Build rates, amounts, totals or estimate to contractors | The manifest model (`extra="forbid"`) and a test that the pack and every pro response hold no rate key or value | [PD] BP-08 |
| No contractor costs or margins to homeowners | Not collected | [SOURCE] MVP:170 |
| No access to another contractor's documents | File links checked against the caller's own invitation and purpose | [SOURCE] ADR-011 |
| Operations follow privileged-role rules | OPS or ADMIN with MFA on the ops host; ADMIN only for selection statements; reads of contractor documents logged | [SOURCE] SEC §11 |
| Historical versions immutable | Triggers: SUBMITTED quote versions and lines, REVIEWED adjustments, PUBLISHED comparisons, selections, invitations' terminal states, the RFQ's manifest copy | [SOURCE] DATA:487 |
| Every transition audited | `audit.record` in the same transaction plus an `rfq_events` row | [SOURCE] API:29 |
| No enumeration | UUIDv7; 404 outside visibility; identical refusals for unknown and foreign ids | [SOURCE] SEC:139, API:21 |
| Safe responses | Refusal codes name only the caller's own state (`STATE_CONFLICT` with a reason, `PACKAGE_REQUIRED`, `VERSION_CONFLICT`) | [SOURCE] STATE:15 |
| Package gating server-side | `package_active` in the service layer for every gated action | [PD] PD-19 |
| Idempotency and concurrency | `Idempotency-Key` on every creating or transition POST; `version` on mutable rows; `FOR UPDATE` on the RFQ row for issue, selection and comparison publication | [SOURCE] IC §7.5, DATA:35 |
| One code, one action | Selection code bound to (owner, SELECT_QUOTE, quote version); unique `challenge_id` on the selection | [SOURCE] SEC:62 |
| Rate limits | Session limits on contractor submission and clarification creation; upload limits as 3.4 | [SOURCE] API:28 |
| No construction money | No route or column takes a payment between homeowner and contractor | [SOURCE] CD-01, IC §23.8 |

### S.1 Permission matrix

| Action | Owner | Household | Invited contractor | Operations | Admin |
|---|---|---|---|---|---|
| Request quotes, nominate | Yes | No | No | On owner's direction | Same as ops |
| Prepare, issue, extend, introduce | No | No | No | Yes (MFA) | Yes |
| Cancel RFQ | Yes (reason) | No | No | Yes (reason) | Yes |
| Accept or decline invitation | No | No | Own | No | No |
| Draft, submit, revise, withdraw quote | No | No | Own | Staff capture for OUTSIDE or offline contractors | Same |
| Ask clarification | No | No | Own invitation | Yes | Yes |
| Review, adjustments | No | No | No | Yes | Yes |
| Publish comparison | No | No | No | Yes (MFA) | Yes |
| Read comparison | Yes | Yes | Never | Yes | Yes |
| Select | Yes (code) | No | No | No | No |
| Selection statement draft and activate | No | No | No | Read | Yes |

---

## T. State machines

Common rules: transition tables in code; a disallowed transition returns 409 `STATE_CONFLICT` and every disallowed pair is tested; terminal states never change; every row below writes an `rfq_events` row and an audit row in the same transaction. [SOURCE] STATE §1, IC §9

### T.1 RFQ

| From → To | Actor | Guard | Side effects | Notify | Audit | Reversal | Marker |
|---|---|---|---|---|---|---|---|
| none → DRAFT | Owner (request) or ops | Package active; ACCEPTED version; CONTRACTOR not NOT_NEEDED; no open RFQ in the category; QD-13 rule | Version id recorded; nominated recipients stored as draft invitations | Ops (when the owner requested) | `rfq.draft` | Cancel | [REC] |
| DRAFT → ISSUED | Ops (MFA) | Package active; the version still ACCEPTED; 1 to max recipients, each eligible; `quotes_due_at` in the future | Manifest frozen with hash; invitations SENT with `respond_by` | Owner; each contractor | `rfq.issued` | Cancel | [REC] |
| ISSUED → ISSUED (deadline extended) | Ops | Before selection; reason | `quotes_due_at` changes | ACCEPTED contractors; SENT ones see it on opening | `rfq.deadline_extended` | Another extension | [REC] |
| ISSUED → CLOSED | System (in the selection transaction) | A selection confirmed | Comparison DECIDED; other quotes NOT_SELECTED; SENT invitations withdrawn | See M | `rfq.closed` | None (terminal) | [SOURCE] STATE:257 |
| DRAFT or ISSUED → CANCELLED | Owner (reason code), ops (reason), system (PACKAGE_ENDED, BASELINE_SUPERSEDED, PROJECT_CLOSED) | No selection | Invitations SENT withdrawn; drafts closed; quotes and comparisons kept read-only | Owner (unless the owner cancelled); contractors with SENT or ACCEPTED invitations | `rfq.cancelled` | None; a new RFQ | [SOURCE] STATE:257; [REC] reasons |

Immutable: the version id and the manifest copy from ISSUED.

### T.2 Invitation

| From → To | Actor | Guard | Side effects | Notify | Audit | Reversal | Marker |
|---|---|---|---|---|---|---|---|
| none → SENT | Ops (at issue or later before the deadline) | Section F checks; below the maximum; package active | `respond_by` = now + window; brief stored | Contractor | `invitation.sent` | Withdraw | [REC] |
| SENT → ACCEPTED | Contractor | Before `respond_by`; RFQ ISSUED and before the deadline; still LISTED; package active | Pack and drawings become readable | None (dashboard) | `invitation.accepted` | None; the contractor may decline to quote by not submitting, or withdraw a quote | [SOURCE] STATE:259 |
| SENT → DECLINED | Contractor | Reason from the N-06 list; OTHER needs a note | None | None (dashboard) | `invitation.declined` | None | [PD] QD-05 (N-06 reasons; answers POQ-008) |
| SENT → EXPIRED | System job | `respond_by` passed | None | None | `invitation.expired` | None | [PD] N-07 by analogy |
| SENT → WITHDRAWN | Owner (before issue only), ops (reason), system (RFQ cancelled or closed, listing left LISTED) | | | Contractor (except owner removal before issue: nothing was sent) | `invitation.withdrawn` | None | [REC] |

ACCEPTED is terminal for the invitation; the outcome lives on the quote versions. Contractor access to the pack ends when the RFQ is CANCELLED or CLOSED without its selection.

### T.3 Quote version

| From → To | Actor | Guard | Side effects | Notify | Audit | Reversal | Marker |
|---|---|---|---|---|---|---|---|
| none → DRAFT | Contractor | Invitation ACCEPTED; RFQ ISSUED; no other DRAFT | | | `quote_version.draft` | Delete draft | [SOURCE] API:168 |
| DRAFT → SUBMITTED | Contractor | Before the deadline (or a revalidation, section I); every manifest line priced or excluded; validity dates valid; tax choice made; attachments AVAILABLE; package active | Amounts and total computed; content hash; previous SUBMITTED → SUPERSEDED; review PENDING | Ops | `quote_version.submitted` | New version or withdrawal | [SOURCE] BR-081, DATA:473 |
| none → SUBMITTED (staff capture) | Ops | Same checks; evidence file; recipient is the invitation's contractor or the OUTSIDE engaged party | As above; `captured_by_staff` | Contractor (LISTED) copy | `quote_version.captured` | Same | [SOURCE] BR-082, API:172 |
| SUBMITTED → SUPERSEDED | System | A newer version submitted | Review CLOSED if not REVIEWED | | `quote_version.superseded` | None | [SOURCE] DATA:473 |
| SUBMITTED → WITHDRAWN | Contractor (reason) or ops (on the contractor's written request) | Before selection | Review CLOSED | Ops | `quote_version.withdrawn` | Submit again before the deadline | [PD] QD-19 |
| SUBMITTED → EXPIRED | System job | `valid_to` passed, no selection | | Contractor (once) | `quote_version.expired` | Renewal version | [SOURCE] EVENT:153 |
| none → SUBMITTED (kind RENEWAL) | Contractor | Latest version EXPIRED; RFQ ISSUED; no selection; content identical to the expired version except validity | Review carried as REVIEWED when the expired version was REVIEWED (identical content), otherwise PENDING | Ops | `quote_version.renewed` | New version | [PD] QD-06 |
| SUBMITTED → SELECTED | System (selection) | Section M guards | Engagement created or reused | Contractor | `quote_version.selected` | None | [SOURCE] STATE:273 |
| SUBMITTED → NOT_SELECTED | System (selection) | Another version selected | | Contractor | `quote_version.not_selected` | None | [SOURCE] STATE:273 |

Immutable from SUBMITTED: lines, totals, terms, attachments, validity, hash.

### T.4 Quote review (per SUBMITTED version)

| From → To | Actor | Guard | Side effects | Notify | Audit | Reversal | Marker |
|---|---|---|---|---|---|---|---|
| none → PENDING | System | Version SUBMITTED | | Ops (with the submission email) | `quote_review.pending` | | [REC] |
| PENDING → NEEDS_CLARIFICATION | Ops | A clarification item addressed to the contractor | | Contractor | `quote_review.needs_clarification` | Answer or reviewer decision | [REC] |
| NEEDS_CLARIFICATION → PENDING | System or ops | Answered or closed | | | `quote_review.pending` | | [REC] |
| PENDING or NEEDS_CLARIFICATION → REVIEWED | Ops | Version still SUBMITTED; unresolved points recorded as adjustments with status OPEN | Adjustments frozen | None | `quote_review.reviewed` | None (a new quote version starts a new review) | [SOURCE] STATE:275 |
| any open → CLOSED | System | Version left SUBMITTED | | | `quote_review.closed` | | [REC] |

### T.5 Comparison

| From → To | Actor | Guard | Side effects | Notify | Audit | Reversal | Marker |
|---|---|---|---|---|---|---|---|
| none → DRAFT | Ops | RFQ ISSUED; at least one REVIEWED version (QD-24) | Snapshot assembled from REVIEWED versions; order seed stored | | `comparison.draft` | Discard draft | [SOURCE] STATE:275 |
| DRAFT → PUBLISHED | Ops (MFA) | Package active; every included version still SUBMITTED and REVIEWED | Snapshot and hash frozen; PDF rendered; an earlier PUBLISHED version → SUPERSEDED | Owner | `comparison.published` | New comparison version | [SOURCE] API:175; [REC] |
| PUBLISHED → SUPERSEDED | System | A newer version published | | | `comparison.superseded` | None | [SOURCE] STATE:275 |
| PUBLISHED → DECIDED | System (selection) | Selection from this version | | | `comparison.decided` | None | [SOURCE] STATE:275 |

A published comparison whose included version later expires or is withdrawn stays published and readable; selection of that version is refused; ops publish a new version. [REC]

### T.6 Selection

| From → To | Actor | Guard | Side effects | Notify | Audit | Reversal | Marker |
|---|---|---|---|---|---|---|---|
| none → CONFIRMED (the row exists) | Owner with a valid one-time code | Section M guards | T.1 CLOSED, T.3 SELECTED and NOT_SELECTED, T.5 DECIDED, invitations closed, connections withdrawn, engagement created or reused, statement text stored | Owner, selected contractor, other contractors, ops | `selection.confirmed` | None in the RFQ; the engagement may end under 3.4 | [PD] QD-12, QD-02 (usage RFQ_SELECTION written) |

Immutable: the whole row (append-only).

---

## U. Data model (minimum)

Module `rfq` (name from DOM 3.10, so no new ADR; IC §4). All tables carry `project_id`. Append-only tables refuse UPDATE and DELETE (`p2b_forbid_mutation`); versioned rows change only lifecycle columns (`p2b_allow_only_columns`). [REC] throughout; [SOURCE] DATA 4.9 for the shape, 3.4 and 3.5 triggers

| Table | Purpose | Key columns | Guard |
|---|---|---|---|
| `rfqs` | One RFQ per project, category and round | category_code (CONTRACTOR), build_plan_version_id (FK), manifest jsonb, manifest_sha256, quote_format_version, state, quotes_due_at, max_recipients (copied from configuration), requested_by, issued_by, issued_at, closed_at, cancel_reason, cancel_note, version | Partial UNIQUE (project_id, category_code) WHERE state IN (DRAFT, ISSUED); manifest columns frozen from ISSUED |
| `rfq_invitations` | One contractor asked to quote | rfq_id, profile_id (nullable for an OUTSIDE party), engagement_id (OUTSIDE party only), source (NOMINATED, INTRODUCED, ENGAGED), introduced_reason, brief jsonb, state, respond_by, responded_at, decline_reason, decline_note, withdraw_reason, version | UNIQUE (rfq_id, profile_id); lifecycle columns only |
| `quote_versions` | Immutable submissions (the "quote" is the set of versions on an invitation) | invitation_id, version_no, state, review_state, valid_from, valid_to, tax_treatment, tax_note, duration_days, schedule jsonb, payment_terms_text, warranty_text, materials_text, exclusions, assumptions, comment, attachment_file_ids, comparable_total numeric(14,2), content_sha256, submitted_by, submitted_at, captured_by_staff, evidence_file_id, withdraw_reason | UNIQUE (invitation_id, version_no); partial UNIQUE one DRAFT per invitation; content frozen from SUBMITTED |
| `quote_lines` | Lines of a version | quote_version_id, manifest_line_no (null for additional items), kind (RFQ_LINE, ADDITIONAL), rate, amount, is_excluded, exclusion_reason, alternate_spec, description and unit and quantity (additional items only) | CHECK priced or excluded; frozen with the version |
| `quote_adjustments` | Plan2Build normalisation | quote_version_id, spec_line_code or manifest_line_no, deviation_type, description, rupee_impact, basis_note, clarification_status, created_by | Editable until the version is REVIEWED |
| `rfq_clarifications` | Structured questions and answers | rfq_id, invitation_id, quote_version_id (nullable), direction (CONTRACTOR_ASKS, PLAN2BUILD_ASKS), question, answer, shared_with_all, state (OPEN, ANSWERED, CLOSED), asked_by, answered_by, close_reason | Lifecycle columns only |
| `comparisons` | Frozen comparison versions | rfq_id, version_no, state, snapshot jsonb, snapshot_sha256, order_seed, document_file_id, published_by, published_at | UNIQUE (rfq_id, version_no); frozen from PUBLISHED |
| `selections` | The homeowner's choice | rfq_id UNIQUE, comparison_id, quote_version_id, profile_id, engagement_id, selected_by, challenge_id UNIQUE, statement_id, statement_text, selected_at | Append-only |
| `selection_statements` | Versioned statement text | version, text, status, note, created_by, activated_by | One ACTIVE; as `acceptance_statements` |
| `rfq_events` | History | subject (RFQ, INVITATION, QUOTE_VERSION, REVIEW, COMPARISON, SELECTION), subject_id, from_state, to_state, actor_role, reason | Append-only |
| `project_engagements` (engagements) | Origin of an engagement | `origin`, `selection_id`; CHECK accepts LISTED with connection or selection | Additive change |
| `file_objects` (documents) | New purposes | QUOTE_ATTACHMENT, COMPARISON_DOCUMENT | Existing |
| `otp_challenges` (identity) | New purpose | SELECT_QUOTE (subject = quote version) | Existing CHECK widened |

Not created [REC]: `quotes` (the invitation already is the one-quote container), `rfq_pack_versions` (no amendments, QD-16), `contract_values` (RC-10), `recommendation_*` tables (QD-10), `share_tokens` (no share link), `contractor_capacity`, `professional_conflicts`, `leads`, any column on `projects`, any `package_service_usage` kind (QD-02).

Events (outbox, ids only): `rfq.requested`, `rfq.issued`, `rfq.deadline_extended`, `rfq.cancelled`, `rfq.closed`, `rfq.invitation_sent`, `rfq.invitation_withdrawn`, `rfq.quote_submitted`, `rfq.quote_expired`, `rfq.clarification_asked`, `rfq.clarification_answered`, `rfq.comparison_published`, `rfq.selection_confirmed`. Consumed: `buildplan.accepted`, `billing.package_changed`, `project.cancelled`, `professional.listing_changed`. [REC]; RC-20

---

## V. API model (proposed, not implemented)

All under `/api/v1`. Creating and transition POSTs take `Idempotency-Key`; mutable rows take `version`. Refusals: 409 `PACKAGE_REQUIRED`, `STATE_CONFLICT` with `details.reason` (NO_ACCEPTED_VERSION, NOT_NEEDED, OPEN_RFQ, ENGAGED, NOT_LISTED, OUTSIDE_AREA, NO_LOCATION, SELF, LIMIT, DEADLINE_PASSED, INCOMPLETE_LINES, EXPIRED, NOT_REVIEWED, STALE_COMPARISON, BASELINE_CHANGED), `VERSION_CONFLICT`; 404 outside visibility. [SOURCE] API conventions; [REC] routes

### V.1 Homeowner host

| Route | Actor | Purpose |
|---|---|---|
| `POST /projects/{id}/rfqs` | Owner, package | Request contractor quotes; body: category, nominated profile ids |
| `GET /projects/{id}/rfqs` | Owner, household | RFQs of the project with states |
| `GET /projects/{id}/rfqs/{rid}` | Owner, household | RFQ status, invitations (contractor names, states, quote version numbers and times; no prices before publication) |
| `POST /projects/{id}/rfqs/{rid}/cancel` | Owner | Reason code |
| `GET /projects/{id}/rfqs/{rid}/comparison` | Owner, household | Current published comparison |
| `GET /projects/{id}/rfqs/{rid}/comparisons/{cid}/document` | Owner, household | Logged link to the PDF |
| `GET /projects/{id}/rfqs/{rid}/quote-files/{fid}/url` | Owner, household | Attachments of quotes in a published comparison |
| `POST /projects/{id}/rfqs/{rid}/selection-code` | Owner, package | Start a SELECT_QUOTE code for a quote version |
| `POST /projects/{id}/rfqs/{rid}/select` | Owner, package | quote_version_id, challenge_id, code, statement_id |

### V.2 Professional host

| Route | Actor | Purpose |
|---|---|---|
| `GET /pro/rfq-invitations` | Contractor | Own invitations |
| `GET /pro/rfq-invitations/{iid}` | Contractor (own) | Brief when SENT; pack, deadline, shared answers when ACCEPTED |
| `POST /pro/rfq-invitations/{iid}/accept`, `/decline` | Contractor (own) | Decline needs a reason |
| `GET /pro/rfq-invitations/{iid}/drawings/{fid}/url` | Contractor (own, ACCEPTED, RFQ open) | Logged link |
| `PUT /pro/rfq-invitations/{iid}/quote-draft` | Contractor | Lines and terms |
| `DELETE /pro/rfq-invitations/{iid}/quote-draft` | Contractor | Discard draft |
| `POST /pro/rfq-invitations/{iid}/quote-draft/submit` | Contractor, package active on the project | Submit |
| `POST /pro/rfq-invitations/{iid}/quote/withdraw` | Contractor | Reason |
| `GET /pro/rfq-invitations/{iid}/quote-versions` | Contractor | Own versions and outcomes |
| `POST /pro/rfq-invitations/{iid}/attachments`, `/attachments/{fid}/complete` | Contractor | Presigned upload |
| `GET`, `POST /pro/rfq-invitations/{iid}/clarifications`; `POST .../clarifications/{qid}/answer` | Contractor | Ask; answer Plan2Build's question |

### V.3 Operations host (OPS or ADMIN, MFA)

| Route | Purpose |
|---|---|
| `GET /ops/rfqs` | Queue by state and deadline |
| `GET /ops/rfqs/{rid}` | Everything, including all versions, adjustments, clarifications, history |
| `POST /ops/projects/{id}/rfqs` | Create a DRAFT at the owner's direction |
| `PUT /ops/rfqs/{rid}/draft` | Recipients, deadline |
| `POST /ops/rfqs/{rid}/issue` | Issue |
| `POST /ops/rfqs/{rid}/invitations` | Introduce a contractor (reason) |
| `POST /ops/rfq-invitations/{iid}/withdraw` | Reason |
| `POST /ops/rfqs/{rid}/deadline` | Extend with reason |
| `POST /ops/rfqs/{rid}/cancel` | Reason |
| `POST /ops/rfq-invitations/{iid}/capture` (+ raw-body evidence upload) | Staff capture |
| `PUT /ops/quote-versions/{qvid}/adjustments`; `POST .../review` (REVIEWED) | Review |
| `POST /ops/rfqs/{rid}/clarifications`; `POST /ops/rfq-clarifications/{qid}/answer`, `/close` | Clarifications |
| `POST /ops/rfqs/{rid}/comparisons` (draft); `POST /ops/comparisons/{cid}/publish` | Comparison |
| `GET /ops/selection-statements`; `POST /admin/selection-statements`, `/{id}/activate` | Statement (ADMIN) |

The 3.5 route `GET /ops/projects/{id}/build-plan/rfq-manifest` stays. Notification events are internal (section R); no public webhook.

---

## W. UI scope (functional only)

No visual design, dashboard redesign, animation, responsive polish or marketing UI. Final UI and UX polish stays a later dedicated phase. [PD] Chirag's 3.6 instruction

| Host | Minimum screens |
|---|---|
| Homeowner | "Contractor quotes" section on the services page: request (nominate from listed contractors covering the plot), RFQ status, cancel; comparison page (adjustment list, line table, totals, PDF link); selection with statement and code |
| Professional | Invitations list; invitation page (brief, accept or decline; then pack, drawings, quote form with every line, terms, attachments, submit; versions and outcome; clarifications) |
| Operations | RFQ queue; RFQ page (draft recipients and deadline, issue, introduce, extend, cancel; quotes with versions; adjustments and review; clarifications; staff capture; comparison draft and publish); selection statements under Build Plan setup |

Phone and desktop Playwright with axe on each screen, as in earlier slices. [SOURCE] PFR G:278

---

## X. Test strategy

| Area | Tests (API unless marked) |
|---|---|
| Accepted Build Plan requirement | Refused with no ACCEPTED version; RFQ names the version; manifest copy equals the 3.5 manifest at issue; hash stored |
| Baseline change | New acceptance with an open RFQ applies QD-15; a CLOSED RFQ is untouched; the RFQ's manifest never changes after a later version |
| RFQ creation | Owner only; household 403; foreign 404; NOT_NEEDED refused; one open RFQ per category; maximum recipients |
| Package gating | Every gated action refused while inactive; reads and withdrawals allowed; package end applies QD-14; reactivation path |
| Eligibility | Not LISTED, hidden, outside area, no location, self, duplicate, engaged-category rule (QD-13), suspension withdraws the open invitation |
| Contractor isolation | Contractor A cannot read B's invitation, quote, versions, lines, attachments, clarifications, counts or the comparison on any route (sweep); ids of others return 404 |
| Internal-rate protection | No rate, amount, total, card or estimate key or value in any pro response or the pack (recursive key and value scan) |
| Quote submission | Every line priced or excluded; dates valid; tax choice; deadline; attachments AVAILABLE; amounts computed server-side |
| Quote revision and immutability | New version supersedes; SUBMITTED rows refuse UPDATE and DELETE (trigger); content hash stable; revalidation after deadline keeps lines identical |
| Review states | Every allowed and disallowed transition; adjustments frozen at REVIEWED; review CLOSED on supersede |
| Clarifications | Asking, answering, sharing without asker identity; no quote change; contractor sees only its own and shared items |
| Comparison neutrality | No rank, score, "lowest" or recommendation field; order independent of prices across seeds; only REVIEWED versions; published snapshot immutable; new version on later changes |
| Comparison document | Deterministic bytes for identical snapshots (fpdf2); homeowner and ops only; logged |
| Homeowner selection | Code required and bound to the version; one selection per RFQ; expired, withdrawn, unreviewed, stale-comparison and not-LISTED refusals; statement stored |
| Engagement integration | Engagement created with origin RFQ_SELECTION; existing engagement with the same contractor reused; other party refused; open connections withdrawn; contact shared after selection only; N-02 unique index holds under concurrent selections |
| Refund compatibility | No `package_service_usage` row from any 3.6 action unless QD-02 decides otherwise; refund flow unchanged |
| Document authorization | Drawing links only for ACCEPTED invitations of open RFQs; attachments only to owner after publication, to the contractor (own) and ops |
| Notifications | One job per event and kind; correct recipients; nothing private before the allowed stage; not-selected email names no winner |
| Audit history | Each transition writes `rfq_events` and audit rows in the same transaction |
| Invalid transitions | Every disallowed pair of T.1 to T.6 returns 409 |
| Historical integrity | Superseded, withdrawn and expired versions and superseded comparisons remain readable and unchanged |
| Competitor isolation in timing | Refusal reasons never depend on other contractors' state |
| Migration | Up, down, up twice; `alembic check` clean; vocabulary equals CHECK constraints |
| Browser (Playwright, phone and desktop, axe) | Owner requests; ops issues; contractor accepts and submits; ops reviews and publishes; owner selects with code; losing contractor sees outcome only |

---

## Y. Open decisions

None for 3.6: QD-01 to QD-26 are decided (section 0). Items still open outside 3.6, unchanged here:

| ID | Topic | Where it returns |
|---|---|---|
| CD-18, CD-28, RE §6 | Recommendation engine at comparison | Future slice (QD-10 deferral) |
| AQ-17 | Fit and risk thresholds | With the recommendation engine |
| F-10 (remainder) | RFQ scope for non-contractor categories | Later slice (QD-26) |
| CQ-02 | Quote-holder review terms | Later (QD-25) |
| F-03, CQ-23 | Platform access for outside professionals | Later; 3.6 uses staff capture (QD-22) |
| D-05, CQ-07 | Contractor enlistment class | Later; not required for 3.6 (QD-21) |
| CQ-13 | Contract value and its visibility | Construction slice |
| POQ-053, POQ-054 | Conflict-of-interest data | Later |
| O-10 | Refund approver before and after substantial work | Billing; QD-02 adds a trigger, not an approver rule |

---

## Z. Production blockers (not implementation blockers)

| Blocker | Why |
|---|---|
| Final client and legal confirmation of the selection statement wording | Production selection |
| Approval of the RFQ, quote and selection email wording | Production notifications (N-11 pattern) |
| Listed, verified CONTRACTOR professionals in Raipur covering real plots | No invitation can go out |
| The 3.5 production readiness items: Raipur production rate card, appointed drawing checker, approved sign-off and acceptance wording, an available structural engineer, a production Unicode PDF font, client confirmation of English-only documents, BP-07A, H-01 | Without an ACCEPTED production Build Plan there is no RFQ baseline; the font also serves the comparison PDF |
| Client confirmation that contractor screens may be English only (PBR-040 asks for Hindi on the quote form) | BR-057, ADR-022 |
| H-02 household quote-review files | Before production with H-01 |

BP-07A stays deferred: quotes carry the contractor's durations; no calendar date, decide-by date or cash flow is computed. [PD] BP-07A

---

## AA. Implementation order (after the decisions)

1. Record Chirag's answers to QD-01 to QD-26 in this document.
2. Module `rfq` with its interface; import-linter contracts (core, integrations, billing isolation, independence); vocabulary enums for every new state and reason.
3. Migration 0015: `rfq` tables, triggers and grants; engagements `origin` and `selection_id` with the CHECK change; file purposes; OTP purpose; selection statement seed (functional wording pending legal confirmation). Up, down, up twice.
4. Interfaces: `buildplan.accepted_manifest`; `engagements.active_engagement`, `engage_from_selection`, `withdraw_open_connections`; reuse `professionals.connection_candidate`, `billing.package_active`.
5. RFQ request, draft, issue, invitations, eligibility, respond, expiry job.
6. Contractor pack and drawing access.
7. Quote drafts, submission, versions, withdrawal, expiry job, staff capture, attachments.
8. Clarifications.
9. Review and adjustments.
10. Comparison draft, publication, fpdf2 document.
11. Selection with code and statement; engagement integration; closing effects.
12. Event handlers: `buildplan.accepted` (QD-15), `billing.package_changed` (QD-14), `project.cancelled`, `professional.listing_changed`.
13. Notifications and templates.
14. Functional screens on the three hosts; contracts regenerated.
15. Tests (section X), Playwright on the production build, migration checks, SLICE3_6_IMPLEMENTATION_REPORT.

---

## AB. Final verdict

The sources and earlier decisions settle the shape of 3.6:
- the accepted version as the baseline;
- one standard pack;
- every line priced or excluded;
- immutable quote versions;
- adjustments never shown to contractors;
- a frozen, neutral comparison;
- the homeowner chooses;
- Plan2Build is never a party.

Chirag's decisions of 2026-10-06 (section 0) settle the rest:
- the invitation model (QD-01);
- the RFQ_SELECTION substantial-work trigger (QD-02, a new product decision; N-12 unchanged);
- windows, limits and validity (QD-04 to QD-06);
- privacy (QD-09);
- the deferred recommendation engine (QD-10);
- selection (QD-12);
- package and baseline events (QD-14, QD-15).

H-03 is resolved by ADR-024. No [OPEN] marker remains for a 3.6 decision.

SLICE 3.6 READINESS = READY
