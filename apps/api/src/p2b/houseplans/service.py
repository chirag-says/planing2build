"""Concept floor plan generation (Checkpoint 1; PD-28, ADR-025).

Request path (API, one transaction): the owner asks for a plan. The server checks the feature is
on, the caller owns the project and the project's requirement is submitted and not under
revision; it serialises on the project (advisory lock + a unique index on in-flight rows), loads
the usable ruleset, and normalises the requirement plus any provisional design inputs into an
ArchitecturalIntent. Missing facts, unsupported cases and conflicts are refused before anything
is written. It records the plan QUEUED and publishes `houseplan.generation_requested`.

Job path (worker, queue `engine`, one at a time): QUEUED → RUNNING → VALID (the validator passed),
INFEASIBLE (with reasons), or FAILED (engine fault, including a plan its own validator rejects,
which is never stored as a document). Its own lifecycle, not Slice 3.1's (CP1-04). No quota and no
credit in Checkpoint 1 (CP1-07)."""

import asyncio
import hashlib
import json
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.audit.interface import record
from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.errors import (
    DesignInputRequired,
    Forbidden,
    GenerationInProgress,
    NotFound,
    PlanEditInvalid,
    PlanOperationRejected,
    PlanUnsupported,
    RevisionConflict,
    StateConflict,
    ValidationFailed,
)
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import (
    ActorType,
    MembershipRole,
    PlanFailureReason,
    PlanGenerationState,
    PlanOpReason,
    PlanValidity,
    ProjectStatus,
    SolverKind,
)
from p2b.houseplans.engine import (
    ArchitecturalIntent,
    DesignInputs,
    DeterministicMVPLayoutSolver,
    HousePlan,
    InputConflict,
    LayoutSolver,
    NeedsInput,
    Normalised,
    RulesetContent,
    Unsupported,
    ZonedLocalSearchSolver,
    fixture_fit,
    generate,
    normalise,
    sha256_of,
)
from p2b.houseplans.engine.edit import BatchRejected, edit
from p2b.houseplans.engine.model import dump
from p2b.houseplans.engine.ops import PlanOp
from p2b.houseplans.models import HousePlanOp, HousePlanRecord, HousePlanVersion
from p2b.houseplans.rulesets import LoadedRuleset, load_ruleset, load_ruleset_by_id
from p2b.identity.interface import Actor
from p2b.projects.interface import design_basis

log = structlog.get_logger(__name__)

S = PlanGenerationState
GENERATION = TransitionTable[PlanGenerationState](
    "house_plan_generation",
    [
        Transition(None, S.QUEUED, "request"),
        Transition(S.QUEUED, S.RUNNING, "start"),
        Transition(S.RUNNING, S.VALID, "succeed"),
        Transition(S.RUNNING, S.INFEASIBLE, "infeasible"),
        Transition(S.RUNNING, S.FAILED, "fail"),
        Transition(S.QUEUED, S.FAILED, "expire"),
        Transition(S.RUNNING, S.FAILED, "expire"),
    ],
)
IN_FLIGHT = (S.QUEUED.value, S.RUNNING.value)
# A plan is laid out from the requirement as submitted: never from a draft, never while it is
# being revised after a request for information, never for a closed project. Defined here, for
# this module, rather than borrowed from Slice 3.1 (CP1-04).
P = ProjectStatus
ELIGIBLE_STATUSES = frozenset(
    s.value
    for s in (
        P.SUBMITTED,
        P.ACCEPTED,
        P.PLANNING,
        P.PLAN_ISSUED,
        P.SOURCING,
        P.CONTRACTED,
        P.BUILDING,
        P.HANDOVER_PENDING,
        P.COMPLETED,
    )
)


class GenerationRequested(EventPayload):
    plan_id: uuid.UUID
    project_id: uuid.UUID


class GenerationFinished(EventPayload):
    plan_id: uuid.UUID
    project_id: uuid.UUID
    state: PlanGenerationState


def _stale_seconds(settings: Settings) -> float:
    return settings.houseplans_solve_timeout_seconds * 3 + 600


def seed_for(project_id: uuid.UUID, sequence: int) -> int:
    return int(hashlib.sha256(f"{project_id}:{sequence}".encode()).hexdigest()[:12], 16)


def require_enabled(settings: Settings) -> None:
    if not settings.houseplans_enabled:
        raise NotFound


async def _expire_stale(session: AsyncSession, settings: Settings, project_id: uuid.UUID) -> None:
    """In-flight rows far past any possible finish (a lost worker) must not block the project."""
    await session.execute(
        update(HousePlanRecord)
        .where(
            HousePlanRecord.project_id == project_id,
            HousePlanRecord.state.in_(IN_FLIGHT),
            HousePlanRecord.created_at
            < func.now() - func.make_interval(0, 0, 0, 0, 0, 0, _stale_seconds(settings)),
        )
        .values(
            state=S.FAILED.value,
            failure_reason=PlanFailureReason.STALE.value,
            completed_at=func.now(),
            version=HousePlanRecord.version + 1,
        )
    )


def _normalised(
    answers: Mapping[str, Any],
    inputs: DesignInputs | None,
    ruleset: LoadedRuleset,
    *,
    question_set_version: int,
    requirement_version: int,
) -> ArchitecturalIntent:
    outcome = normalise(
        answers,
        inputs,
        ruleset.content,
        question_set_version=question_set_version,
        requirement_version=requirement_version,
        ruleset_version=ruleset.version,
        ruleset_sha256=ruleset.sha256,
    )
    if isinstance(outcome, Unsupported):
        raise PlanUnsupported(details={"reasons": [r.value for r in outcome.reasons]})
    if isinstance(outcome, InputConflict):
        raise ValidationFailed(
            details={
                "fields": {
                    "design_inputs": [
                        f"{k.value} contradicts the submitted requirement; "
                        "change the requirement instead"
                        for k in outcome.keys
                    ]
                }
            }
        )
    if isinstance(outcome, NeedsInput):
        raise DesignInputRequired(
            details={
                "missing": [{"key": m.key.value, "reason": m.reason.value} for m in outcome.missing]
            }
        )
    if not isinstance(outcome, Normalised):
        raise TypeError(f"unexpected normalisation outcome {type(outcome).__name__}")
    return outcome.intent


async def request_generation(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    project_id: uuid.UUID,
    *,
    design_inputs: DesignInputs | None,
) -> HousePlanRecord:
    require_enabled(settings)
    basis = await design_basis(session, user_id=actor.user_id, project_id=project_id)
    if basis is None:
        raise NotFound
    if basis.role != MembershipRole.OWNER:
        raise Forbidden
    if basis.status.value not in ELIGIBLE_STATUSES:
        raise StateConflict(details={"current_state": basis.status.value})
    await session.execute(
        select(func.pg_advisory_xact_lock(func.hashtext(f"houseplan-project:{project_id}")))
    )
    await _expire_stale(session, settings, project_id)
    in_flight = await session.scalar(
        select(func.count())
        .select_from(HousePlanRecord)
        .where(HousePlanRecord.project_id == project_id, HousePlanRecord.state.in_(IN_FLIGHT))
    )
    if in_flight:
        raise GenerationInProgress
    ruleset = await load_ruleset(session, settings)
    intent = _normalised(
        basis.answers,
        design_inputs,
        ruleset,
        question_set_version=basis.question_set_version,
        requirement_version=basis.requirement_version,
    )
    last = await session.scalar(
        select(func.max(HousePlanRecord.sequence)).where(HousePlanRecord.project_id == project_id)
    )
    sequence = int(last or 0) + 1
    solver = solver_for(settings.houseplans_solver, ruleset.content)
    plan = HousePlanRecord(
        id=new_id(),
        project_id=project_id,
        sequence=sequence,
        state=GENERATION.target(None, "request").value,
        design_inputs=dump(design_inputs) if design_inputs is not None else None,
        intent=dump(intent),
        intent_sha256=sha256_of(intent),
        question_set_version=basis.question_set_version,
        requirement_version=basis.requirement_version,
        ruleset_id=ruleset.id,
        ruleset_version=ruleset.version,
        engine_version=_engine_version(),
        solver=solver.kind.value,
        seed=seed_for(project_id, sequence),
        requested_by=actor.user_id,
    )
    session.add(plan)
    try:
        await session.flush()
    except IntegrityError:  # the in-flight index: a concurrent request won
        raise GenerationInProgress from None
    await session.refresh(plan)
    await record(
        session,
        action="houseplan.generation_requested",
        entity_type="house_plan",
        entity_id=plan.id,
        project_id=project_id,
        actor_type=ActorType.USER,
        actor_user_id=actor.user_id,
        session_id=actor.session_id,
        new_value={"ruleset_version": ruleset.version, "solver": plan.solver},
    )
    await publish(
        session,
        event_type="houseplan.generation_requested",
        aggregate_type="house_plan",
        aggregate_id=plan.id,
        payload=GenerationRequested(plan_id=plan.id, project_id=project_id),
        dedupe_suffix="requested",
    )
    return plan


def _engine_version() -> str:
    from p2b.houseplans.engine import ENGINE_VERSION

    return ENGINE_VERSION


@dataclass(frozen=True)
class _Outcome:
    state: PlanGenerationState
    document: dict[str, Any] | None = None
    report: dict[str, Any] | None = None
    body_sha256: str | None = None
    schema_version: str | None = None
    infeasibility: dict[str, Any] | None = None
    failure: PlanFailureReason | None = None
    detail: str | None = None


def solver_for(kind: str, content: RulesetContent) -> LayoutSolver:
    """The configured solver, or the Checkpoint 1 solver when the ruleset cannot drive the zoned
    one (no objective section). The choice is stored on the plan, and its job uses that one."""
    if kind == SolverKind.ZONED_LOCAL_SEARCH.value and content.objective is not None:
        return ZonedLocalSearchSolver(content, fixture_fit(content))
    return DeterministicMVPLayoutSolver()


def _run_engine(
    intent: ArchitecturalIntent, ruleset: LoadedRuleset, seed: int, solver: str
) -> _Outcome:
    result = generate(
        intent,
        ruleset.content,
        ruleset_version=ruleset.version,
        ruleset_sha256=ruleset.sha256,
        solver=solver_for(solver, ruleset.content),
        seed=seed,
    )
    if result.outcome == "INFEASIBLE":
        if result.feasibility is not None:
            return _Outcome(S.INFEASIBLE, infeasibility=result.feasibility.as_json())
        reasons = [
            {
                "code": r.code.value,
                "params": r.params,
                "message_key": f"houseplans.infeasible.{r.code.value.lower()}",
            }
            for r in result.reasons
        ]
        return _Outcome(S.INFEASIBLE, infeasibility={"reasons": reasons})
    if (
        result.outcome == "VALID"
        and result.plan is not None
        and result.report is not None
        and result.report.valid
    ):
        return _Outcome(
            S.VALID,
            document=dump(result.plan),
            report=dump(result.report),
            body_sha256=result.plan.meta.body_sha256,
            schema_version=result.plan.meta.schema_version,
        )
    codes = [e.code.value for e in result.report.errors] if result.report else []
    return _Outcome(
        S.FAILED,
        failure=PlanFailureReason.ENGINE_INVALID_OUTPUT,
        detail=json.dumps({"errors": codes, "topology": result.topology})[:4000],
    )


async def run_generation(
    database: Database, settings: Settings, plan_id: uuid.UUID
) -> PlanGenerationState | None:
    """The job. Idempotent: a plan already finished is left alone. Returns the end state."""
    async with database.transaction() as session:
        row = await session.get(HousePlanRecord, plan_id, with_for_update=True)
        if row is None or row.state not in IN_FLIGHT:
            return None
        if row.state == S.QUEUED.value:
            row.state = GENERATION.target(S.QUEUED, "start").value
            row.started_at = (await session.execute(select(func.now()))).scalar_one()
        row.attempts += 1
        row.version += 1
        ruleset = await load_ruleset_by_id(session, row.ruleset_id)
        intent = ArchitecturalIntent.model_validate(row.intent)
        seed, solver = row.seed, row.solver

    started = time.perf_counter()
    try:
        outcome = await asyncio.wait_for(
            asyncio.to_thread(_run_engine, intent, ruleset, seed, solver),
            timeout=settings.houseplans_solve_timeout_seconds,
        )
    except TimeoutError:
        outcome = _Outcome(
            S.FAILED, failure=PlanFailureReason.ENGINE_TIMEOUT, detail="solve budget exceeded"
        )
    except Exception as exc:  # an engine defect: recorded, alerted, never shown as a plan
        log.exception("houseplan.engine_error", plan_id=str(plan_id))
        outcome = _Outcome(
            S.FAILED, failure=PlanFailureReason.ENGINE_ERROR, detail=repr(exc)[:4000]
        )
    solve_ms = int((time.perf_counter() - started) * 1000)
    if outcome.failure == PlanFailureReason.ENGINE_INVALID_OUTPUT:
        log.error("houseplan.engine_invalid_output", plan_id=str(plan_id), detail=outcome.detail)

    async with database.transaction() as session:
        row = await session.get(HousePlanRecord, plan_id, with_for_update=True)
        if row is None or row.state != S.RUNNING.value:
            return None  # expired as stale meanwhile: keep that outcome
        trigger = {S.VALID: "succeed", S.INFEASIBLE: "infeasible", S.FAILED: "fail"}[outcome.state]
        target = GENERATION.target(S.RUNNING, trigger).value
        # Read the clock before touching the row: the CHECKs tie the state to its document,
        # reasons or failure, so every column changes in one flush.
        now = (await session.execute(select(func.now()))).scalar_one()
        row.state, row.completed_at = target, now
        row.solve_ms = solve_ms
        row.version += 1
        if outcome.state == S.VALID:
            row.head_document, row.head_report = outcome.document, outcome.report
            row.head_validity, row.head_revision_no = PlanValidity.VALID.value, 0
            session.add(
                HousePlanVersion(
                    id=new_id(),
                    plan_id=row.id,
                    version_no=1,
                    name="Generated",
                    revision_no=0,
                    schema_version=outcome.schema_version or "",
                    document=outcome.document or {},
                    content_sha256=outcome.body_sha256 or "",
                    validity=PlanValidity.VALID.value,
                    report=outcome.report or {},
                    created_by=None,
                )
            )
        elif outcome.state == S.INFEASIBLE:
            row.infeasibility = outcome.infeasibility
        else:
            row.failure_reason = (outcome.failure or PlanFailureReason.ENGINE_ERROR).value
            row.failure_detail = outcome.detail
        await session.flush()
        await record(
            session,
            action=f"houseplan.generation_{outcome.state.value.lower()}",
            entity_type="house_plan",
            entity_id=row.id,
            project_id=row.project_id,
            actor_type=ActorType.JOB,
            new_value={"solve_ms": solve_ms, "failure_reason": row.failure_reason},
        )
        await publish(
            session,
            event_type="houseplan.generation_finished",
            aggregate_type="house_plan",
            aggregate_id=row.id,
            payload=GenerationFinished(
                plan_id=row.id, project_id=row.project_id, state=outcome.state
            ),
            dedupe_suffix="finished",
        )
        return outcome.state


# ---------- reads ----------


@dataclass(frozen=True)
class PlanView:
    row: HousePlanRecord
    ruleset: LoadedRuleset
    # the caller owns the project and the plan has a document to edit (AD-12). The API decides
    # it; the web app only shows or hides the editing tools accordingly.
    can_edit: bool = False


async def _member(
    session: AsyncSession, settings: Settings, actor: Actor, project_id: uuid.UUID
) -> MembershipRole:
    require_enabled(settings)
    basis = await design_basis(session, user_id=actor.user_id, project_id=project_id)
    if basis is None:
        raise NotFound
    return basis.role


async def _views(session: AsyncSession, rows: list[HousePlanRecord]) -> list[PlanView]:
    cache: dict[uuid.UUID, LoadedRuleset] = {}
    out = []
    for row in rows:
        if row.ruleset_id not in cache:
            cache[row.ruleset_id] = await load_ruleset_by_id(session, row.ruleset_id)
        out.append(PlanView(row, cache[row.ruleset_id]))
    return out


async def list_plans(
    session: AsyncSession, settings: Settings, actor: Actor, project_id: uuid.UUID
) -> list[PlanView]:
    await _member(session, settings, actor, project_id)
    return await list_for_project(session, project_id)


async def list_for_project(session: AsyncSession, project_id: uuid.UUID) -> list[PlanView]:
    rows = (
        await session.scalars(
            select(HousePlanRecord)
            .where(HousePlanRecord.project_id == project_id)
            .order_by(HousePlanRecord.sequence.desc())
        )
    ).all()
    return await _views(session, list(rows))


async def get_plan(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> PlanView:
    role = await _member(session, settings, actor, project_id)
    row = await session.get(HousePlanRecord, plan_id)
    if row is None or row.project_id != project_id:
        raise NotFound
    view = (await _views(session, [row]))[0]
    editable = role == MembershipRole.OWNER and row.head_document is not None
    return PlanView(view.row, view.ruleset, can_edit=editable)


async def get_any(session: AsyncSession, settings: Settings, plan_id: uuid.UUID) -> PlanView:
    require_enabled(settings)
    row = await session.get(HousePlanRecord, plan_id)
    if row is None:
        raise NotFound
    return (await _views(session, [row]))[0]


def document_of(view: PlanView) -> HousePlan | None:
    return HousePlan.model_validate(view.row.head_document) if view.row.head_document else None


# ---------- edits (Checkpoint 3) ----------


async def apply_operations(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    *,
    expected_revision: int,
    ops: list[PlanOp],
) -> tuple[PlanView, tuple[PlanOp, ...]]:
    """Applies one operation batch to the plan's head as the owner (AD-12) and returns the new
    view with the batch that undoes it.

    The batch applies whole or not at all, then the soft terms are re-measured and the
    independent validator judges the result with the plan's own intent and ruleset. Only a
    result with no errors is stored (IC 18.7): the head is overwritten under the row lock and
    `expected_revision`, and the batch is appended to `house_plan_ops`. 404 for a non-member or
    an unknown plan, 403 for a member who is not the owner, 409 STATE_CONFLICT for a plan with no
    document, 409 REVISION_CONFLICT for a stale revision, 422 PLAN_OPERATION_REJECTED for an
    operation that cannot apply, 422 PLAN_EDIT_INVALID with the report for a result the
    validator rejects."""
    role = await _member(session, settings, actor, project_id)
    if role != MembershipRole.OWNER:
        raise Forbidden
    row = await session.get(HousePlanRecord, plan_id, with_for_update=True)
    if row is None or row.project_id != project_id:
        raise NotFound
    if row.state != S.VALID.value or row.head_document is None:
        raise StateConflict(details={"current_state": row.state})
    if row.head_revision_no != expected_revision:
        raise RevisionConflict(details={"current_revision": row.head_revision_no})
    ruleset = await load_ruleset_by_id(session, row.ruleset_id)
    try:
        result = edit(
            HousePlan.model_validate(row.head_document),
            ops,
            ruleset.content,
            intent=ArchitecturalIntent.model_validate(row.intent),
            ruleset_version=ruleset.version,
            ruleset_sha256=ruleset.sha256,
        )
    except BatchRejected as rejected:
        raise PlanOperationRejected(
            details={
                "index": rejected.index,
                "op": rejected.rejected.op.value,
                "code": rejected.rejected.code.value,
            }
        ) from None
    if not result.report.valid:
        raise PlanEditInvalid(details={"report": dump(result.report)})
    row.head_document, row.head_report = dump(result.plan), dump(result.report)
    row.head_revision_no += 1
    row.version += 1
    session.add(
        HousePlanOp(
            id=new_id(),
            plan_id=row.id,
            revision_no=row.head_revision_no,
            ops=[dump(o) for o in ops],
            inverse=[dump(o) for o in result.inverse],
            reason=PlanOpReason.USER.value,
            content_sha256=result.plan.meta.body_sha256 or "",
            actor_id=actor.user_id,
        )
    )
    await session.flush()
    log.info(
        "houseplan.edited",
        plan_id=str(row.id),
        revision=row.head_revision_no,
        ops=[o.op.value for o in ops],
    )
    return PlanView(row, ruleset, can_edit=True), result.inverse
