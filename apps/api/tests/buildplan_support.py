"""Helpers for the Slice 3.5 tests: an eligible project with the package, an outside architect's
approved drawing set, a DEMO item rate card (development values, marked), staff with the roles
the workflow needs, a verified listed structural engineer, and one-time codes read from the
challenge (the delivery job would email them)."""

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy import text

from p2b.core.config import get_settings
from p2b.core.crypto import decrypt
from p2b.core.db import Database
from p2b.core.ids import new_id
from p2b.core.vocabulary import Audience, StaffRole
from p2b.documents.models import FileObject
from p2b.identity.models import OtpChallenge
from tests.billing_support import key
from tests.conftest import ClientFactory, SignIn, UserFactory, csrf_headers
from tests.staff_support import OPS_HEADERS, Staff, verified_staff
from tests.test_engagements import World, give_email, listed_pro, owner_of, sent, world

PRO_H = csrf_headers(Audience.PRO)
CLASSES = ["SITE_PLAN", "FLOOR_PLAN", "ELEVATION", "SECTION", "STRUCTURAL"]
STRUCTURAL = ["A01", "A02", "A04", "A05", "A09", "A12", "A13", "A19"]


def ops_key() -> dict[str, str]:
    return {**OPS_HEADERS, "Idempotency-Key": str(uuid.uuid4())}


def pro_key() -> dict[str, str]:
    return {**PRO_H, "Idempotency-Key": str(uuid.uuid4())}


async def stored(
    database: Database,
    owner: uuid.UUID,
    project_id: str,
    purpose: str = "DRAWING",
    name: str = "plan.pdf",
) -> str:
    """A scanned, AVAILABLE project file (the upload pipeline is tested in test_documents)."""
    file_id = new_id()
    async with database.transaction() as session:
        session.add(
            FileObject(
                id=file_id, bucket="test", object_key=f"test/{file_id}", purpose=purpose,
                owner_user_id=owner, project_id=uuid.UUID(project_id), original_name=name,
                declared_mime="application/pdf", detected_mime="application/pdf", size_bytes=1000,
                sha256=hashlib.sha256(str(file_id).encode()).hexdigest(), state="AVAILABLE",
            )
        )  # fmt: skip
    return str(file_id)


async def code_of(database: Database, challenge_id: str) -> str:
    async with database.transaction() as session:
        challenge = await session.get_one(OtpChallenge, uuid.UUID(challenge_id))
        assert challenge.code_ciphertext is not None
        return decrypt(
            get_settings().encryption_key.get_secret_value(),
            challenge.code_ciphertext,
            challenge.id.bytes,
        )


def ok(response: Response, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def reason(response: Response) -> str:
    body = response.json()["error"]
    return str(body["details"].get("reason") or body["code"])


@dataclass
class Team:
    world: World
    admin: Staff
    advisor: Staff
    issuer: Staff
    owner: uuid.UUID
    card_id: str
    checker_id: str

    @property
    def project_id(self) -> str:
        return self.world.project_id


async def team(
    app: FastAPI,
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    run: Any,
    *,
    package: bool = True,
) -> Team:
    w = await world(app, database, client_for, make_user, sign_in, run if package else None)
    owner = await owner_of(database, w.project_id)
    await give_email(database, owner, f"owner-{owner.hex[:8]}@example.in", "ihb")
    admin = w.admin
    advisor = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    issuer = await verified_staff(database, client_for, sign_in, StaffRole.OPS)
    card = ok(
        await advisor.client.post(
            "/api/v1/ops/item-rate-cards",
            json={"geography": "Raipur", "effective_from": "2026-10-01",
                  "source_reference": "TEST values for development", "is_demo": True},
            headers=ops_key(),
        ),
        201,
    )  # fmt: skip
    ok(
        await advisor.client.put(
            f"/api/v1/ops/item-rate-cards/{card['id']}/lines",
            json={"lines": [
                {"item_code": "TEST-RCC", "description": "TEST concrete", "unit": "cum",
                 "rate": "100.00"},
                {"item_code": "TEST-BRICK", "description": "TEST masonry", "unit": "sqm",
                 "rate": "10.50"},
            ]},
            headers=OPS_HEADERS,
        )
    )  # fmt: skip
    ok(await admin.client.post(
        f"/api/v1/admin/item-rate-cards/{card['id']}/publish", headers=ops_key()
    ))  # fmt: skip
    checker = ok(
        await admin.client.post(
            "/api/v1/admin/drawing-checkers",
            json={"name": "R. Kumar", "qualification": "Registered architect (TEST)"},
            headers=ops_key(),
        ),
        201,
    )
    return Team(w, admin, advisor, issuer, owner, card["id"], checker["id"])


async def approved_set(database: Database, t: Team) -> tuple[str, list[str]]:
    """The family records their own architect, provides the drawings and submits them; the
    appointed checker (no account) approves through operations with a signed note."""
    w = t.world
    outside = ok(
        await w.family.post(
            f"{w.base}/engagements", json={"category": "ARCHITECT", "name": "Own Architect"},
            headers=key(),
        ),
        201,
    )  # fmt: skip
    engagement_id = next(
        c["engagement"]["id"] for c in outside["categories"] if c["code"] == "ARCHITECT"
    )
    view = ok(
        await w.family.post(
            f"{w.base}/design-requests",
            json={"kind": "OUTSIDE_PROFESSIONAL", "engagement_id": engagement_id,
                  "scope_note": "House drawings"},
            headers=key(),
        ),
        201,
    )  # fmt: skip
    request_id = view["design_requests"][-1]["id"]
    view = ok(
        await w.family.post(f"{w.base}/design-requests/{request_id}/sets", headers=key()), 201
    )
    set_id = view["design_requests"][-1]["sets"][-1]["id"]
    for drawing_class in CLASSES:
        file_id = await stored(database, t.owner, w.project_id, name=f"{drawing_class}.pdf")
        ok(
            await w.family.post(
                f"{w.base}/drawing-sets/{set_id}/files",
                json={"file_id": file_id, "drawing_class": drawing_class, "title": drawing_class},
                headers=key(),
            )
        )  # fmt: skip
    view = ok(await w.family.post(f"{w.base}/drawing-sets/{set_id}/submit", headers=key()))
    assert view["design_requests"][-1]["sets"][-1]["state"] == "IN_CHECK"
    note = await stored(
        database, t.advisor.user_id, w.project_id, "BUILD_PLAN_EVIDENCE", "note.pdf"
    )
    view = ok(
        await t.advisor.client.post(
            f"/api/v1/ops/drawing-sets/{set_id}/check",
            json={"appointment_id": t.checker_id, "approve": True, "note": "Checked.",
                  "evidence_file_id": note},
            headers=ops_key(),
        )
    )  # fmt: skip
    drawing_set = view["design_requests"][-1]["sets"][-1]
    assert drawing_set["state"] == "APPROVED"
    return set_id, [f["id"] for f in drawing_set["files"]]


async def drafted(
    database: Database, t: Team, set_id: str, drawing_file_ids: list[str]
) -> dict[str, Any]:
    """A complete DRAFT: every line valued, a two-line BOQ, every stage duration, scope."""
    c = t.advisor.client
    version = ok(
        await c.post(f"/api/v1/ops/projects/{t.project_id}/build-plan/versions", headers=ops_key()),
        201,
    )
    vid = version["snapshot"]["version"]["id"]
    ok(await c.put(f"/api/v1/ops/build-plan-versions/{vid}/drawing-set", json={"set_id": set_id},
                   headers=OPS_HEADERS))  # fmt: skip
    values = [
        {"code": v["code"], "value_text": f"TEST value for {v['code']}",
         "basis": "STRUCTURAL_DESIGN" if v["is_structural"] else "ADVISOR"}
        for v in version["snapshot"]["values"]
    ]  # fmt: skip
    ok(await c.put(f"/api/v1/ops/build-plan-versions/{vid}/values", json={"values": values},
                   headers=OPS_HEADERS))  # fmt: skip
    ok(
        await c.put(
            f"/api/v1/ops/build-plan-versions/{vid}/boq",
            json={"rate_card_id": t.card_id, "lines": [
                {"item_code": "TEST-RCC", "quantity": "12.5", "quantity_basis":
                 "MEASURED_FROM_DRAWING", "drawing_file_id": drawing_file_ids[1],
                 "stage_number": 3, "spec_line_codes": ["A04"]},
                {"item_code": "TEST-BRICK", "quantity": "40", "quantity_basis":
                 "ADVISOR_ESTIMATE", "basis_note": "From the floor plan area", "stage_number": 7},
            ]},
            headers=OPS_HEADERS,
        )
    )  # fmt: skip
    entries = [
        {"entry_key": e["entry_key"], "duration_days": 10} for e in version["snapshot"]["schedule"]
    ]
    entries[1]["predecessors"] = [entries[0]["entry_key"]]
    ok(await c.put(f"/api/v1/ops/build-plan-versions/{vid}/schedule", json={"entries": entries},
                   headers=OPS_HEADERS))  # fmt: skip
    out = ok(
        await c.put(
            f"/api/v1/ops/build-plan-versions/{vid}/scope",
            json={"inclusions": ["Civil and structural work"], "exclusions": ["None."],
                  "assumptions": ["Soil as per the soil report"]},
            headers=OPS_HEADERS,
        )
    )  # fmt: skip
    assert out["missing"] == [], out["missing"]
    result: dict[str, Any] = out
    return result


async def sign_all_by_document(
    database: Database, t: Team, vid: str, lines: list[str] | None = None
) -> Any:
    certificate = await stored(
        database, t.advisor.user_id, t.project_id, "BUILD_PLAN_EVIDENCE", "cert.pdf"
    )
    signed = await stored(
        database, t.advisor.user_id, t.project_id, "BUILD_PLAN_EVIDENCE", "signed.pdf"
    )
    return await t.advisor.client.post(
        f"/api/v1/ops/build-plan-versions/{vid}/signoffs",
        json={"line_codes": lines or STRUCTURAL, "engineer_name": "S. Rao (outside)",
              "registration_number": "TEST-REG-1", "registration_issuer": "TEST council",
              "credential_file_id": certificate, "evidence_file_id": signed,
              "attestation": "Certificate checked against the register."},
        headers=ops_key(),
    )  # fmt: skip


async def submitted(c: AsyncClient, vid: str) -> Any:
    return ok(await c.post(f"/api/v1/ops/build-plan-versions/{vid}/submit", headers=ops_key()))


async def issued(t: Team, vid: str) -> Any:
    return ok(
        await t.issuer.client.post(
            f"/api/v1/ops/build-plan-versions/{vid}/issue", headers=ops_key()
        )
    )


async def accepted(database: Database, t: Team, vid: str) -> Any:
    w = t.world
    challenge = ok(
        await w.family.post(f"{w.base}/build-plan/versions/{vid}/acceptance-code", headers=key())
    )
    code = await code_of(database, challenge["challenge_id"])
    return ok(
        await w.family.post(
            f"{w.base}/build-plan/versions/{vid}/accept",
            json={"challenge_id": challenge["challenge_id"], "code": code},
            headers=key(),
        )
    )


async def full_version(database: Database, t: Team) -> tuple[str, str, list[str]]:
    set_id, files = await approved_set(database, t)
    draft = await drafted(database, t, set_id, files)
    vid = draft["snapshot"]["version"]["id"]
    await submitted(t.advisor.client, vid)
    ok(await sign_all_by_document(database, t, vid))
    return vid, set_id, files


async def verified_engineer(
    database: Database,
    client_for: ClientFactory,
    make_user: UserFactory,
    sign_in: SignIn,
    t: Team,
    run: Any,
) -> tuple[AsyncClient, str, uuid.UUID]:
    """A listed structural engineer with a verified registration and an ACTIVE engagement."""
    client, profile_id, user_id = await listed_pro(
        database, client_for, make_user, sign_in, ("STRUCTURAL_ENGINEER",), name="Eng Verified"
    )
    await give_email(database, user_id, f"eng-{user_id.hex[:8]}@example.in", "pro")
    async with database.transaction() as session:
        category_id, requirement_id = (
            await session.execute(
                text(
                    "SELECT pc.id, (SELECT id FROM listing_requirement_versions "
                    "WHERE category_code = 'STRUCTURAL_ENGINEER' LIMIT 1) "
                    "FROM professional_categories pc WHERE pc.profile_id = :p"
                ),
                {"p": uuid.UUID(profile_id)},
            )
        ).one()
        case_id = new_id()
        await session.execute(
            text(
                "INSERT INTO verification_cases (id, professional_category_id, "
                "requirement_version_id, decision, decided_by, decided_at) VALUES "
                "(:id, :c, :r, 'APPROVED', :u, now())"
            ),
            {"id": case_id, "c": category_id, "r": requirement_id, "u": t.admin.user_id},
        )
        await session.execute(
            text(
                "INSERT INTO verification_checks (id, case_id, kind, subject, outcome, detail, "
                "recorded_by) VALUES (:id, :case, 'REGISTRATION', 'registration', 'PASSED', "
                "CAST(:detail AS jsonb), :u)"
            ),
            {"id": new_id(), "case": case_id, "u": t.admin.user_id,
             "detail": '{"issuer": "TEST council", "number": "TEST-REG-9"}'},
        )  # fmt: skip
    connection_id = await sent(t.world, profile_id, "STRUCTURAL_ENGINEER")
    accepted_connection = await client.post(
        f"/api/v1/pro/connections/{connection_id}/accept", json={}, headers=pro_key()
    )
    assert accepted_connection.status_code == 200, accepted_connection.text
    return client, profile_id, user_id
