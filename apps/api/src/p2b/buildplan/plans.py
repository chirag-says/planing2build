"""Build Plan versions (SLICE3_5_READINESS 0.2 to 0.4).

One Build Plan per project; versions move DRAFT → IN_REVIEW → ISSUED → ACCEPTED or
CHANGES_REQUESTED, with SUPERSEDED and WITHDRAWN. Content (drawing set, values, BOQ, schedule,
scope) changes only while DRAFT; database triggers refuse any other change. Submitting stores the
content hash that sign-offs bind to; issue recomputes it, so a frozen version can never drift.

Schedule (BP-07, BP-07A deferred): durations and explicitly entered predecessors only. Nothing
here calculates a date, a decide-by date or a cash-flow figure, and nothing is inferred from the
display order of stages or from stage numbers.

Refunds (BP-09): issuing is recorded in history, audit and an event, never as a package usage
record; the substantial-work rule stays N-12."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from p2b.buildplan import signoffs
from p2b.buildplan.common import (
    Who,
    conflict,
    db_now,
    history,
    project,
    require_package,
)
from p2b.buildplan.design import classes_of, set_files
from p2b.buildplan.models import (
    BoqLine,
    BuildPlan,
    BuildPlanSpecValue,
    BuildPlanVersion,
    DrawingSet,
    ScheduleEntry,
)
from p2b.catalog.interface import active_spec_masters, item_rate_card
from p2b.construction.interface import stages_for
from p2b.core.config import Settings
from p2b.core.errors import NotFound, StateConflict, ValidationFailed
from p2b.core.ids import new_id
from p2b.core.outbox import EventPayload, publish
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import (
    BuildPlanState,
    DrawingClass,
    DrawingSetState,
    FilePurpose,
    FileState,
    PackageAvailability,
    QuantityBasis,
    RateCardStatus,
    ValueApplicability,
    ValueBasis,
)
from p2b.documents.interface import file_facts

V = BuildPlanState
VERSION = TransitionTable[BuildPlanState](
    "build_plan_version",
    [
        Transition(None, V.DRAFT, "create"),
        Transition(V.DRAFT, V.IN_REVIEW, "submit"),
        Transition(V.IN_REVIEW, V.DRAFT, "return"),
        Transition(V.IN_REVIEW, V.ISSUED, "issue"),
        Transition(V.ISSUED, V.ACCEPTED, "accept"),
        Transition(V.ISSUED, V.CHANGES_REQUESTED, "request_changes"),
        Transition(V.ISSUED, V.WITHDRAWN, "withdraw"),
        Transition(V.DRAFT, V.WITHDRAWN, "withdraw"),
        Transition(V.IN_REVIEW, V.WITHDRAWN, "withdraw"),
        Transition(V.ISSUED, V.SUPERSEDED, "supersede"),
        Transition(V.ACCEPTED, V.SUPERSEDED, "supersede"),
        Transition(V.CHANGES_REQUESTED, V.SUPERSEDED, "supersede"),
    ],
)
REQUIRED_CLASSES = (
    DrawingClass.SITE_PLAN, DrawingClass.FLOOR_PLAN, DrawingClass.ELEVATION, DrawingClass.SECTION,
)  # fmt: skip
MAX_BOQ_LINES = 3000
MAX_LIST_ITEMS = 100


class VersionEvent(EventPayload):
    """`buildplan.issued`, `buildplan.accepted`: ids only."""

    version_id: uuid.UUID
    project_id: uuid.UUID
    version_no: int


def entry_key(stage_number: int, floor: int | None) -> str:
    return f"S{stage_number:02d}" if floor is None else f"S{stage_number:02d}F{floor}"


# --- access ----------------------------------------------------------------------------------


async def plan_of(session: AsyncSession, project_id: uuid.UUID) -> BuildPlan | None:
    return (
        await session.scalars(select(BuildPlan).where(BuildPlan.project_id == project_id))
    ).one_or_none()


async def version_row(
    session: AsyncSession, version_id: uuid.UUID, *, lock: bool = False
) -> BuildPlanVersion:
    version = await session.get(BuildPlanVersion, version_id, with_for_update=lock)
    if version is None:
        raise NotFound
    return version


async def versions_of(session: AsyncSession, project_id: uuid.UUID) -> list[BuildPlanVersion]:
    return list(
        await session.scalars(
            select(BuildPlanVersion)
            .where(BuildPlanVersion.project_id == project_id)
            .order_by(BuildPlanVersion.version_no)
        )
    )


async def _draft(session: AsyncSession, version_id: uuid.UUID, who: Who) -> BuildPlanVersion:
    """A DRAFT version, locked, with the package active; the edit is recorded as the last
    one (the issuer must be someone else, BP-13)."""
    version = await version_row(session, version_id, lock=True)
    if version.state != V.DRAFT.value:
        raise StateConflict(details={"current_state": version.state})
    await require_package(session, version.project_id)
    version.last_edited_by = who.user_id
    version.last_edited_at = await db_now(session)
    version.version += 1
    return version


async def _move(
    session: AsyncSession,
    version: BuildPlanVersion,
    trigger: str,
    who: Who,
    reason: str | None = None,
) -> None:
    old = version.state
    version.state = VERSION.target(BuildPlanState(old), trigger).value
    version.version += 1
    await session.flush()
    await history(
        session, project_id=version.project_id, subject="VERSION", subject_id=version.id,
        old=old, new=version.state, who=who, reason=reason,
        detail={"version_no": version.version_no},
    )  # fmt: skip


# --- create ----------------------------------------------------------------------------------


async def create_version(
    session: AsyncSession, who: Who, project_id: uuid.UUID
) -> BuildPlanVersion:
    """A new DRAFT, carried forward from the latest version, or seeded empty: every S04 line
    without a value, every stage instance without a duration. Nothing is pre-filled with an
    invented value."""
    facts = await project(session, project_id)
    if facts.availability != PackageAvailability.ELIGIBLE:
        raise conflict("NOT_ELIGIBLE", "The project has not passed the initial review.")
    await require_package(session, project_id)
    plan = await plan_of(session, project_id)
    if plan is None:
        plan = BuildPlan(id=new_id(), project_id=project_id)
        session.add(plan)
        await session.flush()
    plan = await session.get_one(BuildPlan, plan.id, with_for_update=True)
    versions = await versions_of(session, project_id)
    if any(v.state in (V.DRAFT.value, V.IN_REVIEW.value) for v in versions):
        raise conflict("OPEN_VERSION", "A version is already being prepared.")
    latest = versions[-1] if versions else None
    drawing_set_id = None
    if latest is not None and latest.drawing_set_id is not None:
        drawing_set = await session.get_one(DrawingSet, latest.drawing_set_id)
        if drawing_set.state == DrawingSetState.APPROVED.value:
            drawing_set_id = drawing_set.id
    version = BuildPlanVersion(
        id=new_id(),
        build_plan_id=plan.id,
        project_id=project_id,
        version_no=(latest.version_no if latest else 0) + 1,
        state=VERSION.target(None, "create").value,
        created_from_id=latest.id if latest else None,
        requirement_version=facts.requirement_version,
        drawing_set_id=drawing_set_id,
        rate_card_id=latest.rate_card_id if latest else None,
        inclusions=list(latest.inclusions) if latest else [],
        exclusions=list(latest.exclusions) if latest else [],
        assumptions=list(latest.assumptions) if latest else [],
        explanation_note=None,
        created_by=who.user_id,
        last_edited_by=who.user_id,
    )
    session.add(version)
    await session.flush()
    if latest is None:
        await _seed(session, version)
    else:
        await _carry_forward(session, latest, version)
    await history(
        session, project_id=project_id, subject="VERSION", subject_id=version.id, old=None,
        new=version.state, who=who, detail={"version_no": version.version_no},
    )  # fmt: skip
    return version


async def _seed(session: AsyncSession, version: BuildPlanVersion) -> None:
    for master in await active_spec_masters(session):
        session.add(
            BuildPlanSpecValue(
                id=new_id(), version_id=version.id, project_id=version.project_id,
                line_code=master.code, master_version_id=master.version_id,
                criteria_text=master.performance_specification, is_structural=master.is_structural,
                applicability=ValueApplicability.APPLICABLE.value,
            )
        )  # fmt: skip
    for stage in await stages_for(session, version.project_id):
        session.add(
            ScheduleEntry(
                id=new_id(), version_id=version.id, project_id=version.project_id,
                entry_key=entry_key(stage.stage_number, stage.floor), stage_instance_id=stage.id,
                stage_number=stage.stage_number, floor=stage.floor,
            )
        )  # fmt: skip
    await session.flush()


async def _carry_forward(
    session: AsyncSession, source: BuildPlanVersion, version: BuildPlanVersion
) -> None:
    for value in await values_of(session, source.id):
        session.add(
            BuildPlanSpecValue(
                id=new_id(), version_id=version.id, project_id=version.project_id,
                line_code=value.line_code, master_version_id=value.master_version_id,
                criteria_text=value.criteria_text, is_structural=value.is_structural,
                applicability=value.applicability,
                not_applicable_reason=value.not_applicable_reason, value_text=value.value_text,
                basis=value.basis, source_note=value.source_note,
                evidence_file_ids=list(value.evidence_file_ids), entered_by=value.entered_by,
                entered_at=value.entered_at, carried_from_id=value.id,
            )
        )  # fmt: skip
    for line in await boq_of(session, source.id):
        session.add(
            BoqLine(
                id=new_id(), version_id=version.id, project_id=version.project_id,
                line_no=line.line_no, rate_card_id=line.rate_card_id, item_code=line.item_code,
                description=line.description, unit=line.unit, quantity=line.quantity,
                quantity_basis=line.quantity_basis, drawing_file_id=line.drawing_file_id,
                basis_note=line.basis_note, rate=line.rate, amount=line.amount,
                stage_number=line.stage_number, floor=line.floor,
                spec_line_codes=list(line.spec_line_codes), assumptions=line.assumptions,
            )
        )  # fmt: skip
    for entry in await schedule_of(session, source.id):
        session.add(
            ScheduleEntry(
                id=new_id(), version_id=version.id, project_id=version.project_id,
                entry_key=entry.entry_key, stage_instance_id=entry.stage_instance_id,
                stage_number=entry.stage_number, floor=entry.floor,
                duration_days=entry.duration_days, predecessors=list(entry.predecessors),
                note=entry.note,
            )
        )  # fmt: skip
    await session.flush()


# --- content ---------------------------------------------------------------------------------


async def values_of(session: AsyncSession, version_id: uuid.UUID) -> list[BuildPlanSpecValue]:
    return list(
        await session.scalars(
            select(BuildPlanSpecValue)
            .where(BuildPlanSpecValue.version_id == version_id)
            .order_by(BuildPlanSpecValue.line_code)
        )
    )


async def boq_of(session: AsyncSession, version_id: uuid.UUID) -> list[BoqLine]:
    return list(
        await session.scalars(
            select(BoqLine).where(BoqLine.version_id == version_id).order_by(BoqLine.line_no)
        )
    )


async def schedule_of(session: AsyncSession, version_id: uuid.UUID) -> list[ScheduleEntry]:
    return list(
        await session.scalars(
            select(ScheduleEntry)
            .where(ScheduleEntry.version_id == version_id)
            .order_by(ScheduleEntry.stage_number, ScheduleEntry.floor.nulls_first())
        )
    )


async def set_drawing_set(
    session: AsyncSession, who: Who, version_id: uuid.UUID, set_id: uuid.UUID
) -> None:
    version = await _draft(session, version_id, who)
    drawing_set = await session.get(DrawingSet, set_id)
    if drawing_set is None or drawing_set.project_id != version.project_id:
        raise NotFound
    if drawing_set.state != DrawingSetState.APPROVED.value:
        raise conflict("SET_NOT_APPROVED", "Only an approved drawing set can be used.")
    version.drawing_set_id = drawing_set.id
    await session.flush()


@dataclass(frozen=True)
class ValueInput:
    code: str
    applicability: ValueApplicability
    value_text: str | None
    basis: ValueBasis | None
    source_note: str | None
    not_applicable_reason: str | None
    evidence_file_ids: list[uuid.UUID]


async def set_values(
    session: AsyncSession, who: Who, version_id: uuid.UUID, inputs: list[ValueInput]
) -> None:
    """PD-14: the advisor supplies project values; the criteria stay the master's."""
    version = await _draft(session, version_id, who)
    rows = {v.line_code: v for v in await values_of(session, version_id)}
    evidence = {e for item in inputs for e in item.evidence_file_ids}
    facts = await file_facts(session, list(evidence))
    for e in evidence:
        f = facts.get(e)
        if (
            f is None
            or f.project_id != version.project_id
            or f.purpose != FilePurpose.BUILD_PLAN_EVIDENCE
            or f.state != FileState.AVAILABLE
        ):
            raise ValidationFailed(details={"fields": {"evidence_file_ids": ["Unknown file."]}})
    now = await db_now(session)
    for item in inputs:
        row = rows.get(item.code)
        if row is None:
            raise ValidationFailed(details={"fields": {"code": [f"Unknown line {item.code}."]}})
        if item.applicability == ValueApplicability.APPLICABLE:
            if not (item.value_text and item.value_text.strip()) or item.basis is None:
                raise ValidationFailed(
                    details={"fields": {item.code: ["A value and its basis are needed."]}}
                )
        elif not (item.not_applicable_reason and item.not_applicable_reason.strip()):
            raise ValidationFailed(details={"fields": {item.code: ["Give the reason."]}})
        applicable = item.applicability == ValueApplicability.APPLICABLE
        row.applicability = item.applicability.value
        row.value_text = item.value_text.strip() if applicable and item.value_text else None
        row.basis = item.basis.value if applicable and item.basis else None
        row.source_note = item.source_note
        row.not_applicable_reason = None if applicable else item.not_applicable_reason
        row.evidence_file_ids = list(dict.fromkeys(item.evidence_file_ids))
        row.entered_by = who.user_id
        row.entered_at = now
        row.carried_from_id = None
    await session.flush()
    await history(
        session, project_id=version.project_id, subject="VERSION", subject_id=version.id,
        old=V.DRAFT.value, new=V.DRAFT.value, who=who, reason="specification values entered",
        detail={"lines": sorted(i.code for i in inputs)},
    )  # fmt: skip


async def refresh_criteria(
    session: AsyncSession, who: Who, version_id: uuid.UUID, code: str
) -> None:
    """BP-19: a newer master version reaches a draft only when the advisor refreshes the line."""
    version = await _draft(session, version_id, who)
    master = next((m for m in await active_spec_masters(session) if m.code == code), None)
    row = next((v for v in await values_of(session, version_id) if v.line_code == code), None)
    if master is None or row is None:
        raise NotFound
    row.master_version_id = master.version_id
    row.criteria_text = master.performance_specification
    await session.flush()
    await history(
        session, project_id=version.project_id, subject="VERSION", subject_id=version.id,
        old=V.DRAFT.value, new=V.DRAFT.value, who=who, reason=f"criteria refreshed: {code}",
    )  # fmt: skip


@dataclass(frozen=True)
class BoqInput:
    item_code: str
    quantity: Decimal
    quantity_basis: QuantityBasis
    drawing_file_id: uuid.UUID | None
    basis_note: str | None
    stage_number: int | None
    floor: int | None
    spec_line_codes: list[str]
    assumptions: str | None


async def usable_card(session: AsyncSession, settings: Settings, card_id: uuid.UUID) -> Any:
    """BP-06: a PUBLISHED card; DEMO cards never in production."""
    card = await item_rate_card(session, card_id)
    if card.status != RateCardStatus.PUBLISHED:
        raise conflict("CARD_NOT_PUBLISHED", "Use a published rate card.")
    if card.is_demo and settings.env == "production":
        raise conflict("DEMO_CARD", "DEMO rates can never price a production Build Plan.")
    return card


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def set_boq(
    session: AsyncSession,
    settings: Settings,
    who: Who,
    version_id: uuid.UUID,
    card_id: uuid.UUID,
    inputs: list[BoqInput],
) -> None:
    """Replace the BOQ. Every line takes its rate, unit and description from one published card;
    amounts are computed here. Quantities measured from drawings name a file of the version's
    approved set."""
    version = await _draft(session, version_id, who)
    if len(inputs) > MAX_BOQ_LINES:
        raise ValidationFailed(details={"fields": {"lines": ["Too many lines."]}})
    card = await usable_card(session, settings, card_id)
    drawing_ids = (
        {f.id for f in await set_files(session, version.drawing_set_id)}
        if version.drawing_set_id
        else set()
    )
    codes = {v.line_code for v in await values_of(session, version_id)}
    await session.execute(delete(BoqLine).where(BoqLine.version_id == version_id))
    for number, item in enumerate(inputs, start=1):
        rate_line = card.lines.get(item.item_code)
        problems = []
        if rate_line is None:
            problems.append("not on the rate card")
        if item.quantity <= 0:
            problems.append("quantity must be positive")
        if item.quantity_basis == QuantityBasis.MEASURED_FROM_DRAWING and (
            item.drawing_file_id not in drawing_ids
        ):
            problems.append("name a drawing of the version's approved set")
        if item.quantity_basis == QuantityBasis.ADVISOR_ESTIMATE and not (
            item.basis_note and item.basis_note.strip()
        ):
            problems.append("an advisor estimate needs a reason")
        if item.stage_number is not None and not 1 <= item.stage_number <= 16:
            problems.append("stage must be 1 to 16")
        if set(item.spec_line_codes) - codes:
            problems.append("unknown specification line")
        if problems:
            raise ValidationFailed(details={"fields": {f"line {number}": problems}})
        assert rate_line is not None  # noqa: S101 (checked above)
        quantity = item.quantity.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        session.add(
            BoqLine(
                id=new_id(), version_id=version_id, project_id=version.project_id,
                line_no=number, rate_card_id=card.id, item_code=item.item_code,
                description=rate_line.description, unit=rate_line.unit, quantity=quantity,
                quantity_basis=item.quantity_basis.value,
                drawing_file_id=item.drawing_file_id
                if item.quantity_basis == QuantityBasis.MEASURED_FROM_DRAWING else None,
                basis_note=item.basis_note, rate=rate_line.rate,
                amount=money(quantity * rate_line.rate), stage_number=item.stage_number,
                floor=item.floor, spec_line_codes=sorted(set(item.spec_line_codes)),
                assumptions=item.assumptions,
            )
        )  # fmt: skip
    version.rate_card_id = card.id
    await session.flush()


@dataclass(frozen=True)
class ScheduleInput:
    entry_key: str
    duration_days: int | None
    predecessors: list[str]
    note: str | None


def _cycle(edges: dict[str, list[str]]) -> bool:
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        if state.get(node) == 1:
            return True
        if state.get(node) == 2:
            return False
        state[node] = 1
        if any(visit(nxt) for nxt in edges.get(node, [])):
            return True
        state[node] = 2
        return False

    return any(visit(node) for node in edges)


async def set_schedule(
    session: AsyncSession, who: Who, version_id: uuid.UUID, inputs: list[ScheduleInput]
) -> None:
    """Durations and explicitly entered predecessors for the project's stage instances. No
    dates, no default ordering (BP-07, BP-07A deferred)."""
    await _draft(session, version_id, who)
    entries = {e.entry_key: e for e in await schedule_of(session, version_id)}
    for item in inputs:
        if item.entry_key not in entries:
            raise ValidationFailed(details={"fields": {item.entry_key: ["Unknown stage entry."]}})
        unknown = set(item.predecessors) - set(entries)
        if unknown or item.entry_key in item.predecessors:
            raise ValidationFailed(details={"fields": {item.entry_key: ["Unknown predecessor."]}})
        if item.duration_days is not None and not 1 <= item.duration_days <= 3650:
            raise ValidationFailed(details={"fields": {item.entry_key: ["1 to 3650 days."]}})
    edges = {key: list(entry.predecessors) for key, entry in entries.items()}
    for item in inputs:
        edges[item.entry_key] = list(dict.fromkeys(item.predecessors))
    if _cycle(edges):
        raise ValidationFailed(details={"fields": {"predecessors": ["The dependencies loop."]}})
    for item in inputs:
        entry = entries[item.entry_key]
        entry.duration_days = item.duration_days
        entry.predecessors = edges[item.entry_key]
        entry.note = item.note
    await session.flush()


async def set_scope(
    session: AsyncSession,
    who: Who,
    version_id: uuid.UUID,
    *,
    inclusions: list[str],
    exclusions: list[str],
    assumptions: list[str],
    explanation_note: str | None,
) -> None:
    version = await _draft(session, version_id, who)
    for name, items in (("inclusions", inclusions), ("exclusions", exclusions),
                        ("assumptions", assumptions)):  # fmt: skip
        if len(items) > MAX_LIST_ITEMS or any(not i.strip() or len(i) > 1000 for i in items):
            raise ValidationFailed(details={"fields": {name: ["Up to 100 items of 1000 chars."]}})
    version.inclusions = [i.strip() for i in inclusions]
    version.exclusions = [i.strip() for i in exclusions]
    version.assumptions = [i.strip() for i in assumptions]
    version.explanation_note = explanation_note
    await session.flush()


# --- hash and completeness -------------------------------------------------------------------


async def content_hash(session: AsyncSession, version: BuildPlanVersion) -> str:
    """sha256 of the version's content in a canonical form: what sign-offs and acceptance bind
    to."""
    drawing_set = (
        await session.get(DrawingSet, version.drawing_set_id) if version.drawing_set_id else None
    )
    content = {
        "version": [str(version.id), str(version.project_id), version.version_no,
                    version.requirement_version],
        "drawing_set": [str(drawing_set.id), drawing_set.content_hash] if drawing_set else None,
        "rate_card": str(version.rate_card_id) if version.rate_card_id else None,
        "values": [
            [v.line_code, str(v.master_version_id), v.criteria_text, v.applicability,
             v.not_applicable_reason, v.value_text, v.basis, v.source_note,
             sorted(str(e) for e in v.evidence_file_ids)]
            for v in await values_of(session, version.id)
        ],
        "boq": [
            [b.line_no, str(b.rate_card_id), b.item_code, b.description, b.unit,
             f"{b.quantity:.3f}", b.quantity_basis,
             str(b.drawing_file_id) if b.drawing_file_id else None, b.basis_note,
             f"{b.rate:.2f}", f"{b.amount:.2f}", b.stage_number, b.floor,
             sorted(b.spec_line_codes), b.assumptions]
            for b in await boq_of(session, version.id)
        ],
        "schedule": [
            [e.entry_key, e.stage_number, e.floor, e.duration_days, sorted(e.predecessors), e.note]
            for e in await schedule_of(session, version.id)
        ],
        "scope": [version.inclusions, version.exclusions, version.assumptions,
                  version.explanation_note],
    }  # fmt: skip
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


async def missing_for_submit(session: AsyncSession, version: BuildPlanVersion) -> list[str]:
    missing: list[str] = []
    values = await values_of(session, version.id)
    structural_applies = any(
        v.is_structural and v.applicability == ValueApplicability.APPLICABLE.value for v in values
    )
    if version.drawing_set_id is None:
        missing.append("DRAWING_SET")
    else:
        drawing_set = await session.get_one(DrawingSet, version.drawing_set_id)
        if drawing_set.state != DrawingSetState.APPROVED.value:
            missing.append("DRAWING_SET_NOT_APPROVED")
        classes = await classes_of(session, drawing_set.id)
        required = list(REQUIRED_CLASSES) + (
            [DrawingClass.STRUCTURAL] if structural_applies else []
        )
        missing += [f"DRAWING_{c.value}" for c in required if c.value not in classes]
    missing += [
        f"VALUE_{v.line_code}"
        for v in values
        if v.applicability == ValueApplicability.APPLICABLE.value and not v.value_text
    ]
    if not await boq_of(session, version.id):
        missing.append("BOQ")
    missing += [
        f"DURATION_{e.entry_key}"
        for e in await schedule_of(session, version.id)
        if e.duration_days is None
    ]
    for name in ("inclusions", "exclusions", "assumptions"):
        if not getattr(version, name):
            missing.append(name.upper())
    return missing


# --- transitions -----------------------------------------------------------------------------


async def submit(session: AsyncSession, who: Who, version_id: uuid.UUID) -> BuildPlanVersion:
    version = await version_row(session, version_id, lock=True)
    if version.state != V.DRAFT.value:
        raise StateConflict(details={"current_state": version.state})
    await require_package(session, version.project_id)
    missing = await missing_for_submit(session, version)
    if missing:
        raise conflict("INCOMPLETE", "The version is not complete.", missing=missing)
    version.content_hash = await content_hash(session, version)
    version.submitted_by = who.user_id
    version.submitted_at = await db_now(session)
    await _move(session, version, "submit", who)
    return version


async def return_to_draft(
    session: AsyncSession, who: Who, version_id: uuid.UUID, reason: str
) -> None:
    version = await version_row(session, version_id, lock=True)
    if version.state != V.IN_REVIEW.value:
        raise StateConflict(details={"current_state": version.state})
    await signoffs.void_all(session, who, version, f"returned to draft: {reason}")
    version.content_hash = None
    version.submitted_by = None
    version.submitted_at = None
    await _move(session, version, "return", who, reason)


async def withdraw(session: AsyncSession, who: Who, version_id: uuid.UUID, reason: str) -> None:
    """Never an ACCEPTED version. Allowed while the package is inactive (BP-09)."""
    version = await version_row(session, version_id, lock=True)
    if version.state not in (V.DRAFT.value, V.IN_REVIEW.value, V.ISSUED.value):
        raise StateConflict(details={"current_state": version.state})
    if version.state == V.IN_REVIEW.value:
        await signoffs.void_all(session, who, version, f"withdrawn: {reason}")
    version.closed_at = await db_now(session)
    version.close_reason = reason
    await _move(session, version, "withdraw", who, reason)


async def supersede(
    session: AsyncSession, who: Who, version: BuildPlanVersion, reason: str
) -> None:
    version.closed_at = await db_now(session)
    version.close_reason = reason
    await _move(session, version, "supersede", who, reason)


async def publish_version_event(
    session: AsyncSession, event_type: str, version: BuildPlanVersion
) -> None:
    await publish(
        session,
        event_type=event_type,
        aggregate_type="build_plan_version",
        aggregate_id=version.id,
        payload=VersionEvent(
            version_id=version.id, project_id=version.project_id, version_no=version.version_no
        ),
        dedupe_suffix=event_type.rsplit(".", 1)[-1],
    )


async def latest_issued(session: AsyncSession, project_id: uuid.UUID) -> BuildPlanVersion | None:
    return (
        await session.scalars(
            select(BuildPlanVersion)
            .where(
                BuildPlanVersion.project_id == project_id,
                BuildPlanVersion.issued_at.is_not(None),
            )
            .order_by(BuildPlanVersion.version_no.desc())
            .limit(1)
        )
    ).one_or_none()


async def count_versions(session: AsyncSession, project_id: uuid.UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(BuildPlanVersion)
            .where(BuildPlanVersion.project_id == project_id)
        )
        or 0
    )
