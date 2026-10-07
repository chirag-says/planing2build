"""Concept floor plan API, job and storage (Checkpoint 1, sections C, D, I; AD-12; CP1-03 to
CP1-07): requirement → queue `engine` → VALID plan with geometry and report, or INFEASIBLE with
reasons; nothing written for a request that cannot be normalised; one generation in flight per
project; never authoritative; feature off means the routes do not exist."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from procrastinate import App
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from p2b.core.config import Settings, get_settings
from p2b.core.db import Database
from p2b.core.jobs import RESOURCES_KEY, JobResources, build_job_app
from p2b.core.outbox import HandlerRegistry, relay_batch
from p2b.core.vocabulary import StaffRole
from p2b.houseplans import handlers as houseplans_handlers
from p2b.houseplans import jobs as houseplans_jobs
from p2b.houseplans import service as houseplans_service
from p2b.houseplans.engine import GenerationResult
from p2b.houseplans.models import HousePlanOp, HousePlanRecord, HousePlanVersion
from p2b.integrations.clamav import AcceptAllScanner
from p2b.integrations.email import MemoryEmailProvider
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.execution_support import household
from tests.houseplans_support import cases, install_ruleset
from tests.staff_support import verified_staff
from tests.test_operations import submitted_project
from tests.test_projects import H, homeowner, new_project

PROTOTYPE = cases()["3bhk_40x65_east"]
PLAN_ANSWERS = {k: v for k, v in PROTOTYPE["answers"].items()}
INPUTS = PROTOTYPE["design_inputs"]


def key() -> dict[str, str]:
    return {**H, "Idempotency-Key": str(uuid.uuid4())}


async def plan_project(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn, **changes: Any
) -> tuple[AsyncClient, str]:
    return await submitted_project(client_for, make_user, sign_in, **{**PLAN_ANSWERS, **changes})


async def request_plan(
    client: AsyncClient,
    project_id: str,
    inputs: dict[str, Any] | None = INPUTS,
    headers: dict[str, str] | None = None,
) -> Response:
    body = {"design_inputs": inputs} if inputs is not None else {}
    return await client.post(
        f"/api/v1/projects/{project_id}/house-plans", json=body, headers=headers or key()
    )


async def plan_rows(database: Database, project_id: str) -> list[HousePlanRecord]:
    async with database.transaction() as session:
        return list(
            await session.scalars(
                select(HousePlanRecord)
                .where(HousePlanRecord.project_id == uuid.UUID(project_id))
                .order_by(HousePlanRecord.sequence)
            )
        )


@pytest.fixture(autouse=True)
def _synthetic_rules_allowed(app: FastAPI, monkeypatch: pytest.MonkeyPatch) -> None:
    """The test environment (P2B_ENV=test) may use the synthetic test ruleset (CP1-06)."""
    settings: Settings = app.state.settings
    allowed = settings.model_copy(
        update={"houseplans_allow_draft_ruleset": True, "houseplans_allow_synthetic_ruleset": True}
    )
    monkeypatch.setattr(app.state, "settings", allowed)


@pytest.fixture(scope="session")
def plan_app() -> App:
    return build_job_app(
        get_settings(), [(houseplans_handlers.JOB_NAMESPACE, houseplans_jobs.blueprint)]
    )


@pytest.fixture
async def worker(app: FastAPI, database: Database, plan_app: App) -> AsyncIterator[Any]:
    """Relay the outbox with the houseplans subscriber, then run the `engine` queue once."""
    registry = HandlerRegistry()
    houseplans_handlers.register(registry, plan_app)

    async def run() -> None:
        resources = JobResources(
            database,
            app.state.settings,
            MemoryEmailProvider(),
            app.state.storage,
            AcceptAllScanner(),
            app.state.image_provider,
            app.state.payment_gateway,
        )
        while await relay_batch(database, registry):
            pass
        await plan_app.run_worker_async(
            queues=["engine"],
            wait=False,
            install_signal_handlers=False,
            additional_context={RESOURCES_KEY: resources},
        )

    async with plan_app.open_async():
        yield run


# ---------- the pipeline ----------


async def test_the_prototype_requirement_becomes_a_valid_plan_through_the_engine_queue(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,
) -> None:
    await install_ruleset(database)
    family, project_id = await plan_project(client_for, make_user, sign_in)
    response = await request_plan(family, project_id)
    assert response.status_code == 202, response.text
    queued = response.json()
    assert queued["state"] == "QUEUED"
    assert queued["is_authoritative"] is False
    assert queued["ruleset_is_synthetic"] is True
    assert queued["ruleset_status"] == "DRAFT"

    await worker()

    detail = (
        await family.get(f"/api/v1/projects/{project_id}/house-plans/{queued['plan_id']}")
    ).json()
    assert detail["state"] == "VALID"
    assert detail["validity"] == "VALID"
    assert detail["validation"]["valid"] is True
    assert detail["validation"]["errors"] == []
    document, geometry = detail["document"], detail["geometry"]
    assert document["meta"]["schema"] == "p2b.houseplan"
    assert document["meta"]["schema_version"] == "1.1.0"
    assert document["meta"]["generator"]["solver"] == "ZONED_LOCAL_SEARCH"
    # Soft terms are scored in the document, and the derived quality block agrees with them.
    soft = [c for c in document["constraints"] if c["strength"] == "SOFT"]
    assert {c["origin"]["kind"] for c in soft} == {"RULESET"}
    assert next(c for c in soft if c["kind"] == "ORIENTATION")["outcome"] == "NOT_EVALUATED"
    quality = detail["quality"]
    assert quality["total"] == sum(c["weight"] * c.get("score_milli", 0) for c in soft)
    assert {t["kind"]: t.get("score_milli") for t in quality["terms"]} == {
        c["kind"]: c.get("score_milli") for c in soft
    }
    assert {r["id"] for r in document["floors"][0]["rooms"]} >= {
        "living",
        "kitchen",
        "parking",
        "bedroom_3",
    }
    assert geometry["units"] == "mm"
    assert geometry["floors"][0]["walls"]
    assert all(w["structural_role"] == "UNASSESSED" for w in document["floors"][0]["walls"])
    assert detail["design_inputs"]["kind"] == "PROVISIONAL_DESIGN_INPUTS"
    assert detail["infeasibility"] is None

    async with database.transaction() as session:
        version = (await session.scalars(select(HousePlanVersion))).one()
    assert version.version_no == 1
    assert version.validity == "VALID"
    assert version.content_sha256 == document["meta"]["body_sha256"]
    listed = (await family.get(f"/api/v1/projects/{project_id}/house-plans")).json()["items"]
    assert [i["plan_id"] for i in listed] == [queued["plan_id"]]


async def test_an_impossible_programme_ends_infeasible_with_reasons_and_no_plan(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,
) -> None:
    await install_ruleset(database)
    small = cases()["3bhk_20x30_too_small"]
    family, project_id = await plan_project(client_for, make_user, sign_in, **small["answers"])
    response = await request_plan(family, project_id, small["design_inputs"])
    assert response.status_code == 202, response.text
    await worker()
    detail = (
        await family.get(f"/api/v1/projects/{project_id}/house-plans/{response.json()['plan_id']}")
    ).json()
    assert detail["state"] == "INFEASIBLE"
    assert detail["document"] is None
    assert detail["geometry"] is None
    assert detail["validation"] is None
    reason = detail["infeasibility"]["reasons"][0]
    assert reason["code"] == "AREA_BUDGET"
    assert reason["params"]["needed_mm2"] > reason["params"]["available_mm2"]
    # The pre-check proves it: no arrangement of the rooms fits, so the plan says so plainly.
    assert detail["infeasibility"]["classification"] == "PROVEN"
    assert detail["infeasibility"]["message_key"] == "houseplans.infeasible.proven"
    assert "cannot fit in any arrangement" in detail["infeasibility"]["explanation"]
    assert {c["kind"] for c in detail["infeasibility"]["constraints"]} >= {"INSIDE_ENVELOPE"}


async def test_an_engine_that_produces_an_invalid_plan_fails_and_shows_nothing(
    monkeypatch: pytest.MonkeyPatch,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,
) -> None:
    await install_ruleset(database)
    family, project_id = await plan_project(client_for, make_user, sign_in)
    monkeypatch.setattr(houseplans_service, "generate", lambda *a, **k: GenerationResult("INVALID"))
    response = await request_plan(family, project_id)
    await worker()
    detail = (
        await family.get(f"/api/v1/projects/{project_id}/house-plans/{response.json()['plan_id']}")
    ).json()
    assert detail["state"] == "FAILED"
    assert detail["failure_reason"] == "ENGINE_INVALID_OUTPUT"
    assert detail["document"] is None
    assert detail["validity"] is None
    assert "failure_detail" not in detail  # internal; operations only


# ---------- refused before anything is written ----------


async def test_missing_inputs_are_listed_and_nothing_is_written(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    await install_ruleset(database)
    family, project_id = await plan_project(client_for, make_user, sign_in)
    response = await request_plan(family, project_id, inputs=None)
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "DESIGN_INPUT_REQUIRED"
    assert {m["key"] for m in body["details"]["missing"]} == {
        "ATTACHED_BATHROOMS",
        "PARKING_SPACES",
        "PARKING_KIND",
        "DINING",
        "KITCHEN",
        "STAIR",
        "UTILITY",
    }
    assert await plan_rows(database, project_id) == []


async def test_unsupported_requirements_and_conflicting_inputs_are_refused(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    await install_ruleset(database)
    family, project_id = await plan_project(client_for, make_user, sign_in, floors="G_PLUS_1")
    response = await request_plan(family, project_id)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PLAN_UNSUPPORTED"
    assert response.json()["error"]["details"]["reasons"] == ["FLOORS_NOT_SUPPORTED"]

    family, project_id = await plan_project(client_for, make_user, sign_in)
    response = await request_plan(family, project_id, {**INPUTS, "setbacks_ft": {"FRONT": 20}})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"  # inputs never replace an answer
    assert await plan_rows(database, project_id) == []


async def test_without_a_usable_ruleset_nothing_generates(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    family, project_id = await plan_project(client_for, make_user, sign_in)
    assert (await request_plan(family, project_id)).json()["error"][
        "code"
    ] == "RULESET_NOT_PUBLISHED"
    await install_ruleset(database)  # synthetic: usable only while the setting allows it
    settings: Settings = app.state.settings
    monkeypatch.setattr(
        app.state,
        "settings",
        settings.model_copy(update={"houseplans_allow_synthetic_ruleset": False}),
    )
    response = await request_plan(family, project_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RULESET_NOT_PUBLISHED"


async def test_a_draft_requirement_cannot_generate(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    await install_ruleset(database)
    family = await homeowner(client_for, make_user, sign_in)
    project_id = (await new_project(family))["project"]["project_id"]
    response = await request_plan(family, project_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "STATE_CONFLICT"


# ---------- concurrency and idempotency (CP1-07) ----------


async def test_one_generation_in_flight_and_idempotent_requests(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    await install_ruleset(database)
    family, project_id = await plan_project(client_for, make_user, sign_in)
    headers = key()
    first = await request_plan(family, project_id, headers=headers)
    again = await request_plan(family, project_id, headers=headers)
    assert again.json()["plan_id"] == first.json()["plan_id"]
    other = await request_plan(family, project_id)
    assert other.status_code == 409
    assert other.json()["error"]["code"] == "GENERATION_IN_PROGRESS"
    assert len(await plan_rows(database, project_id)) == 1


async def test_concurrent_requests_are_serialised(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    await install_ruleset(database)
    family, project_id = await plan_project(client_for, make_user, sign_in)
    responses = await asyncio.gather(*(request_plan(family, project_id) for _ in range(5)))
    assert sorted(r.status_code for r in responses) == [202, 409, 409, 409, 409]
    assert len(await plan_rows(database, project_id)) == 1


async def test_a_lost_generation_expires_and_frees_the_project(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    await install_ruleset(database)
    family, project_id = await plan_project(client_for, make_user, sign_in)
    await request_plan(family, project_id)
    async with database.transaction() as session:
        await session.execute(
            text("ALTER TABLE house_plans DISABLE TRIGGER house_plans_lifecycle_only")
        )
        await session.execute(
            update(HousePlanRecord).values(created_at=func.now() - timedelta(hours=3))
        )
        await session.execute(
            text("ALTER TABLE house_plans ENABLE TRIGGER house_plans_lifecycle_only")
        )
    assert (await request_plan(family, project_id)).status_code == 202
    states = [(r.state, r.failure_reason) for r in await plan_rows(database, project_id)]
    assert states == [("FAILED", "STALE"), ("QUEUED", None)]


# ---------- access (AD-12) and the feature flag (CP1-05) ----------


async def test_members_read_only_the_owner_generates_and_strangers_see_nothing(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,
) -> None:
    await install_ruleset(database)
    family, project_id = await plan_project(client_for, make_user, sign_in)
    plan_id = (await request_plan(family, project_id)).json()["plan_id"]
    await worker()
    member = await household(database, client_for, make_user, sign_in, project_id)
    assert (
        await member.get(f"/api/v1/projects/{project_id}/house-plans/{plan_id}")
    ).status_code == 200
    assert (await request_plan(member, project_id)).status_code == 403
    stranger = await homeowner(client_for, make_user, sign_in)
    assert (await stranger.get(f"/api/v1/projects/{project_id}/house-plans")).status_code == 404
    assert (
        await stranger.get(f"/api/v1/projects/{project_id}/house-plans/{plan_id}")
    ).status_code == 404
    _, other_project = await plan_project(client_for, make_user, sign_in)
    assert (
        await family.get(f"/api/v1/projects/{other_project}/house-plans/{plan_id}")
    ).status_code == 404

    staff = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    listed = await staff.client.get(f"/api/v1/ops/projects/{project_id}/house-plans")
    assert listed.status_code == 200
    assert [i["plan_id"] for i in listed.json()["items"]] == [plan_id]
    detail = await staff.client.get(f"/api/v1/ops/house-plans/{plan_id}")
    assert detail.status_code == 200
    assert detail.json()["failure_detail"] is None


async def test_with_the_feature_off_the_routes_do_not_exist(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
) -> None:
    await install_ruleset(database)
    family, project_id = await plan_project(client_for, make_user, sign_in)
    settings: Settings = app.state.settings
    monkeypatch.setattr(
        app.state, "settings", settings.model_copy(update={"houseplans_enabled": False})
    )
    assert (await request_plan(family, project_id)).status_code == 404
    assert (await family.get(f"/api/v1/projects/{project_id}/house-plans")).status_code == 404
    assert (
        await family.get(f"/api/v1/projects/{project_id}/house-plans/{uuid.uuid4()}")
    ).status_code == 404
    assert await plan_rows(database, project_id) == []


# ---------- the database guards ----------


async def test_a_synthetic_ruleset_can_never_be_approved_or_published(database: Database) -> None:
    ruleset_id = await install_ruleset(database)
    for status in ("APPROVED", "PUBLISHED"):
        with pytest.raises(IntegrityError):
            async with database.transaction() as session:
                await session.execute(
                    text(
                        "UPDATE layout_rulesets SET status = :s, approved_by = NULL WHERE id = :id"
                    ),
                    {"s": status, "id": ruleset_id},
                )
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(
                text("UPDATE layout_rulesets SET content = '{}'::jsonb WHERE id = :id"),
                {"id": ruleset_id},
            )


async def test_a_plan_is_never_authoritative_and_its_versions_never_change(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,
) -> None:
    await install_ruleset(database)
    family, project_id = await plan_project(client_for, make_user, sign_in)
    await request_plan(family, project_id)
    await worker()
    async with database.transaction() as session:  # guards are tested on real rows
        assert await session.scalar(select(func.count()).select_from(HousePlanVersion)) == 1
        assert await session.scalar(select(func.count()).select_from(HousePlanRecord)) == 1
    with pytest.raises(DBAPIError):  # only lifecycle columns may change
        async with database.transaction() as session:
            await session.execute(text("UPDATE house_plans SET is_authoritative = true"))
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("UPDATE house_plans SET intent = '{}'::jsonb"))
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("UPDATE house_plan_versions SET validity = 'INVALID'"))
    with pytest.raises(DBAPIError):
        async with database.transaction() as session:
            await session.execute(text("DELETE FROM house_plan_versions"))


@pytest.mark.parametrize(
    ("env", "changes", "message"),
    [
        ("production", {"houseplans_allow_draft_ruleset": True}, "PUBLISHED ruleset only"),
        ("production", {"houseplans_allow_synthetic_ruleset": True}, "PUBLISHED ruleset only"),
        ("staging", {"houseplans_allow_synthetic_ruleset": True}, "locally and in tests only"),
    ],
)
def test_configuration_refuses_draft_or_synthetic_rules_where_they_do_not_belong(
    env: str, changes: dict[str, bool], message: str
) -> None:
    base = get_settings().model_dump()
    production = {
        "email_provider": "resend",
        "resend_api_key": "re_test",
        "cookie_secure": True,
        "storage_provider": "s3",
        "scanner_provider": "clamav",
        "ai_image_provider": "none",
        "payment_provider": "none",
    }
    values = {**base, "env": env, **(production if env == "production" else {}), **changes}
    with pytest.raises(ValueError, match=message):
        Settings.model_validate(values)


# ---------- editing (Checkpoint 3) ----------


def _moves(detail: dict[str, Any], *, valid: bool) -> dict[str, Any]:
    """The first interior wall move the engine's own edit accepts (or that the validator
    rejects), found with the same ruleset and intent the server uses."""
    from p2b.houseplans.engine import ArchitecturalIntent, HousePlan
    from p2b.houseplans.engine.edit import BatchRejected, edit
    from p2b.houseplans.engine.ops import MoveWall
    from tests.houseplans_support import ruleset

    plan = HousePlan.model_validate(detail["document"])
    intent = ArchitecturalIntent.model_validate(detail["intent"])
    for wall in plan.floors[0].walls:
        if wall.kind.value != "INTERIOR":
            continue
        for delta in (100, -100, 1500, -1500):
            op = MoveWall(wall=wall.id, delta_mm=delta)
            try:
                result = edit(
                    plan, [op], ruleset(), intent=intent, ruleset_version=None, ruleset_sha256=None
                )
            except BatchRejected:
                continue
            if result.report.valid == valid:
                return {"op": "MOVE_WALL", "wall": wall.id, "delta_mm": delta}
    raise AssertionError("no such move")


async def edit_plan(
    client: AsyncClient, project_id: str, plan_id: str, revision: int, ops: list[dict[str, Any]]
) -> Response:
    return await client.post(
        f"/api/v1/projects/{project_id}/house-plans/{plan_id}/ops",
        json={"expected_revision": revision, "ops": ops},
        headers=H,
    )


async def valid_plan(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,
) -> tuple[AsyncClient, str, str, dict[str, Any]]:
    await install_ruleset(database)
    family, project_id = await plan_project(client_for, make_user, sign_in)
    plan_id = (await request_plan(family, project_id)).json()["plan_id"]
    await worker()
    detail = (await family.get(f"/api/v1/projects/{project_id}/house-plans/{plan_id}")).json()
    return family, project_id, plan_id, detail


async def test_the_owner_edits_through_typed_operations_and_undoes_with_the_inverse(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,
) -> None:
    family, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    assert detail["editing"] == {"can_edit": True, "revision_no": 0, "grid_mm": 50}
    assert detail["geometry"]["geometry_version"] == "1.1.0"
    original_hash = detail["document"]["meta"]["body_sha256"]

    move = _moves(detail, valid=True)
    response = await edit_plan(family, project_id, plan_id, 0, [move])
    assert response.status_code == 200, response.text
    edited = response.json()
    assert edited["editing"]["revision_no"] == 1
    assert edited["validation"]["valid"] is True
    assert edited["document"]["meta"]["revision_no"] == 1
    assert edited["document"]["meta"]["source"] == "EDITED"
    assert edited["document"]["meta"]["body_sha256"] != original_hash
    assert edited["inverse"] == [{**move, "delta_mm": -move["delta_mm"]}]
    again = (await family.get(f"/api/v1/projects/{project_id}/house-plans/{plan_id}")).json()
    assert again["document"] == edited["document"]
    assert again["geometry"] == edited["geometry"]

    undone = await edit_plan(family, project_id, plan_id, 1, edited["inverse"])
    assert undone.status_code == 200, undone.text
    assert undone.json()["document"]["meta"]["body_sha256"] == original_hash
    assert undone.json()["editing"]["revision_no"] == 2

    async with database.transaction() as session:
        log = list(
            await session.scalars(
                select(HousePlanOp)
                .where(HousePlanOp.plan_id == uuid.UUID(plan_id))
                .order_by(HousePlanOp.revision_no)
            )
        )
        versions = list(await session.scalars(select(HousePlanVersion)))
    assert [(r.revision_no, r.reason, r.ops) for r in log] == [
        (1, "USER", [move]),
        (2, "USER", edited["inverse"]),
    ]
    assert log[1].content_sha256 == original_hash
    # version 1, the generated plan, is untouched: edits are revisions, not versions
    assert [v.version_no for v in versions] == [1]
    assert versions[0].content_sha256 == original_hash


async def test_invalid_rejected_and_stale_edits_change_nothing(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,
) -> None:
    family, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    url = f"/api/v1/projects/{project_id}/house-plans/{plan_id}"

    broken = await edit_plan(family, project_id, plan_id, 0, [_moves(detail, valid=False)])
    assert broken.status_code == 422, broken.text
    error = broken.json()["error"]
    assert error["code"] == "PLAN_EDIT_INVALID"
    report = error["details"]["report"]
    assert report["valid"] is False
    assert report["errors"]
    assert all(e["entities"] and e["message"] for e in report["errors"])

    rejected = await edit_plan(
        family,
        project_id,
        plan_id,
        0,
        [_moves(detail, valid=True), {"op": "MOVE_WALL", "wall": "w_missing", "delta_mm": 100}],
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "PLAN_OPERATION_REJECTED"
    assert rejected.json()["error"]["details"] == {
        "index": 1,
        "op": "MOVE_WALL",
        "code": "UNKNOWN_ENTITY",
    }

    stale = await edit_plan(family, project_id, plan_id, 3, [_moves(detail, valid=True)])
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "REVISION_CONFLICT"
    assert stale.json()["error"]["details"] == {"current_revision": 0}

    # free geometry is not an operation: the schema refuses it
    free = await edit_plan(
        family, project_id, plan_id, 0, [{"op": "MOVE_WALL", "wall": "w1", "x": 100, "y": 0}]
    )
    assert free.status_code == 422
    assert free.json()["error"]["code"] == "VALIDATION_ERROR"

    after = (await family.get(url)).json()
    assert after["document"] == detail["document"]
    assert after["editing"]["revision_no"] == 0
    async with database.transaction() as session:
        assert (await session.scalar(select(func.count()).select_from(HousePlanOp))) == 0


async def test_only_the_owner_edits_members_read_and_ops_staff_cannot_edit(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,
) -> None:
    family, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    move = _moves(detail, valid=True)
    member = await household(database, client_for, make_user, sign_in, project_id)
    seen = (await member.get(f"/api/v1/projects/{project_id}/house-plans/{plan_id}")).json()
    assert seen["editing"]["can_edit"] is False
    forbidden = await edit_plan(member, project_id, plan_id, 0, [move])
    assert forbidden.status_code == 403
    stranger = await homeowner(client_for, make_user, sign_in)
    assert (await edit_plan(stranger, project_id, plan_id, 0, [move])).status_code == 404

    staff = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    staff_view = (await staff.client.get(f"/api/v1/ops/house-plans/{plan_id}")).json()
    assert staff_view["editing"]["can_edit"] is False
    staff_edit = await staff.client.post(
        f"/api/v1/projects/{project_id}/house-plans/{plan_id}/ops",
        json={"expected_revision": 0, "ops": [move]},
        headers=H,
    )
    assert staff_edit.status_code in (401, 403, 404)
    unchanged = (await family.get(f"/api/v1/projects/{project_id}/house-plans/{plan_id}")).json()
    assert unchanged["editing"]["revision_no"] == 0


async def test_the_operation_log_is_append_only(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,
) -> None:
    family, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    edited = await edit_plan(family, project_id, plan_id, 0, [_moves(detail, valid=True)])
    assert edited.status_code == 200
    for statement in (
        "UPDATE house_plan_ops SET reason = 'REVERT'",
        "DELETE FROM house_plan_ops",
    ):
        with pytest.raises(DBAPIError):
            async with database.transaction() as session:
                await session.execute(text(statement))


async def test_with_the_feature_off_editing_does_not_exist(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    worker: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    family, project_id, plan_id, detail = await valid_plan(
        database, client_for, make_user, sign_in, worker
    )
    off = app.state.settings.model_copy(update={"houseplans_enabled": False})
    monkeypatch.setattr(app.state, "settings", off)
    response = await edit_plan(family, project_id, plan_id, 0, [_moves(detail, valid=True)])
    assert response.status_code == 404
