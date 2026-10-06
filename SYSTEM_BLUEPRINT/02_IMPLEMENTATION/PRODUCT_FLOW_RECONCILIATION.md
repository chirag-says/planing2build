# Plan2Build: product flow reconciliation (modular aggregator)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/PRODUCT_FLOW_RECONCILIATION.md` |
| Version | 2.0 (2026-10-04) |
| Status | Approved by Chirag on 2026-10-05 as the product-model baseline (17 points locked, IHB_FLOW 32.6). Wording safeguards of 2026-10-05 applied: ACCEPTED means initial eligibility only; F-09 and F-13 stay open; package wording is modular. Slice 3.0 built on 2026-10-05 (FOUNDATION_PLAN 4f) |
| Decisions | Chirag's product decisions PD-01 to PD-26, IHB_FLOW section 32.6. Canonical flow: IHB_FLOW section 34 |
| Changes from 1.0 | Corrected after Chirag's second clarification. The product is modular, so no service is mandatory. Champions Club is the name for every approved, listed professional, not a membership layer. Discovery is free. The operations review runs in the background. AI credits are separate from the package. Package pricing rules are configuration, not a fixed rule. Any qualified structural engineer may sign. Questions Q1, Q3 (in part), Q4, Q5 (in part), Q8, Q10, Q11 (structure) and Q17 are now settled; the remaining open points are renumbered F-01 to F-13 in section F |
| Markers | **[SOURCE]** fact from a source, with citation. **[PD]** Chirag's confirmed product decision. **[REC]** Sakha's architecture recommendation, not approved. **[OPEN]** business decision not yet made |

## A. Final product model

1. **Modular aggregator.** [PD-01, PD-17] Plan2Build is a modular aggregator. Homeowners take only what they need:
   - professionals: contractors, architects, structural engineers, site and civil engineers, MEP, interior designers, specialists;
   - services: quote comparison, coordination, assurance and inspections.
   
   No step, category or service is mandatory. A homeowner may use any mix of Plan2Build professionals and their own or outside professionals. The promise is: whatever part of the journey you need help with, Plan2Build helps you find and connect with the right professional or service.
2. **What Plan2Build is not.** [PD-01; SOURCE CD-01, CD-13] It is never the contractor, architect or engineer. It does not own execution, sells no materials at the MVP and never handles construction money.
3. **Free, then paid.** [PD-03, PD-19] Free value comes first:
   - dashboard;
   - indicative estimate;
   - AI designs;
   - gallery;
   - browsing approved professionals.
   
   One paid package unlocks Plan2Build's coordination layer:
   - formal connection and leads;
   - RFQ;
   - quote coordination;
   - structured comparison and review;
   - assurance and inspections;
   - other package services.
   
   Buying the package commits the homeowner to nothing beyond the services they choose to use [PD-20].
4. **Separate priced things.** [PD-04, PD-22] These never merge:
   - the indicative construction estimate;
   - the Plan2Build package fee;
   - paid AI design credits;
   - each professional's own quote.
5. **Quality, not placement.** [PD-08, PD-18] Only Plan2Build-approved professionals are listed, and together they are called the Champions Club. Nothing about listing, ranking or recommendation can be bought.

## B. Final IHB flow

Canonical flow recorded in IHB_FLOW section 34 [PD-26]:

```
Public website → Plan a project → Login (OTP) → Structured requirements → Requirement submitted
  → FREE PROJECT DASHBOARD OPENS IMMEDIATELY
       ├─ Project and requirements
       ├─ Indicative estimate
       ├─ Generate My Design (3 successful free per project) and design gallery
       └─ Discover approved professionals (free)
  → Operations review runs in the background ("Your project is being reviewed by Plan2Build.")
  → Project eligible → the one Plan2Build package becomes purchasable
  → Verified payment → package active
  → Homeowner chooses what they actually need
  → Match and connect the relevant professional(s)
  → RFQ, quotes, comparison, review (for the services chosen)
  → Select only the professional or service needed
  → Execution, possibly with Plan2Build and outside professionals
  → Plan2Build assurance and inspections where applicable
  → Handover → Build record
```

**Review states** [PD-21; built states reused]. The review never blocks free value.

| Review state | Homeowner sees | Package |
|---|---|---|
| SUBMITTED | "Your project is being reviewed by Plan2Build." | Not yet purchasable |
| NEEDS_INFO | The request and the editable requirement | Not yet purchasable |
| ACCEPTED (passed the initial review) | A notice that Plan2Build's initial review is complete and the package can be offered | Purchasable |
| CANCELLED | The reason | Not purchasable; free content kept per F-13 |

**As implemented today, for contrast.** After submitting, the homeowner waits on a status page until operations accept. Only then does the project page show the 16 stages and 67 lines, in "Package A/B/C" cards with criteria hidden "until this package is purchased". There is no estimate on the project, no AI design and no discovery.

## C. Final package model

- **One package, several services.** [PD-09, PD-20] There is one Plan2Build package. It is the paid aggregation, coordination, comparison and assurance layer. It gives the homeowner access to package services, never an obligation to use all of them.
- **A/B/C are not products.** Groups A, B and C are only groupings and timing of the 67 specification lines. They are never products, payments or gates.
- **When it can be bought.** [PD-21] Only when the project is eligible: operations have accepted it (the ACCEPTED status, built). ACCEPTED means the project passed Plan2Build's initial eligibility review and the package may be offered. It is not an approval of the design, the budget, any professional or the future project as a whole.
- **Pricing.** [PD-23] Versioned, configurable pricing rules map approved project characteristics to a price. Which characteristics the POC uses is a configuration choice, not a permanent rule. The server computes the price and stamps it with the rule version. An order's price never changes after creation [REC].
- **Payment.** [PD-10] Razorpay. The homeowner chooses among the modes the offering allows: 100% upfront, or instalments with a configurable structure.
- **Activation.** The package becomes ACTIVE only on a verified capture: a signed webhook or a verified reconciliation fetch, never the browser callback. Kept from the design:
  - one Razorpay order per attempt;
  - event id stored once;
  - amount and order checked against the invoice;
  - invoices;
  - daily reconciliation.
- **Refunds.** [PD-11] A homeowner may request a refund before substantial Plan2Build work is delivered; after that, operations or admin review the case. Every decision needs a reason and an authorized staff action. Refunds go back through Razorpay. Customer wording stays in the final terms.
- **Tax.** [PD-12] Applicable tax is charged and invoiced from a versioned tax configuration. No rate in code.
- **Money boundary.** [SOURCE CD-01, CD-09] No API, table or job accepts construction money.

**Package state** [REC]: NOT_ACTIVE → ACTIVE (first verified capture) → CANCELLED or REFUNDED (staff refund decision). LAPSED exists only if F-06 defines late-instalment handling.

## D. Final professional and Champions Club model

**Listing** [PD-18]. A professional registers and submits details. Plan2Build reviews and verifies them against its quality standard. Only approved professionals are listed publicly. "Champions Club" is the name for that listed, approved set. It is not:
- a membership;
- a tier;
- a purchase;
- a ranking;
- a subset of listed professionals.

There are no "non-Champion" public listings.

| Listing state [REC] | Meaning |
|---|---|
| PENDING_REVIEW | Submitted; Plan2Build checking |
| CHANGES_REQUESTED | Plan2Build asked for more (optional loop) |
| LISTED | Approved; public; shown as a Champions Club professional |
| SUSPENDED | Temporarily hidden, with reason |
| REJECTED | Not approved, with reason; may reapply (F-02) |

Listing state is held per professional and category. The approval checks per category (identity, registration where the profession needs it, references, site visit, portfolio) are F-02. No `club_memberships` table, club application or club review cycle [REC, replacing the 44.8 design].

**Discovery is free** [PD-19]. Before any package, a homeowner can:
- browse approved professionals relevant to the project's requirements and categories;
- view profiles;
- see expertise, category, service area and other relevant information.

There are no artificial visibility limits. Whether direct contact details show on a free profile is F-01.

**Package-gated** [PD-19]:
- formal Plan2Build connection and lead creation;
- RFQ;
- quote collection and coordination;
- structured comparison and review (including review of a quote the homeowner already holds);
- coordination;
- other package services.

**Modular use** [PD-17] [REC for the model]:
- Every professional relationship is optional and per category.
- A homeowner may use a Plan2Build professional for one category and an outside one for another.
- The domain holds service needs and engagements per category, never "the project's contractor" or a single route.

**Outside professionals** [PD-17, PD-24]. Outside professionals may take part where the rules permit. The family's own contractor follows the existing pattern: basic verification and project-only access, not listed [SOURCE CD-27, CD-07]. Extending this to every category is F-03.

**Recommendations** [PD-08; SOURCE CD-18, CD-28]:
- may suggest listed professionals and quote options;
- never brands;
- never paid placement or sold ranking;
- never hidden price ranking;
- never commercial influence.

**Structural sign-off** [PD-24; SOURCE S04 section 3]:
- Where structural sign-off applies, a structural engineer signs before an authoritative Build Plan is issued.
- The signer may be a Plan2Build-listed structural engineer, the homeowner's own, or another qualified engineer outside Plan2Build, where the rules permit.
- Nothing requires Plan2Build's retained engineer to sign.
- How an outside engineer's registration is checked, and how the signature is captured, is F-04.

## E. Final AI design model

- **Placement.** [PD-05, PD-22] "Generate My Design" opens with the free dashboard once the requirement is submitted.
- **Inputs.** The prompt is built server-side from the structured requirement by a versioned template [REC]. The homeowner does not write it. Question set v1 (locked) already holds every input: plot shape and size, facing, setbacks, floors, basement, rooms, Vastu, tier, style, budget [SOURCE REQUIREMENT_QUESTIONS_V1 L.2].
- **Free and paid.**
  - Three successful generations per project are free. A failed generation does not count.
  - Every generation is kept in the project's gallery.
  - After three, further generations are separate paid AI credits. They are not part of the package, and the package never includes them unless Chirag changes this decision.
  - The about-₹99 figure is a working proposal, held as configuration and absent from code and seeds.
- **Record per generation:**
  - project and sequence number;
  - free or paid, with the credit used;
  - provider and model;
  - prompt template version;
  - requirement snapshot: question set version, requirement version and the frozen answers used;
  - input file references;
  - output file;
  - status (QUEUED, RUNNING, SUCCEEDED, FAILED) and failure reason;
  - provider cost and usage when reported;
  - times.
  
  A database CHECK keeps every generation non-authoritative [REC].
- **Pipeline** [REC]: existing job, adapter and outbox architecture, on a `design` queue.
  - A demo provider runs in development and tests [PD-16]. The production provider is AQ-15.
  - Each output carries a burned-in "Illustrative" mark.
  - Outputs are stored privately and served by presigned URL.
  - Provider cost and usage are recorded per generation.
  - A paid credit returns automatically when its generation fails (F-07).
- **Never authoritative.** Never a structural, permit or working drawing. Never a BOQ or RFQ source. Never attachable to a Build Plan, quote or RFQ. A homeowner can mark a design as a reference for the authoritative design workflow (CD-25 method, unchanged in 33.6), and that is all [PD-05, PD-06].
- **Privacy** [REC, from 33.6]. Only design facts and style words go to the provider. Never name, contact details, address, coordinates or locality. Uploads stay out until F-08 is decided.

## Build Plan position (corrected)

- **Optional service.** [PD-13, PD-25] The Build Plan is an authoritative downstream artefact and package service, not the centre of the product and not a reason to route everything through Plan2Build.
- **Inputs.** It may draw on Plan2Build professionals, homeowner-provided information, outside professionals' work (for example an outside architect's drawings) and approved design inputs.
- **Rules.** Issued versions are immutable; changes make a new version. The homeowner formally accepts the issued plan. Structural sign-off (section D) happens before issue where it applies.
- **Specification values.** [PD-14] The S04 master defines criteria. The project value is entered in a Build Plan version and frozen at issue. The RFQ uses the issued, brand-neutral values.
- **RFQ.** [PD-15] It uses authoritative approved information, never AI exploration history. Whether every category's RFQ needs a Build Plan is F-10.

## Conflicts with sources and earlier designs

None of these is rewritten silently. Each source keeps its text, with a dated note pointing here.

| # | Source or earlier design | Confirmed decision | Where the note is |
|---|---|---|---|
| X-01 | 33.6: image generation only for views of an approved plan; S05 section 9, S09, S11 exclude AI design | [PD-05] AI concepts from the requirement are a free entry feature, illustrative only; 33.6 still governs the authoritative path | IHB 32.6 |
| X-02 | CD-25: concept design "inside the package" | Free AI images are not the CD-25 concept design, which stays a package service | IHB 32.6 |
| X-03 | CD-05: "One package holds everything" | [PD-22] AI credits are a separate product; the package still holds the services | IHB 32.6 |
| X-04 | B-01 (Chirag): workspace only after acceptance | [PD-21] Free dashboard on submission; review in the background gates only the package | IHB 32.6, 34 |
| X-05 | CD-26 (Sakha, unreviewed): a listing lead without the package | [PD-19] Formal connection and leads need the package | IHB 32.6; PRO 43 |
| X-06 | CQ-01: "what the single package costs" | [PD-23] Price by configurable rules from project characteristics | IHB 32.6 |
| X-07 | PRO 6.1, S03 7.3: the structural engineer is Plan2Build-retained and never quotes to homeowners | [PD-08, PD-24] Structural engineers are discoverable; any qualified engineer may sign where the rules permit | IHB 32.6; PRO 43 |
| X-08 | S13 premium listing tiers; S23 featured professionals | [PD-08, PD-18] No paid placement; Champions Club is not a tier | IHB 32.6 |
| X-09 | STATE_MODEL 8: no homeowner acceptance | [PD-13] Homeowner formally accepts | IHB 32.6 |
| X-10 | Ruling 2.6, built per A/B/C | [PD-09] One package; A/B/C never gate | IHB 32.6 |
| X-11 | 33.6 privacy rule | Uploads to the provider: F-08 | this document |
| X-12 | CQ-03, CQ-04 open | [PD-10, PD-11] Settled for the POC | IHB 32.6 |
| X-13 | PRO 44.8, STATE_MODEL 4, DATA `club_memberships` and `club_reviews`, API section 8 `/pro/club/*`, `/ops/club/*` (Sakha's CD-27 design): apply, curate, admit, classes, six-monthly reviews | [PD-18] Champions Club is the name for approved listed professionals; no membership system | PRO 44.8, STATE_MODEL 4, DATA, API 8 |
| X-14 | DATA and STATE_MODEL design attributes `projects.path` and `projects.contractor_route` (OWN, CLUB, NONE): one route per project (not built) | [PD-17] Modular: needs and engagements per category | DATA, STATE_MODEL 5 |
| X-15 | RECOMMENDATION_ENGINE eligibility "Champions Club member" | [PD-18] Read as "LISTED for the category" | RECOMMENDATION_ENGINE |

## Impact (summary)

**Stays:** all of Slice 1 and Slice 2, as listed in version 1.0. Nothing is reverted.

**Reshape before or inside 3.0:**
1. The project page waits for ACCEPTED. It becomes the free dashboard on submission, with the background-review notice.
2. A/B/C appear as "Package A/B/C" with a `purchased` flag. They become groups: remove `purchased`, `purchased_packages()` and the "once this package is purchased" notice. [REC] Rename `spec_packages` to `spec_groups` while no production data exists.
3. The single long project page becomes a dashboard layout. Stages move to Construction and lines to Specification.

**Later reshapes:** the `engineer_signoff` copy on project lines goes to per-Build-Plan-version sign-off, by any qualified signer (3.5). The stage order used for dates is fixed with the schedule work.

**Database** [REC]:
- AI design (3.1): generations, prompt templates, quota and credit ledger.
- Professionals (3.2): profiles, categories with listing state, verification records. No club tables.
- Modular core (3.4): `project_service_needs` per category (NEEDED, USING_PLAN2BUILD, USING_OWN, NOT_NEEDED), seeded from the optional `services_needed` answer and editable later. `project_engagements` per category and party: a listed professional, a verified project-only professional, or an outside party recorded by name. Leads, RFQs, quotes, updates, inspections, payment marks and sign-offs all reference an engagement or a category.
- Billing (3.3): offerings, pricing rules, payment modes, instalment plans, orders, invoices, tax configuration, payment attempts and events, refund requests, refunds, billing exceptions, package activation, AI credit purchases.
- The design attributes `projects.path` and `contractor_route` are not built.

**API** [REC]:
- `GET /projects/{id}/overview`.
- Project estimate: `POST` and `GET /projects/{id}/estimate`.
- `GET` and `POST /projects/{id}/designs`, `GET /projects/{id}/designs/{design_id}`, `POST /projects/{id}/designs/{design_id}/reference`.
- `GET /professionals` (free, filtered by category and project fit), `GET /professionals/{id}`.
- Professional registration and the operations approval queue.
- `GET /projects/{id}/offerings` (priced by rules; 409 until eligible); orders, checkout, verified webhook, invoices, refund requests and decisions, reconciliation.
- Service needs and engagements per category.
- The workspace response: `packages` become `groups`, `purchased` removed.

**Frontend** [REC]:
- `/projects/{id}` becomes the dashboard overview: review notice, estimate summary, latest designs, package card, next actions.
- New areas: Requirement, Estimate, Designs, Professionals, Construction (stages), Specification (lines by group), Documents, Package.
- Later: Quotes, Build Plan, Record.
- An area appears only once it has content.

**State models** [REC]:
- Project statuses are unchanged. ACCEPTED means eligible.
- PLANNING starts at package activation, and only for homeowners who take a service that needs planning. Statuses beyond PLANNING (SOURCING, CONTRACTED, BUILDING) are reconsidered in 3.4 so they do not assume one Plan2Build contractor.
- New machines: package activation (C), listing (D), AI generation (E), refund request (REQUESTED → APPROVED → REFUNDED or REFUND_FAILED, or DECLINED), engagement per category (PROPOSED → ACTIVE → ENDED).

## F. Remaining unresolved business decisions

Only open business points. Each has a recommendation.

> **Update (2026-10-05).** F-01, F-02 and F-12 were answered by Chirag in SLICE3_2_READINESS section K0 (D-01, D-02, D-03). F-05, F-06 and F-07 were locked as models in SLICE3_3_READINESS section 0 (L-02, L-03, L-04); their values (prices, instalment shares, tax details, refund wording, the AI credit price) stay open as O-01 to O-12 there. The table below is kept as written.

| ID | Decision | Recommendation | Needed by |
|---|---|---|---|
| F-01 | On a free profile, which details show: name, firm, category, service area, experience, portfolio, registration; and are phone, email and website shown? | Show everything except direct phone, email and website. Contact goes through a Plan2Build connection, which is the package service | 3.2 |
| F-02 | The approval standard for listing, per category (CQ-06): which checks (identity, professional registration, references, site visit, portfolio), periodic re-check, reapplying after rejection | Use the checks already designed in PRO 44.8 as the approval checklist, without any membership. Re-check yearly. Reapply after 6 months | 3.2 |
| F-03 | Outside professionals: may the homeowner add their own architect, engineer or contractor to the project; with what verification and access; does it need the package? | Yes, every category, following the family's-own-contractor pattern (basic verification, project-only access, not listed). Adding them with platform access is a package service. Recording a name only is free | 3.4 |
| F-04 | Structural signer outside Plan2Build: how registration is confirmed and how the sign-off is captured; what a sign-off records (also SLICE3_READINESS D3-11) | Registration number and certificate recorded and checked by operations before the sign-off counts. The engineer signs on the platform with project-only access and OTP, or operations attach a signed sheet. Record: signer, registration, line, Build Plan version, the text signed, time | 3.5 |
| F-05 | What makes a project eligible for the package (the review checklist) | Operations judgement with a recorded reason, against a short written list: new home, in Raipur, facts plausible, review flags resolved | 3.3 |
| F-06 | Commercial values: the POC's pricing characteristics and prices; payment modes per offering; instalment count, triggers and shares; late-instalment handling; which delivered work counts as "substantial" for refunds; tax entity, GSTIN, rate and SAC (accountant) | As configuration only. Development uses marked test values. Late instalment pauses new package services after a grace period you set; delivered work stays available | 3.3 |
| F-07 | AI credits: price (about ₹99 proposed), single credits or bundles, tax, whether a paid credit returns when a generation fails | Single credits first. A failed paid generation returns its credit automatically | 3.3 |
| F-08 | DECIDED for the first version (PD-27, 2026-10-05; built in Slice 3.1). Was: AI design content: exterior and interior views only, or floor-plan-like images too; may uploaded plans or photos go to the provider; limits per account | Views only, no floor-plan pictures. No uploads to the provider in the first version. A configured projects-per-account limit and daily caps | 3.1 |
| F-09 | Before the package is active, are each line's criteria headings ("Grade, exposure class, slump range") shown? | OPEN. Built as a configuration setting (`P2B_SPEC_CRITERIA_BEFORE_PACKAGE`), not a canonical rule. The setting starts at "hidden", which follows ruling 2.6; project values only in the issued Build Plan | Configurable in 3.0 |
| F-10 | Which RFQs need an issued Build Plan: a contractor RFQ only, with other categories (architect, engineer, interior) using the requirement brief? Is the RFQ issued only from a homeowner-accepted plan, and does the baseline lock at acceptance? | Contractor RFQ needs an issued and accepted Build Plan (which may be built from an outside architect's drawings). Other categories use the requirement brief. Baseline locks at acceptance | 3.5, 3.6 |
| F-11 | Assurance and inspections when the contractor is outside Plan2Build | Available as a package service whoever the contractor is | Later |
| F-12 | Do professionals pay anything (listing, leads, commission)? S10 and S13 propose fees; the decisions so far say listing is not bought | No professional-side fees in the POC | 3.2 |
| F-13 | When the review closes a project as not eligible, what does the homeowner keep? | Keep read access to the estimate, designs and requirement. No new free generations. Public discovery stays free | 3.0 copy |

Carried over, unchanged: CQ-07 enlistment class, CQ-09 quote dates, CQ-12, CQ-13, CQ-22 structural scope, CQ-25 architect path, CQ-26 drawing checker, D3-13 drawing method, D3-15 and D-16 production rate card, D3-16 schedule, D3-17 PDF language.

## G. Revised Slice 3 roadmap

Each step ends with API tests, phone and desktop Playwright with axe, migration up, down and up, and a stop for approval.

| Step | Scope | Needs |
|---|---|---|
| 3.0 Free dashboard and background review | Dashboard layout and navigation; dashboard opens on submission; "Your project is being reviewed by Plan2Build."; NEEDS_INFO and closed notices; A/B/C as groups (rename, flag removed); indicative estimate stored on the project with its rate-card version (DEMO card in development, labelled); package card showing "not yet available" or "available once reviewed" with no purchase | Approval of this document. Uses the F-09 and F-13 defaults |
| 3.1 AI design concepts | Generations, prompt templates, 3 successful free, demo provider, gallery, mark as reference, cost and usage telemetry, caps; paid credits shown as unavailable until 3.3 | F-08 |
| 3.2 Professional registration, approval and free discovery | Registration on the professionals host; operations approval queue; listing states; Champions Club label on listed profiles; free directory filtered by category and project fit | F-01, F-02, F-12 |
| 3.3 Billing core | Package eligibility (ACCEPTED), pricing rules, payment modes, Razorpay test mode, verified webhooks, invoices with tax configuration, reconciliation, refund requests and decisions, package activation; AI credits on the same core | F-05, F-06, F-07; Razorpay test account |
| 3.4 Modular services and connection | Service needs per category; engagements (listed, project-only, outside); package-gated connection and leads; quote-holder review | F-03 |
| 3.5 Authoritative design and Build Plan | Design workflow (CD-25), drawings check, specification values, BOQ, structural sign-off by any qualified engineer, issue, homeowner acceptance, PDF | F-04, F-10, CQ-22, CQ-26, D3-13, D3-15, D3-16, D3-17 |
| 3.6 RFQ to selection, per category | RFQ, quotes, comparison, recommendation, selection | F-10, CQ-09 |
| Later | Execution with Plan2Build and outside actors, inspections where applicable, handover, build record | F-11, CQ-11 to CQ-16 |

## H. Verdict

**READY FOR SLICE 3.0** once Chirag approves this document. No open business decision blocks 3.0:
- the review placement is settled (PD-21);
- discovery is not part of 3.0;
- the package card shows no purchase;
- F-09 stays OPEN: 3.0 builds it as a setting that starts at "hidden" (ruling 2.6), so Chirag's answer is a configuration change, not code; F-13 stays OPEN: 3.0 keeps the read-only view a closed project already has and adds nothing new for it.

**NOT READY** for 3.1 to 3.6 until the decisions listed against each step are made.
