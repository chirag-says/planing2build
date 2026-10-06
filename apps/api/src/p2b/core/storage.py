"""Object storage interface (ADR-006, ADR-011). Keys are generated here, never by a client:
`{env}/{purpose}/{yyyy}/{mm}/{file_uuid}`. Uploads first land under `incoming/`; the worker writes
the checked object to the final key, so nothing unscanned is ever served."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

UPLOAD_URL_TTL_SECONDS = 15 * 60
DOWNLOAD_URL_TTL_SECONDS = 15 * 60


def object_key(env: str, purpose: str, created: datetime, file_id: uuid.UUID) -> str:
    return f"{env}/{purpose.lower()}/{created:%Y}/{created:%m}/{file_id}"


def incoming_key(final_key: str) -> str:
    return f"incoming/{final_key}"


@dataclass(frozen=True)
class PresignedUpload:
    url: str
    headers: dict[str, str]  # the browser must send exactly these


class StorageError(Exception):
    pass


class Storage(Protocol):
    def presign_put(self, key: str, content_type: str, size_bytes: int) -> PresignedUpload: ...

    def presign_get(
        self, key: str, download_name: str, content_type: str, *, inline: bool = False
    ) -> str: ...

    async def size_of(self, key: str) -> int | None: ...

    async def read(self, key: str) -> bytes: ...

    async def write(self, key: str, data: bytes, content_type: str) -> None: ...

    async def delete(self, key: str) -> None: ...
