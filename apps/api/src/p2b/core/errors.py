"""Typed application errors and the one error envelope (API_ARCHITECTURE section 1).

Services raise these; handlers turn them into
`{"error": {"code", "message", "details", "request_id"}}`. Nothing else reaches the client:
unexpected exceptions become 500 INTERNAL with no internals.
"""

from collections.abc import Mapping
from typing import Any, ClassVar

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from p2b.core.request_context import current_request_id

log = structlog.get_logger(__name__)


class AppError(Exception):
    code: ClassVar[str] = "INTERNAL"
    status: ClassVar[int] = 500
    default_message: ClassVar[str] = "Something went wrong."

    def __init__(self, message: str | None = None, details: Mapping[str, Any] | None = None):
        self.message = message or self.default_message
        self.details = dict(details or {})
        self.headers: dict[str, str] = {}
        super().__init__(self.message)


class Unauthenticated(AppError):
    code, status, default_message = "UNAUTHENTICATED", 401, "Sign in to continue."


class Forbidden(AppError):
    code, status, default_message = "FORBIDDEN", 403, "You do not have access to this."


class MfaRequired(AppError):
    code, status, default_message = "MFA_REQUIRED", 403, "Confirm your authenticator code."


class CsrfRejected(AppError):
    code, status, default_message = "CSRF_REJECTED", 403, "The request was rejected."


class NotFound(AppError):
    code, status, default_message = "NOT_FOUND", 404, "Not found."


class StateConflict(AppError):
    code, status, default_message = "STATE_CONFLICT", 409, "This action is not allowed now."


class VersionConflict(AppError):
    code, status, default_message = "VERSION_CONFLICT", 409, "This was changed by someone else."


class ValidationFailed(AppError):
    code, status, default_message = "VALIDATION_ERROR", 422, "Some fields need attention."


class InvalidHost(AppError):
    code, status, default_message = "INVALID_HOST", 400, "Unknown host."


class OtpInvalid(AppError):
    code, status = "OTP_INVALID", 400
    default_message = "That code is not valid. Check it, or ask for a new one."


class OtpLocked(AppError):
    code, status = "OTP_LOCKED", 423
    default_message = "Too many wrong codes. Try again later."


class MfaInvalid(AppError):
    code, status = "MFA_INVALID", 400
    default_message = "That code is not valid. Check your authenticator app and try again."


class MfaNotEnrolled(AppError):
    code, status = "MFA_NOT_ENROLLED", 409
    default_message = "Set up your authenticator app first."


class MfaAlreadyEnrolled(AppError):
    code, status = "MFA_ALREADY_ENROLLED", 409
    default_message = "An authenticator app is already set up for this account."


class RateLimited(AppError):
    code, status, default_message = "RATE_LIMITED", 429, "Too many requests. Try again later."

    def __init__(self, retry_after_seconds: int):
        super().__init__(details={"retry_after_seconds": retry_after_seconds})
        self.headers["Retry-After"] = str(retry_after_seconds)


class QuotaExhausted(AppError):
    """A limit on AI design generations was reached. `details.block` says which one."""

    code, status = "QUOTA_EXHAUSTED", 409
    default_message = "No more design generations are available right now."


class DesignInputRequired(AppError):
    """A concept plan needs facts the requirement does not give (`details.missing`)."""

    code, status = "DESIGN_INPUT_REQUIRED", 422
    default_message = "A few more details are needed before a floor plan can be generated."


class PlanUnsupported(AppError):
    """The requirement describes a case the concept plan engine does not support yet."""

    code, status = "PLAN_UNSUPPORTED", 422
    default_message = "A floor plan cannot be generated for this requirement yet."


class RevisionConflict(AppError):
    """The plan changed since the editor loaded it (`details.current_revision`)."""

    code, status = "REVISION_CONFLICT", 409
    default_message = "This floor plan was changed meanwhile. Reload it to continue."


class PlanOperationRejected(AppError):
    """An edit operation cannot apply (`details`: index, op, code); nothing was applied."""

    code, status = "PLAN_OPERATION_REJECTED", 422
    default_message = "That change cannot be made to this floor plan."


class PlanEditInvalid(AppError):
    """The edit applies but the validator rejects the result (`details.report`); nothing was
    stored (IC 18.7)."""

    code, status = "PLAN_EDIT_INVALID", 422
    default_message = "That change would break the floor plan's rules, so it was not saved."


class PlanHistoryUnavailable(AppError):
    """An earlier state of the plan cannot be rebuilt exactly from its operation log (the
    replayed result does not match the recorded hash), so it is not restored (Checkpoint 3.1)."""

    code, status = "PLAN_HISTORY_UNAVAILABLE", 409
    default_message = "That earlier state of the floor plan cannot be restored."


class RulesetNotPublished(AppError):
    """No layout ruleset may be used here (production needs a PUBLISHED one; AD-05)."""

    code, status = "RULESET_NOT_PUBLISHED", 409
    default_message = "Floor plan rules are not available yet."


class GenerationInProgress(AppError):
    """A concept plan generation is already queued or running for this project."""

    code, status = "GENERATION_IN_PROGRESS", 409
    default_message = "A floor plan is already being generated for this project."


class ProviderUnavailable(AppError):
    code, status = "PROVIDER_UNAVAILABLE", 503
    default_message = "A service we depend on is unavailable. Try again shortly."


class PriceUnavailable(AppError):
    """The price cannot be computed: a characteristic the active pricing rule needs is missing
    (`details.missing`), for example a built-up area answered "Not sure yet"."""

    code, status = "PRICE_UNAVAILABLE", 422
    default_message = "The price cannot be worked out from your requirement yet."


class BillingNotConfigured(AppError):
    """No complete, published commercial or tax configuration is in force (`details.missing`)."""

    code, status = "BILLING_NOT_CONFIGURED", 503
    default_message = "Buying online is not available yet."


class SignatureInvalid(AppError):
    code, status, default_message = "SIGNATURE_INVALID", 401, "The signature is not valid."


class NoCredit(AppError):
    code, status = "NO_CREDIT", 409
    default_message = "You have no AI credit to use. Buy one to continue."


class PackageRequired(AppError):
    """A Plan2Build coordination action without an active package on the project (PD-19)."""

    code, status = "PACKAGE_REQUIRED", 409
    default_message = "This needs an active Plan2Build package on the project."


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any]
    request_id: str | None


class ErrorResponse(BaseModel):
    """The shape of every error response; published in OpenAPI for the generated client."""

    error: ErrorBody


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    "4XX": {"model": ErrorResponse, "description": "Client error"},
    "5XX": {"model": ErrorResponse, "description": "Server error"},
}


def envelope(
    status: int,
    code: str,
    message: str,
    details: Mapping[str, Any],
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        headers=dict(headers or {}),
        content={
            "error": {
                "code": code,
                "message": message,
                "details": dict(details),
                "request_id": current_request_id(),
            }
        },
    )


async def _app_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101 (registered for AppError only)
    log.info("request.rejected", error_code=exc.code, status=exc.status)
    return envelope(exc.status, exc.code, exc.message, exc.details, exc.headers)


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    fields: dict[str, list[str]] = {}
    for err in exc.errors():
        # Location is ("body", "field", ...); the first element is the request part.
        path = ".".join(str(part) for part in err["loc"][1:]) or str(err["loc"][0])
        fields.setdefault(path, []).append(str(err["msg"]))
    return envelope(
        422, ValidationFailed.code, ValidationFailed.default_message, {"fields": fields}
    )


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
    message = NotFound.default_message if exc.status_code == 404 else "Request not allowed."
    return envelope(exc.status_code, code, message, {})


async def _unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    log.error("request.failed", error_class=type(exc).__name__, exc_info=exc)
    return envelope(500, AppError.code, AppError.default_message, {})


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(Exception, _unexpected_error)
