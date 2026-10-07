"""Checkpoint 4, engine and provider side: the closed intent schemas, the deterministic edit
compiler on real plans, the requirement bridge into the existing pipeline, the mock interpreter
and the Gemini adapter (over a stubbed HTTP transport: no credentials, no network)."""

import json
from functools import cache
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from p2b.core.ai_text import TextProviderError, TextRequest
from p2b.houseplans.engine import HousePlan, fixture_fit, generate, sha256_of
from p2b.houseplans.engine.assist import (
    AddRoomIntent,
    ChangeRoomType,
    ClarifyIntent,
    EditInterpretation,
    MoveOpeningIntent,
    MoveRoomToward,
    NoProposal,
    Proposal,
    RemoveRoom,
    RenameRoomIntent,
    RequirementIntent,
    ResizeOpeningIntent,
    ResizeRoom,
    UnsupportedIntent,
    compile_edit,
    describe,
    plan_summary,
    requirement_answers,
)
from p2b.houseplans.engine.intent import Normalised, normalise
from p2b.houseplans.engine.solver.zoned_ls import ZonedLocalSearchSolver
from p2b.integrations.ai_text import GeminiTextProvider, MockTextProvider, _inline
from tests.houseplans_support import benchmark_cases, intent_of, ruleset

WEB_FIXTURES = Path(__file__).resolve().parents[2] / "web" / "tests" / "fixtures" / "houseplans"
NAME = "3bhk_45x70_two_cars_puja"


@cache
def plan() -> HousePlan:
    data = json.loads((WEB_FIXTURES / f"{NAME}.json").read_text("utf-8"))
    return HousePlan.model_validate(data["document"])


def reason(result: Proposal | NoProposal) -> str:
    return result.reason if isinstance(result, NoProposal) else "PROPOSED"


def compiled(intent: Any) -> Proposal | NoProposal:
    return compile_edit(
        plan(), intent, ruleset(), arch=intent_of(benchmark_cases()[NAME], ruleset())
    )


# ---------- schemas ----------


def test_the_edit_schema_is_closed_and_takes_no_geometry() -> None:
    ok = EditInterpretation.model_validate(
        {"intent": {"action": "RESIZE_ROOM", "room": "living", "change": "LARGER"}}
    )
    assert isinstance(ok.intent, ResizeRoom)
    for bad in (
        {"intent": {"action": "RESIZE_ROOM", "room": "living", "change": "LARGER", "x": 100}},
        {"intent": {"action": "MOVE_WALL", "wall": "w1", "delta_mm": 100}},
        {"intent": {"action": "ADD_ROOM", "room_type": "STUDY"}},  # not a room type
        {"intent": {"action": "RESIZE_ROOM", "room": "Living Room!", "change": "LARGER"}},
        {"intent": {"action": "CLARIFY", "question": ""}},
        {"intent": {"action": "UNSUPPORTED", "topic": "MAGIC"}},
        {},
    ):
        with pytest.raises(ValidationError):
            EditInterpretation.model_validate(bad)
    schema = json.dumps(EditInterpretation.model_json_schema())
    for word in ("offset_mm", "delta_mm", "x0", "polygon"):
        assert word not in schema


def test_the_requirement_schema_rejects_out_of_range_and_extra_fields() -> None:
    RequirementIntent.model_validate({"plot": {"width_ft": 30, "depth_ft": 50}, "bedrooms": 3})
    for bad in (
        {"bedrooms": 40},
        {"plot": {"width_ft": -3}},
        {"rooms": [{"x": 0, "y": 0}]},
        {"unsupported": ["CERTIFY_EVERYTHING"]},
    ):
        with pytest.raises(ValidationError):
            RequirementIntent.model_validate(bad)


# ---------- compiling edit intents ----------


def test_every_supported_intent_compiles_to_validated_operations() -> None:
    cases: list[tuple[Any, set[str]]] = [
        (ResizeRoom(room="bedroom_1", change="LARGER"), {"MOVE_EDGE"}),
        (ResizeRoom(room="living", change="SMALLER", amount="SLIGHT"), {"MOVE_EDGE"}),
        (AddRoomIntent(room_type="UTILITY"), {"ADD_ROOM_OUTSIDE"}),
        (ChangeRoomType(room="bedroom_3", room_type="PUJA"), {"SET_ROOM_TYPE", "RENAME_ROOM"}),
        (RemoveRoom(room="puja"), {"DELETE_ROOM"}),
        (RenameRoomIntent(room="bedroom_1", name="Master bedroom"), {"RENAME_ROOM"}),
        (MoveOpeningIntent(room="bedroom_2", opening="DOOR"), {"MOVE_OPENING"}),
        (
            ResizeOpeningIntent(room="living", opening="WINDOW", change="WIDER"),
            {"SET_OPENING", "MOVE_OPENING"},
        ),
    ]
    for intent, kinds in cases:
        result = compiled(intent)
        assert isinstance(result, Proposal), (intent, result)
        assert {o.op.value for o in result.ops} == kinds
        assert result.result.report.valid
        # deterministic: the same intent gives the same operations and the same plan
        again = compiled(intent)
        assert isinstance(again, Proposal)
        assert again.ops == result.ops
        assert sha256_of(again.result.plan.body()) == sha256_of(result.result.plan.body())


def test_what_cannot_be_compiled_says_why() -> None:
    assert compiled(UnsupportedIntent(topic="ADD_FLOOR")) == NoProposal(
        "UNSUPPORTED", "ADD_FLOOR", 0
    )
    assert reason(compiled(ClarifyIntent(question="Which room?"))) == "CLARIFY"
    assert reason(compiled(ResizeRoom(room="no_such_room", change="LARGER"))) == "UNKNOWN_ROOM"
    assert reason(compiled(MoveRoomToward(room="kitchen", target="dining"))) == "ALREADY_THERE"
    # the last kitchen cannot go (E-5): every candidate is refused, never forced
    refused = compiled(RemoveRoom(room="kitchen"))
    assert isinstance(refused, NoProposal)
    assert refused.reason == "NOTHING_VALID"
    assert "LAST_KITCHEN_REQUIRED" in refused.detail
    assert reason(compiled(AddRoomIntent(room_type="BEDROOM", area="COURT"))) == "NOTHING_VALID"


def test_a_proposal_is_described_with_the_servers_own_areas() -> None:
    result = compiled(ResizeRoom(room="bedroom_1", change="LARGER"))
    assert isinstance(result, Proposal)
    rooms, _ = describe(plan(), result.result.plan, ruleset())
    bedroom = next(r for r in rooms if r.room == "bedroom_1")
    assert bedroom.kind == "CHANGED"
    assert bedroom.area_after_mm2 is not None
    assert bedroom.area_before_mm2 is not None
    assert bedroom.area_after_mm2 > bedroom.area_before_mm2


def test_the_plan_summary_names_rooms_and_never_carries_coordinates() -> None:
    summary = plan_summary(plan(), ruleset())
    assert {r["id"] for r in summary["rooms"]} == {r.id for r in plan().floors[0].rooms}
    text = json.dumps(summary)
    for word in ("nodes", "walls", "polygon", "x0", "offset_mm"):
        assert word not in text


# ---------- requirement bridge into the existing pipeline ----------


def test_a_complete_description_generates_through_the_existing_solver() -> None:
    intent = RequirementIntent.model_validate(
        {
            "plot": {
                "width_ft": 30,
                "depth_ft": 50,
                "facing": "N",
                "setbacks_ft": {"FRONT": 5, "BACK": 3, "LEFT": 2, "RIGHT": 2},
            },
            "bedrooms": 2,
            "bathrooms": 1,
            "attached_bathrooms": 0,
            "dining": "IN_LIVING",
            "kitchen": "OPEN",
            "utility": True,
            "pooja_room": False,
            "parking": {"kind": "TWO_WHEELER", "spaces": 1},
            "living_size": "LARGE",
            "adjacencies": [{"a": "KITCHEN", "b": "DINING"}],
        }
    )
    bridge = requirement_answers(intent)
    assert bridge.missing == ()
    assert bridge.preferences == ("living_size:LARGE", "adjacent:KITCHEN-DINING:PREFERRED")
    rules = ruleset()
    outcome = normalise(
        bridge.answers,
        bridge.design_inputs,
        rules,
        question_set_version=1,
        requirement_version=1,
        ruleset_version=1,
        ruleset_sha256=sha256_of(rules),
    )
    assert isinstance(outcome, Normalised)
    result = generate(
        outcome.intent,
        rules,
        ruleset_version=1,
        ruleset_sha256="0" * 64,
        solver=ZonedLocalSearchSolver(rules, fixture_fit(rules)),
        seed=0,
    )
    assert result.plan is not None
    assert result.report is not None
    assert result.report.valid


def test_missing_facts_are_listed_never_assumed_and_other_floors_are_unsupported() -> None:
    bridge = requirement_answers(
        RequirementIntent.model_validate({"bedrooms": 3, "floors": 2, "unsupported": ["ADD_FLOOR"]})
    )
    assert {"plot_size", "facing", "setbacks", "bathrooms", "parking"} <= set(bridge.missing)
    assert bridge.unsupported == ("ADD_FLOOR",)
    assert "plot_width_ft" not in bridge.answers
    assert set(bridge.assumed) == {"pooja_room", "utility"}


# ---------- providers ----------


async def test_the_mock_interprets_plain_requests_deterministically() -> None:
    mock = MockTextProvider()
    summary = plan_summary(plan(), ruleset())

    async def edit(text: str, failure: str | None = None) -> Any:
        user = {"plan": summary, "request": text}
        if failure:
            user["previous_failure"] = failure
        request = TextRequest("edit", "s", json.dumps(user), {}, "r")
        return EditInterpretation.model_validate((await mock.structured(request)).data).intent

    assert isinstance(await edit("Make bedroom 1 bigger"), ResizeRoom)
    assert (await edit("Make bedroom 1 bigger", "NOTHING_VALID")).amount == "SLIGHT"
    assert isinstance(await edit("Add a utility room in the rear yard"), AddRoomIntent)
    assert isinstance(await edit("Change bedroom 3 into a puja room"), ChangeRoomType)
    assert (await edit("Change bedroom 3 into a study")).topic == "UNSUPPORTED_ROOM_TYPE"
    assert (await edit("Add a first floor")).topic == "ADD_FLOOR"
    assert (
        await edit("Give me more privacy around the master bedroom")
    ).topic == "PRIVACY_REDESIGN"
    assert isinstance(await edit("Do something nice"), ClarifyIntent)
    requirement = await mock.structured(
        TextRequest(
            "requirement",
            "s",
            json.dumps({"request": "30 by 50 plot, 3 bedrooms, two bathrooms, one car parking"}),
            {},
            "r",
        )
    )
    parsed = RequirementIntent.model_validate(requirement.data)
    assert parsed.plot.width_ft == 30
    assert parsed.plot.depth_ft == 50
    assert (parsed.bedrooms, parsed.bathrooms) == (3, 2)
    assert parsed.parking is not None
    assert parsed.parking.kind == "CAR"


def _gemini(handler: Any, attempts: int = 2) -> GeminiTextProvider:
    return GeminiTextProvider(
        api_key="test-key",
        model="configured-model",
        base_url="https://example.invalid/v1beta",
        timeout_seconds=5,
        attempts=attempts,
        transport=httpx.MockTransport(handler),
    )


async def test_the_gemini_adapter_asks_for_schema_json_and_reads_the_answer() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["body"] = json.loads(request.content)
        answer = {"intent": {"action": "CLARIFY", "question": "Which room?"}}
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}],
                "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 9},
            },
        )

    schema = EditInterpretation.model_json_schema()
    result = await _gemini(handler).structured(TextRequest("edit", "system", "user", schema, "rid"))
    assert seen["url"] == "https://example.invalid/v1beta/models/configured-model:generateContent"
    assert seen["key"] == "test-key"
    config = seen["body"]["generationConfig"]
    assert config["responseMimeType"] == "application/json"
    assert "$ref" not in json.dumps(config["responseJsonSchema"])
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "system"
    assert result.data["intent"]["action"] == "CLARIFY"
    assert result.usage is not None
    assert (result.usage.input_tokens, result.usage.output_tokens) == (120, 9)
    assert "$ref" not in json.dumps(_inline(schema))


async def test_the_gemini_adapter_retries_transient_failures_and_stops() -> None:
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})

    result = await _gemini(flaky).structured(TextRequest("edit", "s", "u", {}, "r"))
    assert result.attempts == 2

    def refused(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400)

    calls["n"] = 0
    with pytest.raises(TextProviderError) as caught:
        await _gemini(refused).structured(TextRequest("edit", "s", "u", {}, "r"))
    assert caught.value.kind == "REJECTED"
    assert calls["n"] == 1  # a refusal is not retried

    def garbage(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}
        )

    with pytest.raises(TextProviderError) as malformed:
        await _gemini(garbage).structured(TextRequest("edit", "s", "u", {}, "r"))
    assert malformed.value.kind == "MALFORMED"

    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(TextProviderError) as timeout:
        await _gemini(slow, attempts=2).structured(TextRequest("edit", "s", "u", {}, "r"))
    assert timeout.value.kind == "TIMEOUT"


def test_the_settings_keep_the_assistant_off_and_the_mock_out_of_production() -> None:
    from p2b.core.config import Settings, get_settings

    base = get_settings()
    assert base.houseplans_ai_enabled is False or base.env in ("local", "test")
    with pytest.raises(ValueError, match="mock text model"):
        Settings.model_validate({**base.model_dump(), "env": "staging", "ai_text_provider": "mock"})
    with pytest.raises(ValueError, match="P2B_GEMINI_API_KEY"):
        Settings.model_validate({**base.model_dump(), "ai_text_provider": "gemini"})
    assert Settings.model_fields["houseplans_ai_enabled"].default is False
    assert Settings.model_fields["ai_text_provider"].default == "none"
    assert Settings.model_fields["ai_text_model"].default is None
