"""Schema versions. A reader accepts any 1.x document and refuses an unknown major version
rather than reinterpreting it. 1.1.0 (Checkpoint 2) only adds the optional `Constraint.score_milli`,
so a 1.0.0 document is already valid 1.1.0 and needs no upgrader. Upgraders (one function per
version step, each with tests) are added here when a step changes meaning; there are none yet."""

from collections.abc import Callable, Mapping
from typing import Any

from p2b.houseplans.engine.model import SCHEMA, SCHEMA_MAJOR

Upgrader = Callable[[dict[str, Any]], dict[str, Any]]
UPGRADERS: dict[str, Upgrader] = {}


def schema_version_of(raw: Mapping[str, Any]) -> str | None:
    meta = raw.get("meta")
    if not isinstance(meta, Mapping) or meta.get("schema") != SCHEMA:
        return None
    version = meta.get("schema_version")
    return version if isinstance(version, str) else None


def is_supported(version: str) -> bool:
    major, _, _ = version.partition(".")
    return major.isdigit() and int(major) == SCHEMA_MAJOR
