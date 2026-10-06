"""AI design concepts (Slice 3.1; PD-05, PD-22; F-08 first version).

Generation is free for 3 successful concepts per project; a failure consumes nothing; the
4th free request never reaches the provider; account limits are configuration; the provider sees
only sanitised design facts; images are private, marked "Illustrative" and served by signed
link; a reference stays illustrative."""

import asyncio
import io
import json
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from PIL import Image
from procrastinate import App
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from p2b.core.config import Settings, get_settings
from p2b.core.db import Database
from p2b.core.images import ImageProviderError, ImageRequest, ImageResult
from p2b.core.jobs import RESOURCES_KEY, JobResources, build_job_app
from p2b.core.outbox import HandlerRegistry, relay_batch
from p2b.core.vocabulary import Audience
from p2b.designs import handlers as designs_handlers
from p2b.designs import jobs as designs_jobs
from p2b.designs.imaging import InvalidImage, finalise
from p2b.designs.models import DesignGeneration, DesignReference
from p2b.designs.prompts import ALLOWED_KEYS, facts, sanitise
from p2b.designs.service import run_generation
from p2b.documents.models import DocumentAccessLog, FileObject
from p2b.integrations.ai_images import DemoImageProvider, UnconfiguredImageProvider
from p2b.integrations.clamav import AcceptAllScanner
from p2b.integrations.email import MemoryEmailProvider
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.test_operations import submitted_project
from tests.test_projects import H, homeowner, new_project, save, submit
from tests.test_questions import COMPLETE
from tests.test_review_workspace import ask, cancel, review_ready

PROVIDER_REQUEST_KEYS = {"prompt", "negative_prompt", "view", "width", "height", "seed"}


class CountingProvider(DemoImageProvider):
    def __init__(self) -> None:
        self.requests: list[ImageRequest] = []

    async def generate(self, request: ImageRequest) -> ImageResult:
        self.requests.append(request)
        return await super().generate(request)


class FailingProvider(DemoImageProvider):
    """Fails `failures` times with the given kind, then behaves like the demo provider."""

    def __init__(self, kind: str = "ERROR", *, retryable: bool = False, failures: int = 99):
        self.kind, self.retryable, self.failures, self.calls = kind, retryable, failures, 0

    async def generate(self, request: ImageRequest) -> ImageResult:
        self.calls += 1
        if self.calls <= self.failures:
            raise ImageProviderError("boom", kind=self.kind, retryable=self.retryable)  # type: ignore[arg-type]
        return await super().generate(request)


class SlowProvider(DemoImageProvider):
    async def generate(self, request: ImageRequest) -> ImageResult:
        await asyncio.sleep(1)
        return await super().generate(request)


class GarbageProvider(DemoImageProvider):
    async def generate(self, request: ImageRequest) -> ImageResult:
        return ImageResult(content=b"not an image", mime="image/png", usage=None)


def key() -> dict[str, str]:
    return {**H, "Idempotency-Key": str(uuid.uuid4())}


async def request_design(
    client: AsyncClient, project_id: str, body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Response:  # fmt: skip
    return await client.post(
        f"/api/v1/projects/{project_id}/designs",
        json=body if body is not None else {"view": "EXTERIOR"},
        headers=headers or key(),
    )


async def designs(client: AsyncClient, project_id: str) -> dict[str, Any]:
    response = await client.get(f"/api/v1/projects/{project_id}/designs")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def run_pending(app: FastAPI, database: Database, provider: Any = None,
                      settings: Settings | None = None) -> list[str]:  # fmt: skip
    """What the worker does for each queued generation."""
    async with database.transaction() as session:
        ids = list(
            await session.scalars(
                select(DesignGeneration.id).where(DesignGeneration.state.in_(["QUEUED", "RUNNING"]))
            )
        )
    outcomes = []
    for generation_id in ids:
        state = await run_generation(
            database, settings or app.state.settings, app.state.storage,
            provider or app.state.image_provider, generation_id,
        )  # fmt: skip
        outcomes.append(state.value if state else "noop")
    return outcomes


async def generated(
    app: FastAPI, database: Database, client: AsyncClient, project_id: str, provider: Any = None
) -> dict[str, Any]:
    response = await request_design(client, project_id)
    assert response.status_code == 202, response.text
    await run_pending(app, database, provider)
    body: dict[str, Any] = (
        await client.get(f"/api/v1/projects/{project_id}/designs/{response.json()['design_id']}")
    ).json()
    return body


async def rows(database: Database, project_id: str) -> list[DesignGeneration]:
    async with database.transaction() as session:
        return list(
            await session.scalars(
                select(DesignGeneration)
                .where(DesignGeneration.project_id == project_id)
                .order_by(DesignGeneration.sequence)
            )
        )


# --- the pipeline -----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def design_app() -> App:
    return build_job_app(get_settings(), [(designs_handlers.JOB_NAMESPACE, designs_jobs.blueprint)])


@pytest.fixture
async def worker(app: FastAPI, database: Database, design_app: App) -> AsyncIterator[Any]:
    """Relay the outbox with the designs subscriber, then run the `ai` queue once."""
    registry = HandlerRegistry()
    designs_handlers.register(registry, design_app)

    async def run() -> None:
        resources = JobResources(
            database, app.state.settings, MemoryEmailProvider(), app.state.storage,
            AcceptAllScanner(), app.state.image_provider, app.state.payment_gateway,
        )  # fmt: skip
        while await relay_batch(database, registry):
            pass
        await design_app.run_worker_async(
            queues=["ai"], wait=False, install_signal_handlers=False,
            additional_context={RESOURCES_KEY: resources},
        )  # fmt: skip

    async with design_app.open_async():
        yield run


async def test_a_request_runs_through_the_queue_to_a_private_marked_image(
    app: FastAPI, database: Database, worker: Any,
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    response = await request_design(family, project_id)
    assert response.status_code == 202, response.text
    queued = response.json()
    assert (queued["state"], queued["funding"], queued["sequence"]) == ("QUEUED", "FREE", 1)
    assert queued["image_url"] is None
    assert queued["is_authoritative"] is False
    listing = await designs(family, project_id)
    assert listing["quota"] == {
        "free_total": 3, "free_used": 0, "in_progress": 1, "free_remaining": 2,
        "can_generate": True, "block": None, "credit_balance": 0, "can_use_credit": False,
        "paid_block": None,
    }  # fmt: skip

    await worker()

    body = (await family.get(f"/api/v1/projects/{project_id}/designs/{queued['design_id']}")).json()
    assert body["state"] == "SUCCEEDED"
    assert body["image_url"].startswith("https://storage.test/test/ai_concept/")
    assert "inline=" in body["image_url"]
    for hidden in ("provider", "model", "prompt", "snapshot", "provider_usage", "failure_detail"):
        assert hidden not in body
    [row] = await rows(database, project_id)
    assert (row.state, row.attempts, row.provider, row.model) == (
        "SUCCEEDED", 1, "demo", "demo-placeholder-v1",
    )  # fmt: skip
    assert row.started_at is not None
    assert row.completed_at is not None
    async with database.transaction() as session:
        file = await session.get_one(FileObject, row.output_file_id)
        views = await session.scalar(
            select(func.count()).select_from(DocumentAccessLog).where(
                DocumentAccessLog.file_id == file.id
            )
        )  # fmt: skip
    assert (file.purpose, file.state, file.declared_mime) == (
        "AI_CONCEPT",
        "AVAILABLE",
        "image/jpeg",
    )
    assert (views or 0) >= 1  # every signed link is logged
    stored = await app.state.storage.read(file.object_key)
    with Image.open(io.BytesIO(stored)) as image:
        assert image.format == "JPEG"
    # AI concepts are not project documents.
    files = (await family.get(f"/api/v1/projects/{project_id}/files")).json()
    assert files == []
    assert (await designs(family, project_id))["quota"]["free_used"] == 1


async def test_three_successful_generations_then_the_fourth_never_reaches_the_provider(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn,
) -> None:  # fmt: skip
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    provider = CountingProvider()
    for _ in range(3):
        assert (await generated(app, database, family, project_id, provider))[
            "state"
        ] == "SUCCEEDED"
    quota = (await designs(family, project_id))["quota"]
    assert (quota["free_used"], quota["free_remaining"], quota["can_generate"], quota["block"]) == (
        3, 0, False, "FREE_QUOTA_USED",
    )  # fmt: skip
    fourth = await request_design(family, project_id)
    assert fourth.status_code == 409
    assert fourth.json()["error"]["code"] == "QUOTA_EXHAUSTED"
    assert fourth.json()["error"]["details"]["block"] == "FREE_QUOTA_USED"
    await run_pending(app, database, provider)
    assert len(provider.requests) == 3
    assert len(await rows(database, project_id)) == 3


async def test_a_failed_generation_consumes_nothing(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn,
) -> None:  # fmt: skip
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    failed = await generated(app, database, family, project_id, FailingProvider())
    assert (failed["state"], failed["failure_reason"], failed["image_url"]) == (
        "FAILED", "PROVIDER_ERROR", None,
    )  # fmt: skip
    assert (await designs(family, project_id))["quota"]["free_remaining"] == 3
    for _ in range(3):
        assert (await generated(app, database, family, project_id))["state"] == "SUCCEEDED"
    assert (await request_design(family, project_id)).status_code == 409
    assert [r.state for r in await rows(database, project_id)] == [
        "FAILED", "SUCCEEDED", "SUCCEEDED", "SUCCEEDED",
    ]  # fmt: skip


async def test_concurrent_requests_cannot_overrun_the_free_quota(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    responses = await asyncio.gather(*(request_design(family, project_id) for _ in range(6)))
    assert sorted(r.status_code for r in responses) == [202, 202, 202, 409, 409, 409]
    assert len(await rows(database, project_id)) == 3


async def test_a_repeated_request_creates_one_generation(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    headers = key()
    first = await request_design(family, project_id, headers=headers)
    again = await request_design(family, project_id, headers=headers)
    assert first.json()["design_id"] == again.json()["design_id"]
    other = await request_design(family, project_id, {"view": "INTERIOR"}, headers=headers)
    assert other.status_code == 409
    assert len(await rows(database, project_id)) == 1


async def test_account_limits_are_configuration(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch, database: Database,
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    family = await homeowner(client_for, make_user, sign_in)
    projects = []
    for _ in range(4):
        project_id = (await new_project(family))["project"]["project_id"]
        assert (await save(family, project_id, COMPLETE, 1)).status_code == 200
        assert (await submit(family, project_id, 2)).status_code == 200
        projects.append(project_id)
    # Default: at most 3 projects a day per account.
    for project_id in projects[:3]:
        assert (await request_design(family, project_id)).status_code == 202
    blocked = await request_design(family, projects[3])
    assert blocked.json()["error"]["details"]["block"] == "ACCOUNT_DAILY_PROJECTS"
    assert (await request_design(family, projects[0])).status_code == 202  # same project: fine
    # Generations a day per account, set lower by configuration.
    settings = app.state.settings.model_copy(update={"ai_max_generations_per_account_per_day": 4})
    monkeypatch.setattr(app.state, "settings", settings)
    capped = await request_design(family, projects[1])
    assert capped.json()["error"]["details"]["block"] == "ACCOUNT_DAILY_GENERATIONS"
    # A failure frees its place in the daily count.
    await run_pending(app, database, FailingProvider())
    assert (await request_design(family, projects[1])).status_code == 202
    # The free quota per project is configuration too.
    unlimited = {"ai_free_generations_per_project": 0, "ai_max_generations_per_account_per_day": 99}
    settings = app.state.settings.model_copy(update=unlimited)
    monkeypatch.setattr(app.state, "settings", settings)
    none_free = await request_design(family, projects[2])
    assert none_free.json()["error"]["details"]["block"] == "FREE_QUOTA_USED"


async def test_daily_limits_use_a_rolling_24_hours(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch, database: Database,
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    family = await homeowner(client_for, make_user, sign_in)
    projects = []
    for _ in range(4):
        project_id = (await new_project(family))["project"]["project_id"]
        assert (await save(family, project_id, COMPLETE, 1)).status_code == 200
        assert (await submit(family, project_id, 2)).status_code == 200
        projects.append(project_id)
    for project_id in projects[:3]:
        assert (await request_design(family, project_id)).status_code == 202
    await run_pending(app, database)
    assert (await request_design(family, projects[3])).json()["error"]["details"]["block"] == (
        "ACCOUNT_DAILY_PROJECTS"
    )

    async def age(hours: float) -> None:
        async with database.transaction() as session:
            await session.execute(
                update(DesignGeneration).values(created_at=func.now() - timedelta(hours=hours))
            )

    await age(23)  # still inside the window
    assert (await request_design(family, projects[3])).status_code == 409
    await age(25)  # out of the window: a new project may generate
    assert (await request_design(family, projects[3])).status_code == 202

    settings = app.state.settings.model_copy(update={"ai_max_generations_per_account_per_day": 1})
    monkeypatch.setattr(app.state, "settings", settings)
    capped = await request_design(family, projects[0])  # the queued one above counts
    assert capped.json()["error"]["details"]["block"] == "ACCOUNT_DAILY_GENERATIONS"
    await run_pending(app, database)
    await age(25)
    assert (await request_design(family, projects[0])).status_code == 202


# --- privacy and control ----------------------------------------------------------------------

PRIVATE_ANSWERS = {
    **COMPLETE,
    "locality": "Shankar Nagar",
    "notes": "Call me on 9876543210 or mail family@example.in",
    "property_type": "OTHER",
    "property_type_other": "Sharma family home at 12 MG Road",
}


async def test_the_provider_sees_only_sanitised_design_facts(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn,
) -> None:  # fmt: skip
    private = {k: PRIVATE_ANSWERS[k] for k in ("locality", "notes", "property_type",
                                                 "property_type_other")}  # fmt: skip
    family, project_id = await submitted_project(client_for, make_user, sign_in, **private)
    provider = CountingProvider()
    await generated(app, database, family, project_id, provider)
    [row] = await rows(database, project_id)
    [sent] = provider.requests
    assert set(row.provider_request) == PROVIDER_REQUEST_KEYS
    assert set(row.snapshot) <= ALLOWED_KEYS
    payload = json.dumps(row.provider_request) + json.dumps(row.snapshot) + sent.prompt
    for secret in ("Shankar", "9876543210", "family@example.in", "Sharma", "MG Road",
                   "21.25", "81.62", "OTHER", "lat", "lng", "upload", "file"):  # fmt: skip
        assert secret.lower() not in payload.lower(), secret
    assert sent.prompt == row.provider_request["prompt"]
    assert "facing East" in sent.prompt
    # Setbacks the family gave are in; the "Not sure" side is left out, not guessed.
    assert row.snapshot["setbacks"] == {"FRONT": 10, "BACK": 5, "RIGHT": 3.5}
    assert "open setbacks of 10 ft front, 5 ft back, 3.5 ft right" in sent.prompt
    assert "ft left" not in sent.prompt
    assert "2,650 sq ft" in sent.prompt


async def test_unknown_setbacks_are_omitted(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn,
) -> None:  # fmt: skip
    unknown = {side: "NOT_SURE" for side in ("FRONT", "BACK", "LEFT", "RIGHT")}
    family, project_id = await submitted_project(client_for, make_user, sign_in, setbacks=unknown)
    provider = CountingProvider()
    await generated(app, database, family, project_id, provider)
    [row] = await rows(database, project_id)
    assert "setbacks" not in row.snapshot
    assert "setback" not in provider.requests[0].prompt


async def test_the_snapshot_is_frozen_at_the_request(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn,
) -> None:  # fmt: skip
    family, project_id, staff = await review_ready(database, client_for, make_user, sign_in)
    first = await request_design(family, project_id)
    assert first.status_code == 202
    [before] = await rows(database, project_id)
    await ask(staff, project_id, "Confirm the style.")
    version = (await family.get(f"/api/v1/projects/{project_id}")).json()["requirement"]["version"]
    assert (
        await save(family, project_id, {**COMPLETE, "style": "TRADITIONAL"}, version)
    ).status_code == 200
    paused = await request_design(family, project_id)
    assert paused.json()["error"]["details"]["block"] == "REQUIREMENT_BEING_UPDATED"
    assert (await submit(family, project_id, version + 1)).status_code == 200
    await run_pending(app, database)
    second = await generated(app, database, family, project_id)
    first_row, second_row = await rows(database, project_id)
    assert first_row.snapshot == before.snapshot  # the queued one ran with what it was given
    assert "style" not in first_row.snapshot or first_row.snapshot["style"] != "TRADITIONAL"
    assert second_row.snapshot["style"] == "TRADITIONAL"
    assert second_row.requirement_version > first_row.requirement_version
    assert second["state"] == "SUCCEEDED"


async def test_the_client_controls_nothing_but_the_view(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    for smuggled in (
        {"view": "EXTERIOR", "provider": "other"},
        {"view": "EXTERIOR", "model": "x"},
        {"view": "EXTERIOR", "prompt": "a castle"},
        {"view": "EXTERIOR", "prompt_template_version": 2},
        {"view": "EXTERIOR", "free_remaining": 99},
        {"view": "EXTERIOR", "funding": "PAID"},
        {"view": "FLOOR_PLAN"},
    ):
        response = await request_design(family, project_id, smuggled)
        assert response.status_code == 422, smuggled
    assert await rows(database, project_id) == []


async def test_only_the_family_reaches_its_designs(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn,
) -> None:  # fmt: skip
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    design = await generated(app, database, family, project_id)
    stranger, own_project = await submitted_project(client_for, make_user, sign_in)
    base = f"/api/v1/projects/{project_id}/designs"
    assert (await stranger.get(base)).status_code == 404
    assert (await request_design(stranger, project_id)).status_code == 404
    assert (await stranger.get(f"{base}/{design['design_id']}")).status_code == 404
    assert (
        await stranger.post(f"{base}/{design['design_id']}/reference", headers=key())
    ).status_code == 404
    # Someone else's design through your own project's address is not found either.
    assert (
        await stranger.get(f"/api/v1/projects/{own_project}/designs/{design['design_id']}")
    ).status_code == 404
    assert (await client_for(Audience.IHB).get(base)).status_code == 401
    owner = (await rows(database, project_id))[0].requested_by
    async with database.transaction() as session:
        accessed = await session.scalar(
            select(func.count()).select_from(DocumentAccessLog).where(
                DocumentAccessLog.viewer_user_id != owner
            )
        )  # fmt: skip
    assert accessed == 0  # no signed link was issued to anyone else


async def test_generation_needs_a_submitted_requirement_and_an_open_project(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn,
) -> None:  # fmt: skip
    family = await homeowner(client_for, make_user, sign_in)
    draft = (await new_project(family))["project"]["project_id"]
    response = await request_design(family, draft)
    assert (response.status_code, response.json()["error"]["details"]["block"]) == (
        409, "NOT_SUBMITTED",
    )  # fmt: skip
    family, closed, staff = await review_ready(database, client_for, make_user, sign_in)
    earlier = await generated(app, database, family, closed)
    await cancel(staff, closed, "Outside Raipur.")
    response = await request_design(family, closed)
    assert response.json()["error"]["details"]["block"] == "PROJECT_CLOSED"
    listing = await designs(family, closed)
    assert listing["quota"]["block"] == "PROJECT_CLOSED"
    assert listing["items"][0]["image_url"]  # a closed project keeps its read-only view
    reference = await family.post(
        f"/api/v1/projects/{closed}/designs/{earlier['design_id']}/reference", headers=key()
    )
    assert reference.status_code == 409


async def test_without_a_provider_generation_is_unavailable(
    app: FastAPI, monkeypatch: pytest.MonkeyPatch,
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    monkeypatch.setattr(app.state, "image_provider", UnconfiguredImageProvider())
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    response = await request_design(family, project_id)
    assert (response.status_code, response.json()["error"]["code"]) == (503, "PROVIDER_UNAVAILABLE")
    assert (await designs(family, project_id))["quota"]["block"] == "PROVIDER_NOT_CONFIGURED"


def test_production_refuses_the_demo_provider() -> None:
    base = get_settings().model_dump()
    production = {
        **base, "env": "production", "email_provider": "resend", "resend_api_key": "key",
        "cookie_secure": True, "storage_provider": "s3", "scanner_provider": "clamav",
        "payment_provider": "none",
    }  # fmt: skip
    with pytest.raises(ValueError, match="demo AI images"):
        Settings(**{**production, "ai_image_provider": "demo"})
    assert Settings(**{**production, "ai_image_provider": "none"}).ai_image_provider == "none"


# --- references -------------------------------------------------------------------------------


async def test_a_reference_stays_illustrative(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn,
) -> None:  # fmt: skip
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    design = await generated(app, database, family, project_id)
    url = f"/api/v1/projects/{project_id}/designs/{design['design_id']}/reference"
    marked = await family.post(url, headers=key())
    assert marked.status_code == 200, marked.text
    body = marked.json()
    assert body["reference"]["kind"] == "ILLUSTRATIVE_REFERENCE"
    assert body["is_authoritative"] is False
    assert (await family.post(url, headers=key())).status_code == 200  # idempotent
    async with database.transaction() as session:
        references = list(await session.scalars(select(DesignReference)))
    assert [r.authority for r in references] == ["ILLUSTRATIVE_ONLY"]
    detail = (await family.get(f"/api/v1/projects/{project_id}")).json()
    assert detail["project"]["status"] == "SUBMITTED"  # nothing else moved
    with pytest.raises(IntegrityError):
        async with database.transaction() as session:
            await session.execute(update(DesignGeneration).values(is_authoritative=True))
    with pytest.raises(IntegrityError):
        async with database.transaction() as session:
            await session.execute(update(DesignReference).values(authority="APPROVED"))

    failed = await generated(app, database, family, project_id, FailingProvider())
    response = await family.post(
        f"/api/v1/projects/{project_id}/designs/{failed['design_id']}/reference", headers=key()
    )
    assert response.status_code == 409


async def test_a_reference_can_be_removed_and_marked_again_without_touching_the_concept(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn,
) -> None:  # fmt: skip
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    design = await generated(app, database, family, project_id)
    url = f"/api/v1/projects/{project_id}/designs/{design['design_id']}/reference"

    def fingerprint(row: DesignGeneration) -> tuple[Any, ...]:
        return (row.state, row.is_authoritative, row.version, row.output_file_id, row.funding,
                row.attempts, row.completed_at, row.snapshot, row.provider_request)  # fmt: skip

    [before] = await rows(database, project_id)
    quota_before = (await designs(family, project_id))["quota"]
    assert (await family.post(url, headers=key())).status_code == 200

    removed = await family.delete(url, headers=H)
    assert removed.status_code == 200, removed.text
    assert removed.json()["reference"] is None
    assert removed.json()["is_authoritative"] is False
    assert (await family.delete(url, headers=H)).status_code == 200  # idempotent
    [after] = await rows(database, project_id)
    assert fingerprint(after) == fingerprint(before)  # only the reference changed
    assert (await designs(family, project_id))["quota"] == quota_before

    again = await family.post(url, headers=key())
    assert again.json()["reference"]["kind"] == "ILLUSTRATIVE_REFERENCE"
    async with database.transaction() as session:
        history = list(
            await session.scalars(select(DesignReference).order_by(DesignReference.marked_at))
        )
    assert [r.removed_at is not None for r in history] == [True, False]
    assert history[0].removed_by == before.requested_by
    assert {r.authority for r in history} == {"ILLUSTRATIVE_ONLY"}

    stranger, _ = await submitted_project(client_for, make_user, sign_in)
    assert (await stranger.delete(url, headers=H)).status_code == 404


# --- the job ----------------------------------------------------------------------------------


async def test_job_states_retries_timeouts_and_bad_output(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn,
) -> None:  # fmt: skip
    family, project_id = await submitted_project(client_for, make_user, sign_in)

    flaky = FailingProvider("UNAVAILABLE", retryable=True, failures=1)
    assert (await generated(app, database, family, project_id, flaky))["state"] == "SUCCEEDED"
    assert (flaky.calls, (await rows(database, project_id))[-1].attempts) == (2, 2)

    quick = app.state.settings.model_copy(update={"ai_provider_timeout_seconds": 0.05})
    assert (await request_design(family, project_id)).status_code == 202
    assert await run_pending(app, database, SlowProvider(), quick) == ["FAILED"]
    timed_out = (await rows(database, project_id))[-1]
    assert (timed_out.failure_reason, timed_out.attempts) == ("PROVIDER_TIMEOUT", 2)

    stubborn = FailingProvider("REJECTED", retryable=False)
    assert (await generated(app, database, family, project_id, stubborn))["failure_reason"] == (
        "PROVIDER_REJECTED"
    )
    assert stubborn.calls == 1  # not retried

    bad = await generated(app, database, family, project_id, GarbageProvider())
    assert bad["failure_reason"] == "INVALID_OUTPUT"

    # Running a finished generation again does nothing.
    finished = (await rows(database, project_id))[0]
    assert await run_generation(database, app.state.settings, app.state.storage,
                                app.state.image_provider, finished.id) is None  # fmt: skip
    quota = (await designs(family, project_id))["quota"]
    assert (quota["free_used"], quota["free_remaining"]) == (1, 2)


async def test_a_generation_lost_by_the_worker_expires_and_frees_its_place(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> None:
    family, project_id = await submitted_project(client_for, make_user, sign_in)
    assert (await request_design(family, project_id)).status_code == 202
    async with database.transaction() as session:
        await session.execute(
            update(DesignGeneration).values(created_at=func.now() - timedelta(hours=2))
        )
    listing = await designs(family, project_id)
    assert listing["items"][0]["state"] == "FAILED"
    assert listing["items"][0]["failure_reason"] == "STALE"
    assert listing["quota"]["free_remaining"] == 3


# --- pure parts -------------------------------------------------------------------------------


async def test_the_demo_provider_is_deterministic() -> None:
    provider = DemoImageProvider()
    request = ImageRequest("p", "n", "EXTERIOR", 512, 384, 7)
    first, again = await provider.generate(request), await provider.generate(request)
    assert first.content == again.content
    other = await provider.generate(ImageRequest("p", "n", "INTERIOR", 512, 384, 7))
    assert other.content != first.content


def test_setbacks_keep_numbers_only() -> None:
    assert sanitise({"setbacks": {"FRONT": 0, "BACK": 7.5, "LEFT": "NOT_SURE", "RIGHT": 4}})[
        "setbacks"
    ] == {"FRONT": 0, "BACK": 7.5, "RIGHT": 4}
    for junk in ({"FRONT": "12 ft from Mr Rao's wall"}, {"TOP": 4}, {"FRONT": True},
                 {"FRONT": -1}, "10 all round", None):  # fmt: skip
        assert "setbacks" not in sanitise({"setbacks": junk}), junk


def test_sanitise_keeps_only_closed_design_facts() -> None:
    answers = {
        **PRIVATE_ANSWERS, "facing": "NOT_SURE", "built_up_area_sqft": "NOT_SURE",
        "style": "<script>", "uploads": ["file-id"], "location": {"lat": 21.2, "lng": 81.6},
        "bedrooms": "3", "vastu": "NOT_NEEDED",
    }  # fmt: skip
    snapshot = sanitise(answers)
    assert set(snapshot) <= ALLOWED_KEYS
    for dropped in ("facing", "built_up_area_sqft", "style", "uploads", "location", "notes",
                    "locality", "property_type", "property_type_other", "vastu"):  # fmt: skip
        assert dropped not in snapshot, dropped
    sentence = facts(snapshot)
    assert "Not sure" not in sentence
    assert "facing" not in sentence
    assert sentence.startswith("Project facts: premium-finish house")


def test_finalise_validates_and_marks_the_image() -> None:
    with pytest.raises(InvalidImage):
        finalise(b"nope")
    tiny = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(tiny, format="PNG")
    with pytest.raises(InvalidImage):
        finalise(tiny.getvalue())
    source = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(source, format="PNG")
    marked = finalise(source.getvalue())
    with Image.open(io.BytesIO(marked)) as image:
        assert image.format == "JPEG"
        assert image.size == (800, 600)
        assert not image.info.get("exif")
        # The mark sits bottom-left on a dark band: the image is no longer plain white there.
        pixel = image.convert("L").getpixel((30, 600 - 30))
        assert isinstance(pixel, int)
        assert pixel < 120
