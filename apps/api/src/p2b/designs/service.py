"""AI design concepts (Slice 3.1; PD-05, PD-22; F-08 first version).

Request path (API, one transaction): the owner asks for a concept of a view; the server checks
the project is eligible, the provider is configured and the quotas allow it, under advisory locks
on the account and the project so concurrent requests cannot overrun them; it freezes the
sanitised requirement snapshot and renders the prompt with the active template version; it
records the generation QUEUED and publishes `design.generation_requested`. The outbox handler
defers the job, so a job exists only if the request committed.

Job path (worker): QUEUED -> RUNNING -> SUCCEEDED, or FAILED with a reason. The provider is
called with a timeout and a small number of attempts; the image is validated, re-encoded and
marked "Illustrative", stored privately, and only then is the generation SUCCEEDED.

Quotas count QUEUED, RUNNING and SUCCEEDED generations, never FAILED ones, so a failure consumes
nothing and an in-flight request holds its place. Every value is configuration. Days are a
rolling 24 hours.
"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.billing.interface import consume_credit, credit_balance, return_credit
from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.errors import NotFound, ProviderUnavailable, QuotaExhausted, StateConflict
from p2b.core.ids import new_id
from p2b.core.images import ImageProvider, ImageProviderError, ImageRequest
from p2b.core.outbox import EventPayload, publish
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.storage import Storage
from p2b.core.vocabulary import (
    ActorType,
    ConfigStatus,
    DesignBlock,
    DesignFailureReason,
    DesignFunding,
    DesignGenerationState,
    DesignView,
    FilePurpose,
    MembershipRole,
    ProjectStatus,
)
from p2b.designs.imaging import OUTPUT_MIME, InvalidImage, finalise
from p2b.designs.models import DesignGeneration, DesignPromptTemplate, DesignReference
from p2b.designs.prompts import render, sanitise, seed_for
from p2b.documents.interface import (
    FileRef,
    concept_files,
    concept_image_url,
    store_generated_file,
)
from p2b.identity.interface import Actor
from p2b.projects.interface import DesignBasis, design_basis

log = structlog.get_logger(__name__)

S = DesignGenerationState
GENERATION = TransitionTable[DesignGenerationState](
    "design_generation",
    [
        Transition(None, S.QUEUED, "request"),
        Transition(S.QUEUED, S.RUNNING, "start"),
        Transition(S.RUNNING, S.SUCCEEDED, "succeed"),
        Transition(S.RUNNING, S.FAILED, "fail"),
        Transition(S.QUEUED, S.FAILED, "expire"),  # stale: the worker never picked it up
    ],
)
COUNTING = (S.QUEUED.value, S.RUNNING.value, S.SUCCEEDED.value)
IN_FLIGHT = (S.QUEUED.value, S.RUNNING.value)
# The family generates once the requirement is submitted, and not while it is being revised
# after a request for information (the snapshot must be what was submitted). Closed projects keep
# their read-only view (F-13 stays open; nothing new is added for them).
P = ProjectStatus
GENERATING_STATUSES = frozenset(
    s.value for s in (P.SUBMITTED, P.ACCEPTED, P.PLANNING, P.PLAN_ISSUED, P.SOURCING,
                      P.CONTRACTED, P.BUILDING, P.HANDOVER_PENDING, P.COMPLETED)
)  # fmt: skip
STATUS_BLOCKS = {
    P.DRAFT.value: DesignBlock.NOT_SUBMITTED,
    P.NEEDS_INFO.value: DesignBlock.REQUIREMENT_BEING_UPDATED,
    P.CANCELLED.value: DesignBlock.PROJECT_CLOSED,
    P.ARCHIVED.value: DesignBlock.PROJECT_CLOSED,
    P.ON_HOLD.value: DesignBlock.PROJECT_CLOSED,
}
FAILURE_BY_KIND = {
    "UNAVAILABLE": DesignFailureReason.PROVIDER_UNAVAILABLE,
    "TIMEOUT": DesignFailureReason.PROVIDER_TIMEOUT,
    "REJECTED": DesignFailureReason.PROVIDER_REJECTED,
    "ERROR": DesignFailureReason.PROVIDER_ERROR,
}


class GenerationRequested(EventPayload):
    generation_id: uuid.UUID
    project_id: uuid.UUID


class GenerationFinished(EventPayload):
    generation_id: uuid.UUID
    project_id: uuid.UUID
    state: DesignGenerationState


@dataclass(frozen=True)
class Quota:
    free_total: int
    free_used: int
    in_progress: int
    free_remaining: int
    block: DesignBlock | None
    paid_block: DesignBlock | None  # for a generation paid with one AI credit
    credit_balance: int


def _stale_seconds(settings: Settings) -> float:
    """Longer than every attempt can take, plus a margin for a busy queue."""
    return settings.ai_provider_timeout_seconds * settings.ai_provider_attempts + 600


async def _expire_stale(
    session: AsyncSession, settings: Settings, *, project_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """In-flight generations far past any possible finish failed silently (a lost worker); they
    must not hold quota for ever."""
    expired = await session.execute(
        update(DesignGeneration)
        .where(
            DesignGeneration.state.in_(IN_FLIGHT),
            (DesignGeneration.project_id == project_id)
            | (DesignGeneration.requested_by == user_id),
            DesignGeneration.created_at
            < func.now() - func.make_interval(0, 0, 0, 0, 0, 0, _stale_seconds(settings)),
        )
        .values(
            state=S.FAILED.value,
            failure_reason=DesignFailureReason.STALE.value,
            completed_at=func.now(),
            version=DesignGeneration.version + 1,
        )
        .returning(DesignGeneration.id, DesignGeneration.funding)
    )
    for generation_id, funding in expired.all():
        if funding == DesignFunding.PAID.value:
            await return_credit(session, generation_id=generation_id)


async def _count(session: AsyncSession, *conditions: Any) -> int:
    value = await session.scalar(
        select(func.count()).select_from(DesignGeneration).where(*conditions)
    )
    return int(value or 0)


async def quota_for(
    session: AsyncSession,
    settings: Settings,
    provider: ImageProvider,
    *,
    basis: DesignBasis,
    user_id: uuid.UUID,
) -> Quota:
    """Quota and the first reason, if any, the family cannot generate now. Server-side only."""
    project_id = basis.project_id
    succeeded = await _count(
        session,
        DesignGeneration.project_id == project_id,
        DesignGeneration.funding == DesignFunding.FREE.value,
        DesignGeneration.state == S.SUCCEEDED.value,
    )
    in_flight = await _count(
        session,
        DesignGeneration.project_id == project_id,
        DesignGeneration.funding == DesignFunding.FREE.value,
        DesignGeneration.state.in_(IN_FLIGHT),
    )
    total = settings.ai_free_generations_per_project
    remaining = max(0, total - succeeded - in_flight)
    paid_block: DesignBlock | None
    if basis.status.value not in GENERATING_STATUSES:
        paid_block = STATUS_BLOCKS.get(basis.status.value, DesignBlock.PROJECT_CLOSED)
    elif not provider.configured:
        paid_block = DesignBlock.PROVIDER_NOT_CONFIGURED
    else:
        paid_block = await _daily_block(session, settings, project_id, user_id)
    # As before Slice 3.3, a used-up free quota is named before the daily caps.
    caps = (DesignBlock.ACCOUNT_DAILY_GENERATIONS, DesignBlock.ACCOUNT_DAILY_PROJECTS)
    block = paid_block
    if remaining == 0 and (block is None or block in caps):
        block = DesignBlock.FREE_QUOTA_USED
    balance = await credit_balance(session, user_id)
    return Quota(total, succeeded, in_flight, remaining, block, paid_block, balance)


async def _daily_block(
    session: AsyncSession, settings: Settings, project_id: uuid.UUID, user_id: uuid.UUID
) -> DesignBlock | None:
    """The PD-27 account caps, which count every generation, free or paid."""
    day = DesignGeneration.created_at > func.now() - text("interval '24 hours'")
    mine = DesignGeneration.requested_by == user_id
    counting = DesignGeneration.state.in_(COUNTING)
    if (
        await _count(session, mine, day, counting)
        >= settings.ai_max_generations_per_account_per_day
    ):
        return DesignBlock.ACCOUNT_DAILY_GENERATIONS
    projects_today = set(
        await session.scalars(
            select(DesignGeneration.project_id).distinct().where(mine, day, counting)
        )
    )
    if (
        project_id not in projects_today
        and len(projects_today) >= settings.ai_max_projects_per_account_per_day
    ):
        return DesignBlock.ACCOUNT_DAILY_PROJECTS
    return None


async def _basis(session: AsyncSession, actor: Actor, project_id: uuid.UUID) -> DesignBasis:
    basis = await design_basis(session, user_id=actor.user_id, project_id=project_id)
    if basis is None:
        raise NotFound
    return basis


async def request_generation(
    session: AsyncSession,
    settings: Settings,
    provider: ImageProvider,
    actor: Actor,
    project_id: uuid.UUID,
    *,
    view: DesignView,
    use_credit: bool = False,
) -> DesignGeneration:
    """A free generation while free ones remain. Once they are used up, a paid one only when the
    family chose 'Use 1 AI credit' (`use_credit`): the credit is spent in this transaction and
    the generation names it; a failure gives it back exactly once."""
    basis = await _basis(session, actor, project_id)
    if basis.role != MembershipRole.OWNER:
        raise NotFound
    # Account first, then project: one order everywhere, so two requests never deadlock.
    for key in (f"design-account:{actor.user_id}", f"design-project:{project_id}"):
        await session.execute(select(func.pg_advisory_xact_lock(func.hashtext(key))))
    await _expire_stale(session, settings, project_id=project_id, user_id=actor.user_id)
    quota = await quota_for(session, settings, provider, basis=basis, user_id=actor.user_id)
    paid = quota.block == DesignBlock.FREE_QUOTA_USED and use_credit
    blocking = quota.paid_block if paid else quota.block
    if blocking is not None:
        details = {"block": blocking.value}
        if blocking == DesignBlock.PROVIDER_NOT_CONFIGURED:
            raise ProviderUnavailable(details=details)
        if blocking in (
            DesignBlock.NOT_SUBMITTED,
            DesignBlock.REQUIREMENT_BEING_UPDATED,
            DesignBlock.PROJECT_CLOSED,
        ):
            raise StateConflict(details={**details, "current_state": basis.status.value})
        raise QuotaExhausted(details=details)
    generation_id = new_id()
    credit_ref = (
        await consume_credit(session, account_user_id=actor.user_id, generation_id=generation_id)
        if paid
        else None
    )

    template = (
        await session.scalars(
            select(DesignPromptTemplate).where(
                DesignPromptTemplate.view == view.value,
                DesignPromptTemplate.status == ConfigStatus.ACTIVE.value,
            )
        )
    ).one_or_none()
    if template is None:
        raise RuntimeError(f"no active prompt template for {view.value}")

    last = await session.scalar(
        select(func.max(DesignGeneration.sequence)).where(DesignGeneration.project_id == project_id)
    )
    sequence = int(last or 0) + 1
    snapshot = sanitise(basis.answers)
    provider_request = {
        "prompt": render(template.body, snapshot),
        "negative_prompt": template.negative_prompt,
        "view": view.value,
        "width": settings.ai_image_width,
        "height": settings.ai_image_height,
        "seed": seed_for(project_id, sequence),
    }
    generation = DesignGeneration(
        id=generation_id,
        project_id=project_id,
        sequence=sequence,
        view=view.value,
        funding=(DesignFunding.PAID if paid else DesignFunding.FREE).value,
        credit_ref=credit_ref,
        free_quota=quota.free_total,
        state=GENERATION.target(None, "request").value,
        provider=provider.name,
        model=provider.model,
        prompt_template_id=template.id,
        prompt_template_version=template.version,
        question_set_version=basis.question_set_version,
        requirement_version=basis.requirement_version,
        snapshot=snapshot,
        provider_request=provider_request,
        requested_by=actor.user_id,
    )
    session.add(generation)
    await session.flush()
    await session.refresh(generation)
    await record(
        session, action="design.generation_requested", entity_type="design_generation",
        entity_id=generation.id, project_id=project_id, actor_type=ActorType.USER,
        actor_user_id=actor.user_id, session_id=actor.session_id,
    )  # fmt: skip
    await publish(
        session,
        event_type="design.generation_requested",
        aggregate_type="design_generation",
        aggregate_id=generation.id,
        payload=GenerationRequested(generation_id=generation.id, project_id=project_id),
        dedupe_suffix="requested",
    )
    return generation


async def _finish(
    session: AsyncSession,
    generation: DesignGeneration,
    target: DesignGenerationState,
    trigger: str,
    **values: Any,
) -> None:
    GENERATION.target(S(generation.state), trigger)  # raises on an invalid transition
    now = (await session.execute(select(func.now()))).scalar_one()
    # Everything at once: the CHECKs tie the state to its output or reason.
    for name, value in values.items():
        setattr(generation, name, value)
    generation.state = target.value
    generation.completed_at = now
    generation.version += 1
    await session.flush()
    if target == S.FAILED and generation.funding == DesignFunding.PAID.value:
        await return_credit(session, generation_id=generation.id)
    await record(
        session, action=f"design.generation_{target.value.lower()}",
        entity_type="design_generation", entity_id=generation.id,
        project_id=generation.project_id, actor_type=ActorType.JOB,
    )  # fmt: skip
    await publish(
        session,
        event_type="design.generation_finished",
        aggregate_type="design_generation",
        aggregate_id=generation.id,
        payload=GenerationFinished(
            generation_id=generation.id, project_id=generation.project_id, state=target
        ),
        dedupe_suffix="finished",
    )


async def run_generation(
    database: Database,
    settings: Settings,
    storage: Storage,
    provider: ImageProvider,
    generation_id: uuid.UUID,
) -> DesignGenerationState | None:
    """The job. Idempotent: a generation already finished is left alone. Returns the end state."""
    async with database.transaction() as session:
        generation = await session.get(DesignGeneration, generation_id, with_for_update=True)
        if generation is None or generation.state not in IN_FLIGHT:
            return None
        if generation.state == S.QUEUED.value:
            generation.state = GENERATION.target(S.QUEUED, "start").value
            generation.started_at = (await session.execute(select(func.now()))).scalar_one()
        generation.provider, generation.model = provider.name, provider.model
        generation.version += 1
        request = ImageRequest(**generation.provider_request)

    failure: tuple[DesignFailureReason, str] | None = None
    result = None
    attempts = 0
    for attempt in range(1, settings.ai_provider_attempts + 1):
        attempts = attempt
        try:
            result = await asyncio.wait_for(
                provider.generate(request), timeout=settings.ai_provider_timeout_seconds
            )
            break
        except TimeoutError:
            failure = (DesignFailureReason.PROVIDER_TIMEOUT, "provider call timed out")
            retryable = True
        except ImageProviderError as exc:
            failure = (FAILURE_BY_KIND[exc.kind], str(exc)[:500])
            retryable = exc.retryable
        log.warning("design.provider_attempt_failed", generation_id=str(generation_id),
                    attempt=attempt, reason=failure[0].value)  # fmt: skip
        if not retryable:
            break
    image: bytes | None = None
    if result is not None:
        try:
            image = finalise(result.content)
            failure = None
        except InvalidImage as exc:
            failure = (DesignFailureReason.INVALID_OUTPUT, str(exc)[:500])

    async with database.transaction() as session:
        generation = await session.get(DesignGeneration, generation_id, with_for_update=True)
        if generation is None or generation.state != S.RUNNING.value:
            return None  # expired as stale meanwhile: keep that outcome
        if image is None or result is None:
            reason, detail = failure or (DesignFailureReason.PROVIDER_ERROR, "no result")
            await _finish(session, generation, S.FAILED, "fail", failure_reason=reason.value,
                          failure_detail=detail, attempts=attempts)  # fmt: skip
            return S.FAILED
        file_id = await store_generated_file(
            session,
            settings,
            storage,
            project_id=generation.project_id,
            owner_user_id=generation.requested_by,
            purpose=FilePurpose.AI_CONCEPT,
            data=image,
            mime=OUTPUT_MIME,
            file_name=f"illustrative-concept-{generation.sequence}.jpg",
        )
        usage = result.usage
        await _finish(
            session, generation, S.SUCCEEDED, "succeed", output_file_id=file_id,
            attempts=attempts,
            provider_usage={
                "amount": str(usage.amount) if usage.amount is not None else None,
                "currency": usage.currency, "units": usage.units,
            } if usage else None,
        )  # fmt: skip
        return S.SUCCEEDED


@dataclass(frozen=True)
class DesignItem:
    generation: DesignGeneration
    image_url: str | None
    reference_marked_at: datetime | None


async def _views(
    session: AsyncSession,
    storage: Storage,
    actor: Actor,
    ip_hash: str,
    project_id: uuid.UUID,
    generations: list[DesignGeneration],
) -> list[DesignItem]:
    files: dict[uuid.UUID, FileRef] = await concept_files(
        session, project_id, [g.output_file_id for g in generations if g.output_file_id]
    )
    references = dict(
        (
            await session.execute(
                select(DesignReference.generation_id, DesignReference.marked_at).where(
                    DesignReference.generation_id.in_([g.id for g in generations]),
                    DesignReference.removed_at.is_(None),
                )
            )
        ).all()
    )
    views = []
    for generation in generations:
        file = files.get(generation.output_file_id) if generation.output_file_id else None
        url = (
            concept_image_url(session, storage, file, viewer_user_id=actor.user_id,
                              ip_hash=ip_hash)
            if file else None
        )  # fmt: skip
        views.append(DesignItem(generation, url, references.get(generation.id)))
    return views


async def list_designs(
    session: AsyncSession,
    settings: Settings,
    storage: Storage,
    provider: ImageProvider,
    actor: Actor,
    project_id: uuid.UUID,
    *,
    ip_hash: str,
) -> tuple[Quota, list[DesignItem]]:
    basis = await _basis(session, actor, project_id)
    await _expire_stale(session, settings, project_id=project_id, user_id=actor.user_id)
    quota = await quota_for(session, settings, provider, basis=basis, user_id=actor.user_id)
    generations = list(
        await session.scalars(
            select(DesignGeneration)
            .where(DesignGeneration.project_id == project_id)
            .order_by(DesignGeneration.sequence.desc())
        )
    )
    return quota, await _views(session, storage, actor, ip_hash, project_id, generations)


async def get_design(
    session: AsyncSession,
    storage: Storage,
    actor: Actor,
    project_id: uuid.UUID,
    design_id: uuid.UUID,
    *,
    ip_hash: str,
) -> DesignItem:
    await _basis(session, actor, project_id)
    generation = await session.get(DesignGeneration, design_id)
    if generation is None or generation.project_id != project_id:
        raise NotFound
    return (await _views(session, storage, actor, ip_hash, project_id, [generation]))[0]


async def _owned_concept(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, design_id: uuid.UUID
) -> DesignGeneration:
    """A succeeded concept of an open project, for its owner. Closed projects stay read only."""
    basis = await _basis(session, actor, project_id)
    if basis.role != MembershipRole.OWNER:
        raise NotFound
    generation = await session.get(DesignGeneration, design_id)
    if generation is None or generation.project_id != project_id:
        raise NotFound
    if STATUS_BLOCKS.get(basis.status.value) == DesignBlock.PROJECT_CLOSED:
        raise StateConflict(details={"current_state": basis.status.value})
    if generation.state != S.SUCCEEDED.value:
        raise StateConflict(details={"current_state": generation.state})
    return generation


async def mark_reference(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, design_id: uuid.UUID
) -> None:
    """Mark a concept as the family's reference for later design work. Nothing else changes:
    the image stays illustrative, and no Build Plan, BOQ, RFQ or approval follows from it.
    Idempotent."""
    await _owned_concept(session, actor, project_id, design_id)
    inserted = await session.execute(
        insert(DesignReference)
        .values(
            id=new_id(), project_id=project_id, generation_id=design_id, marked_by=actor.user_id
        )
        # Literal predicate: a bound one stops matching the index once the plan goes generic.
        .on_conflict_do_nothing(
            index_elements=["generation_id"], index_where=text("removed_at IS NULL")
        )
        .returning(DesignReference.id)
    )
    if inserted.first() is not None:
        await record(
            session, action="design.reference_marked", entity_type="design_generation",
            entity_id=design_id, project_id=project_id, actor_type=ActorType.USER,
            actor_user_id=actor.user_id, session_id=actor.session_id,
        )  # fmt: skip


async def remove_reference(
    session: AsyncSession, actor: Actor, project_id: uuid.UUID, design_id: uuid.UUID
) -> None:
    """Remove the family's reference. Only the reference changes: the generation, its quota
    count and its (always illustrative) authority stay as they were. Idempotent."""
    await _owned_concept(session, actor, project_id, design_id)
    removed = await session.execute(
        update(DesignReference)
        .where(DesignReference.generation_id == design_id, DesignReference.removed_at.is_(None))
        .values(removed_at=func.now(), removed_by=actor.user_id)
        .returning(DesignReference.id)
    )
    if removed.first() is not None:
        await record(
            session, action="design.reference_removed", entity_type="design_generation",
            entity_id=design_id, project_id=project_id, actor_type=ActorType.USER,
            actor_user_id=actor.user_id, session_id=actor.session_id,
        )  # fmt: skip


async def concepts_of_project(
    session: AsyncSession, project_id: uuid.UUID, generation_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """Which of `generation_ids` are this project's AI concepts. Slice 3.5 names them on a design
    request as illustrative references only; they never become drawings."""
    if not generation_ids:
        return set()
    rows = await session.scalars(
        select(DesignGeneration.id).where(
            DesignGeneration.project_id == project_id, DesignGeneration.id.in_(generation_ids)
        )
    )
    return set(rows)
