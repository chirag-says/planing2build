"""The rule marker every route must carry (SECURITY_ARCHITECTURE section 4.1; contract section 8).

A route is deny-by-default: it must declare exactly one authorisation dependency, either
`public_route` or a dependency built by `p2b.identity.interface.require_actor`. Both are marked
here, and `tests/test_route_rules.py` walks every registered route and fails if one carries no
marker or more than one. Core defines the marker so that core routes (health) can use it without
importing any module.
"""

from collections.abc import Callable
from typing import Any

from fastapi import Depends

RULE_ATTRIBUTE = "__p2b_authz_rule__"


def mark_rule[F: Callable[..., Any]](dependency: F, description: str) -> F:
    setattr(dependency, RULE_ATTRIBUTE, description)
    return dependency


def rule_of(dependency: Callable[..., Any]) -> str | None:
    rule = getattr(dependency, RULE_ATTRIBUTE, None)
    return rule if isinstance(rule, str) else None


def _public() -> None:
    """Explicitly unauthenticated. Rate limiting for public routes is applied separately."""


public_route = Depends(mark_rule(_public, "public"))
