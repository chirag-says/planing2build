"""Checkpoint 3.2, API side: the plan detail offers insertion slots to the owner only, and a room
added in open space goes through the operations route, the validator, the log and restore."""

from typing import Any

from p2b.core.db import Database
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.execution_support import household
from tests.test_houseplans_api import (  # noqa: F401  (fixtures)
    _synthetic_rules_allowed,
    edit_plan,
    plan_app,
    valid_plan,
    worker,
)


def fitting(detail: dict[str, Any]) -> dict[str, Any]:
    """The first ADD_ROOM_OUTSIDE from the offered slots that the engine's own edit accepts."""
    from p2b.houseplans.engine import ArchitecturalIntent, HousePlan
    from p2b.houseplans.engine.edit import BatchRejected, edit
    from p2b.houseplans.engine.model import dump
    from p2b.houseplans.engine.ops import AddRoomOutside
    from tests.houseplans_support import ruleset

    plan = HousePlan.model_validate(detail["document"])
    intent = ArchitecturalIntent.model_validate(detail["intent"])
    rules = ruleset()
    for slot in detail["editing"]["insertion_slots"]:
        for room_type in ("UTILITY", "WC", "PUJA", "BEDROOM"):
            rule = rules.rooms[room_type]  # type: ignore[index]
            depth = min(slot["max_depth_mm"], rule.min_short_mm + slot["depth_allowance_mm"] + 100)
            length = min(slot["length_mm"], 2500)
            op = AddRoomOutside.model_validate(
                {
                    "host_room": slot["host_room"],
                    "type": room_type,
                    "side": slot["side"],
                    "offset_mm": slot["offset_mm"],
                    "length_mm": length - length % 50,
                    "depth_mm": depth - depth % 50,
                }
            )
            try:
                result = edit(
                    plan, [op], rules, intent=intent, ruleset_version=None, ruleset_sha256=None
                )
            except BatchRejected:
                continue
            if result.report.valid:
                return dump(op)
    raise AssertionError("no room fits in the offered slots")


async def test_a_room_is_added_in_open_space_validated_logged_and_restorable(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,  # noqa: F811
) -> None:
    family, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    url = f"/api/v1/projects/{project_id}/house-plans/{plan_id}"
    slots = detail["editing"]["insertion_slots"]
    assert slots
    assert {"host_room", "side", "offset_mm", "length_mm", "max_depth_mm"} <= set(slots[0])
    assert all(t["min_area_mm2"] for t in detail["editing"]["room_types"])

    op = fitting(detail)
    added = await edit_plan(family, project_id, plan_id, 0, [op])
    assert added.status_code == 200, added.text
    body = added.json()
    assert body["validation"]["valid"] is True
    assert body["inverse"] == [{"op": "REVERT_TO_REVISION", "revision": 0}]
    new = [
        r
        for r in body["document"]["floors"][0]["rooms"]
        if r["id"] not in {x["id"] for x in detail["document"]["floors"][0]["rooms"]}
    ]
    assert [r["type"] for r in new] == [op["type"]]
    assert body["document"]["compromises"][0]["change_key"] == "ROOM_ADDED_BY_OWNER"
    total = sum(a["area_mm2"] for a in detail["geometry"]["floors"][0]["open_areas"])
    after = sum(a["area_mm2"] for a in body["geometry"]["floors"][0]["open_areas"])
    assert after < total

    undone = await edit_plan(family, project_id, plan_id, 1, body["inverse"])
    assert undone.status_code == 200, undone.text
    assert (
        undone.json()["document"]["meta"]["body_sha256"]
        == detail["document"]["meta"]["body_sha256"]
    )

    # outside the buildable area: refused with its reason, nothing stored
    far = {**op, "depth_mm": 900_000}
    refused = await edit_plan(family, project_id, plan_id, 2, [far])
    assert refused.status_code == 422
    assert refused.json()["error"]["details"]["code"] == "OUTSIDE_BUILDABLE_AREA"
    assert (await family.get(url)).json()["editing"]["revision_no"] == 2


async def test_members_see_no_insertion_slots_and_cannot_add(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,  # noqa: F811
) -> None:
    _, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    member = await household(database, client_for, make_user, sign_in, project_id)
    seen = (await member.get(f"/api/v1/projects/{project_id}/house-plans/{plan_id}")).json()
    assert seen["editing"]["insertion_slots"] == []
    forbidden = await edit_plan(member, project_id, plan_id, 0, [fitting(detail)])
    assert forbidden.status_code == 403
