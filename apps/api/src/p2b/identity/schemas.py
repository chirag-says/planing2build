import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from p2b.core.vocabulary import Audience, StaffRole, UserStatus


class StaffInfo(BaseModel):
    """Present only on the operations host."""

    roles: list[StaffRole]
    mfa_enrolled: bool
    mfa_verified: bool = Field(description="Verified within the last 8 hours on this session")


class MeResponse(BaseModel):
    """`GET /me` (API_ARCHITECTURE section 2). Memberships and pending consents are added when the
    projects and consent tables exist; additive, so no version bump."""

    user_id: uuid.UUID
    audience: Audience
    status: UserStatus
    display_name: str | None
    locale: str
    staff: StaffInfo | None = None


class OtpStartRequest(BaseModel):
    email: EmailStr = Field(max_length=320)


class OtpStartResponse(BaseModel):
    challenge_id: uuid.UUID
    expires_at: datetime
    masked_contact: str


class OtpVerifyRequest(BaseModel):
    challenge_id: uuid.UUID
    code: Annotated[str, StringConstraints(pattern=r"^[0-9]{6}$")]


class OtpVerifyResponse(BaseModel):
    user: MeResponse
    is_new: bool
    mfa_required: bool


class MfaStatusResponse(BaseModel):
    enrolled: bool
    verified: bool
    recovery_codes_left: int


class MfaEnrolmentResponse(BaseModel):
    """Shown once while enrolment is pending. `secret` is for typing into the app by hand."""

    secret: str
    otpauth_uri: str
    qr_svg_data_uri: str


class MfaConfirmRequest(BaseModel):
    code: Annotated[str, StringConstraints(pattern=r"^[0-9]{6}$")]


class MfaConfirmResponse(BaseModel):
    recovery_codes: list[str] = Field(description="Shown once; store them somewhere safe")


class MfaVerifyRequest(BaseModel):
    code: Annotated[str, StringConstraints(min_length=6, max_length=32, strip_whitespace=True)]


class MfaVerifyResponse(BaseModel):
    method: Literal["totp", "recovery"]
    recovery_codes_left: int


class StaffMemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    status: UserStatus
    roles: list[StaffRole]
    mfa_enabled: bool
