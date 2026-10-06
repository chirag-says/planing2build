import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from p2b.core.vocabulary import FileState


class UploadRequest(BaseModel):
    project_id: uuid.UUID
    file_name: str = Field(min_length=1, max_length=200)
    content_type: str = Field(max_length=100)
    size_bytes: int = Field(gt=0)


class FileView(BaseModel):
    file_id: uuid.UUID
    file_name: str
    content_type: str
    size_bytes: int
    state: FileState
    created_at: datetime


class UploadTicket(BaseModel):
    """Upload with an HTTP PUT of the file body to `upload_url`, sending exactly `headers`.
    The URL expires after 15 minutes."""

    file: FileView
    upload_url: str
    headers: dict[str, str]


class DownloadLink(BaseModel):
    url: str
    expires_in_seconds: int
