"""Checkpoint 4 AI benchmark: requirement and edit prompts through the same path as the API.

    cd apps/api && uv run python scripts/benchmark_houseplan_assistant.py OUT.json
        [--provider mock|gemini]

`--pace SECONDS` spaces model calls for free-tier rate limits. Each row records the model
calls (time, schema validity, action) apart from the engine's time.
`mock` (default) runs offline with the deterministic interpreter, so it measures the pipeline
(schema validity, compilation, validator pass rate, repairs, latency), not language
understanding. `gemini` needs P2B_GEMINI_API_KEY and P2B_AI_TEXT_MODEL and measures the model
too; P2B_AI_PRICE_IN_PER_MTOK and P2B_AI_PRICE_OUT_PER_MTOK (USD per million tokens), when
set, turn token counts into an estimated cost. Labels are in
tests/fixtures/houseplans/ai_benchmark_cp4.json and were fixed before the first run."""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from pathlib import Path
from typing import Any

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT / "scripts"))

from benchmark_houseplans import intent_of, load  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from p2b.core.ai_text import TextProvider, TextProviderError, TextRequest  # noqa: E402
from p2b.core.errors import ProviderUnavailable  # noqa: E402
from p2b.houseplans.assistant import (  # noqa: E402
    REQUIREMENT_SYSTEM,
    interpret_edit,
)
from p2b.houseplans.engine import (  # noqa: E402
    HousePlan,
    ZonedLocalSearchSolver,
    fixture_fit,
    generate,
    sha256_of,
)
from p2b.houseplans.engine.assist import (  # noqa: E402
    EditInterpretation,
    RequirementIntent,
    requirement_answers,
)
from p2b.houseplans.engine.intent import Normalised, normalise  # noqa: E402
from p2b.integrations.ai_text import GeminiTextProvider, MockTextProvider  # noqa: E402

FIXTURES = API_ROOT / "tests" / "fixtures" / "houseplans"
WEB_FIXTURES = API_ROOT.parent / "web" / "tests" / "fixtures" / "houseplans"


def provider_of(name: str) -> TextProvider:
    if name == "mock":
        return MockTextProvider()
    key, model = os.environ.get("P2B_GEMINI_API_KEY"), os.environ.get("P2B_AI_TEXT_MODEL")
    if not key or not model:
        raise SystemExit("gemini needs P2B_GEMINI_API_KEY and P2B_AI_TEXT_MODEL")
    return GeminiTextProvider(
        api_key=key,
        model=model,
        base_url="https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds=30,
        attempts=2,
    )


class Timed:
    """Wraps a provider to record each model call: its duration, whether the answer fits the
    intent schema, and the action it named. Paces calls (`--pace`) for free-tier rate limits.
    Records no prompt or answer text beyond the action and the room id."""

    def __init__(self, inner: TextProvider, pace: float):
        self.inner, self.pace = inner, pace
        self.name, self.model, self.configured = inner.name, inner.model, inner.configured
        self.calls: list[dict[str, Any]] = []
        self.paused_ms = 0.0

    async def structured(self, request: TextRequest) -> Any:
        if self.pace and self.calls:
            await asyncio.sleep(self.pace)
            self.paused_ms += self.pace * 1000
        started = time.perf_counter()
        record: dict[str, Any] = {"task": request.task}
        try:
            result = await self.inner.structured(request)
        except TextProviderError as error:
            record |= {
                "ms": round((time.perf_counter() - started) * 1000, 1),
                "error": error.kind,
                "message": str(error),  # e.g. "the model answered 429"; never the key
            }
            self.calls.append(record)
            raise
        record["ms"] = round((time.perf_counter() - started) * 1000, 1)
        model = EditInterpretation if request.task == "edit" else RequirementIntent
        try:
            parsed = model.model_validate(result.data)
            record["schema_valid"] = True
            if isinstance(parsed, EditInterpretation):
                record["action"] = parsed.intent.action
                record["room"] = getattr(parsed.intent, "room", None)
        except ValidationError:
            record["schema_valid"] = False
            raw = result.data.get("intent", {}) if isinstance(result.data, dict) else {}
            record["action"] = raw.get("action") if isinstance(raw, dict) else None
        self.calls.append(record)
        return result

    def take(self) -> list[dict[str, Any]]:
        out, self.calls = self.calls, []
        return out

    def pauses(self) -> float:
        """Pacing time since the last call to this method (neither model nor engine time)."""
        out, self.paused_ms = self.paused_ms, 0.0
        return out


def pct(values: list[float], q: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))] if ordered else 0.0


def check(expect: dict[str, Any], intent: RequirementIntent) -> list[str]:
    got = {
        "width_ft": float(intent.plot.width_ft) if intent.plot.width_ft is not None else None,
        "depth_ft": float(intent.plot.depth_ft) if intent.plot.depth_ft is not None else None,
        "facing": intent.plot.facing.value if intent.plot.facing else None,
        "bedrooms": intent.bedrooms,
        "bathrooms": intent.bathrooms,
        "parking": intent.parking.kind if intent.parking else None,
        "living_size": intent.living_size,
        "pooja_room": intent.pooja_room,
        "utility": intent.utility,
        "vastu": intent.vastu,
    }
    wrong = []
    for key, value in expect.items():
        if key in got and got[key] != (float(value) if key.endswith("_ft") else value):
            wrong.append(key)
        if key == "adjacency" and not any(f"{a.a}-{a.b}" == value for a in intent.adjacencies):
            wrong.append(key)
        if key == "unsupported" and value not in intent.unsupported:
            wrong.append(key)
        if key == "missing" and value not in requirement_answers(intent).missing:
            wrong.append(key)
    return wrong


async def requirements(provider: TextProvider, cases: list[dict[str, Any]]) -> dict[str, Any]:
    _, rules, _ = load(FIXTURES)
    solver = ZonedLocalSearchSolver(rules, fixture_fit(rules))
    rows = []
    for case in cases:
        if isinstance(provider, Timed):
            provider.pauses()
        started = time.perf_counter()
        row: dict[str, Any] = {
            "id": case["id"],
            "category": "requirement",
            "expect": case["expect"],
        }
        try:
            result = await provider.structured(
                TextRequest(
                    "requirement",
                    REQUIREMENT_SYSTEM,
                    json.dumps({"request": case["text"]}),
                    RequirementIntent.model_json_schema(),
                    str(uuid.uuid4()),
                )
            )
            intent = RequirementIntent.model_validate(result.data)
            row["schema_valid"] = True
            row["wrong_fields"] = check(case["expect"], intent)
            bridge = requirement_answers(intent)
            row["missing"] = list(bridge.missing)
            row["unsupported"] = list(bridge.unsupported)
            if case["expect"].get("complete"):
                outcome = normalise(
                    bridge.answers,
                    bridge.design_inputs,
                    rules,
                    question_set_version=1,
                    requirement_version=1,
                    ruleset_version=1,
                    ruleset_sha256=sha256_of(rules),
                )
                if isinstance(outcome, Normalised):
                    plan = generate(
                        outcome.intent,
                        rules,
                        ruleset_version=1,
                        ruleset_sha256="0" * 64,
                        solver=solver,
                        seed=0,
                    )
                    row["generated_valid"] = bool(plan.report and plan.report.valid)
                else:
                    row["generated_valid"] = False
            row["tokens"] = (
                (result.usage.input_tokens or 0) + (result.usage.output_tokens or 0)
                if result.usage
                else 0
            )
        except (TextProviderError, ValidationError) as error:
            row["schema_valid"] = False
            row["error"] = type(error).__name__
        paused = provider.pauses() if isinstance(provider, Timed) else 0.0
        row["ms"] = round((time.perf_counter() - started) * 1000 - paused, 1)
        if isinstance(provider, Timed):
            row["calls"] = provider.take()
            row["model_ms"] = round(sum(c["ms"] for c in row["calls"]), 1)
        rows.append(row)
    return {
        "cases": rows,
        "schema_valid": sum(r["schema_valid"] for r in rows),
        "all_fields_right": sum(1 for r in rows if r.get("schema_valid") and not r["wrong_fields"]),
        "generated_valid": [r["id"] for r in rows if r.get("generated_valid")],
        "total": len(rows),
    }


async def edits(provider: TextProvider, cases: list[dict[str, Any]]) -> dict[str, Any]:
    corpus, rules, _ = load(FIXTURES)
    rows = []
    for case in cases:
        name = case["plan"]
        plan = HousePlan.model_validate(
            json.loads((WEB_FIXTURES / f"{name}.json").read_text("utf-8"))["document"]
        )
        arch = intent_of(corpus[name], rules)
        if isinstance(provider, Timed):
            provider.pauses()
        started = time.perf_counter()
        try:
            outcome = await interpret_edit(
                provider, plan, rules, arch, case["text"], max_repairs=2, expected_revision=0
            )
        except ProviderUnavailable:
            # an outage or rate limit: recorded against the prompt, the run goes on
            calls = provider.take() if isinstance(provider, Timed) else []
            rows.append(
                {
                    "id": case["id"],
                    "category": "edit",
                    "plan": name,
                    "expect": case["expect"],
                    "calls": calls,
                    "status": "PROVIDER_ERROR",
                    "action": None,
                    "action_right": False,
                    "room_right": False,
                    "outcome_right": False,
                    "validator_pass": False,
                    "model_calls": len(calls),
                    "schema_valid_answers": 0,
                    "model_ms": round(sum(c["ms"] for c in calls), 1),
                    "engine_ms": 0.0,
                    "tokens": 0,
                    "ms": round((time.perf_counter() - started) * 1000, 1),
                    "ops": [],
                    "detail": "PROVIDER_ERROR",
                }
            )
            continue
        expect = case["expect"]
        action = (outcome.intent or {}).get("action")
        paused = provider.pauses() if isinstance(provider, Timed) else 0.0
        total = round((time.perf_counter() - started) * 1000 - paused, 1)
        calls = provider.take() if isinstance(provider, Timed) else []
        model_ms = round(sum(c["ms"] for c in calls), 1)
        rows.append(
            {
                "id": case["id"],
                "category": "edit",
                "plan": name,
                "expect": expect,
                "calls": calls,
                "schema_valid_answers": sum(1 for c in calls if c.get("schema_valid")),
                "model_ms": model_ms,
                "engine_ms": round(total - model_ms, 1),  # pacing pauses excluded
                "detail": outcome.detail,
                "status": outcome.status,
                "action": action,
                "action_right": action == expect["action"],
                "room_right": "room" not in expect
                or (outcome.intent or {}).get("room") == expect["room"],
                "outcome_right": "outcome" not in expect or outcome.status == expect["outcome"],
                "validator_pass": outcome.status == "PROPOSED",
                "model_calls": outcome.call.attempts,
                "tokens": outcome.call.input_tokens + outcome.call.output_tokens,
                "ms": round((time.perf_counter() - started) * 1000, 1),
                "ops": [o.op.value for o in outcome.ops],
            }
        )
    return {
        "cases": rows,
        "action_right": sum(r["action_right"] for r in rows),
        "room_right": sum(r["room_right"] for r in rows),
        "outcome_right": sum(r["outcome_right"] for r in rows),
        "proposed": sum(r["validator_pass"] for r in rows),
        "repairs": sum(max(0, r["model_calls"] - 1) for r in rows),
        "provider_errors": sum(r["status"] == "PROVIDER_ERROR" for r in rows),
        "total": len(rows),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--provider", default="mock", choices=("mock", "gemini"))
    parser.add_argument("--pace", type=float, default=0.0, help="seconds between model calls")
    parser.add_argument("--only", default="", help="comma-separated prompt ids (a rerun subset)")
    args = parser.parse_args()
    data = json.loads((FIXTURES / "ai_benchmark_cp4.json").read_text("utf-8"))
    if args.only:
        keep = set(args.only.split(","))
        data = {k: [c for c in data[k] if c["id"] in keep] for k in ("requirement", "edit")}
    provider = Timed(provider_of(args.provider), args.pace)
    req = await requirements(provider, data["requirement"])
    ed = await edits(provider, data["edit"])
    latencies = [r["ms"] for r in req["cases"] + ed["cases"]]
    model_calls = [c["ms"] for r in req["cases"] + ed["cases"] for c in r.get("calls", [])]
    engine = [r["engine_ms"] for r in ed["cases"]]
    tokens = sum(r.get("tokens", 0) for r in req["cases"] + ed["cases"])
    price_in = os.environ.get("P2B_AI_PRICE_IN_PER_MTOK")
    report = {
        "provider": provider.name,
        "model": provider.model,
        "requirement": req,
        "edit": ed,
        "latency_ms": {
            "median": statistics.median(latencies),
            "p95": pct(latencies, 0.95),
            "max": max(latencies),
        },
        "model_call_ms": {
            "median": statistics.median(model_calls) if model_calls else None,
            "p95": pct(model_calls, 0.95),
            "count": len(model_calls),
        },
        "engine_ms_per_edit": {
            "median": statistics.median(engine) if engine else None,
            "p95": pct(engine, 0.95),
        },
        "tokens": tokens,
        "estimated_cost_usd": None if not price_in else round(tokens / 1e6 * float(price_in), 6),
    }
    await asyncio.to_thread(Path(args.out).write_text, json.dumps(report, indent=2), "utf-8")
    summary = {k: v for k, v in req.items() if k != "cases"} | {
        f"edit_{k}": v for k, v in ed.items() if k != "cases"
    }
    print(json.dumps(summary | {"latency_ms": report["latency_ms"]}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
