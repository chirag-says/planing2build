"""Transition tables (STATE_MODEL 1) and the user account machine (STATE_MODEL 2)."""

from enum import StrEnum

import pytest

from p2b.core.errors import StateConflict, ValidationFailed
from p2b.core.state_machine import Transition, TransitionTable
from p2b.core.vocabulary import UserStatus
from p2b.identity.service import USER_ACCOUNT


class Light(StrEnum):
    RED = "RED"
    GREEN = "GREEN"


LIGHTS = TransitionTable[Light](
    "light",
    [
        Transition(None, Light.RED, "install"),
        Transition(Light.RED, Light.GREEN, "go"),
        Transition(Light.GREEN, Light.RED, "force_stop", override_allowed=True),
    ],
)


def test_allowed_transition_returns_the_target() -> None:
    assert LIGHTS.target(None, "install") is Light.RED
    assert LIGHTS.target(Light.RED, "go") is Light.GREEN


def test_disallowed_transition_is_a_state_conflict_carrying_the_current_state() -> None:
    with pytest.raises(StateConflict) as raised:
        LIGHTS.target(Light.GREEN, "go")
    assert raised.value.status == 409
    assert raised.value.details["current_state"] == Light.GREEN


def test_override_needs_the_flag_and_a_reason() -> None:
    assert LIGHTS.override_target(Light.GREEN, "force_stop", "signal fault") is Light.RED
    with pytest.raises(ValidationFailed):
        LIGHTS.override_target(Light.GREEN, "force_stop", "   ")
    with pytest.raises(StateConflict):
        LIGHTS.override_target(Light.RED, "go", "not overridable")


def test_duplicate_transitions_are_rejected_at_definition() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        TransitionTable[Light](
            "dup",
            [Transition(Light.RED, Light.GREEN, "go"), Transition(Light.RED, Light.RED, "go")],
        )


S = UserStatus
EXPECTED_USER_ACCOUNT = {
    (None, "register"): S.PENDING_VERIFICATION,
    (S.PENDING_VERIFICATION, "verify_contact"): S.ACTIVE,
    (S.ACTIVE, "suspend"): S.SUSPENDED,
    (S.SUSPENDED, "reinstate"): S.ACTIVE,
    (S.SUSPENDED, "close_suspended"): S.CLOSED,
    (S.ACTIVE, "close"): S.CLOSED,
}


def test_user_account_table_matches_the_state_model() -> None:
    actual = {(t.source, t.trigger): t.target for t in USER_ACCOUNT.transitions}
    assert actual == EXPECTED_USER_ACCOUNT
    assert not any(t.override_allowed for t in USER_ACCOUNT.transitions)


@pytest.mark.parametrize("source", [None, *UserStatus])
@pytest.mark.parametrize("trigger", sorted({t for _, t in EXPECTED_USER_ACCOUNT}))
def test_every_pair_outside_the_user_account_table_is_refused(
    source: UserStatus | None, trigger: str
) -> None:
    if (source, trigger) in EXPECTED_USER_ACCOUNT:
        assert USER_ACCOUNT.target(source, trigger) is EXPECTED_USER_ACCOUNT[(source, trigger)]
    else:
        with pytest.raises(StateConflict):
            USER_ACCOUNT.target(source, trigger)
