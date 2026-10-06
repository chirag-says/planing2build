"""Transition tables: the only place a state may change (STATE_MODEL section 1, rules 2 and 4).

A module declares its machine as data (`TransitionTable`) and asks it for the target state before
writing. A disallowed trigger raises StateConflict (409) carrying the current state. Overrides are
allowed only where the table says so and only with a reason.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from p2b.core.errors import StateConflict, ValidationFailed


@dataclass(frozen=True)
class Transition[S: StrEnum]:
    source: S | None  # None means "new": the entity is being created
    target: S
    trigger: str
    override_allowed: bool = False


class TransitionTable[S: StrEnum]:
    def __init__(self, name: str, transitions: Iterable[Transition[S]]):
        self.name = name
        self._by_key: dict[tuple[S | None, str], Transition[S]] = {}
        for transition in transitions:
            key = (transition.source, transition.trigger)
            if key in self._by_key:
                raise ValueError(f"{name}: duplicate transition {key}")
            self._by_key[key] = transition

    @property
    def transitions(self) -> tuple[Transition[S], ...]:
        return tuple(self._by_key.values())

    def target(self, current: S | None, trigger: str) -> S:
        transition = self._by_key.get((current, trigger))
        if transition is None:
            raise StateConflict(
                details={"machine": self.name, "current_state": current, "trigger": trigger}
            )
        return transition.target

    def override_target(self, current: S, trigger: str, reason: str | None) -> S:
        """Operations override: only transitions marked override_allowed, and only with a reason."""
        transition = self._by_key.get((current, trigger))
        if transition is None or not transition.override_allowed:
            raise StateConflict(
                details={"machine": self.name, "current_state": current, "trigger": trigger}
            )
        if not reason or not reason.strip():
            raise ValidationFailed(details={"fields": {"reason": ["A reason is required."]}})
        return transition.target
