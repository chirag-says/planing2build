# Plan2Build: Slice 2 readiness (operations review, acceptance, workspace creation)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/SLICE2_READINESS.md` |
| Version | 1.1 (2026-10-04) |
| Status | Decisions 2.1 to 2.10 ruled by Chirag (section 5); review to workspace flow built and tested (FOUNDATION_PLAN 4e). Production launch gates remain (section 5.2) |
| Sources read | `STATE_MODEL.md` sections 1, 5, 6, 7; `DATA_ARCHITECTURE.md` 4.2 to 4.5, 4.11, 4.14, 4.16; `API_ARCHITECTURE.md` sections 4, 18, 19, 22; `SECURITY_ARCHITECTURE.md` 3.3, 4.1, 4.2; `EVENT_AND_BACKGROUND_JOB_ARCHITECTURE.md` (event map); `IHB_FLOW.md` 8.9 (J08), 8.11, EC-003, AMB-067, AMB-068, OQ-052, C-064, C-065; S04 `Plan2Build_Specification_Schema.docx` (tables 4 to 10, read on 2026-10-04); baseline v1.2; FOUNDATION_PLAN v1.2; the code |
| Labels | BLOCKING BEFORE SLICE 2: stops the named part. NON-BLOCKING: Slice 2 can be built; needed later. IMPLEMENTABLE WITH EXISTING DECISIONS: sources and rulings settle it. DEFERRED: outside Slice 2. "Recommendation" marks Sakha's advice, never a fact |

## 1. What the sources already settle

| Topic | Settled by | Classification |
|---|---|---|
| Review outcomes for a submission | STATE_MODEL 5: `SUBMITTED → NEEDS_INFO` (operations, reason); `NEEDS_INFO → SUBMITTED` (homeowner, answers); `SUBMITTED → ACCEPTED` (operations; "review done; workspace instantiation succeeds"). No "under review" state: SUBMITTED means "under Plan2Build review". No "reject" state | IMPLEMENTABLE WITH EXISTING DECISIONS (except the gaps in 2.1 and 2.7) |
| Transition mechanics | STATE_MODEL 1: transition table in code; 409 `STATE_CONFLICT`; one audit row per transition in the same transaction; `version` on every write | IMPLEMENTABLE (framework exists since Slice 1) |
| Staff audiences and roles | SECURITY 4.1 lists the actor sets "ops" and "admin"; 4.2: admin endpoints under `/admin`, ops session with ADMIN role and MFA, admin host only; "no self-registration as ops"; API 18 assigns each endpoint to ops or admin | IMPLEMENTABLE: two global staff roles, `OPS` and `ADMIN`, held per user; project roles `OPS_ADVISOR` and `OPS_FIELD` stay in `project_memberships` |
| Staff-role table (gap G-01) | DATA had no table; FOUNDATION_PLAN G-01 recommended `staff_roles (user_id, role, granted_by, granted_at, revoked_at)` | IMPLEMENTABLE: a storage design for roles the sources define. Built (section 4) |
| MFA | SECURITY 3.3: TOTP (RFC 6238, 30 s, one step of drift), secret encrypted with the application key, ten recovery codes hashed with argon2id and single use, enrolment required at first login on the admin host; session `mfa_verified_at`, re-verification every 8 hours and before approvals and overrides; session id rotated on MFA verify; DATA `mfa_secrets` | IMPLEMENTABLE. Built |
| Who sees what in operations | API 18: ops reads every project ("read-only composites; writes go through module endpoints"); SECURITY 4.2: operations cannot edit business data directly; admin-only account administration | IMPLEMENTABLE. Built for the review queue and submission detail |
| Review queue | DATA `ops_queue_items` (kind, ref, state, priority, claim); EVENT map: `requirement.submitted` creates an ops queue item; API 18 `GET /ops/queues/{kind}` with claim and resolve | IMPLEMENTABLE. Built (ordering: oldest submission first, as the sources set no priority) |
| Stage instances | IHB_FLOW 8.9 and S04 section 4: 16 stages; stages 5, 6 and 9 repeat once per floor (S05 F1: "a G+2 project creates the correct repeated instances of stages 5, 6 and 9, one set per floor"); STATE_MODEL 6: initial state NOT_STARTED; gate status NOT_INSPECTED; DATA `stage_instances` | IMPLEMENTABLE for floors G to G+3; basement open (2.2) |
| Planned dates and durations | D-04 ruling: no invented durations; NULL means "Schedule to be confirmed"; planned dates only from an approved configuration or an operations-entered schedule. Stage master v1 has NULL durations and cost shares | IMPLEMENTABLE: stage instances are created with NULL planned dates; STATE_MODEL 6's "instantiated with planned dates" yields to the later ruling |
| Specification line instances | STATE_MODEL 7: every line instantiated SPECIFIED; S04 section 10 and S05 F1: issued text stored on the instance, code immutable, master changes never alter issued instances; S04 tables 5 to 7 give all 67 lines (code, item, performance specification, consuming stage, decide-by weeks, verified at, brand category); D-03 ruling drops the brand category from A04, A05, A09, A12, A13 | Mostly IMPLEMENTABLE; blocked by 2.3, 2.4 and 2.5 |
| Decision deadlines | S04: "decide by" is weeks before the consuming stage begins; with no planned dates (D-04) the deadline is empty until a schedule exists | IMPLEMENTABLE (deadline NULL) |
| Long-lead flags | S04 section 8 table: C19, C21 (10 weeks); C16, C17, C18, C20, C22, B07 (8 weeks); B14 (6 weeks) | IMPLEMENTABLE |

## 2. Decisions required

### 2.1 A third review outcome: may operations close a submission?

| Item | Content |
|---|---|
| Classification | BLOCKING BEFORE SLICE 2 for a "decline" action only; accept and ask-for-information do not depend on it |
| Source | STATE_MODEL 5 has no reject state. It allows `DRAFT to BUILDING → CANCELLED` by "homeowner or operations" with a reason (refunds per CQ-04, not relevant before payment). R-4 and R-8 route "Other" property types and started construction to operations review without saying what happens if the project does not fit |
| Why it matters | Without a ruling, a submission that Plan2Build cannot take stays SUBMITTED for ever, or the team invents a rule |
| Decision required | (a) Operations may cancel a SUBMITTED or NEEDS_INFO project with a reason, using the canonical CANCELLED state; (b) no decline at all in the POC; and in either case whether the homeowner sees the reason text |
| Recommendation | (a), with the reason chosen from a short list Chirag approves plus free text, the homeowner shown the reason, and the project kept read-only. No new state |

### 2.2 Basement and the per-floor stages

| Item | Content |
|---|---|
| Classification | BLOCKING BEFORE SLICE 2 for workspace creation of projects with a basement (R-6 asks "Will the house have a basement?") |
| Source | S04 section 4 and S05 F1: stages 5, 6 and 9 repeat "per floor"; EC-003 counts floors above ground; nothing says whether a basement is a floor for these stages |
| Decision required | Does a basement add one instance of stages 5, 6 and 9 (and therefore one more Gate 3 slab inspection and Gate 4)? |
| Recommendation | Yes: a basement has its own columns, slab and services, so it is one more floor for stages 5, 6 and 9, listed first and labelled "Basement". Floors G to G+3 then give 1 to 4 sets, plus one for a basement |

### 2.3 One specification line per project, or per floor, for lines at stages 5, 6 and 9

| Item | Content |
|---|---|
| Classification | BLOCKING BEFORE SLICE 2 for specification-line instantiation |
| Source | AMB-067 and OQ-052 leave it open. DATA 4.5 designs one line per project (UNIQUE `project_id, code`, one `consuming_stage_instance_id`). Affected lines in S04: A12 (5), A13, A14, A15, A20 (6), A16 ("5, 6"), and B01 to B04, B06, B08 to B14, B22 (9) |
| Decision required | One instance per project, or one per floor for those lines |
| Recommendation | One per project, as DATA designs it: the family makes each decision once (concrete grade by floor is already inside A12's text, "Grade by floor"); the line links to the first instance of its consuming stage; verification records may cite any floor's gate. Per floor would multiply OTP acknowledgements without a source asking for it |

### 2.4 A01 (soil investigation): structural or not

| Item | Content |
|---|---|
| Classification | BLOCKING BEFORE SLICE 2 for the 67-line master seed |
| Source | S04 table 5 marks A01 with † (structural) and gives it the brand category "Testing lab". S04 rule R9: "No participation revenue on A02, A04, A05, A09, A12, A13, A19 or any line marked †", which by its last words covers A01. The 2026-10-04 ruling dropped the brand category from A04, A05, A09, A12, A13 only. DATA's CHECK forbids a brand category on a structural line |
| Decision required | (a) A01 is structural and its brand category is dropped like the other five; or (b) A01 is not structural and keeps "Testing lab" (it may then receive qualifying options) |
| Recommendation | (a): S04 marks it †, R9's "any line marked †" includes it, and a soil report is life-safety input for the foundation design (A02). The structural set becomes A01, A02, A04, A05, A09, A12, A13, A19 |

### 2.5 Who approves the specification masters before the first workspace

| Item | Content |
|---|---|
| Classification | BLOCKING BEFORE SLICE 2 for specification-line instantiation |
| Source | DATA `spec_line_master_versions.approved_by_user_id` ("structural engineer for structural lines"); API 18: "structural masters require the engineer's sign-off record"; SECURITY 3.3: the engineer's sign-off needs MFA. No engineer account or sign-off flow exists, and Slice 2 would have to seed version 1 from S04 |
| Decision required | (a) Version 1 of all 67 masters is seeded from S04 with Chirag's recorded approval, the structural lines marked "engineer sign-off pending" and re-issued as version 2 once a registered structural engineer signs; or (b) no workspace is created until an engineer signs the structural masters (needs the engineer's account and sign-off flow first, which belongs to the professionals module) |
| Recommendation | (a), because the S04 text on structural lines is a criteria template ("Grade, exposure class, slump range"), not a project value, and project values are written in the Build Plan later; the pending sign-off is shown to operations, never hidden |

### 2.6 What the homeowner sees in the new workspace

| Item | Content |
|---|---|
| Classification | BLOCKING BEFORE SLICE 2 for the homeowner workspace screen |
| Source | AMB-068: whether SPECIFIED lines of packages the family has not bought are visible is not stated. At ACCEPTED no package is bought (ACCEPTED → PLANNING happens on payment). S04 sells the specifications as packages A, B, C. J08 lists a full workspace (Build Plan dashboard, BOQ, calendar), most of which belongs to later slices |
| Decision required | At ACCEPTED, does the homeowner see (a) the project summary and the 16 stages with "Schedule to be confirmed"; (b) that plus the list of decisions (item names only) by package; or (c) that plus each line's performance specification |
| Recommendation | (b): the stages and the decision names show the family what the workspace will hold, while the performance specifications, which are the paid content, appear when the package is issued |

### 2.7 What the homeowner can change after "Needs information"

| Item | Content |
|---|---|
| Classification | NON-BLOCKING for the foundation; blocks the ask-for-information action, because without it NEEDS_INFO would be a dead end |
| Source | STATE_MODEL 5: `NEEDS_INFO → SUBMITTED`, "Resubmit", homeowner, "Answers". API 4: `POST /projects/{id}/requirement/respond` with answers. Which answers may change is not stated |
| Decision required | (a) The whole requirement reopens for editing, with the operations message shown above it; or (b) only the questions operations mark |
| Recommendation | (a): one rule, the same validated form, and the message tells the family what to change. Files can be added; earlier files stay |

### 2.8 Notifications to operations and to the homeowner

| Item | Content |
|---|---|
| Classification | NON-BLOCKING for Slice 2 build; needed before Handover 1 acceptance |
| Source | EVENT map: `requirement.submitted` → ops queue item and an email confirmation to the homeowner; `enquiry.created` → ops queue item; review outcomes notify the homeowner (STATE_MODEL side effects). The notifications module and templates do not exist; no operations mailbox is named |
| Decision required | The operations mailbox address for new submissions and enquiries (or "console only"), and approval of the wording of four short transactional emails: submission received, more information needed, accepted, closed |
| Recommendation | The console queue is the record; one email per new submission and enquiry to a configured operations address; Sakha drafts the four emails for Chirag's approval as plain transactional text |

### 2.9 Stage master configuration values and their approver

| Item | Content |
|---|---|
| Classification | NON-BLOCKING for Slice 2 (stages are created without dates); blocks schedules and the decisions calendar |
| Source | D-04 ruling; API 18: catalog versions by "admin with MFA" |
| Decision required | The durations and cost shares (not invented here), and who on the team may approve a configuration version |
| Recommendation | Values from Plan2Build's engineer; approval by an ADMIN with MFA, recorded on the version |

### 2.10 Production prerequisites (unchanged from the baseline)

| ID | Item | Classification |
|---|---|---|
| S-01 | R2 bucket and its CORS rule (PUT from the homeowner host only), ClamAV on the VPS (about 1.5 GB of memory), nonce-based CSP naming the storage endpoint and the map tile host | NON-BLOCKING for Slice 2; BLOCKING for production |
| M-01, M-02 | Map tile provider and reverse geocoder for production | NON-BLOCKING for Slice 2; BLOCKING for production |
| D-17 | Privacy notice and terms versions for `consents`; grievance contact (AQ-24); consent text on the capture paths (O-4) | NON-BLOCKING for Slice 2; BLOCKING for production self-registration |
| D-16 | Production rate card (values, approver, shape) | NON-BLOCKING; production serves no estimate until then |
| D-12, D-13 | Repository owner and deploy approver (AQ-29), secrets owner (AQ-09), account ownership (AQ-35), Supabase Pro, Resend domain, penetration test, restore drill | NON-BLOCKING for Slice 2 build; BLOCKING for staging and production |
| W-01 | Website content from the client | NON-BLOCKING for Slice 2 |

### 2.11 Deferred (outside Slice 2)

Payment milestones on stage instances (money module); household members and their permissions (OQ-027); editing project facts after acceptance; who changes stage dates; admin catalog publishing screens; MFA reset by an admin; per-project operations assignment (`OPS_ADVISOR`, `OPS_FIELD`); the exception feed.

## 3. Readiness by part

| Part | Status |
|---|---|
| Staff roles, staff sign-in, MFA, operations shell | Unblocked. Built |
| Review queue, claim and release, submission detail with flags, files and contact | Unblocked. Built (read-only review) |
| Ask for information | Built (ruling 2.7) |
| Decline | Built as cancel with a reason (ruling 2.1) |
| Accept with workspace creation | Built (rulings 2.2 to 2.5, 2.9) |
| Homeowner workspace view | Built (ruling 2.6) |
| Notifications | Built: events, jobs and draft templates (ruling 2.8); template wording not approved |

## 4. Foundation built on 2026-10-04

See `FOUNDATION_PLAN.md` section 4d for the full record. In short: staff roles, staff sign-in, TOTP MFA with recovery codes, the review queue fed by `requirement.submitted`, claim and release, the read-only submission detail with flags, contact and logged downloads, and the operations screens. 313 API tests, 30 unit tests and 36 Playwright tests (phone and desktop, axe on every screen) pass.

Verified in particular: a homeowner cannot reach any operations route (404 on the homeowner host; a homeowner session replayed on the admin host is 401); an operations account without a role is 403; OPS cannot open admin routes and ADMIN cannot open review routes (403); review routes refuse a session without MFA, or with MFA older than 8 hours (403 `MFA_REQUIRED`); a TOTP code works once; recovery codes work once; guessing is rate limited and recorded; MFA rotates the session id without extending its absolute lifetime; a submission enters the queue once however often the event is delivered; claims are one person at a time and audited; homeowner responses still carry no review flags; project isolation tests still pass.

Not verifiable yet, because the decision behind it is open: that acceptance creates exactly the intended workspace and that a repeated acceptance creates no second one (2.2 to 2.5).

## 5. Chirag's rulings (2026-10-04) and what was built

### 5.1 Rulings

| Decision | Ruling | Built as |
|---|---|---|
| 2.1 Decline | Use CANCELLED; no REJECTED. Reason required; actor and time recorded; audited. The family sees the reason, never internal notes or flags. Idempotent. A cancelled project cannot be accepted; no reactivation | `SUBMITTED → CANCELLED` and `NEEDS_INFO → CANCELLED`, reason in status history and audit; repeat cancel is a no-op; accept of a cancelled project is 409 |
| 2.2 Basement | A basement adds one instance of each per-floor stage (5, 6, 9), labelled "Basement" | Floors: basement (if any), ground, then each upper floor. G+1 with basement: 13 + 3 × 3 = 22 instances |
| 2.3 Spec lines | One line per project; no per-floor copies | `UNIQUE (project_id, code)`; 67 lines per project |
| 2.4 A01 | Structural. "Testing lab" removed with no replacement. Every structural line carries engineer sign-off pending. No sign-off details invented | A01 is † in the seed; brand category NULL on all eight structural lines; `engineer_signoff` PENDING, shown as "Engineer sign-off pending" |
| 2.5 Seed | S04 is the authoritative v1 seed for the 67 masters; fields and semantics preserved; versioned, reproducible, tested | Extractor plus `--check`; master version 1 ACTIVE; tests compare the JSON with S04 and the database with the JSON |
| 2.6 Workspace | Accept creates it once. Summary, 16 stages with names, status, "Schedule to be confirmed". Line names by package; performance specifications hidden until the package is purchased | As ruled. No package can be purchased yet (billing is not built), so every specification is withheld |
| 2.7 Needs information | Existing state; message stored and shown; answers kept; whole form editable; resubmission recorded and queued again; no internal notes or flags shown | As ruled; a new `requirement.submitted` event per resubmission |
| 2.8 Notifications | Event → job architecture for the six cases; mailbox from configuration; no real address in code | As ruled. Template wording is a draft awaiting approval |
| 2.9 Durations and cost shares | No invented numbers; configurable and versioned; "Schedule to be confirmed"; creation not blocked | Stage master values stay NULL; planned dates NULL; creation does not read them |
| 2.10 Launch gates | Keep as explicit gates; invent no provider or account values | Section 5.2 |

### 5.2 Production launch gates (open)

None of these has an approved value; the code reads each from configuration and nothing here is filled in.

| Gate | Needed before production |
|---|---|
| R2 | Bucket, credentials and the CORS rule (PUT from the homeowner host only) |
| ClamAV | Running on the VPS (about 1.5 GB of memory) |
| Map tiles | Production tile provider (M-01) |
| Geocoder | Production reverse geocoder (M-02) |
| Legal | Privacy notice and terms versions, grievance contact, consent text (D-17) |
| Rate card | Production values, approver and shape (D-16); until then production shows no estimate |
| Repository | Owner and deploy approver (AQ-29) |
| Deployment, backup, monitoring accounts | Account ownership (AQ-35), secrets owner (AQ-09), email domain, restore drill, penetration test (D-12, D-13) |
| CSP | Nonce-based policy naming the production storage and map tile hosts |
| Operations mailbox | A real address for `P2B_OPS_NOTIFICATION_EMAIL` |
| Notification wording | Approval of the six templates |

### 5.3 Still open (business decisions)

Stage durations and cost shares (2.9); who enters or approves a schedule; how a package is purchased and what that unlocks beyond the specifications (billing); who signs off structural lines and what a sign-off records (2.4 ruled only that it is pending); notification wording; whether operations may edit a sent message or reason.

