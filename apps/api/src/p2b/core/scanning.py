"""Malware scanning interface (INTEGRATION_ARCHITECTURE section 7). Fail closed: a scanner that
cannot answer raises, and the file stays unavailable until a retry succeeds."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    signature: str | None = None


class ScannerUnavailable(Exception):
    pass


class Scanner(Protocol):
    async def scan(self, data: bytes) -> ScanResult: ...
