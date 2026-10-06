from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from p2b.core.vocabulary import (
    DesignBlock,
    DesignFailureReason,
    DesignFunding,
    DesignGenerationState,
    DesignView,
)


class DesignRequest(BaseModel):
    """Only the view is the family's choice. Provider, model, prompt, template version, quota and
    price are the server's; unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    view: DesignView = DesignView.EXTERIOR
    use_credit: bool = Field(
        default=False,
        description="The family chose 'Use 1 AI credit'. Spent only when the free generations "
        "are used up; never otherwise, and never without this choice.",
    )


class DesignReferenceOut(BaseModel):
    kind: Literal["ILLUSTRATIVE_REFERENCE"] = "ILLUSTRATIVE_REFERENCE"
    marked_at: datetime


class DesignOut(BaseModel):
    """What the family sees of a generation: no provider, model, prompt, cost or internal
    detail."""

    design_id: str
    sequence: int
    view: DesignView
    state: DesignGenerationState
    funding: DesignFunding
    created_at: datetime
    completed_at: datetime | None
    failure_reason: DesignFailureReason | None
    image_url: str | None = Field(description="Short-lived signed link; only when SUCCEEDED")
    is_authoritative: Literal[False] = False
    reference: DesignReferenceOut | None


class DesignQuotaOut(BaseModel):
    free_total: int
    free_used: int
    in_progress: int
    free_remaining: int
    can_generate: bool
    block: DesignBlock | None
    credit_balance: int = Field(description="The account's AI credits (separate from the package)")
    can_use_credit: bool = Field(
        description="Free generations are used up and one credit may be spent now"
    )
    paid_block: DesignBlock | None = Field(
        description="Why a paid generation cannot run now, when one cannot"
    )


class DesignListOut(BaseModel):
    quota: DesignQuotaOut
    items: list[DesignOut]
