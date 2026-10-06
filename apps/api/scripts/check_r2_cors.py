"""Validate an R2 bucket CORS policy and check it live with preflight requests (launch gate
N-01; infra/r2/README.md).

Policy rules: exact https origins (http only for *.localhost), no wildcard anywhere, method PUT
only, header content-type only. Live: each allowed origin's preflight must be answered with
that exact origin; each refused origin's preflight must not be allowed.

Run: python scripts/check_r2_cors.py --policy ../../infra/r2/cors.production.json
     --endpoint https://<account>.r2.cloudflarestorage.com/<bucket> --refuse https://example.com
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ALLOWED_METHODS = {"PUT"}
ALLOWED_HEADERS = {"content-type"}


@dataclass(frozen=True)
class Preflight:
    origin: str
    allowed: bool
    allow_origin: str | None


def policy_problems(policy: object, expected_origins: set[str] | None = None) -> list[str]:
    """Everything wrong with a policy; empty when it is acceptable."""
    if not isinstance(policy, list) or len(policy) != 1 or not isinstance(policy[0], dict):
        return ["the policy must be a list with exactly one rule"]
    rule = policy[0]
    problems = []
    origins = rule.get("AllowedOrigins", [])
    methods = rule.get("AllowedMethods", [])
    headers = rule.get("AllowedHeaders", [])
    for name, values in (("origin", origins), ("method", methods), ("header", headers)):
        if not values:
            problems.append(f"no allowed {name}")
        if any("*" in str(v) for v in values):
            problems.append(f"wildcard {name}")
    for origin in origins:
        parts = urlsplit(origin)
        local = (parts.hostname or "").endswith(".localhost")
        if parts.scheme != "https" and not (local and parts.scheme == "http"):
            problems.append(f"origin not https: {origin}")
        if parts.path not in ("", "/") or parts.query or parts.fragment or origin.endswith("/"):
            problems.append(f"origin must be scheme and host only: {origin}")
    if set(methods) - ALLOWED_METHODS:
        problems.append(f"methods beyond PUT: {sorted(set(methods) - ALLOWED_METHODS)}")
    if {h.lower() for h in headers} - ALLOWED_HEADERS:
        problems.append(f"headers beyond content-type: {sorted(headers)}")
    if set(rule) - {"AllowedOrigins", "AllowedMethods", "AllowedHeaders", "MaxAgeSeconds"}:
        problems.append(f"unexpected keys: {sorted(set(rule))}")
    if expected_origins is not None and set(origins) != expected_origins:
        problems.append(f"origins {sorted(origins)} are not exactly {sorted(expected_origins)}")
    return problems


def preflight(endpoint: str, origin: str, *, timeout: float = 10) -> Preflight:
    """An OPTIONS preflight for a PUT with content-type, as a browser sends before uploading."""
    response = httpx.options(
        f"{endpoint.rstrip('/')}/cors-check",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
        timeout=timeout,
    )
    allow_origin = response.headers.get("access-control-allow-origin")
    allowed = response.status_code < 400 and allow_origin in (origin, "*")
    return Preflight(origin, allowed, allow_origin)


def live_problems(endpoint: str, allowed: list[str], refused: list[str]) -> list[str]:
    problems = []
    for origin in allowed:
        result = preflight(endpoint, origin)
        if not result.allowed or result.allow_origin != origin:
            problems.append(f"allowed origin refused or loose: {origin} -> {result.allow_origin}")
    for origin in refused:
        if preflight(endpoint, origin).allowed:
            problems.append(f"refused origin was allowed: {origin}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--endpoint", help="bucket URL for live preflights")
    parser.add_argument("--refuse", action="append", default=[], help="an origin that must fail")
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    problems = policy_problems(policy)
    if args.endpoint and not problems:
        problems = live_problems(args.endpoint, policy[0]["AllowedOrigins"], args.refuse)
    for problem in problems:
        print(f"FAIL {problem}")
    if not problems:
        print("OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
