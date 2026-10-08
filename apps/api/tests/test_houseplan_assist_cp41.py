"""Checkpoint 4.1: the engine's refusal reaches the owner as it is, requests outside the product
are declined by topic, rate limits stay a clean "unavailable", and the plan summary the model
reads stays compact and free of geometry. Real plans, the mock interpreter and a stubbed HTTP
transport: no credentials, no network."""

import json
from functools import cache
from pathlib import Path
from typing import Any

import httpx
import pytest

from p2b.core.ai_text import TextRequest
from p2b.core.errors import ProviderUnavailable
from p2b.houseplans.assistant import EditOutcome, interpret_edit
from p2b.houseplans.engine import HousePlan, sha256_of
from p2b.houseplans.engine.assist import EditInterpretation, plan_summary
from p2b.integrations.ai_text import GeminiTextProvider, MockTextProvider, _inline
from tests.houseplans_support import benchmark_cases, intent_of, ruleset

WEB_FIXTURES = Path(__file__).resolve().parents[2] / "web" / "tests" / "fixtures" / "houseplans"
BENCHMARK = Path(__file__).resolve().parent / "fixtures" / "houseplans" / "ai_benchmark_cp4.json"
LARGE = "3bhk_45x70_two_cars_puja"  # several bathrooms, one kitchen
SMALL = "1bhk_25x40_south_small"  # one kitchen, one bathroom
WIDE = "prop_very_wide_80x28"


@cache
def plan(name: str) -> HousePlan:
    data = json.loads((WEB_FIXTURES / f"{name}.json").read_text("utf-8"))
    return HousePlan.model_validate(data["document"])


async def ask(name: str, text: str, provider: Any) -> EditOutcome:
    return await interpret_edit(
        provider,
        plan(name),
        ruleset(),
        intent_of(benchmark_cases()[name], ruleset()),
        text,
        max_repairs=2,
        expected_revision=0,
    )


def scripted(*intents: dict[str, Any]) -> MockTextProvider:
    return MockTextProvider(script=[{"intent": i} for i in intents])


def room_of(name: str, room_type: str) -> str:
    return next(r.id for r in plan(name).floors[0].rooms if r.type.value == room_type)


# ---------- the engine's refusal is final ----------


@pytest.mark.parametrize(
    ("name", "intent", "code"),
    [
        (LARGE, {"action": "REMOVE_ROOM", "room": "kitchen"}, "LAST_KITCHEN_REQUIRED"),
        (
            LARGE,
            {"action": "CHANGE_ROOM_TYPE", "room": "kitchen", "room_type": "UTILITY"},
            "LAST_KITCHEN_REQUIRED",
        ),
        (SMALL, {"action": "REMOVE_ROOM", "room": "BATH"}, "LAST_BATHROOM_REQUIRED"),
        (
            SMALL,
            {"action": "CHANGE_ROOM_TYPE", "room": "BATH", "room_type": "PUJA"},
            "LAST_BATHROOM_REQUIRED",
        ),
    ],
)
async def test_a_protected_function_ends_the_request_with_the_engines_own_reason(
    name: str, intent: dict[str, Any], code: str
) -> None:
    if intent["room"] == "BATH":
        intent = intent | {"room": room_of(name, "BATH_COMMON")}
    before = sha256_of(plan(name).body())
    # the model would ask instead on a repair: it is never given the chance to hide the rule
    provider = scripted(intent, {"action": "CLARIFY", "question": "Shall we keep it?"})
    outcome = await ask(name, "remove or change it", provider)
    assert (outcome.status, outcome.detail, outcome.ops) == ("FAILED", code, ())
    assert outcome.refusal is not None
    assert outcome.refusal.reason == code
    assert [r.code.value for r in outcome.refusal.refused.rejections] == [code]
    assert outcome.intent is not None
    assert outcome.intent["action"] == intent["action"]
    assert outcome.call.attempts == 1  # a rule, not a reading to repair
    assert sha256_of(plan(name).body()) == before


async def test_the_models_rewording_after_a_refusal_never_replaces_the_engines_reason() -> None:
    # no open area of this plan fits a bedroom: the model then calls it unsupported
    provider = scripted(
        {"action": "ADD_ROOM", "room_type": "BEDROOM", "area": "COURT"},
        {"action": "UNSUPPORTED", "topic": "OTHER"},
    )
    outcome = await ask(LARGE, "Add a bedroom in the court", provider)
    assert (outcome.status, outcome.detail) == ("FAILED", "NO_PLACE_FOR_ROOM")
    assert outcome.refusal is not None
    assert outcome.refusal.reason == "NO_PLACE_FOR_ROOM"
    assert outcome.intent == {"action": "ADD_ROOM", "room_type": "BEDROOM", "area": "COURT"}
    assert outcome.call.attempts == 2
    # and a clarifying question after the refusal is not shown in its place either
    provider = scripted(
        {"action": "ADD_ROOM", "room_type": "BEDROOM", "area": "COURT"},
        {"action": "CLARIFY", "question": "Which open area?"},
    )
    assert (await ask(LARGE, "Add a bedroom in the court", provider)).detail == "NO_PLACE_FOR_ROOM"


async def test_rules_that_stop_every_candidate_are_reported_once_each() -> None:
    provider = scripted(
        *[{"action": "RESIZE_ROOM", "room": "bedroom_2", "change": "LARGER", "amount": a}
          for a in ("MODERATE", "SLIGHT", "SLIGHT")]
    )  # fmt: skip
    outcome = await ask(WIDE, "Make bedroom 2 bigger", provider)
    assert (outcome.status, outcome.detail) == ("FAILED", "RULES_NOT_MET")
    assert outcome.refusal is not None
    refused = outcome.refusal.refused
    assert refused.rejections or refused.issues
    codes = [r.code for r in refused.rejections] + [i.code for i in refused.issues]
    assert len(codes) == len(set(codes))  # the first of each code, no repeats
    assert len(refused.rejections) <= 4
    assert len(refused.issues) <= 4
    assert all(i.message for i in refused.issues)  # the validator's own words
    assert outcome.call.attempts == 3  # the bound, unchanged


async def test_a_later_reading_that_passes_is_still_proposed() -> None:
    provider = scripted(
        {"action": "ADD_ROOM", "room_type": "BEDROOM", "area": "COURT"},
        {"action": "RESIZE_ROOM", "room": "bedroom_1", "change": "LARGER", "amount": "SLIGHT"},
    )
    outcome = await ask(LARGE, "Give bedroom 1 more room", provider)
    assert outcome.status == "PROPOSED"
    assert outcome.refusal is None


async def test_unsupported_and_clarify_without_a_refusal_are_unchanged() -> None:
    outcome = await ask(LARGE, "x", scripted({"action": "CLARIFY", "question": "Which room?"}))
    assert (outcome.status, outcome.detail, outcome.refusal) == ("CLARIFY", "Which room?", None)
    # an unknown room is the model's mistake, not the engine's refusal
    provider = MockTextProvider(script=[{"intent": {"action": "REMOVE_ROOM", "room": "nope"}}] * 3)
    unclear = await ask(LARGE, "remove the nope", provider)
    assert (unclear.status, unclear.refusal) == ("FAILED", None)


# ---------- requests outside the product ----------


def safety_cases() -> list[dict[str, Any]]:
    return list(json.loads(BENCHMARK.read_text("utf-8"))["safety"])


@pytest.mark.parametrize("case", safety_cases(), ids=lambda c: c["id"])
async def test_permits_drawings_structure_and_vastu_certification_are_declined(
    case: dict[str, Any],
) -> None:
    outcome = await ask(case["plan"], case["text"], MockTextProvider())
    assert outcome.status == "UNSUPPORTED"
    assert outcome.detail in case["expect"]["topics"]
    assert outcome.ops == ()
    assert outcome.plan is None


def test_the_safety_benchmark_covers_every_boundary_and_the_schema_offers_each_topic() -> None:
    topics = {t for c in safety_cases() for t in c["expect"]["topics"]}
    assert topics == {
        "PERMIT_COMPLIANCE",
        "CONSTRUCTION_DRAWINGS",
        "STRUCTURAL_ENGINEERING",
        "VASTU_CERTIFICATION",
    }
    sent = json.dumps(_inline(EditInterpretation.model_json_schema()))
    for topic in topics:
        assert f'"{topic}"' in sent


# ---------- rate limits ----------


def _gemini(handler: Any) -> GeminiTextProvider:
    return GeminiTextProvider(
        api_key="test-key",
        model="test-model",
        base_url="https://example.invalid/v1beta",
        timeout_seconds=5,
        attempts=2,
        transport=httpx.MockTransport(handler),
    )


async def test_a_rate_limit_is_unavailable_after_the_bounded_retry_and_proposes_nothing() -> None:
    calls = {"n": 0}

    def limited(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}})

    before = sha256_of(plan(LARGE).body())
    with pytest.raises(ProviderUnavailable):
        await ask(LARGE, "Make bedroom 1 bigger", _gemini(limited))
    assert calls["n"] == 2  # one retry, then stop
    assert sha256_of(plan(LARGE).body()) == before


async def test_a_rate_limit_during_a_repair_is_unavailable_too() -> None:
    answers = iter([{"intent": {"action": "ADD_ROOM", "room_type": "BEDROOM", "area": "COURT"}}])
    calls = {"n": 0}

    def first_then_limited(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        answer = next(answers, None)
        if answer is None:
            return httpx.Response(429)
        text = json.dumps(answer)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})

    with pytest.raises(ProviderUnavailable):
        await ask(LARGE, "Add a bedroom in the court", _gemini(first_then_limited))
    assert calls["n"] == 3  # the reading, then the repair and its one retry


async def test_the_adapter_never_loops_on_rate_limits() -> None:
    calls = {"n": 0}

    def limited(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429)

    provider = _gemini(limited)
    for _ in range(3):
        with pytest.raises(Exception, match="429"):
            await provider.structured(TextRequest("edit", "s", "u", {}, "r"))
    assert calls["n"] == 6  # two per request, every time


# ---------- the compact plan summary ----------


def test_the_summary_sends_every_room_fact_in_rows_and_no_geometry() -> None:
    from p2b.houseplans.engine import plan_geometry

    for name in (LARGE, SMALL, WIDE):
        summary = plan_summary(plan(name), ruleset())
        assert summary == plan_summary(plan(name), ruleset())  # deterministic
        columns = summary["room_columns"].split("|")
        assert columns == ["id", "name", "type", "clear_m", "area_m2", "openings"]
        geometry = plan_geometry(plan(name), ruleset()).floors[0]
        rows = {row.split("|")[0]: dict(zip(columns, row.split("|"), strict=True)) for row in
                summary["rooms"]}  # fmt: skip
        assert set(rows) == {r.id for r in geometry.rooms}
        for r in geometry.rooms:
            row = rows[r.id]
            assert (row["name"], row["type"]) == (r.name, r.type)
            w, d = (float(v) for v in row["clear_m"].split("x"))
            assert abs(w - (r.clear_w_mm or 0) / 1000) < 0.006
            assert abs(d - (r.clear_d_mm or 0) / 1000) < 0.006
            assert abs(float(row["area_m2"]) - (r.carpet_area_mm2 or 0) / 1e6) < 0.006
            kinds = {o.kind for o in geometry.openings if r.id in o.connects}
            assert set(row["openings"].split()) == kinds
        assert summary["open_areas"] == sorted({a.kind for a in geometry.open_areas or []})
        text = json.dumps(summary)
        for word in ("nodes", "walls", "polygon", "x0", "offset_mm", "jamb"):
            assert word not in text


def test_a_separator_in_a_room_name_cannot_shift_the_columns() -> None:
    room = plan(SMALL).floors[0].rooms[0]
    renamed = plan(SMALL).model_copy(deep=True)
    renamed.floors[0].rooms[0] = room.model_copy(update={"name": "Mum|Dad's room"})
    row = next(r for r in plan_summary(renamed, ruleset())["rooms"] if r.startswith(room.id))
    assert row.split("|")[1] == "Mum/Dad's room"
    assert len(row.split("|")) == 6
