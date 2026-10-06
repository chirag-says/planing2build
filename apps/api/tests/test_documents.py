"""Uploads: presigned upload, completion, checks before availability, downloads, deletion
(ADR-011; SECURITY sections 5 and 8; API section 15; REQUIREMENT_QUESTIONS_V1 R-15)."""

import asyncio
import hashlib
import io
import uuid
from typing import Any
from urllib.parse import urlparse

import pikepdf
import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from PIL import Image
from pydantic import SecretStr
from sqlalchemy import select

from p2b.core.config import get_settings
from p2b.core.db import Database
from p2b.core.outbox import OutboxEvent
from p2b.core.scanning import ScannerUnavailable, ScanResult
from p2b.core.storage import incoming_key
from p2b.core.vocabulary import FileState
from p2b.documents.inspection import inspect, sniff
from p2b.documents.models import DocumentAccessLog, FileObject
from p2b.documents.service import process_file
from p2b.integrations.clamav import AcceptAllScanner, ClamAvScanner, parse_reply
from p2b.integrations.storage import MemoryStorage, S3Storage
from tests.conftest import ClientFactory, SignIn, UserFactory
from tests.test_projects import H, _key, homeowner, new_project, save, submit
from tests.test_questions import COMPLETE

MB = 1024 * 1024
PNG_SIGNATURE = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])


def jpeg_with_exif() -> bytes:
    image = Image.new("RGB", (40, 30), "red")
    exif = Image.Exif()
    exif[0x010F] = "TestCam"  # Make
    exif[0x0110] = "Model X"  # Model
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def png() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (10, 10), "blue").save(out, format="PNG")
    return out.getvalue()


def pdf(*, javascript: bool = False) -> bytes:
    document = pikepdf.new()
    document.add_blank_page()
    if javascript:
        document.Root.OpenAction = pikepdf.Dictionary(
            S=pikepdf.Name.JavaScript, JS=pikepdf.String("app.alert(1)")
        )
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


@pytest.fixture
def storage(app: FastAPI) -> MemoryStorage:
    store: MemoryStorage = app.state.storage
    store.objects.clear()
    return store


async def ticket(client: AsyncClient, project_id: str, name: str, mime: str, size: int) -> Any:
    return await client.post(
        "/api/v1/uploads",
        json={
            "project_id": project_id,
            "file_name": name,
            "content_type": mime,
            "size_bytes": size,
        },
        headers=_key(),
    )


def incoming_from(ticket_body: dict[str, Any]) -> str:
    """The memory store's presigned URL is https://storage.test/<incoming key>?size=..."""
    return str(urlparse(ticket_body["upload_url"]).path.lstrip("/"))


async def uploaded(
    client: AsyncClient, storage: MemoryStorage, project_id: str, data: bytes, mime: str
) -> dict[str, Any]:
    response = await ticket(client, project_id, "plan.bin", mime, len(data))
    assert response.status_code == 201, response.text
    body = response.json()
    await storage.write(incoming_from(body), data, mime)
    done = await client.post(f"/api/v1/uploads/{body['file']['file_id']}/complete", headers=H)
    assert done.status_code == 200, done.text
    result: dict[str, Any] = done.json()
    return result


async def run_processing(
    database: Database, storage: MemoryStorage, file_id: str, scanner: Any = None
) -> FileState | None:
    return await process_file(database, storage, scanner or AcceptAllScanner(), uuid.UUID(file_id))


async def stored(database: Database, file_id: str) -> FileObject:
    async with database.transaction() as session:
        return await session.get_one(FileObject, uuid.UUID(file_id))


@pytest.fixture
async def setup(
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn
) -> tuple[AsyncClient, str]:
    client = await homeowner(client_for, make_user, sign_in)
    project_id = (await new_project(client))["project"]["project_id"]
    return client, project_id


async def test_upload_ticket_is_bound_to_type_size_and_a_server_key(
    setup: tuple[AsyncClient, str], storage: MemoryStorage
) -> None:
    client, project_id = setup
    response = await ticket(client, project_id, "../../etc/passwd.png", "image/png", 1000)
    assert response.status_code == 201
    body = response.json()
    assert body["file"]["state"] == "PENDING_UPLOAD"
    assert body["headers"] == {"Content-Type": "image/png"}
    file_id = body["file"]["file_id"]
    key = incoming_from(body)
    assert key.startswith("incoming/test/requirement_upload/")
    assert key.endswith(f"/{file_id}")
    assert "passwd" not in body["upload_url"]  # the client's name is metadata only


@pytest.mark.parametrize(
    ("mime", "size", "field"),
    [("application/zip", 100, "content_type"), ("image/png", 10 * MB + 1, "size_bytes")],
)
async def test_type_and_size_limits_come_from_the_question_set(
    setup: tuple[AsyncClient, str], mime: str, size: int, field: str
) -> None:
    client, project_id = setup
    response = await ticket(client, project_id, "x", mime, size)
    assert response.status_code == 422
    assert field in response.json()["error"]["details"]["fields"]


async def test_at_most_ten_files_per_project(setup: tuple[AsyncClient, str]) -> None:
    client, project_id = setup
    for _ in range(10):
        assert (await ticket(client, project_id, "x.png", "image/png", 100)).status_code == 201
    eleventh = await ticket(client, project_id, "x.png", "image/png", 100)
    assert eleventh.status_code == 422


async def test_completion_before_the_upload_arrives_is_refused(
    setup: tuple[AsyncClient, str],
) -> None:
    client, project_id = setup
    file_id = (await ticket(client, project_id, "x.png", "image/png", 100)).json()["file"][
        "file_id"
    ]
    response = await client.post(f"/api/v1/uploads/{file_id}/complete", headers=H)
    assert response.status_code == 409


async def test_a_different_size_than_declared_fails_the_file(
    setup: tuple[AsyncClient, str], storage: MemoryStorage
) -> None:
    client, project_id = setup
    body = (await ticket(client, project_id, "x.png", "image/png", 100)).json()
    file_id = body["file"]["file_id"]
    await storage.write(incoming_from(body), PNG_SIGNATURE + b"0" * 10, "image/png")
    response = await client.post(f"/api/v1/uploads/{file_id}/complete", headers=H)
    assert response.json()["state"] == "FAILED"


async def test_a_photo_becomes_available_without_its_metadata(
    setup: tuple[AsyncClient, str], storage: MemoryStorage, database: Database
) -> None:
    client, project_id = setup
    file = await uploaded(client, storage, project_id, jpeg_with_exif(), "image/jpeg")
    assert file["state"] == "UPLOADED"
    async with database.transaction() as session:
        events = list(await session.scalars(select(OutboxEvent.event_type)))
    assert "documents.upload_completed" in events

    assert await run_processing(database, storage, file["file_id"]) == FileState.AVAILABLE
    record = await stored(database, file["file_id"])
    clean, _ = storage.objects[record.object_key]
    assert dict(Image.open(io.BytesIO(clean)).getexif()) == {}
    assert incoming_key(record.object_key) not in storage.objects  # incoming copy removed
    assert record.detected_mime == "image/jpeg"
    assert record.sha256 is not None


async def test_the_recorded_hash_is_of_the_final_stored_bytes(
    setup: tuple[AsyncClient, str], storage: MemoryStorage, database: Database
) -> None:
    """H-07: upload, process (re-encode), store, read the stored bytes back, recompute: the
    persisted sha256 equals the hash of what is served, not of what was uploaded."""
    client, project_id = setup
    original = jpeg_with_exif()
    file = await uploaded(client, storage, project_id, original, "image/jpeg")
    assert await run_processing(database, storage, file["file_id"]) == FileState.AVAILABLE
    record = await stored(database, file["file_id"])
    final, _ = storage.objects[record.object_key]
    assert final != original  # re-encoded: metadata gone
    assert record.sha256 == hashlib.sha256(final).hexdigest()
    assert record.sha256 != hashlib.sha256(original).hexdigest()
    assert record.size_bytes == len(final)


@pytest.mark.parametrize(
    ("data", "declared", "reason"),
    [
        (pdf(javascript=True), "application/pdf", "PDF_ACTIVE_CONTENT"),
        (png(), "image/jpeg", "TYPE_MISMATCH"),
        (b"MZ\x90\x00 not really a pdf", "application/pdf", "TYPE_MISMATCH"),
    ],
)
async def test_unsafe_or_mislabelled_files_are_quarantined(
    setup: tuple[AsyncClient, str], storage: MemoryStorage, database: Database,
    data: bytes, declared: str, reason: str,
) -> None:  # fmt: skip
    client, project_id = setup
    file = await uploaded(client, storage, project_id, data, declared)
    assert await run_processing(database, storage, file["file_id"]) == FileState.QUARANTINED
    record = await stored(database, file["file_id"])
    assert record.rejection_reason == reason
    assert record.object_key not in storage.objects  # never written to the served key


class InfectedScanner:
    async def scan(self, data: bytes) -> ScanResult:
        return ScanResult(clean=False, signature="Eicar-Test-Signature")


class DownScanner:
    async def scan(self, data: bytes) -> ScanResult:
        raise ScannerUnavailable("down")


async def test_malware_is_quarantined_and_a_scanner_outage_fails_closed(
    setup: tuple[AsyncClient, str], storage: MemoryStorage, database: Database
) -> None:
    client, project_id = setup
    infected = await uploaded(client, storage, project_id, pdf(), "application/pdf")
    await run_processing(database, storage, infected["file_id"], InfectedScanner())
    assert (await stored(database, infected["file_id"])).rejection_reason == "MALWARE"

    waiting = await uploaded(client, storage, project_id, pdf(), "application/pdf")
    with pytest.raises(ScannerUnavailable):
        await run_processing(database, storage, waiting["file_id"], DownScanner())
    assert (await stored(database, waiting["file_id"])).state == "SCANNING"  # retried by the job
    assert await run_processing(database, storage, waiting["file_id"]) == FileState.AVAILABLE


async def test_downloads_are_for_members_only_and_logged(
    setup: tuple[AsyncClient, str], storage: MemoryStorage, database: Database,
    client_for: ClientFactory, make_user: UserFactory, sign_in: SignIn,
) -> None:  # fmt: skip
    client, project_id = setup
    file = await uploaded(client, storage, project_id, png(), "image/png")
    early = await client.get(f"/api/v1/files/{file['file_id']}/url")
    assert early.status_code == 409  # not available before the checks
    await run_processing(database, storage, file["file_id"])
    link = await client.get(f"/api/v1/files/{file['file_id']}/url")
    assert link.status_code == 200
    assert link.json()["expires_in_seconds"] == 900
    stranger = await homeowner(client_for, make_user, sign_in)
    assert (await stranger.get(f"/api/v1/files/{file['file_id']}/url")).status_code == 404
    async with database.transaction() as session:
        logged = list(await session.scalars(select(DocumentAccessLog)))
    assert len(logged) == 1


async def test_files_can_be_removed_and_added_only_while_the_requirement_is_a_draft(
    setup: tuple[AsyncClient, str], storage: MemoryStorage, database: Database
) -> None:
    client, project_id = setup
    file = await uploaded(client, storage, project_id, png(), "image/png")
    assert (await client.delete(f"/api/v1/files/{file['file_id']}", headers=H)).status_code == 204
    assert (await client.get(f"/api/v1/projects/{project_id}/files")).json() == []
    assert (await stored(database, file["file_id"])).state == "DELETED"

    await save(client, project_id, COMPLETE, 1)
    assert (await submit(client, project_id, 2)).status_code == 200
    late = await ticket(client, project_id, "x.png", "image/png", 100)
    assert late.status_code == 409


def test_type_sniffing() -> None:
    assert sniff(jpeg_with_exif()) == "image/jpeg"
    assert sniff(png()) == "image/png"
    assert sniff(pdf()) == "application/pdf"
    assert sniff(b"GIF89a") is None
    assert inspect(pdf(), "application/pdf").ok


def test_clamd_replies_are_parsed_and_errors_fail_closed() -> None:
    assert parse_reply("stream: OK").clean
    infected = parse_reply("stream: Eicar-Test-Signature FOUND")
    assert (infected.clean, infected.signature) == (False, "Eicar-Test-Signature")
    with pytest.raises(ScannerUnavailable):
        parse_reply("INSTREAM size limit exceeded. ERROR")


async def test_clamav_client_speaks_instream() -> None:
    received = bytearray()

    async def clamd(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        assert await reader.readexactly(10) == b"zINSTREAM\0"
        while True:
            size = int.from_bytes(await reader.readexactly(4), "big")
            if size == 0:
                break
            received.extend(await reader.readexactly(size))
        writer.write(b"stream: OK\0")
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(clamd, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        result = await ClamAvScanner("127.0.0.1", port).scan(b"x" * 100_000)
    assert result.clean
    assert len(received) == 100_000


async def test_an_unreachable_scanner_fails_closed() -> None:
    with pytest.raises(ScannerUnavailable):
        await ClamAvScanner("127.0.0.1", 9).scan(b"x")


def test_s3_presigned_upload_signs_type_and_length() -> None:
    settings = get_settings().model_copy(
        update={
            "storage_access_key": SecretStr("k"),
            "storage_secret_key": SecretStr("s"),
            "storage_endpoint_public": "https://files.example.test",
        }
    )
    s3 = S3Storage(settings)
    upload = s3.presign_put("incoming/test/x", "image/png", 1234)
    assert upload.url.startswith("https://files.example.test/p2b-local-private/incoming/test/x?")
    assert "X-Amz-Signature=" in upload.url
    assert "content-length" in upload.url.lower()
    download = s3.presign_get("test/x", 'plan "v2".pdf', "application/pdf")
    assert "response-content-disposition=attachment" in download
