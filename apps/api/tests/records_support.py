"""Helpers for the Slice 3.7C tests: a project whose Gate 6 is cleared (a checklist version with a
Gate 6 checkpoint published by ADMIN, the snag inspection passed and approved), and the handover
steps through the API."""

from typing import Any

from fastapi import FastAPI

from p2b.core.db import Database
from tests.assurance_support import Auditor, appoint, approve, perform, schedule
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.execution_support import Site, ok, ops_key, photo, site, stage
from tests.test_engagements import Run


async def publish_gate6(s: Site) -> None:
    """Version 2: version 1 plus one Gate 6 checkpoint (EX-08: drafted by the auditor and
    operations, published by ADMIN)."""
    versions = ok(await s.ops.client.get("/api/v1/ops/checklists"))
    v1 = next(v for v in versions if v["status"] == "PUBLISHED")
    draft = ok(await s.ops.client.post("/api/v1/ops/checklists",
                                       json={"from_version_id": v1["id"], "note": "Gate 6"},
                                       headers=ops_key()), 201)  # fmt: skip
    points: list[dict[str, Any]] = [
        {k: c[k] for k in ("gate", "sequence", "code", "text", "expected_evidence",
                           "is_critical", "spec_line_code")}
        for c in draft["checkpoints"]
    ]  # fmt: skip
    points.append({"gate": 6, "sequence": 1, "code": "G6-C24", "text": "External works",
                   "spec_line_code": "C24"})  # fmt: skip
    ok(await s.ops.client.put(f"/api/v1/ops/checklists/{draft['id']}/checkpoints",
                              json={"checkpoints": points}, headers=ops_key()))  # fmt: skip
    ok(await s.world.admin.client.post(f"/api/v1/admin/checklists/{draft['id']}/publish",
                                       headers=ops_key()))  # fmt: skip


async def cleared(
    app: FastAPI, database: Database, client_for: ClientFactory, make_user: UserFactory,
    sign_in: SignIn, run: Run | None, **kwargs: Any,
) -> tuple[Site, Auditor]:  # fmt: skip
    """A project whose Gate 6 inspection passed and is approved, with no finding open."""
    s = await site(app, database, client_for, make_user, sign_in, run, **kwargs)
    a = await appoint(database, client_for, make_user, sign_in, s.world.admin)
    await publish_gate6(s)
    snag = (await stage(s, 16))["id"]
    iid = (await schedule(s, snag, a.appointment_id))["id"]
    await perform(a, database, s.project_id, iid)
    await approve(s, iid)
    assert (await stage(s, 16))["gate_status"] == "CLEARED"
    return s, a


async def opened(s: Site) -> dict[str, Any]:
    body: dict[str, Any] = ok(
        await s.ops.client.post(f"/api/v1/ops/projects/{s.project_id}/handover",
                                headers=ops_key())  # fmt: skip
    )
    return body


async def document(
    s: Site, database: Database, kind: str = "MANUAL", title: str = "Pump manual"
) -> dict[str, Any]:
    file_id = await photo(database, s.ops.user_id, s.project_id, purpose="HANDOVER_DOCUMENT")
    body: dict[str, Any] = ok(
        await s.ops.client.post(
            f"/api/v1/ops/projects/{s.project_id}/handover/documents",
            json={"kind": kind, "title": title, "file_id": file_id}, headers=ops_key(),
        )
    )  # fmt: skip
    return body


async def ready(s: Site, database: Database) -> dict[str, Any]:
    """Open, one manual, one warranty document with its warranty entry, READY."""
    await opened(s)
    await document(s, database)
    view = await document(s, database, "WARRANTY", "Waterproofing warranty")
    warranty_doc = next(d for d in view["handover"]["documents"] if d["kind"] == "WARRANTY")
    ok(await s.ops.client.post(
        f"/api/v1/ops/projects/{s.project_id}/handover/warranties",
        json={"item": "Terrace waterproofing", "term": "5 years", "expiry_date": "2031-10-01",
              "installer": "Dry Roofs (TEST)", "spec_line_code": "B16",
              "document_id": warranty_doc["id"]},
        headers=ops_key(),
    ))  # fmt: skip
    body: dict[str, Any] = ok(
        await s.ops.client.post(f"/api/v1/ops/projects/{s.project_id}/handover/ready",
                                headers=ops_key())  # fmt: skip
    )
    return body
