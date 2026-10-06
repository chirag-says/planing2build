"""Identifiers: UUIDv7, time-ordered so inserts stay index-friendly (DATA_ARCHITECTURE 1)."""

import uuid

import uuid_utils


def new_id() -> uuid.UUID:
    return uuid.UUID(bytes=uuid_utils.uuid7().bytes)
