"""Checkpoint 4, API side: the AI assistant proposes, the owner confirms through the operations
route, the validator decides. Runs with the deterministic mock interpreter (no credentials)."""

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response

from p2b.core.ai_text import TextProviderError
from p2b.core.db import Database
from p2b.integrations.ai_text import MockTextProvider
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.execution_support import household
from tests.test_houseplans_api import (  # noqa: F401  (fixtures)
    _synthetic_rules_allowed,
    edit_plan,
    plan_app,
    valid_plan,
    worker,
)
from tests.test_projects import H


@pytest.fixture
def assistant_on(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    _synthetic_rules_allowed: None,  # noqa: F811  (applied first: it replaces the settings)
) -> MockTextProvider:
    on = app.state.settings.model_copy(
        update={"houseplans_ai_enabled": True, "ai_text_provider": "mock"}
    )
    monkeypatch.setattr(app.state, "settings", on)
    mock = MockTextProvider()
    monkeypatch.setattr(app.state, "text_provider", mock)
    return mock


async def ask(
    client: AsyncClient, project_id: str, plan_id: str, text: str, revision: int
) -> Response:
    return await client.post(
        f"/api/v1/projects/{project_id}/house-plans/{plan_id}/assistant/edit",
        json={"text": text, "expected_revision": revision},
        headers=H,
    )


async def test_a_proposal_is_validated_shown_and_stored_only_when_the_owner_applies_it(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,  # noqa: F811
    assistant_on: MockTextProvider,
) -> None:
    family, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    url = f"/api/v1/projects/{project_id}/house-plans/{plan_id}"
    assert detail["editing"]["assistant"] is True
    living = next(r for r in detail["document"]["floors"][0]["rooms"] if r["type"] == "LIVING")

    proposed = await ask(family, project_id, plan_id, f"Make the {living['name']} bigger", 0)
    assert proposed.status_code == 200, proposed.text
    body = proposed.json()
    assert body["status"] == "PROPOSED"
    assert body["intent"]["action"] == "RESIZE_ROOM"
    assert body["ops"]
    assert all(op["op"] == "MOVE_EDGE" for op in body["ops"])
    assert body["preview"]["floors"][0]["rooms"]
    change = next(r for r in body["rooms"] if r["room"] == living["id"])
    assert change["area_after_mm2"] > change["area_before_mm2"]
    assert body["call"]["provider"] == "mock"
    assert body["call"]["model_calls"] >= 1
    # nothing stored by proposing
    assert (await family.get(url)).json()["editing"]["revision_no"] == 0

    applied = await edit_plan(family, project_id, plan_id, body["expected_revision"], body["ops"])
    assert applied.status_code == 200, applied.text
    assert applied.json()["validation"]["valid"] is True
    revisions = (await family.get(f"{url}/revisions")).json()
    assert [r["revision_no"] for r in revisions["items"]] == [1]
    undone = await edit_plan(family, project_id, plan_id, 1, applied.json()["inverse"])
    assert undone.status_code == 200
    assert (
        undone.json()["document"]["meta"]["body_sha256"]
        == detail["document"]["meta"]["body_sha256"]
    )

    # a stale proposal cannot be asked for, and applying stale operations is refused as usual
    stale = await ask(family, project_id, plan_id, "Make the kitchen bigger", 0)
    assert stale.status_code == 409


async def test_unsupported_unclear_and_impossible_requests_store_nothing_and_say_why(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,  # noqa: F811
    assistant_on: MockTextProvider,
) -> None:
    family, project_id, plan_id, _ = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    floor = (
        await ask(family, project_id, plan_id, "Add a first floor with two bedrooms", 0)
    ).json()
    assert (floor["status"], floor["detail"], floor["ops"]) == ("UNSUPPORTED", "ADD_FLOOR", [])
    vague = (await ask(family, project_id, plan_id, "Make it nicer", 0)).json()
    assert vague["status"] == "CLARIFY"
    # the only kitchen cannot be removed (E-5): the engine's rule is the answer the owner gets,
    # at once (CP4.1: no repairs of a protected function), and nothing is stored
    kitchen = (await ask(family, project_id, plan_id, "Remove the kitchen", 0)).json()
    assert (kitchen["status"], kitchen["detail"]) == ("FAILED", "LAST_KITCHEN_REQUIRED")
    assert kitchen["call"]["model_calls"] == 1
    assert kitchen["ops"] == []
    assert kitchen["intent"]["action"] == "REMOVE_ROOM"
    assert kitchen["refusal"]["reason"] == "LAST_KITCHEN_REQUIRED"
    rejection = kitchen["refusal"]["rejections"][0]
    assert (rejection["op"], rejection["code"]) == ("DELETE_ROOM", "LAST_KITCHEN_REQUIRED")
    assert rejection["entities"]
    assert vague["refusal"] is None
    assert floor["refusal"] is None
    # requests outside the product are declined by topic, never answered
    for text, topic in (
        ("Is this house plan approved by the municipality?", "PERMIT_COMPLIANCE"),
        ("Generate the construction drawing.", "CONSTRUCTION_DRAWINGS"),
        ("Tell me the foundation size.", "STRUCTURAL_ENGINEERING"),
        ("Certify this house as Vastu compliant.", "VASTU_CERTIFICATION"),
    ):
        declined = (await ask(family, project_id, plan_id, text, 0)).json()
        assert (declined["status"], declined["detail"], declined["ops"]) == (
            "UNSUPPORTED",
            topic,
            [],
        )
    detail = await family.get(f"/api/v1/projects/{project_id}/house-plans/{plan_id}")
    assert detail.json()["editing"]["revision_no"] == 0


async def test_malformed_model_answers_are_repaired_within_the_bound(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,  # noqa: F811
    app: FastAPI,
    assistant_on: MockTextProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family, project_id, plan_id, _ = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    scripted = MockTextProvider(
        script=[
            {"intent": {"action": "RESIZE_ROOM", "room": "living", "change": "LARGER", "x": 5}},
            TextProviderError("not json", kind="MALFORMED", retryable=False),
            {"intent": {"action": "CLARIFY", "question": "Which side should grow?"}},
        ]
    )
    monkeypatch.setattr(app.state, "text_provider", scripted)
    body = (await ask(family, project_id, plan_id, "Make the living room bigger", 0)).json()
    assert body["status"] == "CLARIFY"
    assert body["call"]["model_calls"] == 3
    # an answer that never fits the schema ends as FAILED after the bound
    monkeypatch.setattr(app.state, "text_provider", MockTextProvider(script=[{"oops": 1}] * 5))
    failed = (await ask(family, project_id, plan_id, "Make the living room bigger", 0)).json()
    assert (failed["status"], failed["detail"], failed["call"]["model_calls"]) == (
        "FAILED",
        "MALFORMED_ANSWER",
        3,
    )
    # a provider that is down or rate-limited (429 after its one retry) is a 503, not a proposal
    for error in ("down", "the model answered 429"):
        monkeypatch.setattr(
            app.state,
            "text_provider",
            MockTextProvider(script=[TextProviderError(error, kind="UNAVAILABLE", retryable=True)]),
        )
        down = await ask(family, project_id, plan_id, "Make the living room bigger", 0)
        assert down.status_code == 503
        assert down.json()["error"]["code"] == "PROVIDER_UNAVAILABLE"
        assert "429" not in down.text  # the provider's own answer is not passed on
    detail = await family.get(f"/api/v1/projects/{project_id}/house-plans/{plan_id}")
    assert detail.json()["editing"]["revision_no"] == 0


async def test_only_the_owner_asks_and_the_feature_is_off_by_default(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,  # noqa: F811
    app: FastAPI,
    assistant_on: MockTextProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family, project_id, plan_id, _ = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    member = await household(database, client_for, make_user, sign_in, project_id)
    assert (await ask(member, project_id, plan_id, "Make the kitchen bigger", 0)).status_code == 403
    seen = (await member.get(f"/api/v1/projects/{project_id}/house-plans/{plan_id}")).json()
    assert seen["editing"]["assistant"] is False
    # free geometry in the request is refused by the schema
    free = await family.post(
        f"/api/v1/projects/{project_id}/house-plans/{plan_id}/assistant/edit",
        json={"text": "bigger", "expected_revision": 0, "ops": [{"op": "MOVE_WALL"}]},
        headers=H,
    )
    assert free.status_code == 422
    off = app.state.settings.model_copy(update={"houseplans_ai_enabled": False})
    monkeypatch.setattr(app.state, "settings", off)
    assert (await ask(family, project_id, plan_id, "Make the kitchen bigger", 0)).status_code == 404
    detail = (await family.get(f"/api/v1/projects/{project_id}/house-plans/{plan_id}")).json()
    assert detail["editing"]["assistant"] is False


async def test_a_description_becomes_requirement_facts_and_differences_never_overwrite(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,  # noqa: F811
    assistant_on: MockTextProvider,
) -> None:
    family, project_id, _, _ = await valid_plan(database, client_for, make_user, sign_in, worker)
    response = await family.post(
        f"/api/v1/projects/{project_id}/house-plans/assistant/requirement",
        json={
            "text": "30 by 50 north facing plot, 4 bedrooms, two bathrooms, one car parking. "
            "I want a large living room, kitchen close to dining, and a private master bedroom."
        },
        headers=H,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "INTERPRETED"
    assert body["intent"]["bedrooms"] == 4
    assert body["design_inputs"]["parking_kind"] == "CAR"
    assert "living_size:LARGE" in body["preferences"]
    assert "setbacks" in body["missing"]
    # the submitted requirement differs on bedrooms: shown, never applied
    assert any(c["key"] == "bedrooms" for c in body["conflicts"])
