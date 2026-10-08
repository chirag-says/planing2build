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
    PlanHistoryUnavailable,
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
    PlanOpRejection,
    PlanSource,
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
from p2b.houseplans.engine.edit import BatchRejected, apply_edit, edit
from p2b.houseplans.engine.model import dump
from p2b.houseplans.engine.ops import (
    PLAN_OP,
    REVERTS,
    PlanOp,
    RevertToRevision,
    RevertToVersion,
)
from p2b.houseplans.engine.validate import validate
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
    assistant: bool = False  # Checkpoint 4: the owner may ask the AI assistant


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
    return PlanView(
        view.row, view.ruleset, can_edit=editable, assistant=editable and assistant_on(settings)
    )


def assistant_on(settings: Settings) -> bool:
    return settings.houseplans_ai_enabled and settings.ai_text_provider != "none"


async def get_any(session: AsyncSession, settings: Settings, plan_id: uuid.UUID) -> PlanView:
    require_enabled(settings)
    row = await session.get(HousePlanRecord, plan_id)
    if row is None:
        raise NotFound
    return (await _views(session, [row]))[0]


def document_of(view: PlanView) -> HousePlan | None:
    return HousePlan.model_validate(view.row.head_document) if view.row.head_document else None


# ---------- edits (Checkpoint 3, 3.1) ----------

MAX_VERSIONS = 100  # named versions per plan
# Logged batches a restore may replay from the nearest named version: about 3.5 ms each on the
# development machine, so a few seconds at most in a worker thread (Checkpoint 3.1 report).
MAX_REPLAY = 1000


async def _owned_plan(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    expected_revision: int,
) -> HousePlanRecord:
    """The plan row, locked, for a change by its owner at the revision the editor saw (AD-12).
    404 for a non-member or an unknown plan, 403 for a member who is not the owner, 409
    STATE_CONFLICT for a plan with no document, 409 REVISION_CONFLICT for a stale revision. The
    role and the revision are the server's own; nothing the client says about them is trusted."""
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
    return row


def _rejected(
    index: int, op: PlanOp, code: PlanOpRejection, entities: tuple[str, ...] = ()
) -> PlanOperationRejected:
    return PlanOperationRejected(
        details={"index": index, "op": op.op.value, "code": code.value, "entities": list(entities)}
    )


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
    `expected_revision`, and the batch is appended to `house_plan_ops`.

    A REVERT_TO_REVISION or REVERT_TO_VERSION (Checkpoint 3.1) must be alone in its batch. It
    makes the head what that revision or named version held, as a new revision: the revision is
    rebuilt from the nearest snapshot and the log (`revision_state`), nothing in the history
    changes, and the restore is audited.

    Errors: those of `_owned_plan`; 422 PLAN_OPERATION_REJECTED for an operation that cannot
    apply (`details`: index, op, code, entities); 422 PLAN_EDIT_INVALID with the report for a
    result the validator rejects; 409 PLAN_HISTORY_UNAVAILABLE when a revision cannot be rebuilt
    exactly."""
    row = await _owned_plan(session, settings, actor, project_id, plan_id, expected_revision)
    ruleset = await load_ruleset_by_id(session, row.ruleset_id)
    intent = ArchitecturalIntent.model_validate(row.intent)
    head = HousePlan.model_validate(row.head_document)
    reverts = [i for i, o in enumerate(ops) if isinstance(o, REVERTS)]
    if reverts and len(ops) > 1:
        raise _rejected(reverts[0], ops[reverts[0]], PlanOpRejection.REVERT_NOT_ALONE)
    inverse: tuple[PlanOp, ...]
    op = ops[0]
    if isinstance(op, RevertToRevision | RevertToVersion):
        plan = await _restored(session, row, head, op, ruleset.content)
        report = validate(
            plan,
            ruleset.content,
            intent=intent,
            ruleset_version=ruleset.version,
            ruleset_sha256=ruleset.sha256,
        )
        inverse = (RevertToRevision(revision=row.head_revision_no),)
        reason = PlanOpReason.REVERT
    else:
        try:
            result = edit(
                head,
                ops,
                ruleset.content,
                intent=intent,
                ruleset_version=ruleset.version,
                ruleset_sha256=ruleset.sha256,
            )
        except BatchRejected as rejected:
            raise _rejected(
                rejected.index,
                ops[rejected.index],
                rejected.rejected.code,
                rejected.rejected.entities,
            ) from None
        plan, report, inverse = result.plan, result.report, result.inverse
        reason = PlanOpReason.USER
    if not report.valid:
        raise PlanEditInvalid(details={"report": dump(report)})
    row.head_document, row.head_report = dump(plan), dump(report)
    row.head_revision_no += 1
    row.version += 1
    session.add(
        HousePlanOp(
            id=new_id(),
            plan_id=row.id,
            revision_no=row.head_revision_no,
            ops=[dump(o) for o in ops],
            inverse=[dump(o) for o in inverse],
            reason=reason.value,
            content_sha256=plan.meta.body_sha256 or "",
            actor_id=actor.user_id,
        )
    )
    if reverts:
        await record(
            session,
            action="houseplan.restored",
            entity_type="house_plan",
            entity_id=row.id,
            project_id=row.project_id,
            actor_type=ActorType.USER,
            actor_user_id=actor.user_id,
            session_id=actor.session_id,
            old_value={"revision_no": row.head_revision_no - 1},
            new_value={"revision_no": row.head_revision_no, "restored": dump(ops[0])},
        )
    await session.flush()
    log.info(
        "houseplan.edited",
        plan_id=str(row.id),
        revision=row.head_revision_no,
        ops=[o.op.value for o in ops],
    )
    return PlanView(row, ruleset, can_edit=True, assistant=assistant_on(settings)), inverse


async def _restored(
    session: AsyncSession,
    row: HousePlanRecord,
    head: HousePlan,
    op: RevertToRevision | RevertToVersion,
    content: RulesetContent,
) -> HousePlan:
    """The head with the body of the revision or version `op` names, as revision head + 1. The
    version is looked up within this plan only."""
    if isinstance(op, RevertToVersion):
        version = await session.scalar(
            select(HousePlanVersion).where(
                HousePlanVersion.plan_id == row.id, HousePlanVersion.version_no == op.version
            )
        )
        if version is None:
            raise _rejected(0, op, PlanOpRejection.UNKNOWN_REVISION)
        target = _snapshot(version)
    else:
        if op.revision > row.head_revision_no:
            raise _rejected(0, op, PlanOpRejection.UNKNOWN_REVISION)
        if op.revision == row.head_revision_no:
            raise _rejected(0, op, PlanOpRejection.NO_MOVEMENT)
        target = await revision_state(session, row.id, op.revision, content)
    meta = head.meta.model_copy(
        update={
            "revision_no": row.head_revision_no + 1,
            "source": PlanSource.EDITED,
            "body_sha256": sha256_of(target.body()),
        }
    )
    return target.model_copy(update={"meta": meta})


def _snapshot(version: HousePlanVersion) -> HousePlan:
    plan = HousePlan.model_validate(version.document)
    if sha256_of(plan.body()) != version.content_sha256:
        raise PlanHistoryUnavailable(details={"version_no": version.version_no})
    return plan.model_copy(
        update={"meta": plan.meta.model_copy(update={"revision_no": version.revision_no})}
    )


async def revision_state(
    session: AsyncSession, plan_id: uuid.UUID, revision: int, content: RulesetContent
) -> HousePlan:
    """The plan as it was at `revision`, rebuilt from the latest named version at or before it
    and the operation log: each logged batch is applied again exactly as `edit` applied it (a
    restore row takes the state it restored), and every step must reproduce the body hash the
    log recorded. Raises PlanHistoryUnavailable when one does not (the engine that wrote the log
    behaved differently), rather than restore something that never existed, and when more than
    MAX_REPLAY batches lie between the revision and its nearest named version. The replay is
    pure computation and runs in a worker thread, so it never blocks the event loop."""
    snapshots = (
        await session.execute(
            select(HousePlanVersion.revision_no, HousePlanVersion.version_no)
            .where(HousePlanVersion.plan_id == plan_id, HousePlanVersion.revision_no <= revision)
            .order_by(HousePlanVersion.revision_no, HousePlanVersion.version_no)
        )
    ).all()
    rows = [
        _Logged(r.revision_no, r.ops, r.content_sha256)
        for r in (
            await session.execute(
                select(HousePlanOp.revision_no, HousePlanOp.ops, HousePlanOp.content_sha256)
                .where(HousePlanOp.plan_id == plan_id, HousePlanOp.revision_no <= revision)
                .order_by(HousePlanOp.revision_no)
            )
        ).all()
    ]
    restores = {
        r.revision_no: op
        for r in rows
        if len(r.ops) == 1
        and isinstance(op := PLAN_OP.validate_python(r.ops[0]), RevertToRevision | RevertToVersion)
    }
    # start from the latest snapshot that no later restore reaches back past
    need = {revision}
    while True:
        start = max(rev for rev, _ in snapshots if rev <= min(need))
        need |= {
            op.revision
            for rev, op in restores.items()
            if rev > start and isinstance(op, RevertToRevision)
        }
        if min(need) >= start:
            break
    replayed = [r for r in rows if r.revision_no > start]
    if len(replayed) > MAX_REPLAY:
        raise PlanHistoryUnavailable(
            details={"revision_no": revision, "reason": "TOO_FAR", "limit": MAX_REPLAY}
        )
    first = max(v for rev, v in snapshots if rev == start)
    wanted = {first} | {
        op.version
        for rev, op in restores.items()
        if rev > start and isinstance(op, RevertToVersion)
    }
    documents = {
        v.version_no: _Snapshot(v.version_no, v.revision_no, v.document, v.content_sha256)
        for v in (
            await session.scalars(
                select(HousePlanVersion).where(
                    HousePlanVersion.plan_id == plan_id, HousePlanVersion.version_no.in_(wanted)
                )
            )
        ).all()
    }
    return await asyncio.to_thread(
        _replay, documents, first, start, replayed, restores, need, content
    )


@dataclass(frozen=True)
class _Logged:
    revision_no: int
    ops: list[dict[str, Any]]
    content_sha256: str


@dataclass(frozen=True)
class _Snapshot:
    version_no: int
    revision_no: int
    document: dict[str, Any]
    content_sha256: str


def _replay(
    documents: dict[int, _Snapshot],
    first: int,
    start: int,
    rows: list[_Logged],
    restores: dict[int, RevertToRevision | RevertToVersion],
    need: set[int],
    content: RulesetContent,
) -> HousePlan:
    def snapshot(version_no: int) -> HousePlan:
        found = documents.get(version_no)
        if found is None:
            raise KeyError(version_no)
        plan = HousePlan.model_validate(found.document)
        if sha256_of(plan.body()) != found.content_sha256:
            raise PlanHistoryUnavailable(details={"version_no": version_no})
        return plan.model_copy(
            update={"meta": plan.meta.model_copy(update={"revision_no": found.revision_no})}
        )

    state = snapshot(first)
    kept = {start: state}
    for r in rows:
        restore = restores.get(r.revision_no)
        try:
            if isinstance(restore, RevertToRevision):
                state = kept[restore.revision]
            elif isinstance(restore, RevertToVersion):
                state = snapshot(restore.version)
            else:
                state, _ = apply_edit(state, [PLAN_OP.validate_python(o) for o in r.ops], content)
        except (BatchRejected, KeyError, ValueError):
            raise PlanHistoryUnavailable(details={"revision_no": r.revision_no}) from None
        if sha256_of(state.body()) != r.content_sha256:
            raise PlanHistoryUnavailable(details={"revision_no": r.revision_no})
        state = state.model_copy(
            update={"meta": state.meta.model_copy(update={"revision_no": r.revision_no})}
        )
        if r.revision_no in need:
            kept[r.revision_no] = state
    return state


# ---------- history (Checkpoint 3.1) ----------


async def _readable_plan(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> HousePlanRecord:
    await _member(session, settings, actor, project_id)
    row = await session.get(HousePlanRecord, plan_id)
    if row is None or row.project_id != project_id:
        raise NotFound
    return row


async def list_versions(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> list[HousePlanVersion]:
    """The plan's named versions, oldest first (members read them; AD-12)."""
    row = await _readable_plan(session, settings, actor, project_id, plan_id)
    return list(
        (
            await session.scalars(
                select(HousePlanVersion)
                .where(HousePlanVersion.plan_id == row.id)
                .order_by(HousePlanVersion.version_no)
            )
        ).all()
    )


async def save_version(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    *,
    name: str,
    expected_revision: int,
) -> HousePlanVersion:
    """Keeps the head as a named, immutable version (owner only). The snapshot is the server's
    head under the row lock at the revision the editor saw, never a document from the client.
    409 STATE_CONFLICT once the plan has MAX_VERSIONS versions."""
    row = await _owned_plan(session, settings, actor, project_id, plan_id, expected_revision)
    count, last = (
        await session.execute(
            select(func.count(), func.max(HousePlanVersion.version_no)).where(
                HousePlanVersion.plan_id == row.id
            )
        )
    ).one()
    if count >= MAX_VERSIONS:
        raise StateConflict(details={"reason": "VERSION_LIMIT", "limit": MAX_VERSIONS})
    head = HousePlan.model_validate(row.head_document)
    version = HousePlanVersion(
        id=new_id(),
        plan_id=row.id,
        version_no=(last or 0) + 1,
        name=name,
        revision_no=row.head_revision_no,
        schema_version=head.meta.schema_version,
        document=row.head_document,
        content_sha256=sha256_of(head.body()),
        validity=row.head_validity or PlanValidity.VALID.value,
        report=row.head_report or {},
        created_by=actor.user_id,
    )
    session.add(version)
    await record(
        session,
        action="houseplan.version_saved",
        entity_type="house_plan",
        entity_id=row.id,
        project_id=row.project_id,
        actor_type=ActorType.USER,
        actor_user_id=actor.user_id,
        session_id=actor.session_id,
        new_value={"version_no": version.version_no, "revision_no": version.revision_no},
    )
    await session.flush()
    return version


async def list_revisions(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    *,
    before: int | None,
    limit: int,
) -> tuple[HousePlanRecord, list[HousePlanOp]]:
    """The newest `limit` logged revisions below `before`, newest first (members read them)."""
    row = await _readable_plan(session, settings, actor, project_id, plan_id)
    query = select(HousePlanOp).where(HousePlanOp.plan_id == row.id)
    if before is not None:
        query = query.where(HousePlanOp.revision_no < before)
    ops = (await session.scalars(query.order_by(HousePlanOp.revision_no.desc()).limit(limit))).all()
    return row, list(ops)
