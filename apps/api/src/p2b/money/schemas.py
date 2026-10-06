"""Payment mark API contracts (EX-05). No model has an amount, a contract value, a percentage,
a balance or a settled flag; a request with any unknown field is refused."""

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from p2b.core.vocabulary import PaymentMarkValue


def _text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("This is required.")
    return value


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MarkIn(Strict):
    value: PaymentMarkValue


class OpsMarkIn(MarkIn):
    """How operations learnt of the OUTSIDE contractor's receipt."""

    reason: Annotated[str, Field(min_length=1, max_length=1000), AfterValidator(_text)]


class MarkOut(BaseModel):
    value: PaymentMarkValue
    marked_at: datetime
    by_operations: bool


class MilestoneOut(BaseModel):
    stage_instance_id: uuid.UUID
    stage_number: int
    floor: int | None
    due: bool = Field(description="The stage is complete; informational only")
    paid: MarkOut | None = Field(description="The owner's mark")
    received: MarkOut | None = Field(description="The contractor's mark")


class MilestonesOut(BaseModel):
    milestones: list[MilestoneOut]
