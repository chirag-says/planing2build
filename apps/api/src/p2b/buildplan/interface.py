"""Public interface of the buildplan module. Notifications read what an email may say about an
issued version; the rfq module (Slice 3.6) reads the ACCEPTED version's contractor manifest, the
RFQ baseline (BP-05, BP-08)."""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from p2b.buildplan.lifecycle import accepted_version
from p2b.buildplan.models import BuildPlanVersion
from p2b.buildplan.views import manifest, snapshot
from p2b.projects.interface import build_plan_facts


@dataclass(frozen=True)
class IssuedNotice:
    owner_user_id: uuid.UUID
    project_code: str
    version_no: int


async def issued_notice(session: AsyncSession, version_id: uuid.UUID) -> IssuedNotice | None:
    version = await session.get(BuildPlanVersion, version_id)
    if version is None:
        return None
    facts = await build_plan_facts(session, version.project_id)
    if facts is None:
        return None
    return IssuedNotice(facts.owner_user_id, facts.code, version.version_no)


@dataclass(frozen=True)
class AcceptedManifest:
    """The contractor RFQ manifest of the project's ACCEPTED version: scope, quantities, issued
    values, drawings with hashes, durations; never Plan2Build's rates or amounts (BP-08)."""

    version_id: uuid.UUID
    version_no: int
    content_hash: str
    manifest: dict[str, Any]


async def accepted_version_id(session: AsyncSession, project_id: uuid.UUID) -> uuid.UUID | None:
    version = await accepted_version(session, project_id)
    return version.id if version else None


async def accepted_manifest(
    session: AsyncSession, project_id: uuid.UUID
) -> AcceptedManifest | None:
    version = await accepted_version(session, project_id)
    facts = await build_plan_facts(session, project_id)
    if version is None or facts is None:
        return None
    view = await snapshot(session, facts, version)
    return AcceptedManifest(version.id, version.version_no, version.content_hash or "", manifest(view))


__all__ = [
    "AcceptedManifest",
    "IssuedNotice",
    "accepted_manifest",
    "accepted_version_id",
    "issued_notice",
]
