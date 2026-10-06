# Plan2Build: Slice 3.4 readiness (modular services and connection)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/SLICE3_4_READINESS.md` |
| Version | 1.0 (2026-10-05) |
| Status | Approved by Chirag on 2026-10-05 with decisions N-01 to N-12 confirmed (section 0). Built on 2026-10-05 (section R). Approved and CLOSED by Chirag on 2026-10-05. N-03 is closed, not open (correction of 2026-10-05, below). Sections B to Q keep the readiness analysis; where they differ, section 0 governs |
| Baseline | PFR v2.0 (approved); PD-01 to PD-27 (IHB_FLOW 32.6); Slice 3.2 K0 (D-01 to D-11); Slice 3.3 section 0 (L-01 to L-08); canonical flow IHB_FLOW 34 |
| Sources read | IHB_FLOW 32, 33, 34; PROFESSIONALS_FLOW 22, 42 to 44 (44.7 leads, 44.8 own contractor); PFR (all); RECOMMENDATION_ENGINE; REQUIREMENT_QUESTIONS_V1 (L.2); SLICE3_READINESS, SLICE3_2_READINESS, SLICE3_3_READINESS; architecture DOMAIN, DATA (4.3, 4.6, 4.7, 4.8, as built 3.2 and 3.3), API (8, 9, 22), STATE (3, 5, 10, 11, 15), SECURITY (4.2, 7), EVENT, AI_AND_RECOMMENDATION, ARCHITECTURE_BASELINE; the code |
| Markers | **[SOURCE]** a source or approved architecture settles it. **[PD]** Chirag's decision (PD, D, L). **[REC]** Sakha's recommendation, not approved. **[OPEN]** undecided. **[SUPERSEDED]** an older design overridden |

Weight of the layers: PD-01 to PD-27, D-01 to D-11 and L-01 to L-08 are Chirag's decisions and take precedence. CD-25 to CD-28 (own contractor CD-27, listing leads CD-26, engine CD-28) are Sakha's designs still unreviewed by Chirag (IHB_FLOW 32, ARCHITECTURE_BASELINE 269): this document treats their details (the limit of three, the 48 hour, 10 day and 30 day windows, decline reasons, class table) as **proposals**, never as rules.

No code changed in this readiness pass.

## 0. Confirmed decisions (Chirag, 2026-10-05)

| ID | Decision [PD] |
|---|---|
| N-01 | Service needs map only to professional categories: contractor work and civil work to Contractor; architectural design to Architect; structural work to Structural Engineer; site/civil engineering to Site/Civil Engineer; MEP to MEP; interior work to Interior Designer; other trade or specialist requirements to a Specialist subtype. Project management and approvals create no professional need. Civil work never maps to Site/Civil Engineer. Requirement service labels and the category taxonomy stay separate concepts |
| N-02 | One ACTIVE engagement per project and category. Many candidate connection requests may exist before an engagement; another professional becomes ACTIVE only after the existing engagement ends |
| N-03 | SOURCING, CONTRACTED and BUILDING are not the professional lifecycle; their use for it is SUPERSEDED. No replacement global status transitions in 3.4. The lifecycle is derived from project, service needs, engagements and, later, construction stages. "Contracted" never means every category is contracted. **Closed (Chirag, 2026-10-05): confirmed, not open, never a blocker.** Professional progress is modelled as service needs, then engagements, then later construction and execution states |
| N-04 | A professional must cover the project's location for a normal connection; mismatch means not eligible. Public directory visibility unaffected. No silent radius expansion; radius stays configuration |
| N-05 | At most 3 open connection requests per project and category; no global per-project limit; another request only after one is withdrawn or closed |
| N-06 | Decline reasons: Unavailable / capacity; Outside service area; Scope mismatch; Schedule mismatch; Compliance / verification issue; Already engaged; Other (a short explanation required). The family sees a neutral message, never private moderation information |
| N-07 | Configurable 48-hour response window; no answer means EXPIRED; no auto-accept; no repeated re-notification; a new request may follow within the cap |
| N-08 | Before acceptance: a limited brief, no name, phone, email, exact address, site pin or documents. After acceptance: name, phone, email, project location, site pin where appropriate, the category, the relevant brief and documents explicitly relevant to that engagement; nothing about other categories or unrelated documents |
| N-09 | Contractors may be connected before the enlistment class exists; no fake class values |
| N-10 | On a package refund: open requests withdrawn automatically and stop consuming package services; history kept; accepted engagements kept; the direct relationship continues; new Plan2Build coordination actions blocked until a valid package exists |
| N-11 | Simple transactional emails (sent, accepted, declined, expired, withdrawn); concise, no marketing, nothing private before acceptance; copy in the externalised catalogue |
| N-12 | "Substantial Plan2Build work" is recorded when a professional accepts a connection, not when a request is sent; visible to operations for refunds; no legal wording in this slice. *Extension recorded 2026-10-06 (not a change to N-12): QD-02 in SLICE3_6_READINESS adds RFQ_SELECTION as a second trigger* |
| Connection and lead | Separate concepts. Connection: the family's formal request and relationship with a professional for a category. Lead: a later operational representation of an opportunity, only if a downstream workflow needs it; no lead entity that duplicates a connection. The old lead design is superseded where it assumes one contractor |
| Quote-holder review | Stays in 3.4 as intake only: the family submits an existing quote for review with the package; normalisation and comparison stay in the later quote workflow |
| Modularity | A project is never one contractor and one lifecycle; categories progress independently |

### 0.1 How the build applies them [REC, within the decisions]

| Point | Applied as |
|---|---|
| N-01 values | The locked requirement set has no "site/civil engineering" or "specialist" service value, so those two categories start UNDECIDED and are set by the family. The mapping is data (`service_value_categories`), keyed by question-set version |
| Engagement start | An engagement row exists from the moment it is ACTIVE: on acceptance (listed professional) or on recording (outside professional). Candidate requests live on `connections` only, so the two never disagree (simplifies D.2) |
| N-02 with several candidates | When one request is accepted, the family's other open requests in that category are withdrawn by the system with the reason "another professional was engaged", and the professionals are told. While an engagement is ACTIVE, new requests for that category are refused until it ends |
| N-04 per category | Profiles hold one base and radius; the check uses that radius for every category. A per-category radius would need new profile data (not in 3.2) |
| N-08 contact | The family gives the name and phone it wants shared when it sends the request (email is the account's); they are shown to the professional only after acceptance. The professional's account email, and a phone the professional adds when accepting, are shown to the family after acceptance. Project location means the locality and the plot pin (the requirement holds no street address). Documents: none by default; the family explicitly shares requirement files with an ACTIVE engagement |
| N-10 scope | Applied when the package ends by refund or by cancellation: both leave no valid package |
| N-12 record | The first acceptance on a package writes `package_service_usage` (CONNECTION_ACCEPTED), shown on the operations refund screen |

## A. Current implementation inventory

| Area | As built | Relevance to 3.4 |
|---|---|---|
| Categories | `service_categories`: CONTRACTOR, ARCHITECT, STRUCTURAL_ENGINEER, SITE_CIVIL_ENGINEER, MEP, INTERIOR_DESIGNER, SPECIALIST; specialist subtypes (Slice 3.2) | The key for per-category needs and engagements |
| Professionals | Profiles, per-category listing state (LISTED and not hidden is public), evidence, verification cases per category with no project scope | Listed professionals are the only ones a connection can reach. A project-only verification (CD-27) is not built: `verification_cases` has no scope or project column, and its one-open-case rule would block a second, project-scoped case |
| Discovery | Public directory and profile; `GET /projects/{id}/professionals` narrows to professionals whose radius covers the plot; neutral daily shuffle | Discovery stays free (PD-19, D-09). Contact details never public (D-01) |
| Requirement | Answers in `project_requirements.answers` (locked set v1): `services_needed` (optional, several), `has_contractor` (Yes/No), `has_quote` (Yes/No), plus brief facts (locality, sizes, floors, basement, budget band, start timeline, priorities) | Seeds service needs. The mapping from service values to categories is not decided (S32 M) |
| Memberships | `project_memberships` roles OWNER, HOUSEHOLD, CONTRACTOR, ARCHITECT, OPS_ADVISOR, OPS_FIELD, AUDITOR_ASSIGNED; only OWNER is used | CONTRACTOR and ARCHITECT are unused. No category column, so they cannot express a per-category engagement on their own |
| Package | `package_entitlements`, `package_active(project)`, `package_service_usage` (empty; written by package services from 3.4 on) | Connection is package-gated (PD-19). The first connection is the first "package service delivered" record (O-04) |
| Project status | ACCEPTED is the latest status reached; SOURCING, CONTRACTED and later are declared but unused | 3.4 must not move the project through single-contractor statuses (L-05, PFR 249) |
| Leads, connections, engagements, RFQ, quotes, messaging, recommendation | Not built | Designed in DATA 4.7 and 4.8, STATE 10 and 11 around one contractor per project (section I) |
| Notifications | Email infrastructure (Resend, Mailpit locally) and notification jobs exist | Professional and homeowner notices need approved wording (3.2 deferred professional emails for that reason) |

## B. Canonical modular service model

```
Project
  └─ Service need (one per category: undecided, needed, not needed)
       └─ Engagement (zero or more per need: who provides this service)
            ├─ party: a listed Plan2Build professional ── Connection (package-gated request, answered by the professional)
            ├─ party: a professional verified for this project only (CD-27 pattern; F-03 open)
            └─ party: an outside professional recorded by the family (no account, no connection)
                 └─ later, per category: RFQ, quote, comparison, selection (3.6); sign-off (3.5)
```

| Rule | Marker |
|---|---|
| Every professional and service is optional, per category, and may be mixed with outside professionals on one project | [PD] PD-17, IHB 34; L-01 |
| The domain holds service needs and engagements per category; never "the project's contractor" or a single route; no `project.contractor`, `project.contractor_route`, `project.path`, `project.contractor_status` | [PD] PD-17, S32 K0 model, L-06; [SUPERSEDED] DATA 117 `path`, `contractor_route` |
| A project holds several independent engagements, one or more categories at a time | [PD] PD-17; [REC] structure below |
| Buying the package commits the family to nothing beyond the services it chooses | [PD] PD-20, L-06 |
| Activation of the package and of engagements changes no project status | [PD] L-05; [REC] section D |

## C. Service-need model

### C.1 States

PFR 227 [REC] proposed one field with NEEDED, USING_PLAN2BUILD, USING_OWN, NOT_NEEDED. Checked against the architecture, that field would duplicate what the engagement already says (who provides the service) and can disagree with it (a need marked USING_PLAN2BUILD whose connection was declined). [REC] Split the two:

| Need state | Meaning |
|---|---|
| UNDECIDED | The family has not said (the requirement question is optional) |
| NEEDED | The family needs this service |
| NOT_NEEDED | The family does not need it |

How a needed service is provided is read from its engagements, so screens show one of: "Not decided", "Not needed", "Needed: no professional yet", "Plan2Build professional requested", "Plan2Build professional", "Your own professional". USING_PLAN2BUILD and USING_OWN become display states derived from the active or proposed engagement, never stored. [REC]

### C.2 Creation from the requirement

| Item | Model | Marker |
|---|---|---|
| When | One need row per top-level category, created when the requirement is first submitted (and for projects submitted before 3.4, on first read) | [REC] |
| From `services_needed` | A chosen service makes its category NEEDED; categories not chosen stay UNDECIDED, never NOT_NEEDED, because the question is optional | [REC] |
| Mapping | `CONSTRUCTION` → CONTRACTOR; `ARCHITECTURAL_DESIGN` → ARCHITECT; `STRUCTURAL_DESIGN` → STRUCTURAL_ENGINEER; `CIVIL_WORK` → SITE_CIVIL_ENGINEER; `MEP` → MEP; `INTERIOR_DESIGN` → INTERIOR_DESIGNER. `PROJECT_MANAGEMENT` and `APPROVALS` map to no professional category (they stay requirement answers; POQ-044). SPECIALIST has no service value: always UNDECIDED at first | [OPEN] N-01; the mapping is Sakha's reading, S32 M declined to invent it |
| `has_contractor` = Yes | The contractor need shows a prompt: "You said you already have a contractor. Record them?" Nothing is created without the family's action | [REC] |
| `has_quote` = Yes | Quote-holder review (CD-04) belongs to the package but its terms are CQ-02: not built in 3.4 | [SOURCE] CD-04; [OPEN] CQ-02 |
| Re-submission (NEEDS_INFO) | A changed `services_needed` answer never overwrites a need the family has set on the services screen; it only fills UNDECIDED rows | [REC] |

### C.3 Changes later

| Rule | Marker |
|---|---|
| The owner may change any need at any time while the project is open (not CANCELLED) | [REC]; owner only until OQ-027 (household permissions) |
| NOT_NEEDED is refused while the category has an active or requested engagement; the family ends or withdraws it first | [REC] |
| Specialist needs carry the chosen subtypes (WATERPROOFING, SOLAR, ...) | [REC] (D-06 subtypes are configurable) |
| Every change is audited (who, from, to, when) | [SOURCE] STATE 1 rule 3 |
| Setting needs is free; it is not a package service | [REC] (PD-19 gates connection, not the family's own planning) |

## D. Engagement model

### D.1 What an engagement is

An engagement is the family's choice of a party to provide one category of service on one project. It is the per-category relationship PD-17 and PFR 227 call for; RFQs, quotes, sign-offs and inspections in later slices reference it. [PD] PD-17; [REC] fields below.

| Party kind | Meaning | How it starts | Marker |
|---|---|---|---|
| LISTED | A Plan2Build professional LISTED (not hidden) in that category | The family chooses them and requests a connection | [PD] PD-19, D-04 |
| PROJECT_ONLY | A professional verified for this project only, labelled "Chosen by the family", not listed, sent no connections elsewhere | Invitation and basic verification | [SOURCE] CD-27 (proposed), PD-18 keeps it; [OPEN] F-03 for other categories and the package question; CQ-23 for failed verification. Not built in 3.4 until F-03 is answered |
| OUTSIDE | A professional the family names, with no account | The family records them | [REC] F-03 recommendation "Recording a name only is free" |
| (none yet) | The need is NEEDED with no engagement | Nothing to create | [REC] |

### D.2 States

```
LISTED:  REQUESTED ──(connection accepted)──► ACTIVE ──► ENDED
            └──(declined, expired, withdrawn)──► CLOSED
OUTSIDE: ACTIVE (on recording) ──► ENDED
PROJECT_ONLY: (F-03) VERIFYING ──► ACTIVE ──► ENDED, or CLOSED when verification fails (CQ-23)
```

| Rule | Marker |
|---|---|
| PFR 250 [REC] proposed PROPOSED → ACTIVE → ENDED; REQUESTED and CLOSED are added so a declined request does not read as an engagement that ended after work | [REC] |
| At most one ACTIVE engagement per project and category | [OPEN] N-02; recommendation: yes for the POC (one structural engineer, one architect, one contractor at a time); several open requests may wait in REQUESTED |
| ENDED by the family, the professional (LISTED or PROJECT_ONLY) or operations, always with a reason; history kept | [REC]; [OPEN] POQ-018, POQ-029 (what ending means mid-build) |
| An engagement never changes the project's status: no SOURCING, CONTRACTED or BUILDING from 3.4 | [PD] L-05; [SUPERSEDED] STATE 5 transitions PLAN_ISSUED → SOURCING ("contractor route chosen") and SOURCING → CONTRACTED; [PD] N-03 (closed 2026-10-05): they are not the professional lifecycle; progress is service needs, then engagements, then later construction and execution states |
| An ACTIVE engagement grants no `project_memberships` row in 3.4: the professional sees the connection brief, not the workspace | [REC]; membership roles CONTRACTOR and ARCHITECT stay unused until a slice needs workspace access (3.5, 3.6) |
| What makes an engagement "active" in the sources is POQ-017 (no D2 source defines it) | [OPEN] POQ-017; 3.4 uses connection acceptance (LISTED) and recording (OUTSIDE) |

## E. Connection and lead lifecycle

### E.1 Vocabulary (kept apart)

| Term | Meaning in Plan2Build | Slice |
|---|---|---|
| Connection | The package-gated, formal request from a family to one listed professional for one category on one project, answered by the professional | 3.4 |
| Lead | The sources' word (CD-26, PRO 44.7) for a contractor request that also expected a quote within 10 days. [REC] In 3.4 "lead" is only the professional's name for an incoming connection (their inbox), the same record; the quote expectation moves to the RFQ invitation in 3.6 | 3.4 (name), 3.6 (quote part) |
| RFQ | A request for quotation built from the scope (Build Plan for contractors, F-10) and sent to engaged professionals | 3.6 |
| Quote | A professional's priced answer to an RFQ, versioned | 3.6 |
| Comparison | Plan2Build's structured, normalised review of quotes | 3.6 |
| Selection | The family's choice of a quote for a category | 3.6 |

### E.2 States and rules

```
(new) ──► SENT ──► ACCEPTED (engagement ACTIVE)
            ├──► DECLINED (reason)
            ├──► EXPIRED (no answer in the response window)
            └──► WITHDRAWN (family, operations or system, with reason)
```

| Question | Model | Marker |
|---|---|---|
| When created | When the owner of an ELIGIBLE project with an ACTIVE package chooses a LISTED professional for a NEEDED category and confirms "Request connection" | [PD] PD-19; [REC] the rest |
| Professional eligible | LISTED and not hidden in that category; account active; not suspended; service radius covers the plot | [SOURCE] PRO 44.7 step 4 (service area), PBR-028 (suspended gets no leads); [PD] D-11 (hidden); [OPEN] N-04 whether radius must cover (the directory filter only narrows today); [OPEN] D-05 class gate for contractors (section G) |
| Duplicate prevention | One open or accepted connection per (project, category, professional); asking again returns the existing one. The same professional may hold connections for two categories (D-06, several categories per professional) | [SOURCE] PRO 44.7 rule "one lead per project and contractor", per category; [SUPERSEDED] DATA 183 UNIQUE (`project_id`, `profile_id`) without category |
| How many at once | A cap of open (SENT) connections per project and category, configuration | [SOURCE] CD-26 proposes 3 for contractors; [OPEN] N-05 the value and whether it applies to every category; [SUPERSEDED] DATA 186 cap per project |
| Data shared on SENT | A brief without identity: category (and specialist subtypes), locality (never the exact address or pin), plot size, built-up area, floors, basement, budget band, start timeline, the needed services. Not the name, phone, email, address, coordinates, documents or designs | [SOURCE] PRO 44.7 step 5, DOMAIN 152, SECURITY 210 (CD-26 proposed); [PD] D-01 spirit |
| Professional privacy on SENT | The family sees the public profile only (D-01): no phone, email or website | [PD] D-01 |
| VIEWED | Recorded when the professional opens it (for the family's status line) | [SOURCE] STATE 11; [REC] keep it as a timestamp, not a state |
| Response | ACCEPTED or DECLINED with a reason from a list | [SOURCE] PRO 44.7 step 6; [OPEN] N-06 the reason list (proposed: fully booked, outside my area, not my type of work; "outside my class" only once D-05 exists) |
| Response window and expiry | `respond_by` from configuration; a scheduled sweep expires SENT connections past it | [SOURCE] CD-26 proposes 48 hours; [OPEN] N-07 the value |
| Revealed on ACCEPTED | [OPEN] POQ-019 and N-08. Recommendation: names both ways; the family's chosen contact channel (email by default, phone only if the family opts in); the professional's account email; the plot address only when the family shares it. No messaging in 3.4 (not built) | [REC] |
| Withdrawal | The family may withdraw a SENT connection at any time, with an optional reason; operations may withdraw with a reason; the system withdraws when the professional is suspended or unlisted for the category, or the project is cancelled or put on hold | [SOURCE] STATE 11 (system or operations), PBR-028, EVENT 94; [REC] family withdrawal |
| After acceptance | The family or the professional may end the engagement with a reason (section D) | [REC]; [OPEN] POQ-018 |
| Inactivity withdrawal (30 days) | Not built in 3.4 | [SOURCE] CD-26 proposal; [OPEN] N-07 |
| Replacement suggestions after a decline | Not built: recommendation engine is not in 3.4 (PFR G 3.6). The family picks another professional | [SOURCE] PFR G; [REC] |
| Audit | Every transition writes an audit row and an append-only event row (actor, from, to, reason, time) | [SOURCE] STATE 1, DATA 185 `lead_events` |
| Package usage | The first connection SENT on an entitlement writes `package_service_usage` (service CONNECTION), feeding the "substantial work" question (O-04) | [SOURCE] S33 E; [OPEN] O-04 whether a connection counts as substantial |

## F. Outside-professional model

| The family says | What happens | Package | Marker |
|---|---|---|---|
| "I already have my own architect." | Need ARCHITECT = NEEDED; an OUTSIDE engagement with the name, optional firm and optional contact, ACTIVE at once. The person has no account and receives nothing | Free | [REC] F-03 recommendation; [OPEN] F-03 |
| "I already have my own contractor." | The same, for CONTRACTOR. Inviting that contractor onto the platform with basic verification and project-only access (CD-27) is a later step, F-03 and CQ-23 | Recording free; platform access a package service per F-03 recommendation | [SOURCE] CD-27 (proposed); [OPEN] F-03, CQ-23 |
| "I want Plan2Build to find my structural engineer." | Need STRUCTURAL_ENGINEER = NEEDED; the family browses listed engineers for that category and requests a connection | Connection needs the package | [PD] PD-19, PD-24 |
| "I don't need an interior designer." | Need INTERIOR_DESIGNER = NOT_NEEDED | Free | [REC] |

Rules: each category is independent; an outside engagement in one category never affects another; recording an outside professional never sends them anything and never makes them visible to any other family; the outside contact is the family's private data (P2), shown only to the family and operations. Outside professionals are never listed, recommended or sent connections. [SOURCE] CD-27 (labelled, not listed); [REC] the rest.

## G. Category-specific behaviour

3.4 uses one connection flow for every category. The differences the sources set apply after connection (RFQ, quotes, retainers, sign-off) and belong to 3.5 and 3.6. [REC]

| Category | 3.4 behaviour | Later or open | Marker |
|---|---|---|---|
| Contractor | Same connection flow. `has_contractor` prompt (C.2) | CD-15: leads go "only to registered contractors, according to their enlistment class"; the class is D-05/CQ-07 OPEN. RFQ needs an issued Build Plan (F-10 recommendation). Quote window 10 days moves to the RFQ (3.6) | [SOURCE] CD-15; [OPEN] N-09: connect contractors without a class check until D-05 (recommended), or hold contractor connections |
| Architect | Same flow | CQ-25 (fee paid directly or through the package; engine shortlist); CQ-18 (Plan2Build's role); architect-only quote fields (3.6) | [SOURCE] CD-25 (on request), CD-01 (fee direct by default); [OPEN] CQ-25 does not block connection |
| Structural engineer | Same flow; the family may also use their own (OUTSIDE) | Sign-off by any qualified engineer and its capture (F-04, 3.5); scope per house CQ-22; never AI-generated (BR-055) | [PD] PD-24, PD-08; [SUPERSEDED] "retained by Plan2Build, never quotes" (PRO 42.1, 44.1 rule 9) |
| Site/civil engineer | Same flow | No role flow in the sources | [PD] D-06 |
| MEP | Same flow | No role flow in the sources | [PD] D-06 |
| Interior designer | Same flow | Whether interiors take part in the POC is CQ-08 (partly answered); interiors as a project type is phase 2 (CD-03) but the locked `services_needed` includes `INTERIOR_DESIGN` | [PD] D-06; [OPEN] CQ-08 |
| Specialist | Same flow; the need records subtypes and the directory narrows to them | After handover, needs go through the back office (CD-12) | [PD] D-06 |
| Project management, approvals | Not professional categories: no need row, no connection | POQ-044 | [OPEN] POQ-044 |

## H. Package gating

| Action | Package | Marker |
|---|---|---|
| Browse the directory and profiles | Free | [PD] PD-19, D-09 |
| Set service needs (needed, not needed) | Free | [REC] |
| Record an outside professional | Free | [REC] F-03 recommendation |
| Choose a listed professional and request a connection | Needs an ACTIVE package on the project and an ELIGIBLE project | [PD] PD-19, PD-08; [SUPERSEDED] CD-26 no-package branch (X-05) |
| Invite the family's own professional onto the platform (project-only access) | Package service per F-03 recommendation | [OPEN] F-03 |
| Quote-holder review | Package service | [SOURCE] CD-04, PFR 128; [OPEN] CQ-02 (terms), not built in 3.4 |
| Package refunded or cancelled while connections are open | Open SENT connections are withdrawn with the reason "package ended"; ACTIVE engagements stay (the relationship is the family's) | [REC]; [OPEN] N-10 |

## I. Data model

Minimum new tables (owner in brackets). Money: none. Construction money: none (G.1 of SLICE3_3_READINESS still holds).

| Table | Columns | Rules | Marker |
|---|---|---|---|
| `project_service_needs` (projects) | `project_id`, `category_code` (top-level `service_categories`), `state` (UNDECIDED, NEEDED, NOT_NEEDED), `subtypes` (specialist), `source` (REQUIREMENT, FAMILY), `updated_by`, `updated_at`, `version` | UNIQUE (`project_id`, `category_code`); audited | [REC] (PFR 227 named the table) |
| `project_engagements` (engagements, new module) | `project_id`, `category_code`, `party_kind` (LISTED, PROJECT_ONLY, OUTSIDE), `profile_id` (LISTED, PROJECT_ONLY), `outside_name`, `outside_firm`, `outside_contact` (P2, encrypted at rest like other contact data), `state` (REQUESTED, ACTIVE, ENDED, CLOSED, and VERIFYING for PROJECT_ONLY), `ended_by_role`, `end_reason`, `created_by`, `created_at`, `activated_at`, `ended_at`, `version` | CHECK party fields by kind; partial UNIQUE one ACTIVE per (`project_id`, `category_code`) if N-02 says so | [REC] |
| `connections` (engagements) | `engagement_id` (UNIQUE), `project_id`, `category_code`, `profile_id`, `state` (SENT, ACCEPTED, DECLINED, EXPIRED, WITHDRAWN), `brief` (snapshot, no identity), `sent_at`, `respond_by`, `viewed_at`, `responded_at`, `decline_reason_code`, `withdrawn_by_role`, `withdraw_reason`, `entitlement_id`, `version` | partial UNIQUE (`project_id`, `category_code`, `profile_id`) where SENT or ACCEPTED; open cap per project and category enforced under a lock on the need row | [REC]; replaces DATA 4.7 `leads` |
| `engagement_events` (engagements) | `engagement_id`, `connection_id`, `from_state`, `to_state`, `actor_user_id`, `actor_role`, `reason`, `at` | Append-only (trigger) | [SOURCE] DATA 185 `lead_events` pattern |

Not created in 3.4: `leads` as designed (DATA 183 to 186: contractor-only, no category, cap per project), `rfqs`, `rfq_invitations`, `quotes`, `quote_versions`, `comparisons`, `selections`, `contract_values`, `threads`, `contractor_capacity`, `professional_conflicts`, recommendation tables, and any column on `projects`. Project-only verification needs a project scope on verification (DATA 168 designed `scope` and `project_id` on `verification_cases`; the as-built table lacks them) and arrives with F-03. [REC]

Superseded by this model when approved: DATA 4.7 `leads` key and cap; STATE 11 "Other leads NOT_SELECTED" (a single winner per project); STATE 5 SOURCING and CONTRACTED as single-contractor statuses; DATA 224 `contract_values` UNIQUE per project and DATA 199 one selection per RFQ (both 3.6 matters, flagged now). [SUPERSEDED] pending Chirag's approval.

## J. API model (proposed, not implemented)

Every route checks, in order: session and audience; project membership (404 outside visibility; owner for writes, OQ-027); project open and ELIGIBLE where stated; package ACTIVE where stated; the category is a top-level category with a NEEDED need where stated; the professional's listing for that category; then the state machine. Writes take `Idempotency-Key`; every transition is audited.

| Route | Actor | Purpose | Gate |
|---|---|---|---|
| `GET /projects/{id}/services` | member | Needs per category with derived status, engagements and connections (family view) | Membership |
| `PUT /projects/{id}/services/{category}` | owner | Set NEEDED or NOT_NEEDED (and specialist subtypes) | Open project; NOT_NEEDED refused with an active or requested engagement |
| `POST /projects/{id}/services/{category}/outside` | owner | Record an outside professional (name, firm, contact) | Open project; free |
| `POST /projects/{id}/services/{category}/connections` | owner | Choose a listed professional (`profile_id`) and send a connection | ELIGIBLE, package ACTIVE, need NEEDED, professional eligible, no duplicate, under the cap |
| `POST /projects/{id}/connections/{cid}/withdraw` | owner | Withdraw a SENT connection | State |
| `POST /projects/{id}/engagements/{eid}/end` | owner | End an ACTIVE engagement with a reason | State |
| `GET /pro/connections`, `GET /pro/connections/{cid}` | professional (the recipient) | Inbox and the brief without identity; first read sets `viewed_at` | Own connections only |
| `POST /pro/connections/{cid}/accept`, `/decline` | professional | Respond before `respond_by`; decline with a reason code | Still LISTED in the category; state |
| `POST /pro/engagements/{eid}/end` | professional | End an ACTIVE engagement with a reason | [OPEN] POQ-018 |
| `GET /ops/projects/{id}/engagements` | OPS or ADMIN with MFA | Read every need, engagement and connection of a project | Staff |
| `POST /ops/connections/{cid}/withdraw`, `POST /ops/engagements/{eid}/end` | OPS with MFA | Withdraw or end with a reason (disputes, suspended professional) | Staff; never a business field outside a transition (SECURITY 126) |

Not proposed: lead suggestions (engine), RFQ, quotes, comparison, selection, messaging, own-professional invitation (F-03).

## K. Frontend model

Homeowner (project dashboard; never "choose your contractor for the whole build"):

1. **Professionals** section of the project becomes a per-category list: Contractor, Architect, Structural engineer, Site/civil engineer, MEP, Interior designer, Specialist. Each card shows the need status and one of three actions: "Find a Plan2Build professional", "Use my own professional", "I don't need this". [REC]
2. **Find**: the directory opened for that category and the project (plot coverage), as today, with a "Choose for this project" action on each profile. [SOURCE] 3.2 directory
3. **Choose → Request connection**: a confirmation stating what the professional will see (the brief without identity) and what happens on acceptance. Without an active package the action explains the package and links to it; nothing is sent. [PD] PD-19
4. **Status** on the card: requested (with the response deadline), accepted (with the revealed contact per N-08), declined (with the reason category), expired, withdrawn; and "Request another" for the same category.
5. **Use my own**: a short form (name, firm, optional contact). The card then reads "Your own professional: name".
6. **I don't need this**: one click, reversible.

Professional: a **Connections** area on the professionals host (inbox, brief, accept, decline with a reason, deadline shown), and a dashboard count of new connections.

Operations: an **Engagements** panel on the project review page (needs, engagements, connections, history) with withdraw and end actions.

## L. Operations model

| Question | Answer | Marker |
|---|---|---|
| Review each connection before it is sent | No: the family's picks are checked by rules (listing, area, suspension), not by staff | [SOURCE] PRO 44.7 step 4 (system check); no source requires staff approval of a family's pick |
| Approve a professional-to-project match | No in 3.4. Staff review applies to engine shortlists (BR-142), which 3.4 does not build | [SOURCE] RE, BR-142 |
| Intervene in rejected connections | Read access and withdraw or end with a reason; no reassignment | [SOURCE] STATE 11 (operations withdraw), CD-10 (operations handle disputes) |
| Override service needs | No: needs are the family's choice; staff never edit them | [REC]; [SOURCE] SECURITY 126 insider rule |
| See all engagements | Yes, read-only, OPS or ADMIN with MFA | [REC] |
| Verify the family's own professional | Yes when F-03 and CQ-23 are answered (CD-27: identity, references, site visit) | [OPEN] F-03 |

## M. Security and privacy

| Flow | Moves | Never moves (until stated) | Marker |
|---|---|---|---|
| Homeowner → professional, on SENT | Category, subtypes, locality, plot size, built-up area, floors, basement, budget band, start timeline, needed services | Name, phone, email, exact address, coordinates, documents, designs, other professionals' names | [SOURCE] PRO 44.7 step 5 (proposed), SECURITY 210 |
| Homeowner → professional, on ACCEPTED | Per N-08 (recommended: name and chosen contact channel) | Coordinates and documents (until a later slice grants workspace access) | [OPEN] POQ-019 |
| Professional → homeowner | Public profile (D-01) before acceptance; per N-08 after | Phone, email, website before acceptance | [PD] D-01 |
| Homeowner → Plan2Build | Needs, choices, outside professionals' details (P2) | | [REC] |
| Professional → Plan2Build | Responses, decline reasons, end reasons | | [REC] |

Controls: project membership on every project route (404 outside); a professional reads only connections addressed to them (404 otherwise); responses shaped per audience (one model per audience, SECURITY 131); outside contacts encrypted and never in logs, events or analytics; event payloads carry ids only; every transition audited with actor and role; suspension or unlisting withdraws open connections; foreign-membership sweep tests extended to the new routes. [SOURCE] SECURITY 4.2, 7; [REC] encryption of outside contacts.

## N. Open product decisions

| ID | Question | Recommendation | Blocks |
|---|---|---|---|
| N-01 | The mapping from `services_needed` to categories (C.2), and that `PROJECT_MANAGEMENT` and `APPROVALS` create no need | As in C.2 | Seeding needs |
| N-02 | One ACTIVE engagement per project and category? | Yes for the POC | Engagement constraint |
| N-03 | Project statuses SOURCING, CONTRACTED, BUILDING: retire, or redefine as derived from engagements? | [SUPERSEDED as a question] Closed by Chirag on 2026-10-05: not the professional lifecycle; progress is service needs, then engagements, then later construction and execution states | Nothing |
| N-04 | Must the professional's service radius cover the plot to receive a connection? | Yes | Eligibility check |
| N-05 | Open-connection cap per project and category, and whether it applies to every category | 3, every category (CD-26 proposal) | Cap value |
| N-06 | Decline reason list | Fully booked; outside my service area; not my type of work; other | Decline form |
| N-07 | Response window (CD-26 proposes 48 hours) and whether inactivity withdrawal (30 days) applies | 48 hours as configuration; no inactivity withdrawal in 3.4 | Expiry sweep |
| N-08 | What is revealed on acceptance (POQ-019) | Names both ways; the family's email, phone only if the family opts in; the professional's account email; no exact address | The accepted view |
| N-09 | Contractor connections before the enlistment class exists (CD-15, D-05) | Allow, without a class check, until D-05 is decided | Contractor category |
| N-10 | Open connections when the package is refunded or cancelled | Withdraw SENT; keep ACTIVE engagements | Billing hook |
| N-11 | Notification emails (new connection, accepted, declined, expired) and their wording | Send plain transactional emails; wording approved by Chirag | Without it, professionals learn of connections only on their dashboard |
| N-12 | Does a connection count as "substantial work" for refunds (O-04)? | No: only delivered services such as a comparison or an inspection | Refund policy |

Carried open and outside 3.4's build: F-03 and CQ-23 (own professional on the platform, PROJECT_ONLY), CQ-02 (quote-holder review), CQ-25 and CQ-18 (architect), CQ-08 (interiors in the POC), D-05/CQ-07 (class), F-04 (structural sign-off), F-10 (which RFQs need a Build Plan), F-11 (assurance with an outside contractor), POQ-017, POQ-018, POQ-029 (engagement activation and ending), POQ-044 (PMC and approvals), OQ-027 (household permissions). (N-03 was listed here; closed 2026-10-05.)

## O. Recommended implementation order

1. Vocabulary and migration: needs, engagements, connections, events; append-only and lifecycle triggers.
2. Service needs: seeding from the requirement (N-01), owner edits, audit.
3. Outside engagements (free).
4. Connections: package gate, eligibility, duplicates, cap, brief snapshot, `package_service_usage`.
5. Professional inbox: read, accept, decline; engagement activation.
6. Withdrawal and ending; system withdrawal on suspension, unlisting, project cancellation, package end (N-10); expiry sweep job (N-07).
7. Operations read and actions.
8. Notifications, if N-11 is approved.
9. Screens: project Professionals section, choose and request, status; professional Connections; operations panel.
10. Tests: per-category independence, package gate, duplicates, cap, privacy of the brief, foreign-membership sweep, expiry, suspension withdrawal; Playwright on phone and desktop with axe.
11. Migration up, down, up; contracts; docs (DATA, API, STATE as built; supersession notes on `leads`, STATE 5 and STATE 11).

After F-03: own-professional invitation and project-only verification. After CQ-02: quote-holder review.

## P. Exact blockers

| Blocker | Blocks |
|---|---|
| N-01 mapping | Seeding needs from the requirement (needs can still be set by hand) |
| N-02, N-04, N-05, N-06, N-07 | Constraint, eligibility rule, cap, decline list, expiry: each can be built as configuration with the recommendation once accepted |
| N-08 (POQ-019) | What the family and the professional see after acceptance; without it acceptance reveals nothing and the connection is not useful |
| N-09 (D-05) | The contractor category's connections, if Chirag prefers to hold them |
| N-11 | Notifications; the flow works without them, but professionals would see connections only by visiting their dashboard |
| F-03, CQ-23 | PROJECT_ONLY engagements (own professional with platform access); not needed for the rest of 3.4 |
| CQ-02 | Quote-holder review, which PFR G placed in 3.4; recommended to move it out |

None of them needs a provider, an account or money.

## Q. Verdict

**READY WITH DECISIONS.** The per-category model (needs, engagements, connections) is settled by PD-17, PD-19, PD-20, PD-24, D-01, D-06, D-11 and L-05 to L-06. N-01, N-02, N-04 to N-08 and N-11 need Chirag's answer or acceptance of the recommendation before the build; N-09 decides whether contractors are included at first. PROJECT_ONLY engagements (F-03, CQ-23) and quote-holder review (CQ-02) stay out of 3.4 until answered.

No code changed in this readiness pass.

## R. Build result (2026-10-05)

Built as sections 0 and 0.1 say: module `engagements` (models, service, views, routers, handlers, jobs, interface), migration `0012_engagements`, notifications, and homeowner, professional and operations screens.

| Area | As built |
|---|---|
| Needs | Derived from the requirement through `service_value_categories` until the family changes one; specialist subtypes on the SPECIALIST need |
| Connections | Owner only; package, category, listing (LISTED and shown), coverage, duplicate and cap checked under a per-category lock (the need row); brief snapshot without identity; the family's contact stored with the request and shown on acceptance |
| Responses | Accept (optional phone; still listed; package active; project not cancelled; no engagement) creates the ACTIVE engagement and withdraws the category's other SENT requests; decline with an N-06 reason; expiry job every 15 minutes on `maintenance` |
| System withdrawals | `billing.package_changed` to REFUNDED or CANCELLED, `project.cancelled`, `professional.listing_changed` out of LISTED |
| Engagements | One ACTIVE per category (partial UNIQUE); outside professionals free; ending by the family, the professional or operations with a reason |
| Files | Nothing shared by default; the family shares requirement files with an ACTIVE listed engagement; links logged |
| N-12 | `package_service_usage` CONNECTION_ACCEPTED on the first acceptance; shown on the operations order screen |
| Quote-holder review | Intake only: QUOTE_DOCUMENT uploads (scanned), a request with 1 to 5 files, an operations email and staff download |
| Emails (N-11) | Family: sent, accepted, declined, expired, withdrawn. Professional: new request, withdrawn. Operations: quote review. Templates in `apps/api/src/p2b/notifications/templates` |
| Screens | Homeowner: Professionals section (`/projects/{id}/services`), directory and profile with "Request a connection", the request screen. Professional: Requests list and detail. Operations: a panel on the project page |

Choices made inside the confirmed decisions [REC]:

| Point | Built as |
|---|---|
| Professional email subjects | N-11 gives the family's subjects; the professional's are "You have a new Plan2Build connection request" and "A Plan2Build connection request was withdrawn" |
| The family's own withdrawal | No "withdrawn" email to the family when they withdrew it themselves |
| Hidden listing | Hiding (D-11) does not withdraw requests already sent; suspension and other exits from LISTED do |
| After an engagement ends | The family's contact stays visible to the professional (already disclosed); the pin and shared files stop |
| Site address | The requirement holds no street address, so the family may add one with the request; shown only after acceptance |
| Outside contacts | Plain P2 text like `user_contacts`; the separate encryption recommended in M was not adopted |
| Directory link | The dashboard's Professionals item opens the services page, which links to the project-filtered directory; the Slice 3.2 Playwright spec was updated for this |

| Check | Result |
|---|---|
| Migration `0012_engagements` | Up, down, up on the test database; `alembic check` clean; dev database at 0012 |
| API tests | 468 passed (18 new in `test_engagements.py`) |
| ruff, mypy strict (src), import-linter | Clean; 4 contracts kept, `engagements` added to the independence and billing contracts |
| Web: `tsc`, ESLint, Vitest 30, `next build` | Clean |
| Playwright, phone and desktop, axe on every screen | 56 passed from the production build in four batches with rate limits reset (32 + 10 + 8 + 6); `engagements.spec.ts` adds 4 |

Carried to 3.5 and later: F-03 and CQ-23 (own professional on the platform), reviewing submitted quotes (quote workflow), D-05 (contractor class), a per-category service radius (profiles hold one), approval of the new email wording.
