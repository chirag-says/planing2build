"""Identity tables owned by this module (DATA_ARCHITECTURE 4.2).

`users`, `user_contacts`, `otp_challenges`, `sessions`, `staff_roles`, `mfa_secrets`. A
self-registered user is created only when its OTP is verified (B-03), so a challenge is keyed by
the normalised contact, not by a contact row. Consents and devices arrive with the slices that
need them.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    LargeBinary,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from p2b.core.db import Base, Timestamps


class User(Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("audience IN ('ihb', 'pro', 'ops')", name="audience"),
        CheckConstraint(
            "status IN ('PENDING_VERIFICATION', 'ACTIVE', 'SUSPENDED', 'CLOSED')", name="status"
        ),
        Index("ix_users_audience_status", "audience", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    audience: Mapped[str] = mapped_column(String(3))
    display_name: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30))
    locale: Mapped[str] = mapped_column(String(10), server_default="en")
    last_login_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))


class UserContact(Timestamps, Base):
    """Email (now) or phone (when SMS is enabled). Unique per audience: one email can hold a
    homeowner account and, separately, a professional account."""

    __tablename__ = "user_contacts"
    __table_args__ = (
        CheckConstraint("audience IN ('ihb', 'pro', 'ops')", name="audience"),
        CheckConstraint("kind IN ('EMAIL', 'PHONE')", name="kind"),
        Index(
            "uq_user_contacts_audience_kind_normalized",
            "audience",
            "kind",
            "normalized",
            unique=True,
        ),
        Index("ix_user_contacts_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    audience: Mapped[str] = mapped_column(String(3))
    kind: Mapped[str] = mapped_column(String(10))
    value: Mapped[str] = mapped_column(String(320))
    normalized: Mapped[str] = mapped_column(String(320))
    verified_at: Mapped[datetime | None]
    is_primary: Mapped[bool] = mapped_column(server_default=text("false"))


class OtpChallenge(Timestamps, Base):
    """One code for one contact, audience and purpose (SECURITY 3.1). Only the argon2id hash is
    kept for verification; the AES-GCM ciphertext exists only until the delivery job sends it."""

    __tablename__ = "otp_challenges"
    __table_args__ = (
        CheckConstraint("audience IN ('ihb', 'pro', 'ops')", name="audience"),
        CheckConstraint(
            "purpose IN ('LOGIN', 'ACCEPT_BUILD_PLAN', 'SIGN_STRUCTURAL', 'SELECT_QUOTE')",
            name="purpose",
        ),
        CheckConstraint(
            "(purpose = 'LOGIN') = (subject_id IS NULL)", name="confirmation_has_subject"
        ),
        CheckConstraint("contact_kind IN ('EMAIL', 'PHONE')", name="contact_kind"),
        CheckConstraint("state IN ('ISSUED', 'VERIFIED', 'EXPIRED', 'LOCKED')", name="state"),
        Index(
            "ix_otp_challenges_contact",
            "audience",
            "contact_kind",
            "contact_normalized",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    audience: Mapped[str] = mapped_column(String(3))
    purpose: Mapped[str] = mapped_column(String(30))
    contact_kind: Mapped[str] = mapped_column(String(10))
    contact_normalized: Mapped[str] = mapped_column(String(320))
    code_hash: Mapped[str] = mapped_column(String(200))
    code_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    state: Mapped[str] = mapped_column(String(10))
    expires_at: Mapped[datetime]
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(SmallInteger)
    verified_at: Mapped[datetime | None]
    locked_at: Mapped[datetime | None]
    delivered_at: Mapped[datetime | None]
    delivery_failed_at: Mapped[datetime | None]
    ip_hash: Mapped[str | None] = mapped_column(String(64))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    subject_id: Mapped[uuid.UUID | None]  # the object a confirmation code is bound to (3.5)


class Session(Base):
    """Server-side session. The cookie holds the token; only sha256(token) is stored, so a database
    leak yields no usable session (SECURITY section 3.2)."""

    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint("audience IN ('ihb', 'pro', 'ops')", name="audience"),
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_active_user", "user_id", postgresql_where=text("revoked_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    audience: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    last_seen_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    expires_at: Mapped[datetime]
    absolute_expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    mfa_verified_at: Mapped[datetime | None]


class StaffRoleGrant(Base):
    """A global staff role held by an operations account (gap G-01; SLICE2_READINESS 1). Rows are
    never deleted: revocation sets `revoked_at`, so the history of who could do what stays."""

    __tablename__ = "staff_roles"
    __table_args__ = (
        CheckConstraint("role IN ('OPS', 'ADMIN')", name="role"),
        Index(
            "uq_staff_roles_active",
            "user_id",
            "role",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    role: Mapped[str] = mapped_column(String(10))
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    granted_at: Mapped[datetime] = mapped_column(server_default=func.now())
    revoked_at: Mapped[datetime | None]
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    reason: Mapped[str] = mapped_column(String(300))


class MfaSecret(Timestamps, Base):
    """TOTP for operations and admin (SECURITY 3.3; DATA 4.2). The secret is AES-GCM encrypted
    with the application key, bound to the user id; `enabled_at` is NULL while enrolment is
    pending. `last_used_step` stops a code being used twice. Recovery codes are argon2id hashes,
    removed when used."""

    __tablename__ = "mfa_secrets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
    secret_ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    enabled_at: Mapped[datetime | None]
    last_used_step: Mapped[int | None] = mapped_column(BigInteger)
    recovery_code_hashes: Mapped[list[str]] = mapped_column(
        ARRAY(String(200)), server_default=text("'{}'::varchar[]")
    )
    version: Mapped[int] = mapped_column(server_default=text("1"))
