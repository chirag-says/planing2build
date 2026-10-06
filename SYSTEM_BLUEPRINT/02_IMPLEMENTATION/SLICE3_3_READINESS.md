# Plan2Build: Slice 3.3 readiness (package eligibility, billing core, AI credits)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/SLICE3_3_READINESS.md` |
| Version | 1.0 (2026-10-05) |
| Status | Approved by Chirag on 2026-10-05; Slice 3.3 built and verified the same day (section P); closed after the final verification run |
| Baseline | `PRODUCT_FLOW_RECONCILIATION.md` v2.0 (PFR); PD-01 to PD-27 (IHB_FLOW 32.6); Slice 3.2 closed (SLICE3_2_READINESS K0 and M) |
| Decisions locked in this pass | Chirag, 2026-10-05: F-05 (eligibility), F-06 (package commercial model), F-07 (AI credits), package states, modularity rule, Razorpay safety, no invented commercial values, R2 CORS launch gate. Recorded in section 0 |
| Sources read | IHB_FLOW 32 and 34; PROFESSIONALS_FLOW 22, 42 to 44; PFR (all); SLICE3_READINESS; SLICE3_2_READINESS; FOUNDATION_PLAN 4f to 4h; architecture INTEGRATION 3 and 4, DATA 4.13 and 4.15, API 7 and 22, STATE 15, SECURITY, EVENT, DOMAIN, ADR-020, ARCHITECTURE_BASELINE, TESTING, OBSERVABILITY, CLOUD, COST_MODEL; the code |
| Markers | **[LOCKED]** Chirag's decision of 2026-10-05 for 3.3. **[PD]** an earlier product decision. **[SOURCE]** a source or approved architecture settles it. **[REC]** Sakha's recommendation, not approved. **[OPEN]** undecided; a configuration value or a question. **[SUPERSEDED]** an older design this document replaces |

No code changed in this readiness pass.

## 0. Decisions locked on 2026-10-05

| ID | Decision [LOCKED] |
|---|---|
| L-01 | Slice 3.2 is closed. The professional model stays as built: modular aggregator, free discovery, listed professionals only, Champions Club as a name, no membership, no paid listing, no ratings, category-level listing, mixing Plan2Build and outside professionals, no one-project-one-contractor assumption |
| L-02 (F-05) | ACCEPTED means: "Plan2Build has completed its initial service-eligibility review and may offer the Plan2Build package for this project." Initial POC checks: new individual house; within the current service geography and capability; requirements sufficiently complete; material review flags resolved; information plausible enough to proceed. ACCEPTED approves no design, budget, professional, category obligation or whole project. The checklist is configurable and auditable |
| L-03 (F-06) | One modular package. Price server-side, versioned, configurable, based on project characteristics, stamped with the rule version, never from the browser. Razorpay; 100% upfront or configurable instalments, with one simple initial instalment configuration; ACTIVE only after verified payment; the browser callback is never authoritative. Refunds: requestable before substantial work, operations or admin review after it, reason and authorised staff action on every decision, refunded through Razorpay, wording in final terms. Applicable tax, invoice issued, entity, GSTIN, rate and SAC from the accountant's configuration. Never construction money |
| L-04 (F-07) | 3 successful generations free per project; more are AI credits, separate from the package; single-generation credits only, no bundles; configurable price (about ₹99 is not a price); a failed paid generation returns its credit; credits use the same billing core |
| L-05 | Package states NOT_ACTIVE → ACTIVE, later ACTIVE → CANCELLED or REFUNDED. LAPSED only if a late-payment rule needs it. Project statuses and professional engagements do not depend on the package globally |
| L-06 | "Package purchased" means the homeowner can use the paid coordination, comparison and assurance services they choose. It never means the whole project enters a Plan2Build construction journey. Professional relationships stay per service category |
| L-07 | GST rate, GSTIN, SAC, final price, instalment percentages and refund legal wording are configuration or open values until supplied |
| L-08 | Production R2 CORS allows the exact approved browser origins for homeowner and professional uploads; no wildcard; a launch dependency |

These settle F-05, F-06 (model; values stay open, section L) and F-07 (model; price stays open) in PFR section F. PFR's table still shows F-01, F-02 and F-12 open; SLICE3_2_READINESS K0 answered them (D-01, D-02, D-03). The PFR and IHB 32.5 registers (CQ-01, CQ-03, CQ-04 still "Not yet asked") need a recorded update when this document is approved; this pass does not edit them.

## A. Current billing-related implementation inventory

Nothing takes money today. What exists:

| Area | As built | File |
|---|---|---|
| Package availability | `PackageAvailability` NOT_SUBMITTED, UNDER_REVIEW, ELIGIBLE, NOT_ELIGIBLE from the project status; ELIGIBLE for ACCEPTED and later statuses | `core/vocabulary.py`, `projects/service.py` (`PACKAGE_AVAILABILITY`) |
| Package active | `package_active(project)` returns `False` for every project | `projects/service.py` |
| Package on the API | `GET /projects/{id}` returns `package.availability` and `purchasable: false` | `projects/schemas.py` |
| Package card | Overview card with modular copy, no price, no button: "Buying it online is not open yet." | `messages/en.json` (Dashboard) |
| Criteria gating | Workspace criteria shown when `spec_criteria_before_package` (F-09 setting, default false) or `package_active` | `projects/review.py`, `core/config.py` |
| Acceptance | `accept_project` moves SUBMITTED → ACCEPTED and creates stages and lines. It records no eligibility checklist; the decision is one claim-holder action with an audit row | `projects/review.py` |
| Review flags | PROPERTY_TYPE_OTHER, CONSTRUCTION_STARTED raised from answers | `core/vocabulary.py`, `catalog/questions.py` |
| AI designs | `design_generations.funding` FREE or PAID with CHECK "PAID names `credit_ref`"; every row today is FREE; `paid_generations_available` is a literal false; quota settings `ai_free_generations_per_project` 3 and daily caps | `designs/models.py`, `designs/schemas.py`, `core/config.py` |
| Stage flag | `is_payment_milestone` on stage masters and instances: tracking of construction payments between homeowner and contractor, no amounts | `catalog/models.py`, `construction/models.py` |
| Professional GSTIN | Optional detail on a professional's business document; unrelated to Plan2Build invoices | `professionals/schemas.py` |
| Idempotency, outbox, jobs, audit, MFA, rate limits | Built and reused by every slice | `core/` |
| Billing module, Razorpay adapter, money tables, webhooks, invoices | Not present. `p2b.billing` does not exist; `integrations/` has no payment adapter | |

Designed but not built (architecture, 2026-10-03): DATA 4.13 billing tables, API 7 routes, STATE 15 machines, INTEGRATION 4 Razorpay flow. Section H lists what this document keeps and replaces.

## B. Final package commercial model

| Rule | Model | Marker |
|---|---|---|
| What is sold | One offering, code `P2B_PACKAGE`. Buying it gives access to the package services the homeowner chooses (PD-19: formal connection and leads, RFQ, quote coordination, comparison and review, coordination, assurance where they apply). Nothing is compulsory; buying commits to nothing else | [LOCKED] L-03, L-06; [PD] PD-09, PD-17, PD-19, PD-20 |
| Who may buy | The project owner, for one project, when the project is ELIGIBLE (ACCEPTED or later, never CANCELLED). Household members cannot pay until OQ-027 decides household permissions | [LOCKED] L-02; [SOURCE] SLICE3_READINESS D3-06 |
| One active package per project | At most one ACTIVE entitlement and one open package order per project. A refunded or cancelled package may be bought again through a new order at the then-current version and price | [REC] |
| Price | Computed by the server from an ACTIVE pricing-rule version and the project's submitted requirement (section B.1). The browser sends no amount. The order stores the inputs, the rule version and the result; it never changes after creation | [LOCKED] L-03 |
| Payment modes | FULL (100% upfront) always available on an offering version; INSTALMENTS only when the offering version names an instalment plan version | [LOCKED] L-03 |
| Initial instalment configuration | One plan shape: N instalments, the first due when the order is created and the rest due a configured number of days after activation. Shares in basis points summing to 10000. Count, shares and days are configuration with no default value; until they are supplied, offering versions offer FULL only | [LOCKED] L-03; values [OPEN] |
| Activation | The entitlement becomes ACTIVE when the first due (FULL: the whole order) is captured and verified (section D). Never on the browser callback | [LOCKED] L-03 |
| Instalments and construction | Instalment triggers never point at construction stages. The older ON_STAGE trigger and "one invoice per milestone" (DATA 4.13, STATE 15, CD-05) are dropped: they tie the fee to a construction journey the homeowner may not run through Plan2Build | [LOCKED] L-06; [SUPERSEDED] CD-05 instalment timing |
| Project status | Activation does not move the project. ACCEPTED stays ACCEPTED. PLANNING starts later, only when a homeowner starts a service that needs planning (3.4 and later). `billing.package_paid → PLANNING` (EVENT, DOMAIN, STATE 5) is superseded | [LOCKED] L-05; [PD] PFR 249 |
| What reads the package | Package-gated services check `package_active(project)`; criteria visibility keeps the F-09 setting OR the active package | [SOURCE] as built |
| Terms | Each offering version names the terms version shown at checkout; the order stamps it. Wording is legal content | [LOCKED] L-03; wording [OPEN] |

### B.1 Pricing rules

Pricing is one small engine driven by data [REC]:

- A pricing-rule version holds a currency, a base amount and an ordered list of adjustments. Adjustment kinds: `BAND` (amount by the band a numeric characteristic falls in) and `ADD_IF` (fixed amount when a characteristic equals a value). Results are rounded to whole rupees and clamped to an optional minimum and maximum.
- Characteristics come from an allow-list read from the submitted requirement: `built_up_area_sqft`, `floors`, `basement`, `quality_tier`, `property_type`. Which of these the POC uses, and every amount, is configuration [OPEN]. Adding a characteristic is a code change reviewed like any other; adding or changing amounts is a new version.
- A rule version is immutable once published (ADMIN with MFA). Publishing runs a preview against fixtures and rejects negative or missing amounts.
- If a characteristic the active rule needs was answered "Not sure yet" (built-up area allows it), the price cannot be computed. The purchase screen says so and offers to update the requirement [REC]; whether operations may quote such projects by hand is [OPEN] (L-08 in section L).
- Prices in development and staging are marked TEST in the version note and refused by production settings, as the DEMO rate cards are today [REC].

## C. AI-credit commercial model

| Rule | Model | Marker |
|---|---|---|
| Free generations | 3 successful per project (setting `ai_free_generations_per_project`); failures never count | [LOCKED] L-04; [PD] PD-22 |
| What is sold | Offering `AI_CREDIT_SINGLE`: one credit = one generation. No bundles | [LOCKED] L-04 |
| Separate from the package | Its own offering, orders and invoices; holding the package gives no credits and buying credits gives no package access | [LOCKED] L-04 |
| Price | Pricing-rule version with a base amount only; value [OPEN] (about ₹99 is a proposal, never seeded) | [LOCKED] L-04 |
| Payment | FULL only, same orders, checkout, webhook, invoice and refund core | [LOCKED] L-04 |
| Grant | A captured, verified payment writes one GRANT entry to the credit ledger. Before that nothing is usable | [LOCKED] L-04 |
| Holder | The account that paid. Usable on any project that account owns [REC]; per-project credits are the alternative [OPEN] |
| Use | Once a project's free generations are used, a generation request carries `use_credit: true` explicitly; the server consumes one credit in the same transaction that creates the generation (`funding = PAID`, `credit_ref` = the ledger entry). No silent spending | [REC] |
| Failure | A PAID generation that ends FAILED or STALE writes a RETURN entry automatically, once per generation (UNIQUE) | [LOCKED] L-04 |
| Daily caps | The PD-27 caps (3 projects, 10 successful generations per account per rolling 24 hours) apply to paid generations too, as a cost and abuse guard [REC]; [OPEN] if Chirag wants paid generations outside the caps |
| Expiry | None [REC] |
| Refund | Only unused credits; a refund writes a REVOKE entry; the balance never goes below zero | [REC] |

## D. Payment state model

Five separate records; each has its own machine through `TransitionTable`, and every transition writes audit and outbox in the same transaction.

**Order** (the immutable commercial record):
`AWAITING_PAYMENT → PART_PAID → PAID`; `AWAITING_PAYMENT → PAID` (FULL); `AWAITING_PAYMENT → CANCELLED` (abandoned or expired before any capture; a scheduled sweep after a configured period [OPEN], or the homeowner starting a different payment mode); `PAID | PART_PAID → REFUNDED` (everything captured is refunded) or `PARTLY_REFUNDED`. Amounts, tax, rule versions and buyer details never change after creation (database trigger allows only state, version and timestamps).

**Payment due** (one per instalment, or one for FULL):
`DUE → PAID`; `DUE → CANCELLED` (order cancelled, or the package ended before it fell due). Overdue is derived from `due_at`, not stored.

**Payment attempt** (one Razorpay order each):
`CREATED → CAPTURED | FAILED | EXPIRED`. The browser hint never changes it. A verified `payment.captured` or `order.paid`, or a verified server-side fetch, moves it to CAPTURED. `payment.authorized` is stored and not acted on: orders are created with automatic capture [REC], and an authorised payment Razorpay does not capture is refunded by Razorpay; reconciliation records it as an exception. This replaces the undocumented PENDING_CONFIRMATION and PENDING states (INTEGRATION 4, STATE 15).

**Package entitlement** (per project):
`NOT_ACTIVE` (no row) `→ ACTIVE` (first due captured) `→ CANCELLED` (staff decision with reason, MFA) or `→ REFUNDED` (a refund decision that ends the package). Stored, with append-only history, not derived from invoices: refunds and cancellations are decisions, not arithmetic. LAPSED is not added; section L asks whether late instalments need it [LOCKED] L-05.

**AI credit ledger** (per account): append-only entries GRANT (+1, from a captured order), CONSUME (−1, names the generation), RETURN (+1, failed paid generation), REVOKE (−1, refund of an unused credit). Balance is the sum; CHECK through a locked running balance that it never goes negative.

Rules that span them:

- A capture for an order that is CANCELLED, or a second capture for a due already PAID, is never applied: it becomes a billing exception (DUPLICATE_CAPTURE, CAPTURE_AFTER_CANCEL) for operations to refund.
- Amount and currency of every capture must equal the attempt's amount; otherwise AMOUNT_MISMATCH, stored, not applied, operations alerted at page level (OBSERVABILITY 46).
- Order-level processing is serialised with an advisory lock on the order, so webhook processing, reconciliation and refunds never interleave.

## E. Refund model

| Rule | Model | Marker |
|---|---|---|
| Who may ask | The homeowner (for their order) or operations on their behalf, with a reason | [LOCKED] L-03 |
| Request | `REQUESTED → APPROVED → PROCESSING → REFUNDED | FAILED`, or `REQUESTED → DECLINED`. FAILED may be retried by staff | [PD] PFR 250, extended |
| Decision | Always a staff action with reason: OPS or ADMIN with fresh MFA. The decision records the approved amount (≤ captured minus already refunded), whether the package ends (ACTIVE → REFUNDED) or stays, and for credits how many unused credits are revoked. Append-only | [LOCKED] L-03 |
| Before substantial work | The request is in policy; staff approve it with a reason | [LOCKED] L-03 |
| After substantial work | Case review by OPS or ADMIN; the decision may be partial or declined, with a reason the homeowner sees | [LOCKED] L-03 |
| "Substantial work" | Not defined [OPEN]. The model keeps a per-entitlement record of package services delivered (first lead sent, first RFQ issued, first comparison delivered, first inspection), written by those services when they exist (3.4 onwards). In 3.3 no package service exists, so every refund is "before substantial work" unless staff record otherwise with a reason | [REC] |
| Execution | A job calls the Razorpay Refunds API with `notes.refund_id` = our id after checking for an existing refund on the payment; `refund.processed` completes it, `refund.failed` fails it; reconciliation covers lost events | [SOURCE] INTEGRATION 72 |
| Documents | A credit note against the original invoice for each refund, from the tax configuration [REC]; format with the accountant [OPEN] |
| Wording | Customer-facing refund terms are legal content, versioned and stamped on the order [OPEN] |
| Never | Automatic refunds, refunds to any other instrument, refunds of construction money (none is ever received) |

## F. Tax and invoice model

| Rule | Model | Marker |
|---|---|---|
| Tax configuration | Versioned rows published by ADMIN with MFA: legal entity name and address, GSTIN, state code, per offering kind the SAC and tax components and rates, whether prices include tax, invoice series format. Every field starts empty; billing refuses to create orders while no complete ACTIVE version exists. Production refuses versions marked TEST | [LOCKED] L-03, L-07 |
| Tax on an order | Computed by the server from the ACTIVE tax version at order creation: taxable value, components (for example CGST and SGST, or IGST) and amounts, rounded per the configuration. Stored on the order and copied to each invoice. Which components apply (place of supply from the buyer's state) is the accountant's rule [OPEN] |
| Buyer details | Name, billing address and state collected at checkout, optional buyer GSTIN if the accountant wants it [OPEN]; stored as a snapshot on the order (personal data, P2) | [REC] |
| Invoice | Plan2Build's own document, never Razorpay's invoice product. Issued for each captured due, after verified capture, so unpaid checkouts never consume numbers [REC]. Whether the accountant needs a document before payment (proforma) or a receipt voucher for advances is [OPEN] |
| Numbering | Gapless sequence per series and financial year, assigned in the issuing transaction from a locked counter row; UNIQUE (series, number). Fixes the global UNIQUE in DATA 4.13 | [SOURCE] INTEGRATION 73; [REC] |
| Lines and tax lines | Invoice lines (description, SAC, quantity, taxable value) and invoice tax lines (component, rate, amount). Immutable | [LOCKED] user list |
| Rendering | PDF rendered by a job, stored privately in R2, served by a logged signed link to the owner and staff | [SOURCE] INTEGRATION 73, EVENT render queue |
| Retention | Financial class, 7 years after the financial year, until the accountant confirms (AQ-11) | [SOURCE] DATA 451 |

No rate, GSTIN, SAC, entity or series value appears in code, migrations or seeds.

## G. Razorpay architecture validation

| Check | Architecture today | Verdict for 3.3 |
|---|---|---|
| Server creates the order | Yes: `POST /invoices/{id}/checkout` creates a Razorpay order with amount in paise, INR, receipt = our code (INTEGRATION 45 to 48; ADR-020) | Kept. The Razorpay order amount comes from our due, never from the request. One Razorpay order per attempt; `provider_order_id` UNIQUE; at most 5 attempts per due per hour (INTEGRATION 75) |
| Browser callback is a hint | Yes (INTEGRATION 58; SECURITY 145) | Kept, with one addition [REC]: the hint endpoint verifies the checkout signature (HMAC of order id and payment id with the key secret) and then queues an immediate server-to-Razorpay fetch of that order's payments. The fetched record, authenticated with our API key, is the authority, exactly as reconciliation is; the hint itself changes nothing. A forged hint queues a fetch that finds no capture |
| Webhook signature | HMAC-SHA256 of the raw body with the per-environment webhook secret, constant-time compare; 401 and a security event when invalid (SECURITY 173; INTEGRATION 22) | Kept. Raw body read before parsing; 256 KB cap; no cookies or CSRF; T4 rate limit |
| Event idempotency | UNIQUE provider event id (INTEGRATION 67; DATA 261) | Kept as UNIQUE (`provider`, `provider_event_id`); a replay returns 200 with no effect |
| Webhook processing | Conflict: a job (INTEGRATION 22 and 55, SECURITY 177) versus inline (API 118, DATA 410) | Resolved: store and return 200, then a job processes the event under the order lock. Same code path as reconciliation |
| Amount verification | Amount must equal the invoice due or AMOUNT_MISMATCH (INTEGRATION 64) | Kept, against the attempt and due, plus currency and order id |
| Reconciliation | Daily job (EVENT 262) but 30-minute checks promised (INTEGRATION 70) | Resolved [REC]: a frequent job (every 15 minutes) checks open attempts older than 30 minutes and processing refunds; the daily job matches every capture of the last 3 days. Manual trigger for ADMIN. Alerts as OBSERVABILITY 46 |
| Capture mode | Not specified | Automatic capture at order creation [REC]; authorised-only payments handled as in section D |
| Package activates only on verified capture | Yes in principle (STATE 357) | Kept; the entitlement transition happens only in the processing job |
| AI credit usable only after verified payment | Not designed | The GRANT entry is written only by the processing job on a verified capture |
| Card data | Not mentioned (no PCI section) | Checkout.js hosted by Razorpay: card, UPI and bank details never touch Plan2Build; we store payment ids, method and amounts only. State this in SECURITY as the PCI position [REC] |
| CSP | `connect-src` and `frame-src` name `api.razorpay.com`; no script source for Checkout (SECURITY 163) | Launch gate N-07: the script, frame and connect sources Razorpay documents for Standard Checkout, checked against Razorpay's documentation at implementation time |
| Local development | Webhooks through a tunnel (ENVIRONMENT 154) | Provider interface with a `fake` adapter for tests and local, and Razorpay test mode in staging; production refuses `fake` [REC], as the AI image provider does |
| Not used | Payment links, subscriptions, Route, escrow (INTEGRATION 78; ADR-020) | Kept |

### G.1 Where construction money is prohibited

Product: CD-01, CD-09 (IHB_FLOW 32), PD-01 (IHB 4294), IHB 34 steps 8 and 14, PFR 19 and 92, PROFESSIONALS_FLOW 22.1 and 44.1 rule 2. Architecture: INTEGRATION 9, 29, 34, 78; ADR-020 11 and 17; DATA 21 and 226; ARCHITECTURE_BASELINE 81 and 162; STATE 291 and 296; DOMAIN 40 and 205; API 206.

Enforcement in 3.3 [REC]:

1. Offering kinds are a closed set, PACKAGE and AI_CREDIT, by database CHECK. Adding a kind is a migration Chirag approves.
2. No billing endpoint accepts an amount; orders reference an offering version only.
3. Billing tables have no column referring to a professional, quote, contract, lead, milestone or stage. Import-linter forbids `p2b.billing` importing `p2b.professionals` or `p2b.construction`.
4. `payment_milestones` (later slice) keeps no amount column.
5. Razorpay Route, escrow, payment links and subscriptions stay unused.
6. Tests assert 1 to 3; the terms say Plan2Build never collects construction payments.

Drift to correct when the architecture is next revised: EVENT 182 (`milestone.due` "with amount from the contract") contradicts CD-09.

## H. Database model

Module `billing` owns all commercial configuration and records [REC]; this replaces `offerings` in `catalog` (DATA 133, not built). `projects` owns the eligibility assessment. Money is `numeric(14,2)` INR with a currency column; paise only on the wire. Every configuration version is immutable once published; every record table is append-only or allows only state changes, enforced by trigger as in earlier slices.

| Table | Purpose and key columns | Rules |
|---|---|---|
| `eligibility_checklist_versions` | `version`, `status` (one ACTIVE), `items` JSONB (id, label, help) | Seeded v1 with the five L-02 checks; ADMIN publishes new versions |
| `eligibility_assessments` | `project_id`, `checklist_version_id`, `results` JSONB (item, outcome PASSED or FAILED, note), `decision` ACCEPT or CANCEL, `assessed_by`, `assessed_at` | Append-only; accept needs every item PASSED |
| `offerings` | `code` PK, `kind` PACKAGE or AI_CREDIT (CHECK), `name` | Seeded `P2B_PACKAGE`, `AI_CREDIT_SINGLE` |
| `offering_versions` | `offering_code`, `version`, `status` (DRAFT, ACTIVE, RETIRED; one ACTIVE), `pricing_rule_version_id`, `payment_modes`, `instalment_plan_version_id`, `terms_version`, `published_by`, `published_at` | Immutable after publish |
| `pricing_rule_versions` | `offering_code`, `version`, `rule` JSONB (base, adjustments, rounding, min, max), `currency`, `is_test`, `note` | Immutable after publish |
| `instalment_plan_versions` | `version`, `instalments` JSONB (number, share in basis points, due rule ON_ORDER or DAYS_AFTER_ACTIVATION with days) | Shares sum to 10000; immutable |
| `tax_configuration_versions` | entity name, address, GSTIN, state code, per offering kind SAC and components with rates, `prices_include_tax`, invoice series format, `is_test` | Immutable; complete before ACTIVE |
| `orders` | `code`, `buyer_user_id`, `project_id` (NULL for credits, or the project it was bought from), `offering_version_id`, `kind`, `quantity` (1), `pricing_inputs`, `pricing_rule_version_id`, `subtotal`, `tax` JSONB, `total`, `currency`, `payment_mode`, `instalment_plan` snapshot, `tax_configuration_version_id`, `terms_version`, `buyer` snapshot, `state`, `version` | Amounts immutable; one open PACKAGE order per project (partial UNIQUE) |
| `payment_dues` | `order_id`, `sequence`, `amount`, `tax`, `due_rule`, `due_at`, `state`, `paid_at` | UNIQUE (`order_id`, `sequence`); amounts immutable |
| `payment_attempts` | `due_id`, `provider`, `provider_order_id`, `amount`, `currency`, `state`, `expires_at` | UNIQUE (`provider`, `provider_order_id`) |
| `payments` | `attempt_id`, `provider`, `provider_payment_id`, `amount`, `method`, `captured_at`, `fee`, `tax_on_fee` | UNIQUE (`provider`, `provider_payment_id`); append-only |
| `payment_events` | `provider`, `provider_event_id`, `event_type`, `payload` (minimal fields), `signature_valid`, `received_at`, `processed_at`, `result` | UNIQUE (`provider`, `provider_event_id`); only `processed_at` and `result` may be set, once |
| `invoices` | `series`, `financial_year`, `number`, `kind` TAX_INVOICE or CREDIT_NOTE, `original_invoice_id`, `order_id`, `due_id`, `payment_id` or `refund_id`, seller and buyer snapshots, `taxable_total`, `tax_total`, `total`, `issued_at`, `document_id` | UNIQUE (`series`, `financial_year`, `number`); immutable |
| `invoice_lines` | `invoice_id`, `description`, `sac`, `quantity`, `taxable_value` | Immutable |
| `invoice_tax_lines` | `invoice_id`, `component`, `rate`, `amount` | Immutable |
| `invoice_sequences` | `series`, `financial_year`, `next_number` | Row-locked counter |
| `refund_requests` | `order_id`, `payment_id`, `amount_requested`, `reason`, `requested_by`, `requested_role`, `state` | |
| `refund_decisions` | `request_id`, `decision`, `approved_amount`, `ends_package`, `credits_revoked`, `reason`, `decided_by`, `role`, `decided_at` | Append-only; MFA checked at the endpoint |
| `refunds` | `decision_id`, `payment_id`, `amount`, `provider_refund_id`, `state`, `credit_note_id` | UNIQUE (`provider`, `provider_refund_id`) |
| `package_entitlements` | `project_id` (UNIQUE), `order_id`, `state`, `activated_at`, `ended_at` | One per project; history below |
| `package_entitlement_history` | `entitlement_id`, `from_state`, `to_state`, `reason`, `actor_user_id`, `actor_role`, `at` | Append-only |
| `package_service_usage` | `entitlement_id`, `service`, `first_used_at`, `ref` | For the substantial-work question; written by later slices |
| `ai_credit_ledger` | `account_user_id`, `entry` GRANT, CONSUME, RETURN, REVOKE, `quantity`, `order_id`, `generation_id`, `refund_id`, `balance_after`, `at` | Append-only; UNIQUE (`generation_id`, `entry`); `balance_after` ≥ 0 |
| `billing_exceptions` | `kind` (AMOUNT_MISMATCH, UNKNOWN_ORDER, DUPLICATE_CAPTURE, CAPTURE_AFTER_CANCEL, AUTHORISED_NOT_CAPTURED, REFUND_MISMATCH, MISSING_EVENT), refs, `expected`, `observed`, `state`, `resolution`, `resolved_by` | Audited resolution |

Changes outside `billing`: `design_generations.credit_ref` points at the ledger CONSUME entry (the column exists); `projects` gains the assessment table; no `projects` column for package state or route (L-05, L-06).

Replaced from DATA 4.13: `package_purchases` (becomes `orders` plus `package_entitlements`), `instalment_schedules` (becomes `payment_dues` with no ON_STAGE trigger), `receipts` (invoices are the receipts), `offerings.price` and `tax_rate` (become versioned rules and tax configuration).

## I. API model

Owner routes use the homeowner session; every POST that creates or transitions takes `Idempotency-Key`.

| Route | Actor | Request | Effect |
|---|---|---|---|
| `GET /projects/{id}/package` | owner | none | Availability; entitlement state; when eligible, the offer: offering version, computed price with tax breakdown, payment modes, instalment preview, terms version; open order |
| `POST /projects/{id}/package/orders` | owner | `offering_version_id`, `payment_mode`, `buyer`, `accept_terms_version` | Order and dues with server price. 409 not eligible, active entitlement, open order, or stale offering version; 422 price inputs missing; 503 no complete tax configuration |
| `POST /payment-dues/{id}/checkout` | order buyer | none | Attempt and Razorpay order; returns public key id, provider order id, amount, prefill |
| `POST /payment-attempts/{id}/confirm` | order buyer | Razorpay ids and checkout signature | Verifies the signature and queues an immediate verified fetch; returns the attempt state. Never marks anything paid |
| `POST /webhooks/razorpay` | Razorpay | raw body, signature header | Stores the event, returns 200, queues processing |
| `GET /orders/{id}`, `GET /me/billing` | buyer | none | Orders, dues, attempts summary, invoices, refund requests |
| `GET /invoices/{id}/document` | buyer, staff | none | Logged signed link |
| `POST /orders/{id}/refund-requests` | buyer | `reason` | REQUESTED; operations queue item |
| `GET /me/ai-credits` | account | none | Balance, ledger, the credit offer and price |
| `POST /ai-credits/orders` | account | `offering_version_id`, `buyer`, `accept_terms_version`, optional `project_id` | Credit order, quantity 1 |
| `POST /projects/{id}/designs` | owner | adds `use_credit` (bool) | When free generations are used up and `use_credit` is true, consumes one credit; 409 `NO_CREDIT` otherwise |
| `POST /ops/projects/{id}/accept` | OPS with MFA, claim | adds `checks` (item, outcome, note) for the ACTIVE checklist | 422 unless every item is PASSED; stores the assessment with the decision |
| `GET /ops/billing/orders`, `/ops/billing/orders/{id}` | OPS or ADMIN with MFA | filters | Orders, payments, events summary, invoices, refunds |
| `POST /ops/orders/{id}/refund-requests` | OPS or ADMIN with MFA | `amount`, `reason` | Staff-raised request |
| `POST /ops/refund-requests/{id}/approve`, `/decline` | OPS or ADMIN with fresh MFA | `amount`, `ends_package`, `reason` | Decision; approved refunds run as a job |
| `POST /ops/packages/{project_id}/cancel` | ADMIN with fresh MFA | `reason` | ACTIVE → CANCELLED without a refund |
| `GET /ops/billing/exceptions`, `POST .../{id}/resolve` | OPS or ADMIN with MFA | `resolution`, `reason` | Exception workflow; never edits a payment event |
| `POST /admin/billing/reconcile` | ADMIN with MFA | window | Queues reconciliation |
| `GET`, `POST /admin/billing/{offerings,pricing-rules,instalment-plans,tax-configurations,eligibility-checklists}` and `POST .../{id}/publish`, `POST /admin/billing/pricing-rules/{id}/preview` | ADMIN with fresh MFA | version content | New versions only; publish validates completeness; never edit in place |

Superseded from API 7: `POST /projects/{id}/package/purchase`, `POST /invoices/{id}/checkout`, `GET /offerings/current`, `POST /ops/payments/{id}/refund`.

## J. Frontend routes

| Host | Route | Screen |
|---|---|---|
| Homeowner | `/projects/[projectId]/package` | The offer: what the package gives, modular copy, price with tax breakdown, payment mode, instalment preview, billing details, terms acceptance, pay; "Confirming your payment" after Checkout, polling the order |
| Homeowner | `/projects/[projectId]/package/orders/[orderId]` | Order status, dues, invoices, request a refund |
| Homeowner | `/account/billing` | All orders, invoices and AI credits for the account |
| Homeowner | Designs area (existing) | When free designs are used up: credit balance, "Use 1 AI credit", "Buy 1 AI credit" leading to `/account/ai-credits/buy?project=…` |
| Homeowner | Overview card (existing) | ELIGIBLE: price and "View the package"; ACTIVE: "Package active" |
| Operations | `/projects/[projectId]` (existing) | Eligibility checklist in the accept dialog |
| Operations | `/billing`, `/billing/orders/[orderId]`, `/billing/refunds`, `/billing/refunds/[requestId]`, `/billing/exceptions` | Orders, refund queue and decisions, exceptions |
| Operations (ADMIN) | `/admin/billing` and version editors | Offerings, pricing rules with preview, instalment plans, tax configuration, eligibility checklists; publish with MFA |

All screens follow UI_DESIGN_SYSTEM (shadcn/ui), phone and desktop, axe checked.

## K. Security and idempotency rules

1. Server price truth: the client sends offering version ids and choices, never amounts; orders snapshot every input.
2. Order amounts, tax and versions are immutable by trigger; configuration versions are immutable after publish.
3. Every create or transition POST takes `Idempotency-Key`; outbound Razorpay calls are idempotent through `receipt` and refund `notes`, and refunds check for an existing refund first.
4. Webhooks: raw-body HMAC, per-environment secret, constant-time compare, UNIQUE event id, 200 on replay, 256 KB cap, T4 limit, processing in a job under the order lock.
5. Activation, credit grants and invoice issue happen only in the processing job after a verified capture with matching amount, currency and order.
6. The browser hint triggers a verified fetch at most; it never sets state.
7. Refund decisions, cancellations, exception resolutions and configuration publishing need OPS or ADMIN as listed, with MFA re-verified within the window (SECURITY 78), a reason, an audit row and history.
8. Billing data classes: buyer snapshot P2; payment ids, events and GSTIN P3; never in analytics or logs beyond ids.
9. Only the Razorpay key id reaches the browser; key secret and webhook secret are server secrets per environment.
10. Rate limits: checkout T2 plus 5 attempts per due per hour; webhook T4; order creation T2.
11. No construction money (section G.1).
12. Production refuses the `fake` provider, TEST pricing and TEST tax configuration.

## L. Open decisions that genuinely remain

| ID | Question (on-screen wording would follow its answer) | Recommendation | Blocks |
|---|---|---|---|
| O-01 | Package price: which characteristics, and the amounts | None; Chirag sets them. Development uses marked TEST values | Live payments, not building |
| O-02 | Instalments at launch: count, shares, days after activation; or FULL only | Launch FULL only; add the plan when values exist | Offering INSTALMENTS, not building |
| O-03 | What happens when a later instalment is unpaid | Package stays ACTIVE; operations follow up; no LAPSED until a rule exists | LAPSED state |
| O-04 | What counts as "substantial work" for refunds | The first delivered package service (lead, RFQ, comparison, inspection), recorded per entitlement | Refund policy wording |
| O-05 | Tax: legal entity (ConjunIQ Technologies Private Limited appears in a source; not confirmed as the invoicing entity), GSTIN, SAC, rate, inclusive or exclusive prices, place of supply, invoice timing (after payment, proforma or receipt voucher), series format, retention (AQ-11, AQ-20) | Ask the accountant; nothing invented | Live invoices |
| O-06 | Refund and purchase terms wording | Legal | Live payments |
| O-07 | AI credit: price; per account or per project; inside or outside the daily caps | Per account; inside the caps | Live credits |
| O-08 | Price when a needed characteristic is "Not sure yet" | Ask the family to update the requirement; no manual quotes in the POC | Purchase for those projects |
| O-09 | Razorpay account: entity, KYC, test keys now, live keys and webhook secret later (AQ-09, AQ-35) | Plan2Build company account, Chirag owner plus a second admin | Staging tests (test keys), launch (live) |
| O-10 | Who approves refunds: OPS and ADMIN alike, or ADMIN after substantial work | OPS before, ADMIN after | Refund role check |
| O-11 | Projects already ACCEPTED before the checklist exists | Keep them eligible; mark their assessment "accepted before checklist v1" in history | Migration backfill |
| O-12 | How long an unpaid order stays open before it is cancelled | A setting; value from Chirag | Order sweep |

Still open from PFR and unchanged by 3.3: F-03, F-04, F-09 (criteria before package; setting stays hidden), F-10, F-11, F-13, D-05 (enlistment class), OQ-027 (household payers).

## M. Slice 3.3 implementation order

1. Eligibility checklist: versions, assessment table, accept with checks, operations dialog, backfill marker (O-11).
2. Billing module skeleton: vocabulary, import-linter rules (G.1), payment gateway interface with `fake` and Razorpay adapters, settings, production refusals.
3. Commercial configuration: offerings, offering versions, pricing rules with the evaluator and preview, instalment plans, tax configuration; ADMIN screens with MFA; TEST seeds for development only.
4. Orders and dues: server pricing, tax computation, buyer snapshot, terms stamp, immutability triggers.
5. Checkout, attempts, the hint endpoint with verified fetch, webhook intake, the processing job under the order lock.
6. Reconciliation (15-minute and daily jobs), billing exceptions, alerts.
7. Invoices: sequences, issue on capture, lines and tax lines, PDF rendering, logged links.
8. Package entitlement: activation, history, `package_active`, overview card and package screens.
9. AI credits: ledger, credit orders, `use_credit` on generation, automatic return on failure, designs screens.
10. Refunds: requests, decisions, Razorpay refund job, credit notes, entitlement and credit effects, operations queue.
11. Tests: unit (pricing, tax, numbering, ledger), API (state machines, idempotency, replay, out-of-order, amount mismatch, duplicate capture, forged hint, refund limits, no construction-money surface), Playwright on phone and desktop with axe against the `fake` provider, plus a staging run in Razorpay test mode once test keys exist (O-09).
12. Migration up, down and up; contracts regenerated.
13. Docs: FOUNDATION_PLAN 4i, DATA and API as built, SECURITY PCI position, PFR and IHB register updates, architecture drift (EVENT 182, `billing.package_paid → PLANNING`).

Building with TEST values needs none of O-01 to O-08; the `fake` provider needs no Razorpay account.

## N. Exact launch gates

| Gate | Requirement |
|---|---|
| N-01 R2 CORS (carried from Slice 3.2) | Production private bucket CORS: AllowedOrigins exactly `https://plan2build.in` and `https://professionals.plan2build.in` (the `www` host redirects to the apex and serves no pages); AllowedMethods `PUT`; AllowedHeaders `content-type` (the only header presigned uploads sign); no wildcard origin, method or header; the admin host is not listed. Staging bucket: `https://staging.plan2build.in` and `https://staging-professionals.plan2build.in`. Verified by a preflight from each allowed origin (allowed) and from another origin (refused) before launch. Replaces S-01's "homeowner host only" |
| N-02 CSP for storage | Both hosts' `connect-src` names the R2 upload endpoint; the homeowner host's `img-src` allows the signed portfolio image links used by the directory |
| N-03 Razorpay live | Account under the confirmed entity, KYC complete, live key id and secret, webhook secret per environment, webhook URL and event list configured, test-mode run passed in staging |
| N-04 Commercial values | Published, non-TEST offering versions with prices (O-01, O-02, O-07) |
| N-05 Tax and invoices | Published, non-TEST tax configuration and invoice format approved by the accountant (O-05) |
| N-06 Terms | Purchase and refund terms published (O-06), versions stamped on orders |
| N-07 Checkout CSP | Script, frame and connect sources for Razorpay Standard Checkout per Razorpay's documentation |
| N-08 Security | External penetration test before the first real payment (SECURITY 243); alerts for AMOUNT_MISMATCH, signature failures and stale attempts live |
| N-09 Recovery | Payment data restore runbook rehearsed (OBSERVABILITY 112); PITR decision AQ-32 taken for payment volume |
| Carried | S-01 ClamAV and VPS sizing, M-01, M-02, W-01, D-12, D-16, D-17 (ARCHITECTURE_BASELINE) |

## O. Verdict

**READY WITH DECISIONS.** Slice 3.3 can be built end to end with marked TEST values and the `fake` provider once Chirag approves this document. No open item blocks building. O-01 to O-07 and O-09 block live money, not code; O-08, O-10, O-11 and O-12 need an answer (or acceptance of the recommendation) during the build.

No code changed in this readiness pass.

## P. Build result (2026-10-05)

Built as this document says; run results in FOUNDATION_PLAN.md section 4i, tables in DATA_ARCHITECTURE.md (migration 0011), routes in API_ARCHITECTURE.md section 22, launch gate N-01 artifacts in `infra/r2/`.

Implementation choices and differences from sections H to J:

| Item | This document | Built | Why |
|---|---|---|---|
| Refund requests in the operations queue | "operations queue item" | Listed on the operations billing page (REQUESTED and FAILED) with their own screens; not `ops_queue_items` | The refund screens carry the decision; a second queue would duplicate them |
| `package_entitlements` uniqueness | UNIQUE per project | One ACTIVE per project (partial UNIQUE), with ended rows kept | A refunded or cancelled package may be bought again (section B) |
| `eligibility_assessments.decision` | ACCEPT or CANCEL | Not stored: the table records acceptances only; cancelling keeps its reason in the status history | Cancelling needs no checklist |
| Billing exception kinds | includes MISSING_EVENT | Not used | Reconciliation applies a verified capture whose webhook never came; nothing for operations to do |
| `orders.price` | not listed | Stored with the taxable value and tax lines | The price the rule computed, before tax, kept for audit |
| Fake gateway state | not specified | `fake_gateway_records` table, written only by the fake adapter; empty outside local and tests | The API and worker share provider-side state the way Razorpay holds it |
| Routes | `/ops/refund-requests/...`, `/ops/packages/...` | `/ops/billing/refund-requests/...` (approve, decline, retry), `/ops/billing/packages/{project}/cancel`, `/orders/{id}/cancel` added, eligibility versions at `/admin/eligibility-checklists` | One prefix per area |
| Frontend | `/billing/refunds` list | Refunds listed on `/billing`; detail at `/billing/refunds/[requestId]`; credit orders at `/account/orders/[orderId]` | Fewer pages, same flows |

Open decisions, as built (each a setting or a marked default, none a business rule):

| ID | Built as |
|---|---|
| O-01, O-02, O-05, O-06, O-07 (price) | Published configuration versions only. Local development publishes TEST versions (`python -m p2b.billing.seed_dev`); production refuses TEST versions and the fake gateway |
| O-03 | No LAPSED state; an unpaid later instalment stays DUE |
| O-04 | `package_service_usage` exists and is shown to staff; no package service writes it yet (3.4) |
| O-07 (holder, caps) | Credits held by the paying account; the daily caps count paid generations (the recommendation), pending Chirag's answer |
| O-08 | A missing characteristic shows "update your requirement"; no manual quotes |
| O-09 | Fake gateway locally; Razorpay adapter built and tested against a mock transport; no Razorpay account connected |
| O-10 | OPS and ADMIN may decide refunds (L-03 wording); the before and after "substantial work" split waits for O-04 and O-10 |
| O-11 | Projects accepted before the checklist show "Accepted before the eligibility checklist existed"; no assessment rows are invented |
| O-12 | `P2B_BILLING_UNPAID_ORDER_HOURS` unset: unpaid orders stay open until the buyer cancels; the sweep runs when it is set |

Closure run (2026-10-05, final code state): API 450 passed; ruff, mypy, import-linter (4 contracts), `tsc`, ESLint, Vitest 30 and the production build clean; migration check clean on the test database; Playwright 52 passed on phone and desktop with axe. Slice 3.3 closed and verified.
