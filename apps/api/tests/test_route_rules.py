"""Deny by default: every route carries exactly one authorisation rule (SECURITY section 4.1;
IMPLEMENTATION_CONTRACT section 8). Adding a public route changes PUBLIC_ROUTES on purpose."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from p2b.core.authz import rule_of

PUBLIC_ROUTES = {
    ("GET", "/healthz"),
    ("GET", "/readyz"),
    ("POST", "/api/v1/auth/otp/start"),
    ("POST", "/api/v1/auth/otp/verify"),
    ("POST", "/api/v1/public/estimate"),
    ("GET", "/api/v1/public/requirement-questions"),
    ("POST", "/api/v1/public/enquiries"),
    # Slice 3.2, D-09: the professional directory is public.
    ("GET", "/api/v1/public/professional-categories"),
    ("GET", "/api/v1/public/professionals"),
    ("GET", "/api/v1/public/professionals/{profile_id}"),
    # Slice 3.3: the payment provider's webhook, authenticated by its signature instead.
    ("POST", "/api/v1/webhooks/razorpay"),
}


@dataclass(frozen=True)
class EffectiveRoute:
    methods: frozenset[str]
    path: str
    dependant: Dependant


def _api_routes(app: FastAPI) -> list[EffectiveRoute]:
    """Routes as served, with router prefixes applied (FastAPI keeps included routers nested)."""
    routes = [
        EffectiveRoute(frozenset(ctx.methods or ()), ctx.path, ctx.dependant)
        for ctx in iter_route_contexts(app.routes)
        if isinstance(ctx.original_route, APIRoute) and ctx.path is not None
    ]
    assert routes, "no routes found; the route walker no longer matches FastAPI's structure"
    return routes


def _rules(dependant: Dependant) -> Iterator[str]:
    for sub in dependant.dependencies:
        call: Any = sub.call
        rule = rule_of(call) if call is not None else None
        if rule is not None:
            yield rule
        yield from _rules(sub)


def test_every_route_declares_exactly_one_rule(app: FastAPI) -> None:
    problems = {
        (route.path, tuple(sorted(route.methods))): rules
        for route in _api_routes(app)
        if len(rules := list(_rules(route.dependant))) != 1
    }
    assert problems == {}, f"routes without exactly one authorisation rule: {problems}"


def test_public_routes_are_exactly_the_reviewed_list(app: FastAPI) -> None:
    public = {
        (method, route.path)
        for route in _api_routes(app)
        if list(_rules(route.dependant)) == ["public"]
        for method in route.methods
    }
    assert public == PUBLIC_ROUTES


def test_every_route_outside_health_is_versioned(app: FastAPI) -> None:
    unversioned = {
        route.path
        for route in _api_routes(app)
        if not route.path.startswith("/api/v1/") and route.path not in {"/healthz", "/readyz"}
    }
    assert unversioned == set()


def test_the_walker_sees_the_identity_routes(app: FastAPI) -> None:
    paths = {route.path for route in _api_routes(app)}
    assert {"/api/v1/me", "/api/v1/auth/logout", "/healthz", "/readyz"} <= paths
