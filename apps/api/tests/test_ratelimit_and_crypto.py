"""Rate limiter (API_ARCHITECTURE section 1 tiers; ADR-007) and crypto helpers (SECURITY 3.1, 9)."""

import pytest
from cryptography.exceptions import InvalidTag

from p2b.core.crypto import decrypt, encrypt, keyed_hash
from p2b.core.db import Database
from p2b.core.errors import RateLimited
from p2b.core.ratelimit import Limit, enforce, hit

KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
RULE = Limit("test_rule", 3, 600)


async def test_hits_are_allowed_up_to_the_limit_then_refused(database: Database) -> None:
    decisions = [await hit(database, RULE, "subject-a") for _ in range(4)]
    assert [d.allowed for d in decisions] == [True, True, True, False]
    assert [d.count for d in decisions] == [1, 2, 3, 4]
    assert 0 < decisions[-1].retry_after_seconds <= RULE.window_seconds


async def test_subjects_and_rules_are_counted_separately(database: Database) -> None:
    for _ in range(3):
        await hit(database, RULE, "subject-a")
    assert (await hit(database, RULE, "subject-b")).allowed
    assert (await hit(database, Limit("other_rule", 3, 600), "subject-a")).allowed


async def test_enforce_raises_with_retry_after(database: Database) -> None:
    for _ in range(3):
        await enforce(database, RULE, "subject-a")
    with pytest.raises(RateLimited) as raised:
        await enforce(database, RULE, "subject-a")
    assert raised.value.status == 429
    assert int(raised.value.headers["Retry-After"]) > 0


def test_keyed_hash_depends_on_the_key() -> None:
    assert keyed_hash("k1", "a@example.in") == keyed_hash("k1", "a@example.in")
    assert keyed_hash("k1", "a@example.in") != keyed_hash("k2", "a@example.in")
    assert "a@example.in" not in keyed_hash("k1", "a@example.in")


def test_encryption_round_trips_and_is_bound_to_its_row() -> None:
    blob = encrypt(KEY, "123456", b"row-1")
    assert b"123456" not in blob
    assert decrypt(KEY, blob, b"row-1") == "123456"
    assert encrypt(KEY, "123456", b"row-1") != blob  # fresh nonce every time
    with pytest.raises(InvalidTag):
        decrypt(KEY, blob, b"row-2")


def test_a_short_key_is_refused() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        encrypt("c2hvcnQ=", "x", b"r")
