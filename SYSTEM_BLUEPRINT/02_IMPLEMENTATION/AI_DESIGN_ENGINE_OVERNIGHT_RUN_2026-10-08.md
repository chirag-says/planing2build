# Plan2Build: AI design engine, overnight run 2026-10-08 (CP3.1 → CP3.2 → CP4)

| Item | Value |
|---|---|
| Run | Started about 00:55 IST and ended about 04:05 IST on 2026-10-08, unattended under Chirag's overnight brief |
| Branch | `houseplans-checkpoint-1` (not pushed by this run) |
| Outcome | All three checkpoints committed and tagged. CP5 not started |

## Status

| Checkpoint | Status | Commit | Tag | API suite | Web unit | Floor-plan e2e |
|---|---|---|---|---|---|---|
| CP3.1 editor depth and persistence | **Done**: E-5 applied (a home keeps a kitchen and a bathroom or toilet), report finalised | `4ec4323` (on top of Chirag's `83969e0` "cp3.1 done") | `houseplans-cp3.1` | 831 passed, 0 failed, 0 skipped | 166 passed, 2 opt-in skipped | 3 passed, 1 phone skip |
| CP3.2 open-area room insertion | **Done** | `b5d5b14` | `houseplans-cp3.2` | 853 passed, 0 failed, 0 skipped | 179 passed, 2 opt-in skipped | 4 passed, 2 phone skips |
| CP4 structured AI intent and conversational editing | **Done, one exception**: Gemini not run live (no credentials on this machine) | `79be220` | `houseplans-cp4` | 870 passed, 0 failed, 0 skipped | 182 passed, 2 opt-in skipped | 5 passed, 3 phone skips |

Every checkpoint also passed:

- ruff format and ruff;
- mypy strict on src, tests and scripts;
- import-linter 5/5;
- ESLint, `tsc` strict and `next build`;
- the UI token and prose checks;
- contracts regenerated and current;
- the nine exported engine plans byte-identical (no solver or validator change).

Phone skips are by design: editing is for tablets and computers (AD-14).

Reports:

- `AI_DESIGN_ENGINE_CHECKPOINT_3_1_REPORT.md`
- `AI_DESIGN_ENGINE_CHECKPOINT_3_2_REPORT.md` (montage in `AI_DESIGN_ENGINE_CHECKPOINT_3_2_ASSETS/`)
- `AI_DESIGN_ENGINE_CHECKPOINT_4_REPORT.md`

## Tags

`houseplans-cp1` (`22628ab`), `houseplans-cp2.2.1` (`7b0a5ea`), `houseplans-cp3` (`c9c0341`), `houseplans-cp3.1` (`4ec4323`), `houseplans-cp3.2` (`b5d5b14`), `houseplans-cp4` (`79be220`). The existing tags were not moved and no commit was rewritten.

## What each checkpoint added

- **CP3.1**: Chirag had committed the CP3.1 tree before E-5 as `83969e0` and pushed it. The E-5 rule went on top:
  - removing or retyping out of its function the last kitchen is refused with `LAST_KITCHEN_REQUIRED`, the last bathroom or toilet with `LAST_BATHROOM_REQUIRED`, naming the room and with a readable message;
  - a bathroom may still become a toilet;
  - compromise records, the requirement and every validator rule are unchanged.
- **CP3.2**:
  - ADD_ROOM_OUTSIDE adds a room in open space against an outside wall, given by host, side, offset, length and depth, never free coordinates;
  - insertion slots are derived on read and offered to the owner;
  - an open-area panel explains with numbers why a size cannot fit and draws a UI-only preview;
  - 230 of 419 attempts were accepted on seven real plans (CP3.1's slice: 1 of 936). The 30x40 plan without parking has no open space against a wall.
- **CP4**:
  - a provider interface, with Gemini over HTTPS (JSON schema output, configured model, server-side key), a deterministic mock and an unconfigured default;
  - closed intent schemas for requirements and edits, plus a deterministic compiler (first candidate the validator passes);
  - a requirement bridge to the existing `normalise` and solver;
  - an assistant service with at most two re-asks and nothing stored until the owner applies a proposal through `/ops`;
  - the "Ask about your plan" panel and a 36-prompt benchmark;
  - off by default everywhere.

## Unresolved blockers

None blocking. One item could not be verified here:

- **Live Gemini**: no `P2B_GEMINI_API_KEY` on this machine. The adapter is tested against a stubbed HTTP transport. Run `cd apps/api && uv run python scripts/benchmark_houseplan_assistant.py out.json --provider gemini` with a key and a chosen model (`P2B_AI_TEXT_MODEL`) to measure the real model and confirm the `responseJsonSchema` request is accepted as sent.

## Known limitations (details in each report)

- The CP3.2 open-area insertion can still be refused when the new room's end walls meet a neighbour's window or door (73 of 419); the server names the item.
- The CP4 preferences (large living, adjacency, privacy, circulation, entrance) are carried and shown, but the solver does not read them yet. "More privacy" is answered as unsupported. Compilation is greedy (first valid candidate, fixed order).
- The requirement interpretation has an API but no web screen yet, and it never edits the submitted requirement.
- The mock interpreter's benchmark numbers measure the pipeline, not language understanding.
- Production rate limits for edits, versions and the assistant are still development values (D-7).

## Incidents during the run

- Docker Desktop was not running at the start; it was started and the local stack brought up with the houseplans override.
- A full API run during CP3.1 verification earlier had shown a teardown TRUNCATE timeout while a web build ran at the same time. Every full run tonight was made with nothing else heavy running, and all were clean.
- A scripted text replacement with an empty match corrupted the uncommitted `apps/web/e2e/floor-plan.spec.ts` during CP4. It was restored from the CP3.2 commit and the CP4 scenario added again. No committed file was affected; the spec passed before the commit.

## State left behind

- Working tree clean.
- No development servers running (the web dev server and the montage servers were stopped).
- The local Docker stack (`p2b-local`) is up and healthy with `infra/local/compose.houseplans.yml`: houseplans on, synthetic ruleset loaded, mock assistant on. It is local only; stop it with `pnpm local:down`.
- Nothing pushed.

## What should be done next

1. Review CP3.1 (E-5), CP3.2 and CP4, and push the branch and tags if accepted.
2. Run the AI benchmark against Gemini with a key and a chosen model. Review the system prompts and the unsupported topics. Decide the production rate limits for the assistant and the edits (D-7).
3. Decide whether the layout solver should read the stated preferences (large living room, kitchen beside dining, private master bedroom). That is solver work, deliberately out of CP4.
4. Decide on a web screen for describing a home in words before generation (the API is ready).
5. AD-16 final disclaimer wording before any production use.
6. Only then CP5 (3D), as directed.
