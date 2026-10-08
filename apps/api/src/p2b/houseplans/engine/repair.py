"""Deterministic repair: validate → typed operations for issues with an AUTO repair → validate,
at most three passes, each of which must strictly reduce the error count or it is discarded.

Repairs only move hosted elements along walls. They never remove or add a room, change a room
type or a count, or relax a requirement: those need the homeowner (Part 8 of the brief).

Every applied repair records why (`RepairReason`) and the validation code it answered. Checkpoint 2
repairers: an opening slides inside its host (OPENING_OUTSIDE_HOST) or off another opening
(OPENING_OVERLAP, the later opening moves); a fixture moves to the nearest clear slot on its own
wall, else on the room's other walls in wall order (FIXTURE_OUTSIDE_ROOM, FIXTURE_BLOCKS_OPENING,
FIXTURE_CLEARANCE_BLOCKED). OBJECTIVE repairs are part of the contract but none exists yet: no
objective term depends on where an opening or a fixture sits, and moving walls belongs to the
editing checkpoint."""

from collections.abc import Callable
from dataclasses import dataclass, field

from p2b.core.vocabulary import EntityKind, RepairReason, ValidationCode, WallSide
from p2b.houseplans.engine.derive import Analysis, WallInfo, analyse, fixture_info, with_clearances
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
    reason: RepairReason = RepairReason.VALIDATION_ERROR


@dataclass
class RepairResult:
    plan: HousePlan
    report: ValidationReport
    applied: list[AppliedRepair] = field(default_factory=list)


Repairer = Callable[[ValidationIssue, HousePlan, Analysis, RulesetContent], list[PlanOp]]


def _entities(issue: ValidationIssue, kind: EntityKind) -> list[str]:
    return [e.id for e in issue.entities if e.kind == kind]


def _slide_opening(
    issue: ValidationIssue, plan: HousePlan, an: Analysis, rules: RulesetContent
) -> list[PlanOp]:
    ids = _entities(issue, EntityKind.OPENING)
    info = an.openings.get(ids[0] if ids else "")
    if info is None:
        return []
    jamb, width, length = rules.openings.jamb_clearance_mm, info.opening.width_mm, info.wall.length
    if width > length - 2 * jamb:
        return []
    offset = min(max(info.opening.offset_mm, jamb), length - jamb - width)
    return [MoveOpening(opening=info.opening.id, offset_mm=offset)]


def _separate_openings(
    issue: ValidationIssue, plan: HousePlan, an: Analysis, rules: RulesetContent
) -> list[PlanOp]:
    """Slides the later of two overlapping openings (by id) to the nearest grid offset on the same
    wall that stays inside the host and clear of every other opening there."""
    ids = sorted(_entities(issue, EntityKind.OPENING))
    info = an.openings.get(ids[-1] if ids else "")
    if info is None:
        return []
    o, wall = info.opening, info.wall
    jamb = rules.openings.jamb_clearance_mm
    others = [
        (i.start, i.end) for k, i in an.openings.items() if k != o.id and i.wall.id == wall.id
    ]
    lo, hi = jamb, wall.length - jamb - o.width_mm
    if hi < lo:
        return []
    shift = info.start - o.offset_mm  # where the opening's span starts relative to its offset

    def clear(offset: int) -> bool:
        start, end = offset + shift, offset + shift + o.width_mm
        return all(min(end, b) <= max(start, a) for a, b in others)

    g = rules.grid_mm
    offsets = range(-(-lo // g) * g, hi + 1, g)  # grid offsets from lo (rounded up) to hi
    for offset in sorted(offsets, key=lambda s: (abs(s - o.offset_mm), s)):
        if clear(offset):
            return [MoveOpening(opening=o.id, offset_mm=offset)]
    return []


def _room_walls(an: Analysis, room: str, first: WallInfo) -> list[tuple[WallInfo, WallSide]]:
    """The fixture's own wall first, then the room's other orthogonal walls in id order."""
    out = [(first, WallSide.LEFT if room in first.left_rooms else WallSide.RIGHT)]
    for wall_id in sorted(an.walls):
        w = an.walls[wall_id]
        if w.id == first.id or not w.orthogonal:
            continue
        if room in w.left_rooms:
            out.append((w, WallSide.LEFT))
        elif room in w.right_rooms:
            out.append((w, WallSide.RIGHT))
    return out


def _slide_fixture(
    issue: ValidationIssue, plan: HousePlan, an: Analysis, rules: RulesetContent
) -> list[PlanOp]:
    """Moves the fixture to the nearest position on its own wall, else on the room's next wall,
    that is inside the room and clear of door zones, other fixtures and their clearances. Nothing
    else about it changes."""
    ids = _entities(issue, EntityKind.FIXTURE)
    info = an.fixtures.get(ids[0] if ids else "")
    if info is None or info.wall is None or not info.wall.orthogonal:
        return []
    clear = an.clear_rects.get(info.fixture.room)
    rule = rules.fixtures.get(info.fixture.type)
    if clear is None or rule is None:
        return []
    f = info.fixture
    others = [o for k, o in an.fixtures.items() if k != f.id]
    taken = [r for o in others for r in (o.footprint, o.clearance) if r is not None]
    footprints = [r for o in others if (r := o.footprint) is not None]
    zones = [z for o in an.openings.values() for z in o.zones]
    for wall, side in _room_walls(an, f.room, info.wall):
        start = f.offset_mm if wall.id == info.wall.id else 0
        offsets = range(0, wall.length - f.w_mm + 1, rules.grid_mm)
        for offset in sorted(offsets, key=lambda s: (abs(s - start), s)):
            moved = fixture_info(
                f.model_copy(update={"wall": wall.id, "side": side, "offset_mm": offset}),
                wall,
                rule.clear_front_mm,
            )
            fp, cl = moved.footprint, moved.clearance
            if (
                fp is not None
                and clear.contains(fp)
                and (cl is None or clear.contains(cl))
                and all(fp.overlap_area(z) == 0 for z in zones)
                and all(fp.overlap_area(t) == 0 for t in taken)
                and (cl is None or all(cl.overlap_area(r) == 0 for r in footprints))
            ):
                return [MoveFixture(fixture=f.id, wall=wall.id, offset_mm=offset, side=side)]
    return []


REPAIRERS: dict[ValidationCode, Repairer] = {
    ValidationCode.OPENING_OUTSIDE_HOST: _slide_opening,
    ValidationCode.OPENING_OVERLAP: _separate_openings,
    ValidationCode.FIXTURE_OUTSIDE_ROOM: _slide_fixture,
    ValidationCode.FIXTURE_BLOCKS_OPENING: _slide_fixture,
    ValidationCode.FIXTURE_CLEARANCE_BLOCKED: _slide_fixture,
}


def _target(op: PlanOp) -> str:
    return getattr(op, "opening", None) or getattr(op, "fixture", None) or ""


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
        moved: set[str] = set()
        for problem in result.report.errors:
            fixer = REPAIRERS.get(problem.code)
            if fixer is None:
                continue
            for op in fixer(problem, result.plan, an, ruleset):
                # One move per element per pass: later issues about it are judged next pass.
                if _target(op) not in moved:
                    moved.add(_target(op))
                    planned.append((problem.code, op))
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
