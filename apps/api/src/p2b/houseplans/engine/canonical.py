"""Canonical JSON and content hashes. The body hash excludes `meta`, so plan ids, timestamps and
revision numbers never change what a plan's geometry hashes to."""

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonical_json(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", by_alias=True)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_of(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()
