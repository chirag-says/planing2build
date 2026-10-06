"""Launch gate N-01 (SLICE3_3_READINESS): the bucket CORS rule allows exactly the homeowner and
professionals hosts, PUT with content-type only, no wildcard. The policies are checked as files,
and the local storage (configured from cors.local.json's origins) is checked live with real
preflights: allowed origins pass, every other origin is refused."""

import importlib.util
import json
import re
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[3]
R2 = REPO / "infra" / "r2"
LOCAL_STORAGE = "http://localhost:9000/p2b-local-private"

spec = importlib.util.spec_from_file_location(
    "check_r2_cors", Path(__file__).resolve().parents[1] / "scripts" / "check_r2_cors.py"
)
assert spec is not None
assert spec.loader is not None
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

EXPECTED = {
    "cors.production.json": {"https://plan2build.in", "https://professionals.plan2build.in"},
    "cors.staging.json": {
        "https://staging.plan2build.in",
        "https://staging-professionals.plan2build.in",
    },
    "cors.local.json": {"http://ihb.localhost:8080", "http://pro.localhost:8080"},
}


def policy(name: str) -> object:
    return json.loads((R2 / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_each_policy_allows_exactly_the_two_upload_hosts(name: str) -> None:
    assert check.policy_problems(policy(name), EXPECTED[name]) == []


def test_the_admin_host_and_www_are_never_upload_origins() -> None:
    origins = {o for name in EXPECTED for o in policy(name)[0]["AllowedOrigins"]}  # type: ignore[index]
    assert not any("admin" in o or "://www." in o for o in origins)


@pytest.mark.parametrize(
    ("rule", "problem"),
    [
        (
            {
                "AllowedOrigins": ["*"],
                "AllowedMethods": ["PUT"],
                "AllowedHeaders": ["content-type"],
            },
            "wildcard origin",
        ),
        (
            {
                "AllowedOrigins": ["https://plan2build.in"],
                "AllowedMethods": ["PUT", "GET"],
                "AllowedHeaders": ["content-type"],
            },
            "methods beyond PUT",
        ),
        (
            {
                "AllowedOrigins": ["https://plan2build.in"],
                "AllowedMethods": ["PUT"],
                "AllowedHeaders": ["*"],
            },
            "wildcard header",
        ),
        (
            {
                "AllowedOrigins": ["http://plan2build.in"],
                "AllowedMethods": ["PUT"],
                "AllowedHeaders": ["content-type"],
            },
            "origin not https",
        ),
        (
            {
                "AllowedOrigins": ["https://plan2build.in/"],
                "AllowedMethods": ["PUT"],
                "AllowedHeaders": ["content-type"],
            },
            "scheme and host only",
        ),
    ],
)
def test_loose_policies_are_rejected(rule: dict[str, object], problem: str) -> None:
    assert any(problem in p for p in check.policy_problems([rule]))


def test_local_storage_is_configured_from_the_local_policy() -> None:
    compose = (REPO / "infra" / "local" / "compose.yml").read_text(encoding="utf-8")
    match = re.search(r"-s3\.allowedOrigins=([^\"]+)\"", compose)
    assert match is not None
    assert set(match.group(1).split(",")) == EXPECTED["cors.local.json"]


def _storage_up() -> bool:
    try:
        httpx.options(LOCAL_STORAGE, timeout=2)
    except httpx.HTTPError:
        return False
    return True


@pytest.mark.skipif(not _storage_up(), reason="local storage (Compose) is not running")
def test_local_preflights_allow_the_upload_hosts_and_refuse_every_other_origin() -> None:
    allowed = sorted(EXPECTED["cors.local.json"])
    refused = ["http://admin.localhost:8080", "https://example.com", "http://localhost:3000"]
    assert check.live_problems(LOCAL_STORAGE, allowed, refused) == []
    for origin in allowed:
        assert check.preflight(LOCAL_STORAGE, origin).allow_origin == origin
    for origin in refused:
        assert not check.preflight(LOCAL_STORAGE, origin).allowed
