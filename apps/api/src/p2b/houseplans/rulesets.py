"""Which layout ruleset a generation may use (AD-05, CP1-05, CP1-06).

Production: the one PUBLISHED ruleset, never anything else. Elsewhere, only where settings allow:
the newest APPROVED or DRAFT ruleset, and a synthetic (test-data) one only when
`houseplans_allow_synthetic_ruleset` is set, which configuration permits in local and test only.
A job always reloads the exact ruleset its plan row names, so a plan is reproducible against the
rules it used."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.config import Settings
from p2b.core.errors import RulesetNotPublished
from p2b.core.vocabulary import RulesetStatus
from p2b.houseplans.engine.canonical import sha256_of
from p2b.houseplans.engine.ruleset import RulesetContent
from p2b.houseplans.models import LayoutRuleset


@dataclass(frozen=True)
class LoadedRuleset:
    id: uuid.UUID
    version: int
    status: RulesetStatus
    is_synthetic: bool
    content: RulesetContent
    sha256: str


def _loaded(row: LayoutRuleset) -> LoadedRuleset:
    content = RulesetContent.model_validate(row.content)
    if content.synthetic != row.is_synthetic:
        raise RulesetNotPublished(details={"reason": "synthetic flag mismatch"})
    return LoadedRuleset(
        id=row.id,
        version=row.version,
        status=RulesetStatus(row.status),
        is_synthetic=row.is_synthetic,
        content=content,
        sha256=sha256_of(content),
    )


async def load_ruleset(session: AsyncSession, settings: Settings) -> LoadedRuleset:
    published = await session.scalar(
        select(LayoutRuleset).where(LayoutRuleset.status == RulesetStatus.PUBLISHED.value)
    )
    if published is not None and not published.is_synthetic:
        return _loaded(published)
    if settings.env == "production" or not settings.houseplans_allow_draft_ruleset:
        raise RulesetNotPublished
    statuses = (RulesetStatus.APPROVED.value, RulesetStatus.DRAFT.value)
    query = select(LayoutRuleset).where(LayoutRuleset.status.in_(statuses))
    if not (settings.houseplans_allow_synthetic_ruleset and settings.env in ("local", "test")):
        query = query.where(LayoutRuleset.is_synthetic.is_(False))
    row = await session.scalar(query.order_by(LayoutRuleset.version.desc()).limit(1))
    if row is None:
        raise RulesetNotPublished
    return _loaded(row)


async def load_ruleset_by_id(session: AsyncSession, ruleset_id: uuid.UUID) -> LoadedRuleset:
    row = await session.get(LayoutRuleset, ruleset_id)
    if row is None:
        raise RulesetNotPublished(details={"ruleset_id": str(ruleset_id)})
    return _loaded(row)
