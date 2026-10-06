# Plan2Build: Slice 3.2 readiness (professional registration, approval and free discovery)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/SLICE3_2_READINESS.md` |
| Version | 1.1 (2026-10-05) |
| Status | Decisions confirmed by Chirag on 2026-10-05 (section K0); D-05 stays OPEN. Slice 3.2 built on 2026-10-05 (section M), awaiting Chirag's review. Section K keeps the original recommendations for the record; where they differ, K0 governs |
| Baseline | `PRODUCT_FLOW_RECONCILIATION.md` v2.0 (approved 2026-10-05); PD-01 to PD-27 (IHB_FLOW 32.6); canonical flow IHB_FLOW 34 |
| Sources read | IHB_FLOW 32, 34; PROFESSIONALS_FLOW 6, 7, 8, 9, 10, 11, 42 to 44 (44.8 superseded by PD-18); S01, S02 (D1 verification spine), S03, S05, S10, S13, S14, S23, S24; round 2 client questions (all unanswered); architecture DATA 4.7, STATE_MODEL 3 and 4, API 8, SECURITY, DOMAIN 3.8, EVENT, PERFORMANCE, RECOMMENDATION_ENGINE; the code |
| Markers | **[SOURCE]** a source settles it. **[PD]** Chirag's product decision. **[REC]** Sakha's recommendation, not approved. **[OPEN]** undecided. **[SUPERSEDED]** an older source or design overridden by a PD |

## A. What exists today

| Area | State |
|---|---|
| Professional tables, routes, screens | None |
| Identity | Audience `pro` exists, with the host `pro.localhost` (local) and `professionals.plan2build.in` (design), email OTP sign-in, a session policy (7 days idle, 30 absolute) and its own cookie |
| Self-registration | Off for professionals: setting `self_registration_audiences` holds only `ihb`. An unknown professional email cannot create an account |
| Accounts created by operations | Supported by identity: a user created in PENDING_VERIFICATION becomes ACTIVE on first verified sign-in (used today for staff) |
| Professionals host | One placeholder page (`/` with the foundation shell) |
| Project roles | `project_memberships.role` allows CONTRACTOR and ARCHITECT (unused). Project-level only; no listing meaning |
| Operations | Staff roles OPS and ADMIN with MFA; one queue kind (`REQUIREMENT_REVIEW`) on `ops_queue_items`, with claim, release, resolve |
| Documents | Presigned uploads, ClamAV, EXIF stripping, signed downloads with an access log; purposes REQUIREMENT_UPLOAD and AI_CONCEPT |
| Confirmed absent (code, migrations, dev database) | `club_memberships`, club tiers, club applications, `club_reviews`, `projects.contractor_route`, `projects.path`, `projects.contractor_status`, any professional or verification table |

The architecture documents hold a professional design (DATA 4.7, STATE_MODEL 3, API 8). It is a proposal, partly superseded: the Club parts carry dated "superseded" notes (PD-18), and several downstream parts (leads, RFQ, selections, project states) still assume one contractor per project. Those belong to later slices and are not touched by 3.2.

## B. Source comparison for the 3.2 behaviours

| Behaviour | Status | Evidence |
|---|---|---|
| Only approved, verified professionals are publicly listed | [PD] PD-18, PD-19; [SOURCE] S02 "Discovery eligibility is derived from the verification result" | IHB 32.6; S02 P55, P65 |
| "Champions Club" is the name for the listed set; no membership, tier, purchase, ranking | [PD] PD-18 | IHB 32.6 |
| Club application, curation scorecard, admission, classes by scorecard, six-monthly review | [SUPERSEDED] by PD-18 | PRO 44.8 note; DATA, STATE_MODEL 4, API 8 notes |
| Discovery is free: browse, profiles, expertise, category, relevant information | [PD] PD-19, PD-03 | IHB 32.6 |
| Formal connection, leads, RFQ, quote coordination need the package | [PD] PD-19; not in 3.2 | IHB 32.6 |
| No paid placement, no sold ranking, no commercial influence | [PD] PD-08, PD-18; [SOURCE] S14 "Position is not for sale" | IHB 32.6; S14 l.387 |
| Premium listing tiers, featured listings, growth tiers | [SUPERSEDED] by PD-08, PD-18 | S13 P10, P52; S10 P53 |
| No star ratings; no price sort or filter | [SOURCE] BR-089 unchanged, PBR-038; S05 P184, P185 | IHB 4252; PRO 3151 |
| Ratings and reviews at all | [OPEN] CQ-17 | IHB 32.5 |
| Profile separate from verification; verification as a gated state machine per category | [SOURCE] S01 P67, S02 P65, P90 | |
| Category-specific checks (identity, credentials, business, GST, portfolio, references, site visit, insurance) | [SOURCE] lists exist per category (S01 T5, T10; S02 P71 to P83; S03 T12: contractors two reference calls and a site visit) | PRO 9.4 |
| Which checks are required before listing | [OPEN] F-02 | REC F |
| Suspension per category with a reason; active records kept | [SOURCE] S02 P90, T6.R6, T15.R8 | |
| Expiry, periodic re-verification | [OPEN] no source (PMI-005, PMI-006) | PRO 769 |
| Reapply after rejection | [SOURCE] S02 "may allow re-application based on policy"; timing [OPEN] | S02 T6 |
| Joining routes: invitation, enrolment campaign, website registration | [SOURCE] CD-14 "All three ... available"; CD-07 Plan2Build builds the Raipur list and creates accounts | IHB 32.2 |
| Which routes are live in the POC | [OPEN] CQ-08 (round 2 question 2, unanswered) | |
| Categories to discover | [PD] PD-08: contractor, architect, structural engineer, site/civil engineer, MEP, interior designer, other supported | IHB 32.6 |
| Category codes and subtypes | [SOURCE] S01 four categories; specialist subtypes configurable (S01 §3); "site/civil engineer" has no code anywhere; taxonomy [OPEN] POQ-002 | PRO 6.1 |
| One professional in several categories | [OPEN] POQ-003; [CONFLICT] PC-014 | PRO 3267 |
| Contact details on free profiles | [OPEN] F-01, POQ-019; no source either way | PRO 1879, 4241 |
| Contractor enlistment class | [OPEN] CQ-07 (round 2 question 3); 44.7 class table is a proposal whose assignment depended on the superseded scorecard | IHB 4267; PRO 4271 |
| Professional fees | [OPEN] F-12, POQ-028, POQ-031; [SOURCE] S14 "Listing is free for the contractors we invite"; paid placement [SUPERSEDED] | |
| Family's own contractor: basic verification, project-only, not listed | [SOURCE] CD-27 (kept by PD-18); not part of 3.2 (Slice 3.4, F-03, CQ-23) | |
| Auditors | Not listed or discoverable in any source; retained (CD-21, CQ-15). Not part of 3.2 | |
| Structural engineers | [PD] PD-08 discoverable; PD-24 any qualified engineer may sign. Listing in 3.2 like other categories | |

## C. Professional domain model [REC]

One professional account, one profile, any number of categories. Listing is per category. Nothing links a professional to a project in 3.2.

| Entity | Purpose | Key fields |
|---|---|---|
| `service_categories` (catalog) | The categories and subtypes Plan2Build supports, as data | `code`, `parent_code` (subtypes), `name`, `discoverable`, `sequence`, `active` |
| `listing_requirements` (catalog, versioned) | What a category must pass to be listed (F-02), as data | `category`, `version`, `status` (one ACTIVE), `checks` (list of check kinds with required or optional), `validity_months` (null until decided), `approved_by` |
| `professional_profiles` | The professional's own profile | `user_id` (unique), `display_name`, `firm_name`, `principal_name`, `bio`, `years_experience`, `team_size`, `base_locality` (public text), `base_geom` (private point), `service_radius_km`, public contact fields only as F-01 decides, `version` |
| `professional_categories` | One row per profile and category: the listing state | `profile_id`, `category`, `subtypes`, `listing_state`, `requirement_version`, `listed_at`, `review_due_at` (if F-02 sets validity), `reason`, `reapply_after`, `version`; UNIQUE (`profile_id`, `category`) |
| `verification_cases` | One review of one category (first listing, resubmission, later re-check) | `professional_category_id`, `state`, `submitted_at`, `reviewer_id`, `decided_at`, `decision`, `reason`; at most one open case per category (partial UNIQUE) |
| `verification_checks` | Each check's result, including reference calls and site visits as structured details | `case_id`, `kind` (IDENTITY, PROFESSIONAL_REGISTRATION, BUSINESS, PORTFOLIO, REFERENCE, SITE_VISIT, INSURANCE), `outcome` (PASSED, FAILED, NOT_APPLICABLE), `detail` jsonb, `recorded_by`, `recorded_at`; append-only |
| `verification_evidence` | Documents the professional supplies for a case | `case_id`, `kind`, `file_id` (documents purpose VERIFICATION_EVIDENCE, private); locked once submitted |
| `portfolio_items` | Work shown on the public profile | `profile_id`, `category`, `file_id` (purpose PORTFOLIO), `caption`, `review_state` (PENDING, APPROVED, REJECTED); only APPROVED items are public |
| Service area | Base point and radius in the POC | On the profile; polygons later if needed (`service_areas` in DATA 4.7 is kept for that) |
| Availability or capacity | Not needed for free discovery | Deferred (`contractor_capacity` in DATA 4.7 stays for the lead slice) |

Not built: `club_memberships`, club tiers, club applications, `club_reviews`, `listing_entries` (the directory queries `professional_categories` with indexes first; a projection is added only if measured load needs it), `projects.contractor_route`, `projects.path`, contractor class columns (until CQ-07).

**Modularity.** The future link is Project → service need (category) → engagement → professional category row. 3.2 builds only the right-hand side: listing is keyed by (professional, category), so a later engagement points to `professional_categories`, and a project can mix a Plan2Build contractor, an outside architect and a Plan2Build structural engineer without a project-level contractor field. The existing project roles CONTRACTOR and ARCHITECT are left alone; the engagement slice decides how they map.

**Resolved conflict.** STATE_MODEL 4 called LISTED "never stored, always computed" from membership, verification and capacity. Membership is gone (PD-18) and capacity is not a discovery concern, so listing state is stored on `professional_categories` and changed only by the review decisions below [REC].

## D. Champions Club

Champions Club = the brand name for the approved public professional ecosystem: every professional category row in LISTED is shown as a Champions Club professional. It is a display label computed from `listing_state = LISTED`. There is no membership entity, application, tier, fee, review cycle or ranking attached to it, and there are no public non-Champion professionals because only LISTED rows are public. [PD-18]

## E. Verification and listing model

**States per professional category** [REC; names from PD-18 and REC D, DRAFT from S01 and S02]:

```
DRAFT ──submit──▶ PENDING_REVIEW ──request changes──▶ CHANGES_REQUESTED ──resubmit──▶ PENDING_REVIEW
PENDING_REVIEW ──approve──▶ LISTED            PENDING_REVIEW ──reject──▶ REJECTED
LISTED ──suspend──▶ SUSPENDED ──reinstate──▶ LISTED
REJECTED ──reapply (after the waiting time, OPEN)──▶ PENDING_REVIEW
```

DRAFT is justified by S01 and S02 (both start at Draft): the professional fills the profile and uploads evidence before anything reaches operations. Two transitions depend on open decisions and are not built until decided: expiry (LISTED → PENDING_REVIEW on `review_due_at`, if F-02 sets validity) and the professional withdrawing a listing (LISTED → DRAFT or a WITHDRAWN state; no source).

| Question | Answer |
|---|---|
| Who verifies | Operations staff (OPS role), claiming the case from a new queue kind `PROFESSIONAL_REVIEW` on the existing `ops_queue_items` [SOURCE S01 T39, S02 T13; REC for the queue reuse] |
| Decisions | Request changes, approve (to LISTED), reject: each with a reason where it is not an approval, fresh MFA, an audit row and a status history [SOURCE S02 T13 "Reviewer, timestamp, reason, evidence set"; REC MFA, matching the review decisions] |
| Evidence stored | Uploaded documents (private, P3, scanned), check results with details (who was called, when, outcome; site visit date and checklist), reviewer and time [SOURCE S01 T40, S03, S05] |
| Category-specific checks | Defined per category in `listing_requirements` (data, versioned). Which checks: F-02 [OPEN] |
| Expiry | [OPEN] F-02. No source defines it |
| Re-verification | A new verification case on the same category row; while open, the listing state stays as decided by F-02 (stay LISTED or hide) [OPEN] |
| Suspend and reinstate | Per category, reason required, active records kept [SOURCE S02 P90]. Who: STATE_MODEL 3 says Admin; S01 says admin or operations. [REC] OPS with MFA suspends and reinstates; ADMIN can too |
| Reject and reapply | Reason required; reapply waiting time [OPEN] (F-02) |
| Account-level suspension | Existing user status SUSPENDED hides every category (identity already has it) |

## F. Public discovery (free)

| Free in 3.2 | Detail |
|---|---|
| Browse | LISTED professional categories only |
| Filter | Category and subtype; location (a locality, or near a point with a radius, matched against each professional's service area); text search on display and firm names. No price, budget or rating filter or sort (BR-089) |
| Order | No paid or rank order. [OPEN] D-08: alphabetical, or a stable daily shuffle |
| View profile | The fields F-01 allows, approved portfolio items, approved categories and subtypes, service area (locality and radius, never the base address or point), years of experience, the Champions Club label and "Verified by Plan2Build" with the categories it covers |
| From a project | The dashboard's Professionals area opens the directory pre-filtered by the project's locality and, if the family answered it, the `services_needed` categories [REC] |

Not in 3.2: connection, leads, Request quote, RFQ, quote coordination, comparison, messaging, recommendations, shortlists, ratings, reviews, prices, availability.

## G. Security and privacy

| Data | Who sees it |
|---|---|
| Verification documents and check details (references' names and phones, site visit address) | Operations (OPS) through logged, short-lived signed links; the professional sees their own uploads. Never public, never in analytics, never sent to any AI service [SOURCE DATA privacy classes P2, P3; SECURITY] |
| Profile fields | The professional edits their own; public sees only the F-01 fields of LISTED categories |
| Base location | Private point; public sees locality text and radius only |
| Portfolio | Professional uploads; public only after operations approve each item; EXIF stripped (existing pipeline) |
| Contact details | Exactly as F-01 decides |
| Reviewer notes and reasons | Operations; the professional sees the reason given with a decision (changes requested, rejected, suspended), never internal notes |

Access control: professional routes on the professionals host for the `pro` audience, own profile only (404 otherwise); operations routes on the admin host for OPS with MFA; public directory routes need no sign-in (or the homeowner session, per decision D-09) and return LISTED data only. Every state change writes an audit row and a history row; every document link is logged; rate limits on registration and uploads. Professional terms and consent for storing verification documents are a legal launch gate (D-17), not a build blocker.

## H. API proposal (not implemented)

| Route | Actor | Purpose |
|---|---|---|
| `GET /public/professional-categories` | public | Discoverable categories and subtypes |
| `GET /public/professionals` | public (or homeowner, D-09) | LISTED directory with filters, cursor pages |
| `GET /public/professionals/{public_id}` | public (or homeowner) | One public profile |
| `GET`, `PUT /pro/profile` | professional | Own profile (draft fields editable; changes to a LISTED category's verified fields reopen review per F-02) |
| `POST /pro/categories`, `GET /pro/categories` | professional | Add a category, see listing states and reasons |
| `POST /pro/uploads`, `POST /pro/uploads/{id}/complete` | professional | Evidence and portfolio files (existing pipeline, new purposes) |
| `POST /pro/categories/{code}/submit` | professional | Submit or resubmit for review; Idempotency-Key |
| `POST /ops/professionals` | OPS | Create an account and draft profile on a professional's behalf (only if CQ-08 includes it) |
| `GET /ops/queues/professional-review` | OPS with MFA | Queue (existing queue machinery) |
| `GET /ops/professionals/{id}` | OPS with MFA | Profile, categories, cases, evidence list, checks, history |
| `GET /ops/files/{id}/url` | OPS with MFA | Extended to verification evidence and portfolio, logged |
| `POST /ops/verification-cases/{id}/checks` | OPS with MFA | Record a check result |
| `POST /ops/verification-cases/{id}/request-changes`, `/approve`, `/reject` | OPS with MFA | Decisions with reason; Idempotency-Key |
| `POST /ops/professional-categories/{id}/suspend`, `/reinstate` | OPS with MFA | With reason |
| `POST /ops/portfolio-items/{id}/approve`, `/reject` | OPS with MFA | Portfolio review |

## I. Frontend routes

| Host | Route | Screen |
|---|---|---|
| Professionals | `/sign-in` | Email code sign-in (existing component) |
| Professionals | `/register` | Only if CQ-08 includes self-registration |
| Professionals | `/profile` | Profile form |
| Professionals | `/profile/categories` | Categories, subtypes, evidence uploads, submit |
| Professionals | `/profile/portfolio` | Portfolio items and their review state |
| Professionals | `/verification` | Listing state per category, reasons, requested changes |
| Homeowner | `/professionals` | Directory (also reachable from the project dashboard's Professionals area) |
| Homeowner | `/professionals/{id}` | Public profile |
| Operations | `/professionals/queue` | Review queue |
| Operations | `/professionals/{id}` | Verification detail: evidence, checks, decisions, suspension, portfolio review |

No screen for connection, Request quote or any package-gated service.

## J. Database impact

New, in the catalog module: `service_categories`, `listing_requirements` (versioned). New professionals module: `professional_profiles`, `professional_categories`, `verification_cases`, `verification_checks` (append-only), `verification_evidence`, `portfolio_items`. Extended: `file_objects.purpose` (VERIFICATION_EVIDENCE, PORTFOLIO); `ops_queue_items.kind` (PROFESSIONAL_REVIEW). Public portfolio images need a decision on serving: signed links like AI concepts, or a public bucket for approved items only (an R2 launch gate either way).

Explicitly not created: `club_memberships`, `club_tiers`, `club_applications`, `club_reviews`, `projects.contractor_route`, `projects.path`, any project-to-contractor column.

## K0. Confirmed decisions (Chirag, 2026-10-05)

These are product decisions for Slice 3.2, not recommendations.

| ID | Decision |
|---|---|
| D-01 | Public profile shows: professional name; firm or business name; categories; service area; experience; team size where applicable; bio; approved portfolio; relevant registration and verification information; the "Champions Club" label. Not shown: phone, email, website. Formal contact stays a package service |
| D-02 | Configurable, category-specific checklist stored as versioned data. Initial POC defaults (not permanent legal rules): Contractor: identity, business details with GST where applicable, portfolio, 2 references, site verification. Architect: identity, applicable professional registration or credential, portfolio. Structural engineer: identity, applicable registration or credential, portfolio and/or references. Site/civil engineer: same as structural engineer. MEP: identity, relevant qualification or licence where applicable, portfolio and/or references. Interior designer: identity, portfolio, reference. Specialist: identity, portfolio, relevant licence or credential where applicable, reference where appropriate. No universal registration body is hard-coded. Re-verification target every 12 months; rejected professionals may reapply after 6 months; both configurable |
| D-03 | No professional-side fees in the POC: no listing, registration, lead, commission, subscription, premium placement or paid ranking fee. A POC rule; may change by a later commercial decision |
| D-04 | Both self-registration and operations-created or operations-invited accounts; both enter the same workflow: DRAFT → PENDING_REVIEW ↔ CHANGES_REQUESTED → LISTED or REJECTED; LISTED ↔ SUSPENDED. Self-registration never makes anyone public; only approval makes a category LISTED |
| D-05 | OPEN. No contractor enlistment class in Slice 3.2: no fields, no rules |
| D-06 | Categories: Contractor, Architect, Structural Engineer, Site/Civil Engineer, MEP, Interior Designer, Specialist. Specialist subtypes configurable. Several categories per professional. Approval and listing per professional and category |
| Terminology | "Champions Club" is the Plan2Build brand name for the approved public professional ecosystem: not a membership, tier, subscription, paid program, ranking or a qualification separate from approval. Internal concepts: Professional, Professional Category, Verification, Listing Status. No club tables |
| D-07 | No ratings or reviews in the POC |
| D-08 | Neutral daily shuffle for general order: never paid, sponsored, alphabetical, price-first or commercially influenced; not described as a recommendation. Project-aware filters may narrow, never rank |
| D-09 | The directory is public: anyone can browse, view public profiles and filter on public information; signed-in homeowners also get project-aware filters. No package and no login needed to browse |
| D-10 | OPS and ADMIN may suspend and reinstate a category listing, with authorisation, reason, audit and MFA as the privileged-action pattern requires. Suspended is not rejected: the professional stays in the system, not listed until reinstated |
| D-11 | A listed professional may hide their own listing and show it again: reversible, audited, distinct from SUSPENDED and REJECTED, no loss of verification history; showing again restores the approval state unless re-verification is required |
| Model | Professional → Professional Category → Verification and Evidence → Listing State; later Project → Service Need → Engagement → Professional. No `project.contractor_route`, `project.path`, `project.contractor_status`; no single global professional route |
| Privacy | Public and homeowners never see verification documents, internal notes, reviewer identity, rejection reasons, internal evidence or moderation notes. Professionals see only their own verification data. OPS and ADMIN see evidence per permissions. Every verification, suspension and reinstatement decision is audited |

## K. Decisions required (original recommendations, superseded by K0)

Each: source evidence, recommendation, reason, product and technical consequence. None is selected.

| ID | Decision | Evidence | Recommendation | Reason | Consequence |
|---|---|---|---|---|---|
| D-01 (F-01) | Which fields a free public profile shows, including phone, email and website | No source either way (POQ-019); S24 cards show no contact details; PD-19 "relevant information" | Show display name, firm, categories and subtypes, locality and service radius, years of experience, team size, bio, approved portfolio, the Champions Club label and what Plan2Build verified. Do not show phone, email or website | Contact through Plan2Build is the package service (PD-19); public contact details let the free directory replace it | Product: homeowners contact professionals through the package. Technical: no contact columns are public; the field list is data on the profile view |
| D-02 (F-02) | What each category must pass to be listed; whether listings expire and when they are re-checked; reapply waiting time | S01 T5, T10; S02 P71 to P83; S03 (contractors: two references and a site visit); expiry: no source | Contractor: identity, business (GST where registered), portfolio, two reference calls, a site visit. Architect: identity, Council of Architecture registration (Sakha's addition: the sources say only "professional registration where applicable"; Indian law reserves the title "architect" for registered architects), portfolio. Structural engineer and site/civil engineer: identity, professional registration or degree, portfolio or references. Interior designer and specialists (including MEP): identity, portfolio, one reference; licence where the trade needs one. Re-check every 12 months; reapply 6 months after rejection | Uses only checks the sources name; matches what S03 planned for contractors | Product: sets the quality bar and operations workload. Technical: stored as `listing_requirements` data, versioned, so changes need no code |
| D-03 (F-12) | Do professionals pay anything in the POC | S14 "Listing is free for the contractors we invite"; S13, S10 fee ideas (paid placement parts superseded); POQ-028, POQ-031 | No fees of any kind in the POC | Recruitment of a first Raipur list is easier free; avoids billing for professionals in 3.3 | Product: no revenue from professionals in the POC. Technical: nothing to build; if fees come later they must never touch listing or order (PD-08) |
| D-04 (CQ-08) | Which onboarding routes are live in the POC | CD-14 all three routes "available"; CD-07 Plan2Build builds the list and creates accounts; round 2 Q2 unanswered | Two routes: operations create the account and draft profile for invited professionals (CD-07), and self-registration on the professionals host. Both go through the same review before listing. Project invitation of the family's own contractor stays in Slice 3.4; campaign import later | CD-07 is explicit for the POC; self-registration is cheap once review exists and CD-14 says it is available | Product: anyone can apply, only reviewed ones are listed. Technical: switch `self_registration_audiences` to include `pro`; one ops "create professional" route |
| D-05 (CQ-07) | What sets a contractor's enlistment class | Round 2 Q3 unanswered; 44.7 class table is a proposal tied to the superseded scorecard | Keep CQ-07 open and leave class out of 3.2; add it with the lead slice | Free discovery does not need a class; class only gates leads and RFQ invitations (later, package-gated) | Product: directory shows no class. Technical: no class column now; later a versioned rule table and a reviewed value per contractor category |
| D-06 | The POC category list, codes and subtypes; may one professional hold several categories | PD-08 list; S01 four categories; specialist subtypes configurable (S01 §3); "site/civil engineer" has no code; POQ-002, POQ-003 | Categories: Contractor, Architect, Structural engineer, Site/civil engineer, MEP, Interior designer, Specialist (subtypes configurable: waterproofing, solar, landscaping, fabrication, painting). Several categories per professional allowed, each reviewed and listed separately | Follows PD-08 literally; per-category listing already supports several | Product: one firm can be listed as contractor and interior designer separately. Technical: categories are rows in `service_categories`, no code change to add one |
| D-07 (CQ-17) | Ratings and reviews in the POC directory | BR-089 no star ratings (unchanged); D3 mockups show them; CQ-17 not asked | None in the POC | BR-089 stands; ratings need verified engagements that do not exist yet | Product: profiles show verification, not stars. Technical: nothing to build |
| D-08 | Directory order (no source) | BR-089, PD-08 forbid paid or rank order | A stable daily shuffle within the filtered set | Alphabetical order favours names starting with A; a daily shuffle is neutral and still stable while paging | Product: no position can be gamed or bought. Technical: order by a hash of profile id and date |
| D-09 | Is the directory public (no sign-in) or for signed-in homeowners only | CD-22 "contractor listing is part of POC" (public website); PD-19 free discovery | Public on the homeowner host, with project-aware filters when signed in | Matches the website listing in CD-22 and the free top-of-funnel model | Product: discoverable by search engines. Technical: cache-friendly read routes; rate limits on the public API |
| D-10 | Who may suspend and reinstate a listing | STATE_MODEL 3 says Admin; S01 says admin or operations | OPS with fresh MFA, with a reason; ADMIN also | Operations run the review; MFA and audit cover abuse | Product: faster response to problems. Technical: same decision pattern as requirement review |
| D-11 | Can a professional hide their own listing | No source | Yes: withdraw a category (back to DRAFT), audited | A professional's control over their own public presence | Product: a busy professional can step back. Technical: one more transition |

Also open but outside 3.2: F-03 (outside professionals on a project), CQ-23 (own contractor failing verification), CQ-15 and AQ-06 (auditors), F-04 (outside structural engineer's sign-off), POQ-051 (audit data on public profiles).

## L. Verdict and order

**Verdict (1.1): READY.** Decisions confirmed in K0; D-05 stays OPEN and out of scope. Original verdict (1.0): READY WITH DECISIONS. D-01, D-02, D-04 and D-06 block coding. D-03, D-07, D-08, D-09, D-10 and D-11 are quick confirmations. D-05 (CQ-07) does not block 3.2 if class is left out, as recommended.

**Implementation order after approval:**

1. Catalog: `service_categories` and versioned `listing_requirements`, seeded from D-02 and D-06.
2. Professionals module: profiles, category rows with the listing state machine, verification cases, checks, evidence, portfolio items; migration with up, down, up.
3. Professional onboarding on the professionals host per D-04: sign-in, profile, categories, uploads with the new purposes, submit and resubmit, verification status page; operations "create professional" if chosen.
4. Operations review: queue kind PROFESSIONAL_REVIEW, detail page, check recording, decisions with MFA, suspension and reinstatement, portfolio review, draft notification emails to the professional.
5. Public directory: API, `/professionals` and `/professionals/{id}`, the dashboard Professionals area with project-aware filters, order per D-08.
6. Tests (API, unit, Playwright phone and desktop with axe, privacy of evidence, only LISTED visible, no paid or rank order), docs, report.

No code was changed in this pass.

## M. Build result (2026-10-05)

Built as K0 says; run results in FOUNDATION_PLAN.md section 4h, tables in DATA_ARCHITECTURE.md (migration 0010), routes in API_ARCHITECTURE.md section 22.

Differs from this document's plan:

| Item | Plan | Built | Why |
|---|---|---|---|
| Notification emails to the professional (L step 4) | Draft emails on decisions | Not built; decisions and messages show on the professional's dashboard | Email wording is content Chirag has not approved |
| Project-aware filter | Project needs and location | Location only (plot inside the service radius) | Mapping the requirement's services to categories would be an invented rule |
| Storage CORS (launch gate S-01) | "PUT from the homeowner host only" | Local storage now allows the homeowner and professionals hosts; the production R2 rule needs the same two origins | Professionals upload evidence and portfolio photos (K0, D-02) |
| Portfolio images | Public bucket (DATA 6) | Signed inline links from the private bucket | No public bucket exists before the R2 launch gate; the nonce CSP (S-01) must also allow these images on the homeowner host |

Open and undecided (not built): automatic hiding of listings past their re-verification date; operations correcting a locked name or firm; a professional-account suspension separate from category suspension; D-05.
