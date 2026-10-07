"""AI-assisted design interpretation for concept floor plans (Checkpoint 4).

    homeowner's words -> language model (structured intent only) -> deterministic compiler
    -> proposed typed operations, validated as a preview -> the owner confirms -> /ops applies
    and validates again -> stored or refused

The model never sees or returns coordinates and never changes a plan: it answers in a closed
schema (`engine.assist`), the engine compiles the intent into the first candidate batch that
the validator passes, and nothing is stored until the owner applies the proposal through the
operations route like any other edit. When no candidate passes, the refusal reasons go back to
the model for a different reading, at most `ai_text_max_repairs` times, then the assistant says
it could not make the change. The feature is off unless `houseplans_ai_enabled` is set.

Privacy: the request text is sent to the provider with the plan summary (room ids, names,
types, sizes, open-area kinds); it is not stored or logged. Logs carry the provider, model,
outcome, attempts, timing and token counts with a correlation id."""

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal

import structlog
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.core.ai_text import TextProvider, TextProviderError, TextRequest, TextResult
from p2b.core.config import Settings
from p2b.core.errors import (
    Forbidden,
    NotFound,
    ProviderUnavailable,
    RevisionConflict,
    StateConflict,
)
from p2b.core.vocabulary import MembershipRole
from p2b.houseplans.engine import ArchitecturalIntent, HousePlan, RulesetContent
from p2b.houseplans.engine.assist import (
    EditInterpretation,
    OpeningChange,
    Proposal,
    RequirementBridge,
    RequirementIntent,
    RoomChange,
    compile_edit,
    describe,
    plan_summary,
    requirement_answers,
)
from p2b.houseplans.engine.ops import PlanOp
from p2b.houseplans.models import HousePlanRecord
from p2b.houseplans.rulesets import load_ruleset_by_id
from p2b.houseplans.service import S, _member, require_enabled
from p2b.identity.interface import Actor
from p2b.projects.interface import design_basis

log = structlog.get_logger(__name__)

MAX_TEXT = 400

ROLE = (
    "You are an assistant that interprets what a homeowner asks for in their concept floor "
    "plan. You are not an architect, structural engineer, approval authority or Vastu authority, "
    "and you never claim to be. "
)
EDIT_SYSTEM = ROLE + (
    "Answer with exactly one intent in the JSON schema. Name rooms only by the ids in the plan "
    "summary. Never give coordinates, millimetres, shapes or walls: the plan's engine decides "
    "all geometry and its rules decide what is allowed. Use UNSUPPORTED with a topic for "
    "another floor, curved or free shapes, structural engineering, permits or approvals, Vastu "
    "certification, a privacy redesign, images or 3D, or a room type the summary does not list. "
    "Use CLARIFY with one short question when the room or the change is not clear. When "
    "previous_failure is given, the last reading could not be applied for those reasons: give a "
    "smaller or different reading of the same request, or CLARIFY."
)
REQUIREMENT_SYSTEM = ROLE + (
    "Turn the homeowner's description of the home into the JSON schema. Fill only what they "
    "said; leave everything else empty and never guess sizes, setbacks or facing. Put questions "
    "you need answered in clarifications, and anything outside a single-storey concept plan "
    "(another floor, structural engineering, permits, Vastu certification, images or 3D) in "
    "unsupported."
)


@dataclass(frozen=True)
class Call:
    provider: str
    model: str
    request_id: str
    duration_ms: int
    attempts: int  # model calls made, including repairs
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class EditOutcome:
    status: Literal["PROPOSED", "UNSUPPORTED", "CLARIFY", "FAILED"]
    intent: dict[str, Any] | None
    ops: tuple[PlanOp, ...]
    plan: HousePlan | None  # the proposed plan (validated), for the preview drawing
    rooms: list[RoomChange]
    openings: list[OpeningChange]
    detail: str | None  # the unsupported topic, the question, or why it failed
    expected_revision: int
    call: Call


@dataclass(frozen=True)
class RequirementOutcome:
    status: Literal["INTERPRETED", "FAILED"]
    intent: RequirementIntent | None
    bridge: RequirementBridge | None
    conflicts: list[dict[str, Any]]  # where the words differ from the submitted requirement
    call: Call


def _enabled(settings: Settings, provider: TextProvider) -> None:
    require_enabled(settings)
    if not settings.houseplans_ai_enabled:
        raise NotFound
    if not provider.configured:
        raise ProviderUnavailable


def _schema(model: Any) -> dict[str, Any]:
    return model.model_json_schema()  # type: ignore[no-any-return]


class _Meter:
    def __init__(self, provider: TextProvider, request_id: str):
        self.provider, self.request_id = provider, request_id
        self.started = time.monotonic()
        self.calls = self.tokens_in = self.tokens_out = 0

    async def ask(
        self, task: str, system: str, user: dict[str, Any], schema: dict[str, Any]
    ) -> TextResult:
        self.calls += 1
        result = await self.provider.structured(
            TextRequest(
                task=task,
                system=system,
                user=json.dumps(user, separators=(",", ":"), ensure_ascii=False),
                schema=schema,
                request_id=self.request_id,
            )
        )
        if result.usage is not None:
            self.tokens_in += result.usage.input_tokens or 0
            self.tokens_out += result.usage.output_tokens or 0
        return result

    def done(self) -> Call:
        return Call(
            provider=self.provider.name,
            model=self.provider.model,
            request_id=self.request_id,
            duration_ms=int((time.monotonic() - self.started) * 1000),
            attempts=self.calls,
            input_tokens=self.tokens_in,
            output_tokens=self.tokens_out,
        )


async def propose_edit(
    session: AsyncSession,
    settings: Settings,
    provider: TextProvider,
    actor: Actor,
    project_id: uuid.UUID,
    plan_id: uuid.UUID,
    *,
    text: str,
    expected_revision: int,
) -> EditOutcome:
    """A proposal for one sentence, as typed operations validated against the plan's head. Owner
    only (AD-12); nothing is stored. 404 when the feature is off or for a non-member, 403 for a
    member who is not the owner, 409 for a plan without a document or a stale revision, 503
    when no model is configured."""
    _enabled(settings, provider)
    role = await _member(session, settings, actor, project_id)
    if role != MembershipRole.OWNER:
        raise Forbidden
    row = await session.get(HousePlanRecord, plan_id)
    if row is None or row.project_id != project_id:
        raise NotFound
    if row.state != S.VALID.value or row.head_document is None:
        raise StateConflict(details={"current_state": row.state})
    if row.head_revision_no != expected_revision:
        raise RevisionConflict(details={"current_revision": row.head_revision_no})
    ruleset = await load_ruleset_by_id(session, row.ruleset_id)
    plan = HousePlan.model_validate(row.head_document)
    arch = ArchitecturalIntent.model_validate(row.intent)
    return await interpret_edit(
        provider,
        plan,
        ruleset.content,
        arch,
        text,
        max_repairs=settings.ai_text_max_repairs,
        expected_revision=expected_revision,
    )


async def interpret_edit(
    provider: TextProvider,
    plan: HousePlan,
    content: RulesetContent,
    arch: ArchitecturalIntent | None,
    text: str,
    *,
    max_repairs: int,
    expected_revision: int,
) -> EditOutcome:
    """The model's reading of one sentence, compiled; repaired at most `max_repairs` times when
    the answer is malformed or no candidate passes the rules. No I/O but the model call: the
    same path the API and the offline benchmark use."""
    summary = plan_summary(plan, content)
    meter = _Meter(provider, str(uuid.uuid4()))
    failure: str | None = None
    intent_data: dict[str, Any] | None = None
    status: Literal["PROPOSED", "UNSUPPORTED", "CLARIFY", "FAILED"] = "FAILED"
    detail: str | None = "NOTHING_VALID"
    for _ in range(1 + max_repairs):
        user: dict[str, Any] = {"plan": summary, "request": text[:MAX_TEXT]}
        if failure:
            user["previous_failure"] = failure
        try:
            answer = await meter.ask("edit", EDIT_SYSTEM, user, _schema(EditInterpretation))
            interpretation = EditInterpretation.model_validate(answer.data)
        except TextProviderError as error:
            if error.kind in ("UNAVAILABLE", "TIMEOUT", "REJECTED"):
                _log(meter.done(), "edit", "UNAVAILABLE")
                raise ProviderUnavailable from None
            failure, detail = "MALFORMED_ANSWER", "MALFORMED_ANSWER"
            continue
        except ValidationError:
            failure, detail = "ANSWER_DID_NOT_MATCH_SCHEMA", "MALFORMED_ANSWER"
            continue
        intent_data = interpretation.intent.model_dump(mode="json")
        compiled = compile_edit(plan, interpretation.intent, content, arch=arch)
        if isinstance(compiled, Proposal):
            rooms, openings = describe(plan, compiled.result.plan, content)
            call = meter.done()
            _log(call, "edit", "PROPOSED")
            return EditOutcome(
                "PROPOSED",
                intent_data,
                compiled.ops,
                compiled.result.plan,
                rooms,
                openings,
                None,
                expected_revision,
                call,
            )
        if compiled.reason in ("UNSUPPORTED", "CLARIFY"):
            status = compiled.reason
            detail = compiled.detail
            break
        failure = f"{compiled.reason}:{compiled.detail}"
        detail = compiled.reason
    call = meter.done()
    _log(call, "edit", status)
    return EditOutcome(status, intent_data, (), None, [], [], detail, expected_revision, call)


async def interpret_requirement(
    session: AsyncSession,
    settings: Settings,
    provider: TextProvider,
    actor: Actor,
    project_id: uuid.UUID,
    *,
    text: str,
) -> RequirementOutcome:
    """A homeowner's description turned into requirement facts and provisional design inputs,
    compared with the project's submitted requirement (which stays the authority: differences
    are shown, never applied). Generation then runs through the existing route and solver."""
    _enabled(settings, provider)
    basis = await design_basis(session, user_id=actor.user_id, project_id=project_id)
    if basis is None:
        raise NotFound
    if basis.role != MembershipRole.OWNER:
        raise Forbidden
    meter = _Meter(provider, str(uuid.uuid4()))
    intent: RequirementIntent | None = None
    for _ in range(1 + settings.ai_text_max_repairs):
        try:
            answer = await meter.ask(
                "requirement",
                REQUIREMENT_SYSTEM,
                {"request": text[:MAX_TEXT]},
                _schema(RequirementIntent),
            )
            intent = RequirementIntent.model_validate(answer.data)
            break
        except TextProviderError as error:
            if error.kind in ("UNAVAILABLE", "TIMEOUT", "REJECTED"):
                _log(meter.done(), "requirement", "UNAVAILABLE")
                raise ProviderUnavailable from None
        except ValidationError:
            continue
    call = meter.done()
    if intent is None:
        _log(call, "requirement", "FAILED")
        return RequirementOutcome("FAILED", None, None, [], call)
    bridge = requirement_answers(intent)
    conflicts = [
        {"key": key, "requirement": basis.answers.get(key), "said": said}
        for key, said in bridge.answers.items()
        if key
        in (
            "plot_width_ft",
            "plot_depth_ft",
            "facing",
            "bedrooms",
            "bathrooms",
            "car_parking",
            "pooja_room",
        )
        and basis.answers.get(key) is not None
        and _differs(basis.answers.get(key), said)
    ]
    _log(call, "requirement", "INTERPRETED")
    return RequirementOutcome("INTERPRETED", intent, bridge, conflicts, call)


def _differs(a: Any, b: Any) -> bool:
    try:
        return float(a) != float(b)
    except (TypeError, ValueError):
        return bool(a != b)


def _log(call: Call, task: str, outcome: str) -> None:
    log.info(
        "houseplan.assistant",
        task=task,
        outcome=outcome,
        provider=call.provider,
        model=call.model,
        request_id=call.request_id,
        duration_ms=call.duration_ms,
        model_calls=call.attempts,
        input_tokens=call.input_tokens,
        output_tokens=call.output_tokens,
    )
