# Plan2Build: AI design engine, live Gemini validation of CP4 (2026-10-08)

| Item | Value |
|---|---|
| Document | `SYSTEM_BLUEPRINT/02_IMPLEMENTATION/AI_DESIGN_ENGINE_GEMINI_LIVE_VALIDATION_2026-10-08.md` |
| Date | 2026-10-08, 10:20 to 12:00 IST |
| Basis | Chirag's "Live Gemini validation + CP4 production-readiness check" brief; `AI_DESIGN_ENGINE_CHECKPOINT_4_REPORT.md`; `AI_DESIGN_ENGINE_OVERNIGHT_RUN_2026-10-08.md` |
| Starting point | `houseplans-checkpoint-1` at `6b7c676`, clean; tags `houseplans-cp3.1`, `houseplans-cp3.2`, `houseplans-cp4` in place |
| Verdict | **READY WITH FIXES REQUIRED** (section 16) |

Every Gemini number in this report comes from live calls to the Gemini API. The mock interpreter's numbers appear only in the comparison of section 6, labelled as mock.

## 1. Objective

Validate the committed CP4 assistant against the real Gemini API through the existing provider abstraction, without changing the architecture:

```
text -> Gemini (closed JSON schema) -> strict intent -> deterministic compiler -> typed operations
     -> validator -> preview -> explicit Apply -> stored edit
```

## 2. Environment

- Windows development machine; the API venv runs the adapter and the same `interpret_edit` loop the API route uses; no database is involved in model calls.
- Key: `P2B_GEMINI_API_KEY` in `apps/api/.env`. The file is ignored by `.gitignore` (`.env`) and untracked, and it was read by a local helper per run without printing.
- The first two keys were refused for every model with 403 `PERMISSION_DENIED` ("Your project has been denied access"). The third key, from another project, works. Listing models worked with every key, so authentication itself was never the problem.

## 3. Provider and model configuration

- **Configuration, unchanged:** `P2B_AI_TEXT_PROVIDER=gemini`, `P2B_AI_TEXT_MODEL` and `P2B_GEMINI_API_KEY`, read by the settings and by the benchmark harness. No new mechanism was added.
- **Model: `gemini-3.5-flash-lite`.** It was chosen from the models this key lists for `generateContent` as the pinned, non-preview Flash-Lite: low cost, suited to structured JSON, low latency. The `-latest` aliases were avoided because they can change underneath. It was passed per run through `P2B_AI_TEXT_MODEL`; nothing is hard-coded.
- **Older models are gone:** `gemini-2.5-flash` and `gemini-2.5-flash-lite` answer 404, "no longer available to new users".
- **Adapter settings, unchanged:** timeout 30 s, 2 attempts per call (transient failures only), at most 2 repairs (3 model calls per request).

## 4. Smoke test

**PASS after one adapter correction.**

| Prompt | First run | After the correction |
|---|---|---|
| Requirement: "30 by 50 plot, 3 bedrooms, two bathrooms, one car parking …" | Valid; every stated fact right; facing, setbacks, attached bathrooms, dining and kitchen listed as missing; living size, kitchen-dining and private master bedroom kept as preferences | Same |
| "Make the living room larger." | **FAILED**: all 3 answers named an action that does not exist (`"MODIFY_SIZE"`); our schema refused each; nothing stored | Gemini returns `RESIZE_ROOM living LARGER` (3 of 3 tries). The deterministic compiler then finds no candidate the validator accepts in this plan (parking would shrink below its size, a room would cross the setback line, an opening would leave its wall), so after the bounded repairs it ends FAILED with nothing stored: a correct engine refusal |
| "Add a utility room in the open space at the back." | `ADD_ROOM UTILITY REAR_YARD` → `ADD_ROOM_OUTSIDE`, validated, re-validated independently, input plan unchanged | Same |

**Root cause and correction.** Pydantic's JSON Schema expresses the intent union as `oneOf`, with each action as a `const`, a `discriminator` whose mapping points at `$defs` (dangling once the references are inlined), and the `action` tag optional because it has a default. Gemini's structured output did not enforce that shape. `integrations/ai_text._inline` now sends the forms Gemini follows:

- `oneOf` becomes `anyOf`, and `const` becomes a one-value `enum`;
- `discriminator` and `default` are removed;
- a one-value enum field (the tag) becomes required;
- a map keyed by an enum (setbacks by side, found in the benchmark) becomes explicit properties, because `propertyNames` let Gemini write `front` and `rear`.

Our own Pydantic models still validate every answer exactly as strictly. Only the schema text sent to Gemini changed.

## 5. The 36-prompt benchmark (live Gemini)

**Harness.** The existing benchmark (`scripts/benchmark_houseplan_assistant.py`, `ai_benchmark_cp4.json`), unchanged in prompts, labels and path. Three additions were needed to measure and to survive the free tier:

- a timing wrapper recording each model call (duration, schema validity, action, room id);
- `--pace` between calls;
- provider errors recorded against the prompt instead of aborting, with `--only` for re-running a subset.

**Runs on the final code:**

- Run 3: all 36 prompts, 12 s apart. 25 were answered; 11 consecutive edit calls got HTTP 429 (free-tier rate limit).
- Run 3b: those 11 re-run, 30 s apart. All answered.

The tables below combine run 3 with run 3b for those 11 prompts. An earlier run (run 1, before the setback correction) gave the same edit picture with no rate limits: 20 of 21 outcomes right.

**Requirement interpretation (15):**

| ID | Schema | Labelled facts | Notes |
|---|---|---|---|
| r01–r04, r06, r07, r09–r11, r14, r15 | valid | all right | Missing facts listed, never guessed |
| r05 complete | valid | all right | Not generated: the prompt states no attached-bathroom count, and Gemini correctly left it empty (the mock had assumed 0). **Benchmark expectation mismatch.** The bridge was proven separately on Gemini output with the count stated (section 11) |
| r08 duplex | valid | all right | ADD_FLOOR unsupported |
| r12 impossible (20x30, 6 bedrooms) | valid | all right | Gemini also flagged ADD_FLOOR, inferring that the programme cannot fit on one storey. Not labelled; questionable but harmless (shown as a note, never applied) |
| r13 Vastu certification | valid | all right | VASTU_CERTIFICATION unsupported |

Result: **15 / 15 schema-valid, 15 / 15 with every labelled fact right**, and 0 / 1 generated for r05 (the label mismatch above).

**Edits (21):**

| ID | Gemini intent (final) | Outcome | Expected | Matched | Model calls | Gemini ms (calls) | Engine ms |
|---|---|---|---|---|---|---|---|
| e01 bedroom 1 bigger | RESIZE_ROOM bedroom_1 | PROPOSED (MOVE_EDGE) | RESIZE_ROOM, PROPOSED | yes | 1 | 1271 | 49 |
| e02 living smaller | RESIZE_ROOM living | PROPOSED (MOVE_EDGE) | RESIZE_ROOM | yes | 1 | 6920 | 35 |
| e03 kitchen closer to living | MOVE_ROOM_TOWARD kitchen | PROPOSED (2 × MOVE_EDGE) | MOVE_ROOM_TOWARD | yes | 1 | 6458 | 30 |
| e04 add utility | ADD_ROOM UTILITY | PROPOSED (ADD_ROOM_OUTSIDE) | ADD_ROOM, PROPOSED | yes | 1 | 7857 | 28 |
| e05 bathroom in the court | ADD_ROOM, ADD_ROOM, then CLARIFY | CLARIFY | ADD_ROOM | **no (final action)** | 3 | 10813, 15056, 9136 | 46 |
| e06 bedroom 3 into a study | UNSUPPORTED UNSUPPORTED_ROOM_TYPE | UNSUPPORTED | UNSUPPORTED | yes | 1 | 5362 | 90 |
| e07 bedroom 3 into a puja | CHANGE_ROOM_TYPE bedroom_3 | PROPOSED | CHANGE_ROOM_TYPE, PROPOSED | yes | 1 | 9056 | 26 |
| e08 move bedroom 2 door | MOVE_OPENING bedroom_2 | PROPOSED | MOVE_OPENING | yes | 1 | 4211 | 39 |
| e09 wider living window | RESIZE_OPENING living | PROPOSED | RESIZE_OPENING, PROPOSED | yes | 1 | 5848 | 26 |
| e10 privacy | UNSUPPORTED PRIVACY_REDESIGN | UNSUPPORTED | UNSUPPORTED | yes | 1 | 5633 | 8 |
| e11 remove puja | REMOVE_ROOM puja | PROPOSED (DELETE_ROOM) | REMOVE_ROOM, PROPOSED | yes | 1 | 8896 | 27 |
| e12 remove kitchen | REMOVE_ROOM kitchen, then UNSUPPORTED OTHER | UNSUPPORTED (no proposal) | REMOVE_ROOM, FAILED | **no** | 2 | 4733, 7428 | 18 |
| e13 rename bedroom 1 | RENAME_ROOM bedroom_1 | PROPOSED | RENAME_ROOM, PROPOSED | yes | 1 | 1418 | 27 |
| e14 another floor | UNSUPPORTED ADD_FLOOR | UNSUPPORTED | UNSUPPORTED | yes | 1 | 1517 | 5 |
| e15 "make it nicer" | CLARIFY | CLARIFY | CLARIFY | yes | 1 | 2230 | 6 |
| e16 kitchen a lot bigger | RESIZE_ROOM kitchen | PROPOSED | RESIZE_ROOM | yes | 1 | 1732 | 20 |
| e17 toilet in rear yard | ADD_ROOM × 3 | FAILED (nothing valid) | ADD_ROOM | yes | 3 | 1304, 1537, 1422 | 45 |
| e18 remove a column | UNSUPPORTED STRUCTURAL_ENGINEERING | UNSUPPORTED | UNSUPPORTED | yes | 1 | 1301 | 12 |
| e19 curved wall | UNSUPPORTED FREE_SHAPE | UNSUPPORTED | UNSUPPORTED | yes | 1 | 1456 | 16 |
| e20 narrower kitchen window | RESIZE_OPENING kitchen | PROPOSED | RESIZE_OPENING | yes | 1 | 12139 | 17 |
| e21 bedroom 2 bigger (80x28) | RESIZE_ROOM bedroom_2 × 3 | FAILED (nothing valid) | RESIZE_ROOM | yes | 3 | 1496, 1572, 1333 | 103 |

Result:

- right action 19 / 21, right room 21 / 21, right outcome 20 / 21;
- **11 validated proposals**, 7 repairs (e05: 2, e12: 1, e17: 2, e21: 2);
- 0 provider errors in the combined results.

**Strict score (every label met): 33 / 36.** The three misses are r05 (expectation mismatch), e05 and e12 (section 14).

## 6. Gemini against the mock

The mock is a deterministic keyword interpreter for tests. Its numbers say nothing about Gemini; they are shown only so the two can be told apart.

| Measure | Mock (offline) | Gemini (live) |
|---|---|---|
| Schema-valid answers | 15 / 15 requirement; every edit answer | 15 / 15 requirement; **43 / 43 model answers** |
| Requirement facts all right | 14 / 15 | **15 / 15** |
| Edit action right | 20 / 21 | 19 / 21 |
| Edit room right | 19 / 21 | **21 / 21** |
| Edit outcome right | 21 / 21 | 20 / 21 |
| Validated proposals | 10 | 11 |
| Correct refusals (labelled unsupported) | 5 / 5 | 5 / 5 (plus 2 / 2 in requirements) |
| Repairs used | 8 | 7 |
| Requests ending FAILED | 4 | 2 |
| Median latency per prompt | 7 ms | 1.7 s per model call; 5.5 s per edit request |
| P95 latency | 58 ms | 10.8 s per model call; 12.2 s per edit request |

## 7. Latency

Model time and engine time are measured apart, with pacing pauses excluded.

| Stage | Median | P95 |
|---|---|---|
| Gemini call (43 answered calls) | 1.73 s | 10.8 s (max 15.1 s) |
| Schema parsing (Pydantic) | 0.02 ms | |
| Compile, including validation of each candidate (4 candidates) | 20.6 ms | |
| One validation | 2.5 ms | |
| Engine per edit request (all compile attempts, describe) | 27 ms | 90 ms |
| Total proposal latency per edit request (model + engine) | 5.5 s | 12.2 s |

Gemini's latency varied a lot through the morning: one-word test calls took 8–10 s at 10:50 and 1.3–1.6 s at 11:15. Almost all of the proposal time is the model; the engine's share is tens of milliseconds.

## 8. Structured-output validity

- After the correction, 43 of 43 answered calls fitted the schema, and every answer named only plan room ids.
- Before it, 3 of 3 answers to one prompt invented an action, and Gemini wrote setback keys our schema does not have. Our models refused every one of them; nothing reached the compiler.
- No answer contained coordinates, wall or polygon data, HousePlan JSON or operations: the schema has no field for them, and extra fields are refused.

## 9. Repair behaviour

- **Bound held:** at most 3 model calls per request (e05, e17 and e21 used the full bound). The retry count was not raised.
- **Malformed answers:** in the smoke test before the correction, 3 malformed answers were followed by a clean FAILED.
- **Refusals fed back:** when the compiler refused, the refusal codes went back to Gemini, which gave a smaller reading (e21), the same reading (e17), a clarifying question (e05, and all four protected-function attempts) or an "unsupported" (e12). Every request ended with a clean status and nothing stored.
- **Free-tier 429s:** these were retried once by the adapter, then returned as "unavailable" (503 in the API), never as a guess or a proposal.

## 10. Unsupported requests

All labelled unsupported edits were declined with the right topic:

- a study (not a room type in this ruleset);
- a privacy redesign;
- another floor;
- removing a column (structural engineering);
- a curved wall (free shape).

In requirements, a duplex was flagged ADD_FLOOR and "must be Vastu certified" was flagged VASTU_CERTIFICATION. Nothing hallucinated support. Permit or approval and construction-drawing requests are not in the benchmark; the prompt and schema cover them (PERMIT_COMPLIANCE), but this run did not test them live.

## 11. Protected functions and the generation bridge

**Protected functions:** on the 25x40 plan, which has one kitchen and one common bathroom, all four attempts went through live Gemini:

| Request | Result | Model calls | Plan |
|---|---|---|---|
| Remove the kitchen | CLARIFY: "Can we keep the kitchen since a kitchen is required in the plan?" | 2 | unchanged |
| Change the kitchen into a utility room | CLARIFY: "Could you keep the kitchen and add a utility room instead?" | 2 | unchanged |
| Remove the bathroom | CLARIFY | 2 | unchanged |
| Change the bathroom into a puja room | CLARIFY | 2 | unchanged |

In each case the first reading was refused by the deterministic E-5 rule (`LAST_KITCHEN_REQUIRED` / `LAST_BATHROOM_REQUIRED`), and on the bounded re-ask Gemini asked instead. In the benchmark, e12 (remove the last kitchen on the 45x70 plan) was refused the same way. No proposal was produced in any of the five.

**Generation bridge:** the complete description with the attached-bathroom count stated was read by Gemini with nothing missing. It went through `normalise` and the existing zoned solver to a VALID plan: living, kitchen, parking, two bedrooms, common bath, passage.

## 12. Security findings

| Check | Result |
|---|---|
| Key in tracked files | 0 files |
| Key in git history (pickaxe over all commits) | 0 commits |
| Key in run logs and result files | none |
| Key setting referenced in the web app or contracts | none |
| `apps/api/.env` | ignored, untracked |
| Key sent only server-side, in the `x-goog-api-key` header; never logged, never in an API response (`AssistantCallOut` carries provider and model names only) | yes (code review) |
| Feature flag off by default; mock refused outside local and test; owner-only routes; proposals never stored until Apply through `/ops` | unchanged; covered by the CP4 tests in the suite |
| What Gemini receives | room ids, names, types, clear sizes, areas, opening kinds per room, open-area kinds, the allowed room types and the request text; no coordinates, no personal data |

No unsafe behaviour was found. The adapter correction is the only code change.

## 13. Cost and free-tier observations

| Measure | Value |
|---|---|
| Tokens per edit request | about 950–1,000 in and 45 out per model call (the plan summary dominates) |
| Tokens per requirement request | about 160 in and 250 out |
| Final-code runs | 28,239 tokens over 43 answered calls (requirements 3,924; edits 24,315) |
| Free-tier rate limit | 11 consecutive 429s at 12 s spacing in run 3, none at 30 s spacing in run 3b. Probably a per-minute token window; the 429 bodies were not captured, so the exact limit is not known |

Prompts are compact and bounded (request text 400 characters). Unsupported and clarify answers stop after one call; drags and manual edits never call the model; the web panel calls only on a button press; and the server limits each session to 30 assistant requests per 10 minutes. No background loop exists. No price was set, so no cost is stated, and no remaining free quota is claimed.

## 14. Failure classification

| Case | Class | What happened | Change? |
|---|---|---|---|
| Smoke "living larger" (before the fix) | Schema failure (provider schema form) | Gemini ignored `oneOf`, `const` and the discriminator and invented an action | **Fixed** in the adapter |
| r05 setbacks (before the fix) | Schema failure (provider schema form) | `propertyNames` not enforced; keys `front` and `rear` | **Fixed** in the adapter |
| Smoke "living larger" (after the fix) | Validator rejection (correct) | No candidate passes the rules in that plan | No |
| r05 not generated | Benchmark expectation mismatch | The prompt lacks the attached-bathroom count; not guessing is right | No (label kept; bridge proven separately) |
| r12 extra ADD_FLOOR | Model over-interpretation (harmless) | Inferred a second storey for an infeasible programme | No |
| e05 bathroom in the court | Compiler limitation, then model repair behaviour | ADD_ROOM was right; no slot in the 60x90 court fits a bathroom at its smallest size; after two refusals Gemini asked which open area | No |
| e12 remove last kitchen | Benchmark expectation mismatch (model repair behaviour) | REMOVE_ROOM was right and the E-5 rule refused it; on the re-ask Gemini answered UNSUPPORTED instead of repeating, so the outcome is "unsupported" rather than FAILED. No proposal either way | No |
| e17 toilet in the 40x80 rear yard, e21 bedroom 2 bigger on 80x28 | Validator rejection (correct) | Right intents; no candidate passes the rules | No |
| 429 rate limits in runs 2 and 3 | Infrastructure (free tier) | Clean "unavailable"; re-run with wider spacing | No (see limitations) |

## 15. Known limitations

| ID | Limitation |
|---|---|
| L-1 | Free-tier rate limits: bursts of edits trigger 429s (about 1,000 input tokens per edit call). The owner sees "The assistant is not available right now". A POC with several people would hit this; a paid tier or a smaller plan summary is needed for real use |
| L-2 | Latency is the model's: about 1.5–2 s typically for this model, with spikes of 10–15 s. The panel shows "Working it out…" but there is no streaming or cancel |
| L-3 | When the engine refuses a protected or impossible change, the owner sees Gemini's follow-up question or "unsupported", not the precise reason (for example "the only kitchen"). The refusal code is known server-side; showing it directly would be clearer |
| L-4 | Permit, approval and construction-drawing requests were not exercised live (not in the benchmark) |
| L-5 | One model only (`gemini-3.5-flash-lite`). Other models would need their own run; the schema forms now sent are generic JSON Schema |
| L-6 | Gemini's free tier may use prompts to improve Google products. The plan summary contains no personal data, but the request text is the owner's own words |

## 16. Recommendation

**READY WITH FIXES REQUIRED.**

The architecture holds against the real model:

- every Gemini answer passed through the strict schema;
- every change was compiled deterministically and validated;
- protected functions and impossible requests were refused by the engine;
- unsupported requests were declined honestly;
- nothing was stored without Apply;
- no coordinates or geometry ever came from the model.

With the adapter correction, interpretation quality is good: 15 / 15 requirements fully right, 21 / 21 rooms right, 20 / 21 edit outcomes right, strict score 33 / 36, and none of the misses unsafe.

Fixes required before limited POC use with homeowners:

1. **Rate limits:** a paid tier or a quota plan, or a smaller plan summary per call (L-1).
2. **Engine refusals reach the owner:** when the engine refuses (E-5, nothing valid), show the engine's own reason instead of relying on the model's follow-up (L-3).
3. **Decide the data terms:** the free tier versus a paid tier with no-training terms (INTEGRATION_ARCHITECTURE already calls for paid-tier terms), before real homeowners type into it (L-6).
4. **A live check of permit, approval and construction-drawing refusals**, added to the benchmark set (L-4).

## 17. Code changed, tests, commit

| File | Change |
|---|---|
| `apps/api/src/p2b/integrations/ai_text.py` | `_inline` sends Gemini the schema forms it enforces (section 4) |
| `apps/api/tests/test_houseplan_assist.py` | A test of the sent schema (no `oneOf`, `const`, `discriminator` or `propertyNames`; action tag required; setbacks as explicit keys; unknown actions still refused by our model) |
| `apps/api/scripts/benchmark_houseplan_assistant.py` | Per-call timing and validity records, `--pace`, `--only`, provider errors recorded and the run continued, P95 |
| This report | New |

Regression gates and the commit are in section 18.

## 18. Regression gates

All run on the final code, after the adapter correction.

| Gate | Result |
|---|---|
| API suite | 871 passed (870 at CP4 plus the new schema test), 29 min 40 s |
| API format, lint, types | ruff format and check clean; mypy clean over 338 files (src, tests, scripts) |
| Import boundaries | 5 contracts kept, 0 broken |
| Web lint, typecheck, unit tests | eslint and tsc clean; 182 passed, 2 skipped (unchanged) |
| Web production build | passes |
| Floor-plan e2e (local stack, mock interpreter) | 5 passed, 3 skipped by design (editing on phones) |
| Exported plans | re-exported; byte-identical (no diff) |
| Live benchmark after the change | runs 3 and 3b (section 5) were made on the final adapter code |

The deterministic engine, the compiler, the validator and the web app were not changed. The commit holds the three files of section 17 and this report. No tag was created or moved, and nothing was pushed.
