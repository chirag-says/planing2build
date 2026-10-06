"""AI image generation interface (INTEGRATION_ARCHITECTURE section 6; Slice 3.1). The designs
module depends on `ImageProvider`, never on a vendor SDK; the provider is chosen by configuration
(`P2B_AI_IMAGE_PROVIDER`). The request carries only the rendered prompt and image parameters, so
nothing personal can reach a provider through this interface."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

View = Literal["EXTERIOR", "INTERIOR"]


@dataclass(frozen=True)
class ImageRequest:
    prompt: str
    negative_prompt: str
    view: View
    width: int
    height: int
    seed: int


@dataclass(frozen=True)
class ProviderUsage:
    """What the provider reported for one image, when it reports anything."""

    amount: Decimal | None
    currency: str | None
    units: str | None


@dataclass(frozen=True)
class ImageResult:
    content: bytes
    mime: str
    usage: ProviderUsage | None


class ImageProviderError(Exception):
    """A provider call failed. `kind` maps to the generation's failure reason; `retryable` says
    whether another attempt can succeed."""

    def __init__(
        self,
        message: str,
        *,
        kind: Literal["UNAVAILABLE", "TIMEOUT", "REJECTED", "ERROR"],
        retryable: bool,
    ):
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable


class ImageProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def configured(self) -> bool:
        """False when no provider is set up (production until AQ-15 is decided)."""
        ...

    async def generate(self, request: ImageRequest) -> ImageResult: ...
