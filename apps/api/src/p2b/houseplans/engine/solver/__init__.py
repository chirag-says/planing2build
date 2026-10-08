"""The layout solver contract. Every solver (the Checkpoint 1 DeterministicMVPLayoutSolver, the
CP-SAT solver after the feasibility check) takes the same LayoutProblem and returns either room
rectangles with their access topology, or INFEASIBLE with reasons. A solver never builds walls,
openings or a HousePlan itself: one shared path turns its rectangles into the plan, and the same
validator judges every solver's output."""

from dataclasses import dataclass, field
from typing import Protocol

from p2b.core.vocabulary import InfeasibleReason, OpeningKind, RoomType, SolverKind
from p2b.houseplans.engine.geom import Rect
from p2b.houseplans.engine.ruleset import ZoningRules


@dataclass(frozen=True)
class RoomDemand:
    key: str
    room_type: RoomType
    enclosed: bool
    min_short_mm: int  # clear dimension
    min_area_mm2: int  # clear area
    target_area_mm2: int  # clear area aimed for (preferred, else minimum)


@dataclass(frozen=True)
class ParkingDemand:
    key: str
    clear_w_mm: int  # across the road edge
    clear_d_mm: int


@dataclass(frozen=True)
class RelationDemand:
    room: str
    host: str
    access: OpeningKind  # DOOR or VOID


@dataclass(frozen=True)
class LayoutProblem:
    region: Rect  # wall-centreline region: the buildable envelope inset by half the exterior wall
    grid_mm: int
    wall_allowance_mm: int  # centreline minus clear dimension, conservatively the exterior wall
    rooms: tuple[RoomDemand, ...]  # programme order
    relations: tuple[RelationDemand, ...]
    parking: ParkingDemand | None
    zoning: ZoningRules
    passage_key: str
    passage_clear_mm: int
    door_span_mm: int  # door width + jamb clearance at both ends
    void_span_mm: int


@dataclass(frozen=True)
class Access:
    room: str  # the room entered
    via: str  # the room it is entered from
    kind: OpeningKind  # DOOR or VOID


@dataclass(frozen=True)
class Placed:
    rects: dict[str, Rect]
    added_rooms: dict[str, RoomType]  # rooms the solver adds (circulation)
    access: tuple[Access, ...]
    entry_room: str
    topology: str


@dataclass(frozen=True)
class InfeasibleDetail:
    code: InfeasibleReason
    params: dict[str, int | str] = field(default_factory=dict)


@dataclass(frozen=True)
class Infeasible:
    reasons: tuple[InfeasibleDetail, ...]


SolveOutcome = Placed | Infeasible


class LayoutSolver(Protocol):
    kind: SolverKind
    version: str

    def solve(self, problem: LayoutProblem, *, seed: int) -> SolveOutcome: ...
