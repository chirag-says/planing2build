"""ClamAV adapter behind `p2b.core.scanning.Scanner` (INTEGRATION section 7). Speaks clamd's
INSTREAM command over TCP: the protocol is a command, length-prefixed chunks and a one-line reply,
small enough not to need a client library. Timeouts: connect 2 s, reply 60 s."""

import asyncio

from p2b.core.config import Settings
from p2b.core.scanning import Scanner, ScannerUnavailable, ScanResult

CHUNK = 64 * 1024


class ClamAvScanner:
    def __init__(self, host: str, port: int):
        self._host, self._port = host, port

    async def scan(self, data: bytes) -> ScanResult:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), timeout=2
            )
        except (OSError, TimeoutError) as exc:
            raise ScannerUnavailable(f"clamd unreachable: {type(exc).__name__}") from exc
        try:
            writer.write(b"zINSTREAM\0")
            for start in range(0, len(data), CHUNK):
                chunk = data[start : start + CHUNK]
                writer.write(len(chunk).to_bytes(4, "big") + chunk)
            writer.write((0).to_bytes(4, "big"))
            await writer.drain()
            reply = await asyncio.wait_for(reader.readuntil(b"\0"), timeout=60)
        except (OSError, TimeoutError, asyncio.IncompleteReadError) as exc:
            raise ScannerUnavailable(f"clamd failed: {type(exc).__name__}") from exc
        finally:
            writer.close()
        return parse_reply(reply.rstrip(b"\0").decode("utf-8", "replace"))


def parse_reply(text: str) -> ScanResult:
    """`stream: OK`, `stream: <signature> FOUND`, or `... ERROR` (fail closed)."""
    body = text.split(":", 1)[-1].strip()
    if body == "OK":
        return ScanResult(clean=True)
    if body.endswith(" FOUND"):
        return ScanResult(clean=False, signature=body.removesuffix(" FOUND").strip())
    raise ScannerUnavailable(f"clamd reply: {text[:120]}")


class AcceptAllScanner:
    """Tests only (the settings guard refuses it in production)."""

    async def scan(self, data: bytes) -> ScanResult:
        return ScanResult(clean=True)


def build_scanner(settings: Settings) -> Scanner:
    if settings.scanner_provider == "clamav":
        return ClamAvScanner(settings.clamav_host, settings.clamav_port)
    return AcceptAllScanner()
