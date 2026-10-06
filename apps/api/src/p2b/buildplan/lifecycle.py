"""Issue, homeowner acceptance and change requests (SLICE3_5_READINESS 0.2, 0.4; BP-05, BP-09,
BP-13).

Issue: operations with MFA, never the version's last editor; every condition of 0.4; the
content hash recomputed and compared; the PDF rendered and stored in the same transaction, so an
ISSUED version always has its document. Acceptance: the owner, confirmed by a one-time code
bound to the version; the record names the exact version, its content hash and the issued
document's sha256; a later acceptance supersedes the earlier accepted version. Neither writes a
package usage record: the refund rule stays N-12 (BP-09)."""

import hashlib
import uuid
from string import Template

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.buildplan import pdf, plans, signoffs
from p2b.buildplan.common import Who, conflict, db_now, require_package
from p2b.buildplan.models import (
    AcceptanceStatement,
    BuildPlan,
    BuildPlanAcceptance,
    BuildPlanVersion,
    DrawingSet,
)
from p2b.buildplan.views import snapshot
from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.errors import StateConflict
from p2b.core.ids import new_id
from p2b.core.storage import Storage
from p2b.core.vocabulary import BuildPlanState, DrawingSetState, FilePurpose, OtpPurpose
from p2b.documents.interface import file_facts, store_generated_file
from p2b.identity.interface import verify_confirmation
from p2b.projects.interface import BuildPlanFacts
from p2b.specification.interface import record_accepted_values

V = BuildPlanState


async def acceptance_statement(
    session: AsyncSession, facts: BuildPlanFacts, version: BuildPlanVersion
) -> tuple[uuid.UUID, str]:
    """The ACTIVE acceptance statement (versioned configuration, BP-05) filled in for this exact
    version. Version 1 is functional wording, pending final client and legal confirmation."""
    statement = await signoffs.active_statement(session, AcceptanceStatement)
    text = Template(statement.text).substitute(
        version_no=str(version.version_no),
        project_code=facts.code,
        content_hash=version.content_hash or "",
    )
    return statement.id, text


async def _render_and_store(
    session: AsyncSession,
    settings: Settings,
    storage: Storage,
    facts: BuildPlanFacts,
    version: BuildPlanVersion,
    *,
    owner: uuid.UUID,
    accepted_copy: bool,
) -> uuid.UUID:
    view = await snapshot(session, facts, version)
    if not accepted_copy:
        view["version"]["state"] = V.ISSUED.value  # rendered as issued, in the issuing transaction
        for entry in view["history"]:
            if entry["version_no"] == version.version_no:
                entry["state"] = V.ISSUED.value
    created = version.accepted_at if accepted_copy else version.issued_at
    assert created is not None  # noqa: S101 (set before rendering)
    data = pdf.render(settings, view, created_at=created, accepted_copy=accepted_copy)
    suffix = "accepted" if accepted_copy else "issued"
    return await store_generated_file(
        session, settings, storage, project_id=version.project_id, owner_user_id=owner,
        purpose=FilePurpose.BUILD_PLAN_DOCUMENT, data=data, mime="application/pdf",
        file_name=f"{facts.code}-build-plan-v{version.version_no}-{suffix}.pdf",
    )  # fmt: skip


async def issue(
    session: AsyncSession,
    settings: Settings,
    storage: Storage,
    who: Who,
    facts: BuildPlanFacts,
    version_id: uuid.UUID,
) -> BuildPlanVersion:
    version = await plans.version_row(session, version_id, lock=True)
    if version.state != V.IN_REVIEW.value:
        raise StateConflict(details={"current_state": version.state})
    await require_package(session, version.project_id)
    if version.last_edited_by == who.user_id:
        raise conflict("LAST_EDITOR", "The last editor of a version cannot issue it.")
    if await plans.content_hash(session, version) != version.content_hash:
        raise conflict("CONTENT_CHANGED", "The version's content no longer matches its hash.")
    drawing_set = await session.get_one(DrawingSet, version.drawing_set_id)
    if drawing_set.state != DrawingSetState.APPROVED.value:
        raise conflict("SET_NOT_APPROVED", "The drawing set is no longer the approved one.")
    assert version.rate_card_id is not None  # noqa: S101 (a submitted version has a BOQ)
    await plans.usable_card(session, settings, version.rate_card_id)
    unsigned = await signoffs.unsigned_lines(session, version)
    if unsigned:
        raise conflict("UNSIGNED", "Structural lines are not signed.", lines=unsigned)
    now = await db_now(session)
    version.issued_by = who.user_id
    version.issued_at = now
    version.issued_document_id = await _render_and_store(
        session, settings, storage, facts, version, owner=who.user_id, accepted_copy=False
    )
    await plans._move(session, version, "issue", who)
    for earlier in await plans.versions_of(session, version.project_id):
        if earlier.id != version.id and earlier.state in (
            V.ISSUED.value, V.CHANGES_REQUESTED.value,
        ):  # fmt: skip
            await plans.supersede(session, who, earlier, f"version {version.version_no} issued")
    await plans.publish_version_event(session, "buildplan.issued", version)
    return version


async def request_changes(
    session: AsyncSession, who: Who, version_id: uuid.UUID, project_id: uuid.UUID, reason: str
) -> None:
    version = await plans.version_row(session, version_id, lock=True)
    if version.project_id != project_id:
        raise StateConflict(details={"current_state": "OTHER_PROJECT"})
    if version.state != V.ISSUED.value:
        raise StateConflict(details={"current_state": version.state})
    await require_package(session, project_id)
    await plans._move(session, version, "request_changes", who, reason)


async def check_acceptable(
    session: AsyncSession, version_id: uuid.UUID, project_id: uuid.UUID
) -> BuildPlanVersion:
    version = await plans.version_row(session, version_id, lock=True)
    if version.project_id != project_id:
        raise StateConflict(details={"current_state": "OTHER_PROJECT"})
    if version.state != V.ISSUED.value:
        raise StateConflict(details={"current_state": version.state})
    await require_package(session, project_id)
    latest = await plans.latest_issued(session, project_id)
    if latest is None or latest.id != version.id:
        raise conflict("NOT_LATEST", "Only the latest issued version can be accepted.")
    if await signoffs.revoked_after_issue(session, version.id):
        raise conflict("SIGNOFF_REVOKED", "A structural sign-off was revoked after issue.")
    return version


async def accept(
    session: AsyncSession,
    database: Database,
    settings: Settings,
    storage: Storage,
    who: Who,
    facts: BuildPlanFacts,
    version_id: uuid.UUID,
    *,
    challenge_id: uuid.UUID,
    code: str,
    ip_hash: str,
) -> BuildPlanVersion:
    version = await check_acceptable(session, version_id, facts.project_id)
    await verify_confirmation(
        database, settings, challenge_id=challenge_id, code=code, user_id=who.user_id,
        purpose=OtpPurpose.ACCEPT_BUILD_PLAN, subject_id=version.id, ip_hash=ip_hash,
    )  # fmt: skip
    assert version.issued_document_id is not None  # noqa: S101 (CHECK issued_has_document)
    issued_doc = (await file_facts(session, [version.issued_document_id]))[
        version.issued_document_id
    ]
    statement_id, statement_text = await acceptance_statement(session, facts, version)
    now = await db_now(session)
    session.add(
        BuildPlanAcceptance(
            id=new_id(), version_id=version.id, project_id=version.project_id,
            version_no=version.version_no, content_hash=version.content_hash or "",
            issued_document_sha256=issued_doc.sha256 or "", accepted_by=who.user_id,
            challenge_id=challenge_id, statement_id=statement_id, statement_text=statement_text,
            ip_hash=ip_hash, accepted_at=now,
        )
    )  # fmt: skip
    await session.flush()
    plan = await session.get_one(BuildPlan, version.build_plan_id, with_for_update=True)
    if plan.accepted_version_id is not None:
        earlier = await plans.version_row(session, plan.accepted_version_id, lock=True)
        await plans.supersede(session, who, earlier, f"version {version.version_no} accepted")
    version.accepted_at = now
    await plans._move(session, version, "accept", who)
    version.accepted_document_id = await _render_and_store(
        session, settings, storage, facts, version, owner=facts.owner_user_id, accepted_copy=True
    )
    plan.accepted_version_id = version.id
    plan.version += 1
    await session.flush()
    values = await plans.values_of(session, version.id)
    await record_accepted_values(session, version.project_id, {v.line_code: v.id for v in values})
    await plans.publish_version_event(session, "buildplan.accepted", version)
    return version


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def accepted_version(session: AsyncSession, project_id: uuid.UUID) -> BuildPlanVersion | None:
    plan = (
        await session.scalars(select(BuildPlan).where(BuildPlan.project_id == project_id))
    ).one_or_none()
    if plan is None or plan.accepted_version_id is None:
        return None
    return await session.get(BuildPlanVersion, plan.accepted_version_id)
