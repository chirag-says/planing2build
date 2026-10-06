"""Helpers for the Slice 3.7 tests: a project with its stages and an engaged contractor (listed,
through an accepted connection, or outside), stored stage photos, and the execution steps
through the API."""

import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy import text

from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.vocabulary import Audience, StaffRole
from p2b.documents.models import FileObject
from tests.billing_support import key
from tests.conftest import ClientFactory, SignIn, UserFactory, csrf_headers
from tests.staff_support import Staff, verified_staff
from tests.test_engagements import (
    Run,
    World,
    category_of,
    give_email,
    listed_pro,
    owner_of,
    pro_post,
    sent,
    services,
    world,
)

PRO_H = csrf_headers(Audience.PRO)
OPS_H = csrf_headers(Audience.OPS)
GATES = {3, 4, 6, 9, 10, 16}
MILESTONES = {1, 3, 4, 6, 7, 10, 11, 13, 14, 16}


def pro_key() -> dict[str, str]:
    return {**PRO_H, "Idempotency-Key": str(uuid.uuid4())}


def ops_key() -> dict[str, str]:
    return {**OPS_H, "Idempotency-Key": str(uuid.uuid4())}


def ok(response: Response, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def reason(response: Response) -> str:
    body = response.json()["error"]
    return str(body["details"].get("reason") or body["code"])


@dataclass
class Site:
    world: World
    owner: uuid.UUID
    ops: Staff
    pro: AsyncClient | None
    pro_user: uuid.UUID | None
    profile_id: str | None
    engagement_id: str

    @property
    def project_id(self) -> str:
        return self.world.project_id

    @property
    def family(self) -> AsyncClient:
        return self.world.family

    @property
    def base(self) -> str:
        return self.world.base

    @property
    def pro_base(self) -> str:
        return f"/api/v1/pro/engagements/{self.engagement_id}"


async def site(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn, run: Run | None, *, outside: bool = False,
) -> Site:  # fmt: skip
    """An accepted project with its stages; a listed contractor engaged through an accepted
    connection (needs the package, so `run`), or an outside contractor recorded by the family."""
    w = await world(app, database, client_for, make_user, sign_in, run)
    owner = await owner_of(database, w.project_id)
    await give_email(database, owner, f"owner-{owner.hex}@example.in", "ihb")
    ops = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    if outside:
        body = ok(
            await w.family.post(
                f"{w.base}/engagements",
                json={"category": "CONTRACTOR", "name": "Sharma Constructions",
                      "contact": "0771 400 000"},
                headers=key(),
            ),
            201,
        )  # fmt: skip
        engagement_id = str(category_of(body, "CONTRACTOR")["engagement"]["id"])
        return Site(w, owner, ops, None, None, None, engagement_id)
    pro, profile_id, user_id = await listed_pro(database, client_for, make_user, sign_in)
    await give_email(database, user_id, f"c-{user_id.hex}@example.in", "pro")
    accepted = await pro_post(pro, await sent(w, profile_id), "accept", phone="+91 90000 11111")
    assert accepted.status_code == 200, accepted.text
    engagement_id = str(category_of(await services(w), "CONTRACTOR")["engagement"]["id"])
    return Site(w, owner, ops, pro, user_id, profile_id, engagement_id)


async def stages(s: Site) -> list[dict[str, Any]]:
    body = ok(await s.family.get(f"{s.base}/execution"))
    out: list[dict[str, Any]] = body["stages"]
    return out


async def stage(s: Site, number: int, floor: int | None = None) -> dict[str, Any]:
    for row in await stages(s):
        if row["stage_number"] == number and (floor is None or row["floor"] == floor):
            return row
    raise AssertionError(f"no stage {number}")


async def photo(
    database: Database, uploader: uuid.UUID, project_id: str, *, purpose: str = "STAGE_EVIDENCE",
    state: str = "AVAILABLE",
) -> str:  # fmt: skip
    """A scanned stage photo (the upload pipeline is tested in test_documents)."""
    file_id = new_id()
    async with database.transaction() as session:
        session.add(
            FileObject(
                id=file_id, bucket="test", object_key=f"test/{file_id}", purpose=purpose,
                owner_user_id=uploader, project_id=uuid.UUID(project_id), original_name="site.jpg",
                declared_mime="image/jpeg", detected_mime="image/jpeg", size_bytes=1000,
                sha256="0" * 64, state=state,
                capture_claim={"captured_at": "2026-10-06T09:00:00+05:30"},
            )
        )  # fmt: skip
    return str(file_id)


def update_body(file_ids: list[str], kind: str = "PROGRESS", **extra: Any) -> dict[str, Any]:
    return {"kind": kind, "note": "Footing excavation done on grid A.", "file_ids": file_ids,
            **extra}  # fmt: skip


async def post(s: Site, database: Database, stage_id: str, kind: str = "PROGRESS") -> Response:
    assert s.pro is not None
    assert s.pro_user is not None
    file_id = await photo(database, s.pro_user, s.project_id)
    return await s.pro.post(
        f"{s.pro_base}/stages/{stage_id}/updates", json=update_body([file_id], kind),
        headers=pro_key(),
    )  # fmt: skip


async def requested(s: Site, database: Database, stage_id: str) -> dict[str, Any]:
    """The stage with a completion request pending (started by a progress update first)."""
    ok(await post(s, database, stage_id), 201)
    body = ok(await post(s, database, stage_id, "COMPLETION_REQUEST"), 201)
    out: dict[str, Any] = body["stage"]
    return out


async def household(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
    project_id: str,
) -> AsyncClient:  # fmt: skip
    user_id = await make_user(Audience.IHB)
    client = client_for(Audience.IHB)
    await sign_in(client, user_id, Audience.IHB)
    async with database.transaction() as session:
        await session.execute(
            text(
                "INSERT INTO project_memberships (id, project_id, user_id, role) "
                "VALUES (:id, :project_id, :user_id, 'HOUSEHOLD')"
            ),
            {"id": new_id(), "project_id": uuid.UUID(project_id), "user_id": user_id},
        )
    return client


async def set_gate(database: Database, stage_id: str, status: str) -> None:
    """Stands in for the assurance module (3.7B), which owns gate clearance."""
    async with database.transaction() as session:
        await session.execute(
            text("UPDATE stage_instances SET gate_status = :s WHERE id = :id"),
            {"s": status, "id": uuid.UUID(stage_id)},
        )
