# Plan2Build: testing architecture

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/01_ARCHITECTURE/TESTING_ARCHITECTURE.md` |
| Version | 0.1 (proposed) |
| Date | 2026-10-03 |
| Status | Architecture proposal for Chirag's review. |
| Business authority | S06 §16.1 (critical automated tests), S01 §23.3 (QA scenario groups), S05 module acceptance criteria, BR-161 (version check on every write) |
| Related | ENVIRONMENT_AND_DEPLOYMENT.md (pipeline), SECURITY_ARCHITECTURE.md section 13, STATE_MODEL.md (transition tables), API_ARCHITECTURE.md (contract) |

## 1. Principles

1. Tests follow the architecture: modules are tested through their service functions, the API through its contract, flows through the browser. The transition tables in STATE_MODEL.md and the authorisation rules in API_ARCHITECTURE.md are the specification; tests are generated from them where possible rather than hand-written per case.
2. The critical tests named by the sources (S06 §16.1) exist from the first sprint and run on every pull request; a release cannot ship without them.
3. Fast feedback: unit and service tests run in under 3 minutes; the full pipeline under 15 minutes.
4. Test data is synthetic and built by factories; no production data in tests.

## 2. Layers

| Layer | Scope | Tooling | Database | Count target at POC | Runs |
|---|---|---|---|---|---|
| Unit | Pure logic: scoring, smoothing, TOPSIS, rank-order centroid, rule interpreter, configuration validator, state transition functions, money arithmetic, deadline computation, prompt builder | pytest, hypothesis for property tests | None | 400 | Every push |
| Service (module) | A module's service functions against a real Postgres: transitions with audit and outbox rows, optimistic locking, idempotency, event emission | pytest, testcontainers (Postgres with PostGIS), factories (factory_boy) | Real, per test transaction rollback | 500 | Every push |
| Contract | OpenAPI validity, request and response schema fuzzing, error shape, pagination, rate limit headers | Schemathesis, pytest | Real | Generated | Every push |
| Authorisation matrix | Every endpoint × every role × own and foreign membership; expected 2xx, 403 or 404 from the route registry's declared rule | pytest, generated parametrisation | Real | Generated (about 250 endpoints × 8 roles) | Every push |
| Response shape | Per-audience response models contain no forbidden fields (supplier or brand for auditors; internal rates for homeowners; other quotes for contractors) | pytest snapshot of model fields | None | 30 | Every push |
| Jobs | Each job's idempotency (run twice, one effect), retry classification, outbox relay fan-out, scheduled sweeps against time-travelled fixtures (`freezegun`) | pytest | Real | 120 | Every push |
| Integration (providers) | Adapters against recorded fixtures (webhook payloads, provider responses), signature verification, replay, amount mismatch, out-of-order events | pytest with `respx` for HTTP mocks and stored fixtures | Real | 80 | Every push |
| Web unit | Components, host-based middleware routing, form validation, PWA queue logic (IndexedDB with fake-indexeddb), SWR hooks | Vitest, Testing Library | None | 200 | Every push |
| End-to-end | The flows in section 4 through the browser against an ephemeral Compose stack (api, worker, web, Postgres, Mailpit) with seeded data; OTP read from Mailpit | Playwright | Ephemeral | 25 flows | Pull request (smoke subset of 8), nightly (all) |
| Offline PWA | Inspection pack download, checkpoints offline, evidence queued, reconnect, sync without duplicates, lock | Playwright with network emulation | Ephemeral | 4 | Nightly |
| Migration | Upgrade and downgrade on a fresh database; upgrade on the latest staging dump copy; `squawk` lint | CI job | Fresh and copy | All migrations | Every push with a migration |
| Performance | Lighthouse CI budgets on public pages; k6 on staging | Lighthouse CI, k6 | Staging | 5 pages, 3 k6 scenarios | PR (Lighthouse), quarterly (k6) |
| Security | Dependency and image scanning, gitleaks, ZAP baseline, header checks | CI | Staging for ZAP | | PR, weekly |
| Accessibility | axe checks on the main screens; keyboard navigation of forms | Playwright with axe | Ephemeral | 15 screens | Nightly |
| Restore and rebuild drills | OBSERVABILITY_AND_OPERATIONS.md 7.4 | Scripts | Staging | 2 | Monthly, quarterly |

## 3. The critical tests (S06 §16.1), stated as tests

| Test | Assertion |
|---|---|
| Build Plan immutability | After `issue`, any write to the issued version returns 409; a new draft version is required; the issued PDF's hash is unchanged |
| Quote isolation | Contractor A's session cannot read B's quote, the comparison or the adjustment list on any endpoint (matrix test plus explicit cases) |
| Comparison never mutates quotes | After adjustments and finalisation, the quote version rows and lines equal their submitted snapshot (hash compare) |
| Locked inspection immutable | After `lock`, writes to checkpoints, evidence links or results return 409; the report hash recomputed equals the stored hash |
| Invalid state jumps | For every machine, every transition not in the table returns 409; an override not marked `override_allowed` returns 409 even with MFA; an allowed override without a reason returns 422 |
| Webhook replay | The same Razorpay event delivered twice produces one `payment_events` row, one state change, one receipt |
| Offline sync replay | The same sync batch posted twice yields one set of checkpoint results; a gap in `batch_seq` is rejected and reported |
| Configuration validator | An engine configuration with a brand item type, a payment-derived signal or a price-sorted listing rule is rejected with a reason; the valid fixture passes |
| Version check on every write (BR-161) | Every mutating endpoint without a matching `version` returns 409 `VERSION_CONFLICT` |
| Auditor blindness (BR-122) | The auditor's pack and views contain no `supplier`, `brand` or `product` keys |

## 4. End-to-end flows

Homeowner: estimate and enquiry; register by OTP and create a project; submit the requirement; buy the package (Razorpay test mode); receive the concept design decision screen; see the Build Plan issue (with a seeded issued version); choose a specification line by OTP; send listing leads and see eligibility reasons; view the comparison and select by OTP; mark a milestone paid; raise an issue; view the build record and share it.

Professional: register and submit verification; apply to the Club; receive and accept a lead; open the RFQ pack and submit a quote version; post a stage update with evidence; acknowledge a variation by OTP; submit rectification evidence; auditor PWA flow (section 2).

Operations: claim a verification and approve with MFA; curate a Club application; review a recommendation and reorder with a reason; complete adjustments and finalise a comparison; schedule an inspection and approve a report; assess a variation; record a refund; publish a catalog version and see the estimator update.

## 5. Test data

- Factories for every table with realistic Raipur-shaped data (localities, plot sizes, classes), deterministic seeds for reproducibility.
- A "world" fixture builds one project at each project state with the related rows, used by the matrix and e2e suites.
- Time is controlled (`freezegun` in Python, a clock injection in the web app) so deadline, expiry and escalation tests are deterministic.
- Provider fixtures: recorded webhook bodies with valid signatures for the test secrets; image provider returns a fixed PNG; Resend mocked with a capture.

## 6. Quality gates

| Gate | Threshold |
|---|---|
| Coverage | 85% lines on `apps/api/src/p2b/*/service.py` and `recommendation/core`; 70% overall; coverage never decreases on a PR |
| Type checks | `mypy --strict` on the API; `tsc --noEmit` on the web |
| Lint | `ruff`, `eslint`, `import-linter` (module boundaries), custom rule: no router function without an authorisation dependency |
| Contract | OpenAPI diff with no breaking changes unless the PR carries the `breaking-api` label and a version note |
| Flake policy | A test that fails intermittently twice is quarantined with an issue and fixed within a sprint; no retries on by default |

## 7. Open points

| ID | Question | Default until answered |
|---|---|---|
| AQ-34 | Whether the client participates in acceptance testing on staging per gate (S05 gates) | Yes, with a scripted acceptance checklist per gate derived from the S05 criteria |
