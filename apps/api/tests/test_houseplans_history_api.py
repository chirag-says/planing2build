"""Checkpoint 3.1, API side: structural edits through the operations route, server-side restore of
a revision or a named version (REVERT_TO_REVISION, REVERT_TO_VERSION) rebuilt from the
operation log, named versions, the revision list, and concurrent edits. Real engine plans from the
live queue, as in test_houseplans_api."""

import asyncio
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from p2b.audit.models import AuditEvent
from p2b.core.db import Database
from p2b.houseplans import service as houseplans_service
from p2b.houseplans.engine.edit import apply_edit
from p2b.houseplans.models import HousePlanOp, HousePlanVersion
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.execution_support import household
from tests.test_houseplans_api import (  # noqa: F401  (fixtures)
    _synthetic_rules_allowed,
    edit_plan,
    plan_app,
    valid_plan,
    worker,
)
from tests.test_projects import H, homeowner


def find_op(detail: dict[str, Any], kind: str, *, valid: bool = True) -> dict[str, Any]:
    """The first structural operation of `kind` the engine's own edit accepts (or rejects),
    with the ruleset and intent the server uses."""
    from p2b.core.vocabulary import RoomSide
    from p2b.houseplans.engine import ArchitecturalIntent, HousePlan
    from p2b.houseplans.engine.edit import BatchRejected, edit
    from p2b.houseplans.engine.model import dump
    from p2b.houseplans.engine.ops import DeleteRoom, MoveEdge, PlanOp
    from tests.houseplans_support import ruleset

    plan = HousePlan.model_validate(detail["document"])
    intent = ArchitecturalIntent.model_validate(detail["intent"])
    rooms = plan.floors[0].rooms
    candidates: list[PlanOp] = (
        [
            MoveEdge(room=r.id, side=s, delta_mm=d)
            for r in rooms
            for s in RoomSide
            for d in (100, -100, 200, -200)
        ]
        if kind == "MOVE_EDGE"
        else [DeleteRoom(room=a.id, merge_into=b.id) for a in rooms for b in rooms if a != b]
    )
    for op in candidates:
        try:
            result = edit(
                plan, [op], ruleset(), intent=intent, ruleset_version=None, ruleset_sha256=None
            )
        except BatchRejected:
            continue
        if result.report.valid == valid:
            return dump(op)
    raise AssertionError(f"no {kind}")


def url(project_id: str, plan_id: str) -> str:
    return f"/api/v1/projects/{project_id}/house-plans/{plan_id}"


async def save(client: AsyncClient, project_id: str, plan_id: str, name: str, revision: int) -> Any:
    return await client.post(
        f"{url(project_id, plan_id)}/versions",
        json={"name": name, "expected_revision": revision},
        headers={**H, "Idempotency-Key": str(uuid.uuid4())},
    )


async def test_a_structural_edit_is_undone_by_restoring_the_revision_from_the_log(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,  # noqa: F811
) -> None:
    family, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    generated = detail["document"]["meta"]["body_sha256"]
    move = find_op(detail, "MOVE_EDGE")

    first = await edit_plan(family, project_id, plan_id, 0, [move])
    assert first.status_code == 200, first.text
    one = first.json()
    assert one["inverse"] == [{"op": "REVERT_TO_REVISION", "revision": 0}]
    assert one["validation"]["valid"] is True

    second_move = find_op(one, "MOVE_EDGE")
    second = await edit_plan(family, project_id, plan_id, 1, [second_move])
    assert second.status_code == 200, second.text

    # back to revision 1: rebuilt from version 1 and the log, stored as revision 3
    back = await edit_plan(
        family, project_id, plan_id, 2, [{"op": "REVERT_TO_REVISION", "revision": 1}]
    )
    assert back.status_code == 200, back.text
    restored = back.json()
    assert restored["editing"]["revision_no"] == 3
    assert restored["document"]["meta"]["body_sha256"] == one["document"]["meta"]["body_sha256"]
    assert restored["document"]["meta"]["revision_no"] == 3
    assert restored["inverse"] == [{"op": "REVERT_TO_REVISION", "revision": 2}]

    # and to the generated plan, through a log that now holds a restore
    original = await edit_plan(
        family, project_id, plan_id, 3, [{"op": "REVERT_TO_REVISION", "revision": 0}]
    )
    assert original.status_code == 200, original.text
    assert original.json()["document"]["meta"]["body_sha256"] == generated
    redo = await edit_plan(
        family, project_id, plan_id, 4, [{"op": "REVERT_TO_REVISION", "revision": 3}]
    )
    assert redo.status_code == 200, redo.text
    assert redo.json()["document"]["meta"]["body_sha256"] == one["document"]["meta"]["body_sha256"]

    revisions = (await family.get(f"{url(project_id, plan_id)}/revisions")).json()
    assert revisions["head_revision_no"] == 5
    assert [
        (i["revision_no"], i["reason"], i["restored_revision"]) for i in revisions["items"]
    ] == [
        (5, "REVERT", 3),
        (4, "REVERT", 0),
        (3, "REVERT", 1),
        (2, "USER", None),
        (1, "USER", None),
    ]
    assert revisions["items"][-1]["ops"] == ["MOVE_EDGE"]
    assert all(i["by_you"] for i in revisions["items"])
    page = (await family.get(f"{url(project_id, plan_id)}/revisions?limit=2&before=4")).json()
    assert [i["revision_no"] for i in page["items"]] == [3, 2]
    assert page["next_before"] == 2

    async with database.transaction() as session:
        restores = (
            await session.scalars(
                select(AuditEvent)
                .where(AuditEvent.action == "houseplan.restored")
                .order_by(AuditEvent.at)
            )
        ).all()
        log_rows = await session.scalar(select(func.count()).select_from(HousePlanOp))
        versions = await session.scalar(select(func.count()).select_from(HousePlanVersion))
    assert len(restores) == 3
    assert restores[0].new_value == {
        "revision_no": 3,
        "restored": {"op": "REVERT_TO_REVISION", "revision": 1},
    }
    assert log_rows == 5  # nothing rewritten, only appended
    assert versions == 1


async def test_named_versions_are_kept_listed_and_restored_without_rewriting_history(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,  # noqa: F811
) -> None:
    family, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    generated = detail["document"]["meta"]["body_sha256"]
    edited = await edit_plan(family, project_id, plan_id, 0, [find_op(detail, "MOVE_EDGE")])
    assert edited.status_code == 200
    edited_hash = edited.json()["document"]["meta"]["body_sha256"]

    saved = await save(family, project_id, plan_id, "Bigger kitchen", 1)
    assert saved.status_code == 201, saved.text
    assert saved.json() | {"created_at": None} == {
        "version_no": 2,
        "name": "Bigger kitchen",
        "revision_no": 1,
        "validity": "VALID",
        "created_at": None,
        "created_by_you": True,
    }
    stale = await save(family, project_id, plan_id, "Late", 0)
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "REVISION_CONFLICT"
    control = await save(family, project_id, plan_id, "bad\u0007name", 1)
    assert control.status_code == 422

    member = await household(database, client_for, make_user, sign_in, project_id)
    listed = (await member.get(f"{url(project_id, plan_id)}/versions")).json()
    assert [(v["version_no"], v["name"], v["created_by_you"]) for v in listed["items"]] == [
        (1, "Generated", False),
        (2, "Bigger kitchen", False),
    ]
    assert (await save(member, project_id, plan_id, "Mine", 1)).status_code == 403
    member_restore = await edit_plan(
        member, project_id, plan_id, 1, [{"op": "REVERT_TO_VERSION", "version": 1}]
    )
    assert member_restore.status_code == 403
    stranger = await homeowner(client_for, make_user, sign_in)
    assert (await stranger.get(f"{url(project_id, plan_id)}/versions")).status_code == 404

    to_one = await edit_plan(
        family, project_id, plan_id, 1, [{"op": "REVERT_TO_VERSION", "version": 1}]
    )
    assert to_one.status_code == 200, to_one.text
    assert to_one.json()["document"]["meta"]["body_sha256"] == generated
    assert to_one.json()["inverse"] == [{"op": "REVERT_TO_REVISION", "revision": 1}]
    to_two = await edit_plan(
        family, project_id, plan_id, 2, [{"op": "REVERT_TO_VERSION", "version": 2}]
    )
    assert to_two.status_code == 200, to_two.text
    assert to_two.json()["document"]["meta"]["body_sha256"] == edited_hash

    for ops, code in (
        ([{"op": "REVERT_TO_VERSION", "version": 9}], "UNKNOWN_REVISION"),
        ([{"op": "REVERT_TO_REVISION", "revision": 3}], "NO_MOVEMENT"),
        ([{"op": "REVERT_TO_REVISION", "revision": 30}], "UNKNOWN_REVISION"),
        (
            [find_op(to_two.json(), "MOVE_EDGE"), {"op": "REVERT_TO_REVISION", "revision": 0}],
            "REVERT_NOT_ALONE",
        ),
    ):
        refused = await edit_plan(family, project_id, plan_id, 3, ops)
        assert refused.status_code == 422, refused.text
        assert refused.json()["error"]["details"]["code"] == code

    async with database.transaction() as session:
        versions = (
            await session.scalars(select(HousePlanVersion).order_by(HousePlanVersion.version_no))
        ).all()
        audit = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "houseplan.version_saved")
        )
    assert [(v.version_no, v.content_sha256) for v in versions] == [
        (1, generated),
        (2, edited_hash),
    ]
    assert audit == 1
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("UPDATE house_plan_versions SET name = 'changed'"))


async def test_two_edits_racing_on_one_revision_store_exactly_one(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,  # noqa: F811
) -> None:
    family, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    move = find_op(detail, "MOVE_EDGE")
    other = find_op(detail, "DELETE_ROOM")
    responses = await asyncio.gather(
        edit_plan(family, project_id, plan_id, 0, [move]),
        edit_plan(family, project_id, plan_id, 0, [other]),
    )
    assert sorted(r.status_code for r in responses) == [200, 409]
    loser = next(r for r in responses if r.status_code == 409)
    assert loser.json()["error"] == {
        **loser.json()["error"],
        "code": "REVISION_CONFLICT",
        "details": {"current_revision": 1},
    }
    async with database.transaction() as session:
        assert await session.scalar(select(func.count()).select_from(HousePlanOp)) == 1


async def test_rooms_are_removed_and_retyped_as_recorded_changes_from_the_requirement(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,  # noqa: F811
) -> None:
    family, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    delete = find_op(detail, "DELETE_ROOM")
    removed = await edit_plan(family, project_id, plan_id, 0, [delete])
    assert removed.status_code == 200, removed.text
    document = removed.json()["document"]
    assert delete["room"] not in {r["id"] for r in document["floors"][0]["rooms"]}
    assert removed.json()["validation"]["valid"] is True
    assert removed.json()["inverse"] == [{"op": "REVERT_TO_REVISION", "revision": 0}]
    gone = next(r for r in detail["document"]["floors"][0]["rooms"] if r["id"] == delete["room"])
    if gone["origin"]["kind"] != "SOLVER":
        (record,) = document["compromises"]
        assert record["change_key"] == "ROOM_REMOVED_BY_OWNER"
        assert record["accepted_by_user"] is True

    bedroom = next(r for r in document["floors"][0]["rooms"] if r["type"] == "BEDROOM")
    renamed = await edit_plan(
        family,
        project_id,
        plan_id,
        1,
        [
            {"op": "SET_ROOM_TYPE", "room": bedroom["id"], "type": "PUJA"},
            {"op": "RENAME_ROOM", "room": bedroom["id"], "name": "Prayer room"},
        ],
    )
    # the server, not the editor, decides whether the plan still passes
    assert renamed.status_code in (200, 422), renamed.text
    if renamed.status_code == 200:
        changes = {c["change_key"] for c in renamed.json()["document"]["compromises"]}
        assert "ROOM_TYPE_CHANGED_BY_OWNER" in changes
    else:
        assert renamed.json()["error"]["code"] == "PLAN_EDIT_INVALID"

    open_room = await edit_plan(
        family,
        project_id,
        plan_id,
        2 if renamed.status_code == 200 else 1,
        [{"op": "SET_ROOM_TYPE", "room": bedroom["id"], "type": "PARKING"}],
    )
    assert open_room.status_code == 422
    assert open_room.json()["error"]["details"]["code"] == "ROOM_TYPE_NOT_ALLOWED"
    assert open_room.json()["error"]["details"]["entities"] == [bedroom["id"]]


async def test_a_log_that_no_longer_replays_exactly_is_not_restored(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    one = await edit_plan(family, project_id, plan_id, 0, [find_op(detail, "MOVE_EDGE")])
    assert one.status_code == 200
    two = await edit_plan(family, project_id, plan_id, 1, [find_op(one.json(), "MOVE_EDGE")])
    assert two.status_code == 200

    real = apply_edit

    def drifted(plan: Any, ops: Any, content: Any) -> Any:  # an engine that changed behaviour
        edited, inverse = real(plan, ops, content)
        floor = edited.floors[0]
        renamed = [floor.rooms[0].model_copy(update={"name": "Drifted"}), *floor.rooms[1:]]
        return edited.model_copy(
            update={"floors": [floor.model_copy(update={"rooms": renamed})]}
        ), inverse

    monkeypatch.setattr(houseplans_service, "apply_edit", drifted)
    refused = await edit_plan(
        family, project_id, plan_id, 2, [{"op": "REVERT_TO_REVISION", "revision": 1}]
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "PLAN_HISTORY_UNAVAILABLE"
    assert refused.json()["error"]["details"] == {"revision_no": 1}
    # nothing stored; a restore from a named version needs no replay and still works
    to_one = await edit_plan(
        family, project_id, plan_id, 2, [{"op": "REVERT_TO_VERSION", "version": 1}]
    )
    assert to_one.status_code == 200, to_one.text
    assert to_one.json()["editing"]["revision_no"] == 3


async def test_a_restore_replays_at_most_the_limit_and_a_named_version_shortens_it(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    current = detail
    for revision in range(3):
        step = await edit_plan(
            family, project_id, plan_id, revision, [find_op(current, "MOVE_EDGE")]
        )
        assert step.status_code == 200, step.text
        current = step.json()
    monkeypatch.setattr(houseplans_service, "MAX_REPLAY", 1)
    far = await edit_plan(
        family, project_id, plan_id, 3, [{"op": "REVERT_TO_REVISION", "revision": 2}]
    )
    assert far.status_code == 409
    assert far.json()["error"]["details"] == {"revision_no": 2, "reason": "TOO_FAR", "limit": 1}

    # a version saved at revision 3 becomes the starting point: revision 4 is one batch away
    assert (await save(family, project_id, plan_id, "Checkpoint", 3)).status_code == 201
    for revision in (3, 4):
        step = await edit_plan(
            family, project_id, plan_id, revision, [find_op(current, "MOVE_EDGE")]
        )
        assert step.status_code == 200, step.text
        current = step.json()
        if revision == 3:
            target = current["document"]["meta"]["body_sha256"]
    near = await edit_plan(
        family, project_id, plan_id, 5, [{"op": "REVERT_TO_REVISION", "revision": 4}]
    )
    assert near.status_code == 200, near.text
    assert near.json()["document"]["meta"]["body_sha256"] == target
