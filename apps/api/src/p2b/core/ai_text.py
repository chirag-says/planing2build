"""Structured-output language model interface (Checkpoint 4; AI-assisted design interpretation).

The houseplans assistant depends on `TextProvider`, never on a vendor SDK; the provider is chosen
by configuration (`P2B_AI_TEXT_PROVIDER`). A request carries a bounded system text, the user's
words and a JSON schema the answer must follow. The provider returns parsed JSON or fails; the
caller validates the JSON again against its own models and never trusts it as geometry.

Nothing here decides anything about a plan: the model proposes an intent, the deterministic
engine compiles it into typed operations, and the validator decides."""

from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class TextRequest:
    task: str  # a short tag for logs and the mock ("requirement", "edit")
    system: str
    user: str
    schema: dict[str, Any]  # JSON Schema of the expected answer
    request_id: str  # correlation id, sent nowhere personal


@dataclass(frozen=True)
class TextUsage:
    input_tokens: int | None
    output_tokens: int | None


@dataclass(frozen=True)
class TextResult:
    data: Any  # the parsed JSON answer
    usage: TextUsage | None
    duration_ms: int
    attempts: int


class TextProviderError(Exception):
    """A provider call failed. `kind` says how; `retryable` whether another attempt can help."""

    def __init__(
        self,
        message: str,
        *,
        kind: Literal["UNAVAILABLE", "TIMEOUT", "REJECTED", "MALFORMED", "ERROR"],
        retryable: bool,
    ):
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable


class TextProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def configured(self) -> bool: ...

    async def structured(self, request: TextRequest) -> TextResult: ...
