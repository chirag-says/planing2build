import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from p2b.core.vocabulary import (
    EligibilityOutcome,
    FileState,
    ProjectStatus,
    QueueItemState,
    ReviewFlag,
)


class QueueItemOut(BaseModel):
    item_id: uuid.UUID
    state: QueueItemState
    claimed_by_me: bool
    claimed_by_email: str | None
    claimed_at: datetime | None
    created_at: datetime


class ReviewProjectOut(BaseModel):
    project_id: uuid.UUID
    code: str
    status: ProjectStatus
    locality: str | None
    submitted_at: datetime | None
    review_flags: list[ReviewFlag]


class ReviewQueueEntry(BaseModel):
    item: QueueItemOut
    project: ReviewProjectOut


class ReviewQueuePage(BaseModel):
    entries: list[ReviewQueueEntry]
    next_cursor: str | None = Field(description="Pass back as `cursor` for the next page")


class StaffFileOut(BaseModel):
    file_id: uuid.UUID
    file_name: str
    content_type: str
    size_bytes: int
    state: FileState
    created_at: datetime


class ReviewRequirementOut(BaseModel):
    question_set_version: int
    answers: dict[str, Any]


class HistoryOut(BaseModel):
    from_status: ProjectStatus | None
    to_status: ProjectStatus
    actor_email: str | None
    reason: str | None
    at: datetime


class InformationRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000, description="Shown to the family")


class EligibilityCheckIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(min_length=1, max_length=41)
    outcome: EligibilityOutcome
    note: str = Field(default="", max_length=1000)


class AcceptRequest(BaseModel):
    """Accepting records the package-eligibility checklist (F-05): every item of the active
    version, each PASSED."""

    model_config = ConfigDict(extra="forbid")

    checks: list[EligibilityCheckIn] = Field(min_length=1, max_length=20)


class EligibilityItemOut(BaseModel):
    id: str
    label: str
    help: str


class EligibilityResultOut(BaseModel):
    item_id: str
    outcome: EligibilityOutcome
    note: str


class EligibilityOut(BaseModel):
    """The checklist operations confirm before accepting, and, once accepted, what they
    recorded. `assessment` is null for projects accepted before checklist version 1."""

    checklist_version: int | None
    items: list[EligibilityItemOut]
    assessment: list[EligibilityResultOut] | None
    assessed_by_email: str | None
    assessed_at: datetime | None


class CancellationRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000, description="Shown to the family")


class OpsProjectDetail(BaseModel):
    """A submission as operations review it (API 18), with its decision history."""

    project: ReviewProjectOut
    city_code: str
    created_at: datetime
    owner_email: str | None
    requirement: ReviewRequirementOut
    files: list[StaffFileOut]
    queue_item: QueueItemOut | None
    history: list[HistoryOut]
    eligibility: EligibilityOut


class StaffDownloadLink(BaseModel):
    url: str
    expires_in_seconds: int
