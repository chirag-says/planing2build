"""Helpers for the Slice 3.7B tests: an appointed auditor with a professionals-host account, the
inspection steps through the API, and the restoration of the seeded checklist after a test that
publishes another version."""

import uuid
from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient
from sqlalchemy import text

from p2b.core.db import Database
from p2b.core.vocabulary import Audience
from tests.buildplan_support import code_of
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.execution_support import PRO_H, Site, ok, ops_key, photo, pro_key
from tests.staff_support import Staff
from tests.test_engagements import give_email

CHECKLIST_V1 = "37000000-0000-7000-8000-000000000001"


@dataclass
class Auditor:
    client: AsyncClient
    user_id: uuid.UUID
    appointment_id: str
    code: str


async def appoint(
    database: Database, client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
    admin: Staff, name: str = "S. Iyer",
) -> Auditor:  # fmt: skip
    """An auditor with an account, appointed by ADMIN (EX-09)."""
    user_id = await make_user(Audience.PRO)
    email = f"auditor-{user_id.hex}@example.in"
    await give_email(database, user_id, email, "pro")
    client = client_for(Audience.PRO)
    await sign_in(client, user_id, Audience.PRO)
    body = ok(
        await admin.client.post(
            "/api/v1/admin/auditor-appointments",
            json={"name": name, "qualification": "Chartered civil engineer (TEST)",
                  "registration_reference": "TEST-CE-1", "account_email": email},
            headers=ops_key(),
        ),
        201,
    )  # fmt: skip
    return Auditor(client, user_id, str(body["id"]), str(body["auditor_code"]))


async def appoint_without_account(admin: Staff, name: str = "R. Das") -> str:
    body = ok(
        await admin.client.post(
            "/api/v1/admin/auditor-appointments",
            json={"name": name, "qualification": "Civil engineer (TEST)"}, headers=ops_key(),
        ),
        201,
    )  # fmt: skip
    return str(body["id"])


async def schedule(s: Site, stage_id: str, appointment_id: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = ok(
        await s.ops.client.post(
            f"/api/v1/ops/stages/{stage_id}/inspections",
            json={"appointment_id": appointment_id, **extra}, headers=ops_key(),
        ),
        201,
    )  # fmt: skip
    return next(i for i in body["inspections"] if i["stage_instance_id"] == stage_id and
                i["state"] == "SCHEDULED")  # fmt: skip


async def detail(a: Auditor, inspection_id: str) -> dict[str, Any]:
    out: dict[str, Any] = ok(await a.client.get(f"/api/v1/pro/inspections/{inspection_id}"))
    return out


async def results(
    a: Auditor, database: Database, project_id: str, inspection_id: str, *,
    findings: dict[str, str] | None = None, result: str = "PASS",
) -> list[dict[str, Any]]:  # fmt: skip
    """Every checkpoint answered: `result` everywhere, a non-conformance with a finding of the
    given severity on the checkpoints named in `findings` (code to severity)."""
    view = await detail(a, inspection_id)
    evidence = await photo(database, a.user_id, project_id, purpose="INSPECTION_EVIDENCE")
    items = []
    for c in view["checkpoints"]:
        severity = (findings or {}).get(c["code"])
        item: dict[str, Any] = {"checkpoint_id": c["id"], "result": result,
                                "file_ids": [evidence]}  # fmt: skip
        if severity:
            item.update(result="NON_CONFORMANCE", severity=severity,
                        description="Cover blocks missing at the column base.",
                        corrective_action="Place 50 mm cover blocks before the pour.",
                        due_date="2099-01-31")  # fmt: skip
        items.append(item)
    return items


async def perform(
    a: Auditor, database: Database, project_id: str, inspection_id: str, **kwargs: Any
) -> dict[str, Any]:
    """Readiness, every result, and submission with the emailed code."""
    url = f"/api/v1/pro/inspections/{inspection_id}"
    ok(await a.client.post(f"{url}/readiness", headers=pro_key()))
    items = await results(a, database, project_id, inspection_id, **kwargs)
    ok(await a.client.put(f"{url}/results", json={"results": items}, headers=PRO_H))
    return await submit(a, database, inspection_id)


async def submit(a: Auditor, database: Database, inspection_id: str) -> dict[str, Any]:
    url = f"/api/v1/pro/inspections/{inspection_id}"
    challenge = ok(await a.client.post(f"{url}/submission-code", headers=PRO_H))
    code = await code_of(database, challenge["challenge_id"])
    out: dict[str, Any] = ok(
        await a.client.post(
            f"{url}/submit", json={"summary": "Checked on site.",
                                   "challenge_id": challenge["challenge_id"], "code": code},
            headers=pro_key(),
        )
    )  # fmt: skip
    return out


async def approve(s: Site, inspection_id: str) -> dict[str, Any]:
    out: dict[str, Any] = ok(
        await s.ops.client.post(
            f"/api/v1/ops/inspections/{inspection_id}/approve", headers=ops_key()
        )
    )
    return out


async def restore_checklists(database: Database) -> None:
    """The seeded version 1 PUBLISHED again and later versions removed (reference data)."""
    async with database.transaction() as session:
        for statement in (
            "TRUNCATE inspections, inspection_results, non_conformances, inspection_reports, "
            "test_results CASCADE",
            "ALTER TABLE checklist_versions DISABLE TRIGGER USER",
            "ALTER TABLE checkpoints DISABLE TRIGGER USER",
            f"DELETE FROM checkpoints WHERE checklist_version_id <> '{CHECKLIST_V1}'",  # noqa: S608
            f"DELETE FROM checklist_versions WHERE id <> '{CHECKLIST_V1}'",  # noqa: S608
            f"UPDATE checklist_versions SET status = 'PUBLISHED' WHERE id = '{CHECKLIST_V1}'",  # noqa: S608
            "ALTER TABLE checkpoints ENABLE TRIGGER USER",
            "ALTER TABLE checklist_versions ENABLE TRIGGER USER",
        ):
            await session.execute(text(statement))
