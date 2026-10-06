"""Storage adapters behind `p2b.core.storage.Storage` (ADR-006): S3 API for R2 or MinIO, and an
in-memory store for tests. boto3 is synchronous, so its network calls run in a worker thread."""

import asyncio
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from p2b.core.config import Settings
from p2b.core.storage import (
    DOWNLOAD_URL_TTL_SECONDS,
    UPLOAD_URL_TTL_SECONDS,
    PresignedUpload,
    Storage,
    StorageError,
)

_CONFIG = Config(
    signature_version="s3v4",
    s3={"addressing_style": "path"},
    connect_timeout=5,
    read_timeout=60,
    retries={"max_attempts": 3},
)


class S3Storage:
    def __init__(self, settings: Settings):
        if settings.storage_access_key is None or settings.storage_secret_key is None:
            raise ValueError("storage credentials are required for the s3 provider")
        credentials: dict[str, Any] = {
            "aws_access_key_id": settings.storage_access_key.get_secret_value(),
            "aws_secret_access_key": settings.storage_secret_key.get_secret_value(),
            "region_name": settings.storage_region,
            "config": _CONFIG,
        }
        self._bucket = settings.storage_bucket_private
        self._internal = boto3.client(
            "s3", endpoint_url=settings.storage_endpoint_internal, **credentials
        )
        # Presigned URLs must name the host the browser can reach.
        self._public = boto3.client(
            "s3", endpoint_url=settings.storage_endpoint_public, **credentials
        )

    def presign_put(self, key: str, content_type: str, size_bytes: int) -> PresignedUpload:
        url = self._public.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": size_bytes,
            },
            ExpiresIn=UPLOAD_URL_TTL_SECONDS,
        )
        return PresignedUpload(url=url, headers={"Content-Type": content_type})

    def presign_get(
        self, key: str, download_name: str, content_type: str, *, inline: bool = False
    ) -> str:
        """`inline` lets the browser show an image in the page (AI concepts); downloads stay
        attachments."""
        safe_name = download_name.replace('"', "").replace("\\", "")
        disposition = "inline" if inline else "attachment"
        url: str = self._public.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ResponseContentType": content_type,
                "ResponseContentDisposition": f'{disposition}; filename="{safe_name}"',
            },
            ExpiresIn=DOWNLOAD_URL_TTL_SECONDS,
        )
        return url

    async def size_of(self, key: str) -> int | None:
        try:
            head = await asyncio.to_thread(self._internal.head_object, Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise StorageError(str(exc)) from exc
        except BotoCoreError as exc:
            raise StorageError(str(exc)) from exc
        return int(head["ContentLength"])

    async def read(self, key: str) -> bytes:
        try:
            response = await asyncio.to_thread(
                self._internal.get_object, Bucket=self._bucket, Key=key
            )
            return bytes(await asyncio.to_thread(response["Body"].read))
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(str(exc)) from exc

    async def write(self, key: str, data: bytes, content_type: str) -> None:
        try:
            await asyncio.to_thread(
                self._internal.put_object,
                Bucket=self._bucket, Key=key, Body=data, ContentType=content_type,
            )  # fmt: skip
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(str(exc)) from exc

    async def delete(self, key: str) -> None:
        try:
            await asyncio.to_thread(self._internal.delete_object, Bucket=self._bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(str(exc)) from exc


class MemoryStorage:
    """Tests only. Presigned URLs point at a fake host; tests call `write` to simulate uploads."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def presign_put(self, key: str, content_type: str, size_bytes: int) -> PresignedUpload:
        return PresignedUpload(
            url=f"https://storage.test/{key}?size={size_bytes}",
            headers={"Content-Type": content_type},
        )

    def presign_get(
        self, key: str, download_name: str, content_type: str, *, inline: bool = False
    ) -> str:
        mode = "inline" if inline else "download"
        return f"https://storage.test/{key}?{mode}={download_name}"

    async def size_of(self, key: str) -> int | None:
        stored = self.objects.get(key)
        return len(stored[0]) if stored else None

    async def read(self, key: str) -> bytes:
        if key not in self.objects:
            raise StorageError(f"missing {key}")
        return self.objects[key][0]

    async def write(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = (data, content_type)

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)


def build_storage(settings: Settings) -> Storage:
    if settings.storage_provider == "s3":
        return S3Storage(settings)
    return MemoryStorage()
