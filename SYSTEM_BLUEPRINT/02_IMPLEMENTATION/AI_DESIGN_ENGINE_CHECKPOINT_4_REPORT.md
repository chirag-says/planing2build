# Plan2Build: AI design engine, Checkpoint 4 report (structured AI intent and conversational editing)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_CHECKPOINT_4_REPORT.md` |
| Date | 2026-10-08 (overnight run under Chirag's standing instructions) |
| Basis | Chirag's overnight brief of 2026-10-08, sections 11 to 30; `AI_DESIGN_ENGINE_CHECKPOINT_3_2_REPORT.md`; `AI_AND_RECOMMENDATION_ARCHITECTURE.md` and `INTEGRATION_ARCHITECTURE.md` (Gemini server-side, adapters stable while models change) |
| Branch | `houseplans-checkpoint-1`, on top of `b5d5b14` (tag `houseplans-cp3.2`) |
| Scope kept out | No image generation, 3D, Three.js, GLB or WebGL; no second solver; no solver or validator change; no HousePlan schema change; no migration; no new dependency (Gemini is called over HTTPS with the existing `httpx`) |
| Feature flag | `houseplans_ai_enabled` defaults to false and `ai_text_provider` to `none` in every environment. The mock interpreter is refused outside local and test; Gemini needs a server-side key and a configured model name |
| Live Gemini | **Not exercised live in this run: no Gemini credentials exist on this machine.** The adapter is tested against a stubbed HTTP transport (request shape, schema, parsing, retries, timeouts, refusals). A live run is one command once a key and model are set (section 7) |

---

## 1. Scope and outcome

CP4 lets AI understand what a homeowner asks for while the deterministic engine keeps deciding all geometry:

```
words ──> model (closed JSON schema: an intent, never coordinates)
      ──> deterministic compiler (candidate typed operations, first that the validator passes)
      ──> proposal (operations + before/after measured by the engine + preview), nothing stored
      ──> owner chooses Apply ──> POST /ops (applied and validated again, logged, undoable)
```

- **Conversational edits**: in the plan editor, "Ask about your plan" takes one sentence. The answer is one of four things:
  - a proposal, such as "Make Living room larger." with "Living room: 20.86 m² to 23.10 m²", drawn as a preview, then Apply or Cancel;
  - an explicit "not supported" with the topic;
  - a question back;
  - "I could not make that change without breaking the plan's current rules." after at most two re-asks.
- **Requirement interpretation**: a homeowner's description becomes requirement facts, provisional design inputs and stated preferences. Missing facts are listed, never guessed. Where the words differ from the submitted requirement, the differences are shown and never applied. Generation then goes through the existing route and the existing deterministic solver (no second solver).
- **Providers**: one `TextProvider` interface, with Gemini (HTTPS, strict JSON schema output), a deterministic mock (local, tests, CI, offline benchmark) and an unconfigured provider (default).

## 2. Architecture and contracts

| Piece | Where | What it guarantees |
|---|---|---|
| `TextProvider` | `core/ai_text.py` | Request: bounded system text, the user payload, a JSON Schema, a correlation id. Result: parsed JSON, token usage, duration, attempts. Typed errors (UNAVAILABLE, TIMEOUT, REJECTED, MALFORMED) |
| Gemini adapter | `integrations/ai_text.py` | `generateContent` with `responseMimeType: application/json` and `responseJsonSchema` (refs inlined); temperature 0; key in a header, never logged; model from configuration; 10 s connect and configured total timeout; transient failures (429, 5xx, timeouts, network) retried up to `ai_text_attempts`, refusals not retried |
| Mock interpreter | `integrations/ai_text.py` | Deterministic keyword reading of plain English into the same schemas; a scripted mode for malformed answers and provider failures in tests |
| ArchitecturalIntent | `engine/assist.py` `RequirementIntent` | Plot (size, facing, setbacks), floors, bedrooms, bathrooms, attached bathrooms, puja, utility, dining and kitchen arrangement, parking (kind, spaces), living size, adjacencies, private rooms, circulation, entrance side, Vastu preference, accepted compromises, clarifications, unsupported topics. Closed, bounded, no geometry |
| EditIntent | `engine/assist.py` | Discriminated union: RESIZE_ROOM, MOVE_ROOM_TOWARD, ADD_ROOM, CHANGE_ROOM_TYPE, REMOVE_ROOM, RENAME_ROOM, MOVE_OPENING, RESIZE_OPENING, UNSUPPORTED (ADD_FLOOR, FREE_SHAPE, STRUCTURAL_ENGINEERING, PERMIT_COMPLIANCE, VASTU_CERTIFICATION, PRIVACY_REDESIGN, UNSUPPORTED_ROOM_TYPE, IMAGES_OR_3D, OTHER), CLARIFY. Rooms are named by existing ids; `extra="forbid"` everywhere |
| ProposedEdit | `assistant.EditOutcome`, `AssistantEditOut` | Status, the intent, typed operations, the revision they apply to, the proposed plan's geometry (preview), room and opening changes measured by the engine, the reason when there is no proposal, call metadata |
| Compiler | `engine/assist.compile_edit` | A fixed, ordered list of candidate batches from the plan's own geometry (for example each side by 600 then 300 mm for "larger", each insertion slot at the smallest fitting size for "add"); at most 24 candidates; the first that the engine applies and the validator passes. Never forces: E-5, re-hosting and every validator rule apply |
| Requirement bridge | `engine/assist.requirement_answers` | Maps the intent onto the RQ v1 answers and DesignInputs that `normalise` already reads; lists missing facts; optional rooms not mentioned are shown as assumed absent |
| Service | `houseplans/assistant.py` | Owner only; off unless enabled; revision checked; `interpret_edit` loop with at most `ai_text_max_repairs` (2) re-asks carrying the refusal reasons; nothing stored; logs without prompt text |
| Routes | `houseplans/router.py` | `POST …/house-plans/{id}/assistant/edit` and `POST …/house-plans/assistant/requirement`, 30 per session per 10 minutes; `EditingOut.assistant` tells the editor whether to show the panel |

Product language: the panel calls itself "AI-assisted design interpretation: a suggested change based on your words". The system prompts say the model is not an architect, engineer, approval or Vastu authority. The AD-16 draft disclaimer stays on the page.

## 3. Files

| File | Change |
|---|---|
| `apps/api/src/p2b/core/ai_text.py` (new) | The provider interface |
| `apps/api/src/p2b/integrations/ai_text.py` (new) | Gemini, mock and unconfigured providers; `build_text_provider` |
| `apps/api/src/p2b/houseplans/engine/assist.py` (new) | Intent schemas, requirement bridge, edit compiler, change description, plan summary |
| `apps/api/src/p2b/houseplans/assistant.py` (new) | The assistant service and its bounded loop |
| `apps/api/src/p2b/houseplans/router.py`, `schemas.py`, `service.py` | Routes and contracts; `PlanView.assistant` |
| `apps/api/src/p2b/core/config.py`, `main.py`, `.env.example` | Settings and guards; the provider on app state |
| `apps/api/scripts/benchmark_houseplan_assistant.py` (new), `tests/fixtures/houseplans/ai_benchmark_cp4.json` (new) | The AI benchmark (section 7) |
| `apps/api/tests/test_houseplan_assist.py` (new), `test_houseplans_assistant_api.py` (new) | Section 6 |
| `apps/web/src/components/plan2build/plan/plan-assistant.tsx` (new), `src/lib/plan/assistant.ts` (new) | The panel and the proposal texts |
| `apps/web/src/components/plan2build/plan/plan-workspace.tsx`, `src/lib/plan/types.ts`, `messages/en.json` | Panel placement; `Plan.assistant` messages |
| `apps/web/tests/unit/plan-cp4.test.tsx` (new), `e2e/floor-plan.spec.ts`, `tests/fixtures/houseplans/*.json` | Section 6 (fixtures: only the editing block changed; plans byte-identical) |
| `infra/local/compose.houseplans.yml`, `README.md` | The mock assistant on in the local stack; how to try Gemini |
| `packages/contracts/*` | Regenerated |

## 4. Security and privacy

- The API key lives in server configuration (`SecretStr`), is sent only in the request header to the provider, and is never logged or returned. The browser never talks to the model.
- Owner only (403 for members, 404 when off or for strangers); rate limited; requests bounded to 400 characters; the model sees room ids, names, types, sizes and open-area kinds, no personal data.
- No coordinates reach the server from the model or the browser: the model's answer is validated against a closed schema, and the operations in a proposal are the server's own compilation. If someone edits them in the browser, they pass the same validation as any manual edit.
- Nothing is stored by asking. Applying uses the operations route (row lock, expected revision, validator, append-only log, undo).
- Logs: `houseplan.assistant` with task, outcome, provider, model, correlation id, duration, model calls and token counts; no prompt or answer text. No conversation transcript is stored.

## 5. Bounded repair

When the model's answer does not fit the schema, or no candidate passes the plan's rules, the refusal reasons go back to the model (`previous_failure`) for a different reading. There are at most 2 re-asks, so 3 model calls in all, then the request ends as FAILED with the message above. The tests prove the bound: three calls for an impossible request and for a model that keeps answering malformed JSON. A provider outage is a 503, not a proposal.

## 6. Tests

| Suite | Result |
|---|---|
| Engine and provider (`test_houseplan_assist.py`, new, 12) | Closed edit schema (extra fields, unknown actions, unknown room types, bad ids, empty questions, unknown topics refused; no geometry fields in the schema); requirement schema bounds; every supported intent compiles to validated operations on a real plan, deterministically; unsupported, clarify, unknown room, already-adjacent and impossible requests (the last kitchen, E-5) say why; proposals described with the engine's areas; the plan summary carries no coordinates; a complete description goes through `normalise` and the existing zoned solver to a VALID plan; missing facts listed, other floors unsupported; the mock interpreter; the Gemini adapter's request (URL, key header, schema JSON with refs inlined, system text), answer parsing and token usage, retry on 503, no retry on 400, malformed answers and timeouts; settings defaults off and guards (mock outside local and test refused; Gemini without key or model refused) |
| API (`test_houseplans_assistant_api.py`, new, 5) | A proposal validated and shown, nothing stored until applied through `/ops`, then logged and undone to the generated body; a stale revision refused; unsupported, unclear and impossible requests store nothing and say why (three model calls at most); malformed answers repaired within the bound and then FAILED; provider outage 503; members 403 and no panel; free geometry in the request refused; feature off 404 and no panel; a description becomes requirement facts with differences from the submitted requirement shown, never applied |
| Full API suite | **870 passed, 0 failed, 0 skipped** in 31 min 43 s on the final CP4 tree (853 from CP3.2 plus 17 new) |
| Web unit (Vitest, 3 new, 182 passed, 2 opt-in montages skipped) | Proposal texts from structured results (intent sentence, room areas and opening widths in units); unsupported, clarify and failed messages; the panel labelled, describing itself as AI-assisted interpretation, with nothing to apply before a proposal and no authority claims |
| Web e2e (live stack, mock interpreter, axe; 5 passed, 3 phone skips by design) | New scenario: a second floor declined in words with nothing stored; a plain request becomes a proposal (several phrasings tried in order, since which change a plan allows depends on the plan), not stored; Apply stores revision 1 through `/ops`, valid; the revision is in the history; Undo restores the generated body. All earlier floor-plan scenarios pass |
| Static | API: ruff format and ruff, mypy strict (338 files), import-linter 5/5 (the engine stays pure), contracts regenerated. Web: ESLint, `tsc` strict, `next build`. Repo: `check_ui_tokens` 0, `check_words` 0 |
| CP2.2.1 and CP3.x | Engine goldens and CP3, CP3.1 and CP3.2 tests inside the full suite; exported plans byte-identical |

## 7. AI benchmark

Dataset: `tests/fixtures/houseplans/ai_benchmark_cp4.json`, 36 prompts with labels written before the first run:

- 15 requirement descriptions: 2BHK, 3BHK, 4BHK, parking kinds, attached bathrooms, utility, puja, privacy, adjacency, orientation, an impossible programme, a vague request, a duplex, Vastu certification;
- 21 edit commands on six real plans: resize, move closer, add in open areas, retype, unsupported room type, door move, window resize, privacy, removal (including the last kitchen), rename, another floor, vague, structural, curved.

Offline run with the mock interpreter (`--provider mock`):

| Measure | Result |
|---|---|
| Requirement answers valid against the schema | 15 / 15 |
| Requirement answers with every labelled fact right | 14 / 15 (r10: "2 bedrooms with one attached bathroom, 2 bathrooms" read the bathroom count wrong) |
| Complete description generated to a VALID plan by the existing solver | 1 / 1 (the only prompt giving setbacks; the others correctly list setbacks and other facts as missing) |
| Edit intents with the labelled action | 20 / 21 (e03 "move the kitchen closer to the living room" asked back instead) |
| Edit intents naming the labelled room | 19 / 21 |
| Edits ending with the labelled outcome (proposal, unsupported, question or failure) | 21 / 21 |
| Proposals that passed the validator | 10 (every PROPOSED outcome is validated by construction) |
| Re-asks used | 8 (four requests used the full bound and ended FAILED: two additions with no room in that open area, the last kitchen, a bedroom that cannot grow) |
| Latency, engine plus mock | median 7.6 ms, max 247 ms per prompt (the maximum includes one plan generation) |
| Tokens and cost | 0 with the mock; the Gemini run reports tokens, and cost when `P2B_AI_PRICE_IN_PER_MTOK` / `_OUT_` are set |

These numbers measure the pipeline: schema validation, compilation, validator gating, repair bounds and latency. They do not measure language understanding, because the mock is a keyword interpreter. The same harness measures Gemini with `--provider gemini` once `P2B_GEMINI_API_KEY` and `P2B_AI_TEXT_MODEL` are set; that run has not been made.

## 8. Performance

| Measure (development machine) | Result |
|---|---|
| Compiling an intent (candidates evaluated through the engine and validator) | 5 to 90 ms per request on the benchmark plans; at most 24 candidates |
| Proposal response besides the model call | one compile plus geometry for the preview (a few milliseconds) |
| Model call | not measured live (no credentials); bounded by `ai_text_timeout_seconds` (30 s default) and `ai_text_attempts` (2) |

No optimisation was needed. Solver benchmarks are untouched.

## 9. Known limitations

| ID | Limitation |
|---|---|
| L-1 | Gemini not run live (no credentials here); the adapter's request and response handling are tested against a stubbed transport. MED confidence that `responseJsonSchema` with inlined refs is accepted as is by the configured model; the answer is validated by our schema either way, and a mismatch shows as MALFORMED, never as a change |
| L-2 | Preferences (large living room, kitchen beside dining, private master bedroom, circulation, entrance side) are carried in the intent and shown, but the CP2 solver does not read them yet; generation uses the facts only |
| L-3 | "More privacy" is answered as unsupported (PRIVACY_REDESIGN): no deterministic operation set is defined for it yet; the owner can move rooms, doors and windows |
| L-4 | The requirement bridge does not change the submitted requirement: differences are shown and the requirement form stays the authority. There is no web screen for the description yet; the route is ready |
| L-5 | Compilation is greedy: the first candidate the validator passes, in a fixed order, not the best of all; "move closer" moves or stretches the room along one axis only |
| L-6 | The mock interpreter is for development and tests only and reads English keywords; its benchmark numbers say nothing about a real model |
| L-7 | The preview overlay outlines the main changed room only |

## 10. Decisions taken under the overnight instructions

| ID | Decision |
|---|---|
| G-1 | Gemini over HTTPS with `httpx` (already a dependency) rather than a vendor SDK: about 60 lines, no new dependency, the adapter is the stable part (TECH_STACK: models are retired often) |
| G-2 | No default model name: the model is configuration; without it the provider is not built |
| G-3 | AI proposals carry the operations the server compiled; the owner's Apply sends them through the operations route. Proposals are not stored server-side: the operations route validates them again, so a stored proposal would add state without adding safety |
| G-4 | The requirement path proposes design inputs and shows differences from the submitted requirement; it never edits the requirement |
| G-5 | Repairs bounded at 2 (configurable down to 0); provider outages are 503, never a fallback answer |
| G-6 | The log batch reason for applied AI proposals stays USER (the owner applied them); adding an AI reason would need a migration and was not required |

## 11. Acceptance criteria

| Criterion | Met? | Evidence |
|---|---|---|
| Structured architectural intent works | Yes | Schema, bridge to `normalise`, generation through the existing solver (tests, benchmark) |
| Structured edit intent works | Yes | Closed union; every action tested |
| Deterministic operation compilation works | Yes | Same intent, same operations and body hash (tests) |
| MockProvider works | Yes | Tests, e2e, benchmark |
| Real Gemini provider works behind the abstraction | Partly | Implemented and tested against a stubbed HTTP transport; **not run live (no credentials)**: see L-1 |
| AI proposals require confirmation | Yes | Nothing stored by asking (API tests, e2e); Apply goes through `/ops` |
| Validator remains authoritative | Yes | Proposals validated before showing and again when applied |
| Bounded repair works | Yes | Three model calls at most (API tests) |
| Initial generation bridge uses the existing deterministic solver | Yes | `requirement_answers` then `normalise` then `generate` (test and benchmark) |
| AI benchmark exists | Yes | 36 prompts, harness, offline results |
| Production AI remains off | Yes | Defaults off and `none`; mock refused outside local and test; Gemini needs a key and a model |
| All tests, build and static checks pass | Yes | API 870/870; web 182 passed; floor-plan e2e 5 passed, 3 skipped by design (editing on phones) |
| CP2.2.1 engine unchanged; CP3 and CP3.x behaviour valid | Yes | Goldens and earlier checkpoint tests in the suite; exported plans byte-identical |
| Report written; commit and tag | Yes | This report; section 12 |

## 12. Verdict, commit and tag

**Committed with one stated exception.** Every gate in sections 6 and 11 passed on the final tree except the live Gemini run, which needs credentials this machine does not have (L-1). The brief allows for missing credentials: the mock stays available, every test is green and production AI stays off. Commit `AI design engine Checkpoint 4: structured AI intent and conversational editing`, tag `houseplans-cp4`; the commit hash is in `AI_DESIGN_ENGINE_OVERNIGHT_RUN_2026-10-08.md`. Before any homeowner sees the assistant:

- run the benchmark against Gemini with a key and a chosen model;
- review the system prompts;
- decide whether the solver should read the preferences (L-2).

CP5 is not started.
