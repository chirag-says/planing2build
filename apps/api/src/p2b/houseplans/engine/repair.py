"""Deterministic repair: validate → typed operations for issues with an AUTO repair → validate,
at most three passes, each of which must strictly reduce the error count or it is discarded.

Repairs only move hosted elements along their host. They never remove or add a room, change a
room type or a count, or relax a requirement: those need the homeowner (Part 8 of the brief)."""

from collections.abc import Callable
from dataclasses import dataclass, field

from p2b.core.vocabulary import EntityKind, ValidationCode
from p2b.houseplans.engine.derive import Analysis, analyse, fixture_info, with_clearances
from p2b.houseplans.engine.intent import ArchitecturalIntent
from p2b.houseplans.engine.model import HousePlan
from p2b.houseplans.engine.ops import MoveFixture, MoveOpening, OperationRejected, PlanOp, apply
from p2b.houseplans.engine.ruleset import RulesetContent
from p2b.houseplans.engine.validate import ValidationIssue, ValidationReport, validate

MAX_PASSES = 3


@dataclass(frozen=True)
class AppliedRepair:
    code: ValidationCode
    op: PlanOp
    inverse: PlanOp


@dataclass
class RepairResult:
    plan: HousePlan
    report: ValidationReport
    applied: list[AppliedRepair] = field(default_factory=list)


Repairer = Callable[[ValidationIssue, HousePlan, Analysis, RulesetContent], list[PlanOp]]


def _entity(issue: ValidationIssue, kind: EntityKind) -> str | None:
    return next((e.id for e in issue.entities if e.kind == kind), None)


def _slide_opening(
    issue: ValidationIssue, plan: HousePlan, an: Analysis, rules: RulesetContent
) -> list[PlanOp]:
    ident = _entity(issue, EntityKind.OPENING)
    info = an.openings.get(ident or "")
    if info is None:
        return []
    jamb, width, length = rules.openings.jamb_clearance_mm, info.opening.width_mm, info.wall.length
    if width > length - 2 * jamb:
        return []
    offset = min(max(info.opening.offset_mm, jamb), length - jamb - width)
    return [MoveOpening(opening=info.opening.id, offset_mm=offset)]


def _slide_fixture(
    issue: ValidationIssue, plan: HousePlan, an: Analysis, rules: RulesetContent
) -> list[PlanOp]:
    """Moves the fixture along its own wall to the nearest position that is inside the room and
    clear of door zones and other fixtures. Nothing else about it changes."""
    ident = _entity(issue, EntityKind.FIXTURE)
    info = an.fixtures.get(ident or "")
    if info is None or info.wall is None or not info.wall.orthogonal:
        return []
    clear = an.clear_rects.get(info.fixture.room)
    rule = rules.fixtures.get(info.fixture.type)
    if clear is None or rule is None:
        return []
    f, wall = info.fixture, info.wall
    others = [o for k, o in an.fixtures.items() if k != f.id]
    taken = [r for o in others for r in (o.footprint, o.clearance) if r is not None]
    zones = [z for o in an.openings.values() for z in o.zones]
    offsets = range(0, wall.length - f.w_mm + 1, rules.grid_mm)
    for offset in sorted(offsets, key=lambda s: (abs(s - f.offset_mm), s)):
        moved = fixture_info(f.model_copy(update={"offset_mm": offset}), wall, rule.clear_front_mm)
        fp, cl = moved.footprint, moved.clearance
        if (
            fp is not None
            and clear.contains(fp)
            and (cl is None or clear.contains(cl))
            and all(fp.overlap_area(z) == 0 for z in zones)
            and all(fp.overlap_area(t) == 0 for t in taken)
            and (cl is None or all(cl.overlap_area(r) == 0 for o in others if (r := o.footprint)))
        ):
            return [MoveFixture(fixture=f.id, wall=f.wall, offset_mm=offset, side=f.side)]
    return []


REPAIRERS: dict[ValidationCode, Repairer] = {
    ValidationCode.OPENING_OUTSIDE_HOST: _slide_opening,
    ValidationCode.FIXTURE_OUTSIDE_ROOM: _slide_fixture,
}


def repair(
    plan: HousePlan,
    ruleset: RulesetContent,
    *,
    intent: ArchitecturalIntent | None = None,
    report: ValidationReport | None = None,
    ruleset_version: int | None = None,
    ruleset_sha256: str | None = None,
) -> RepairResult:
    def check(candidate: HousePlan) -> ValidationReport:
        return validate(
            candidate,
            ruleset,
            intent=intent,
            ruleset_version=ruleset_version,
            ruleset_sha256=ruleset_sha256,
        )

    result = RepairResult(plan, report or check(plan))
    for _ in range(MAX_PASSES):
        if result.report.valid:
            break
        an = with_clearances(analyse(result.plan), ruleset)
        planned: list[tuple[ValidationCode, PlanOp]] = []
        for problem in result.report.errors:
            fixer = REPAIRERS.get(problem.code)
            if fixer is not None:
                planned.extend(
                    (problem.code, op) for op in fixer(problem, result.plan, an, ruleset)
                )
        if not planned:
            break
        candidate, applied = result.plan, []
        for code, op in planned:
            try:
                candidate, inverse = apply(candidate, op)
            except OperationRejected:
                continue
            applied.append(AppliedRepair(code, op, inverse))
        new_report = check(candidate)
        if len(new_report.errors) >= len(result.report.errors):
            break
        result = RepairResult(candidate, new_report, result.applied + applied)
    return result
