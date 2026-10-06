"""Runtime configuration from the environment (12-factor; ENVIRONMENT_AND_DEPLOYMENT section 1).

Every variable is documented in apps/api/.env.example. A missing required variable fails at start.
"""

from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from p2b.core.vocabulary import Audience

Environment = Literal["local", "test", "staging", "production"]


@dataclass(frozen=True)
class SessionPolicy:
    """Idle and absolute session lifetimes per audience (SECURITY_ARCHITECTURE section 3.2)."""

    idle: timedelta
    absolute: timedelta


SESSION_POLICIES: dict[Audience, SessionPolicy] = {
    Audience.IHB: SessionPolicy(idle=timedelta(days=14), absolute=timedelta(days=90)),
    Audience.PRO: SessionPolicy(idle=timedelta(days=7), absolute=timedelta(days=30)),
    Audience.OPS: SessionPolicy(idle=timedelta(hours=12), absolute=timedelta(hours=24)),
}

# Operations sessions must re-verify MFA within this window (SECURITY section 3.3).
MFA_REVERIFY_WINDOW = timedelta(hours=8)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="P2B_", extra="ignore")

    env: Environment
    service_name: str = "p2b-api"
    release: str = "dev"

    database_url: PostgresDsn = Field(description="postgresql+asyncpg:// URL for the app role")
    migrate_database_url: PostgresDsn | None = Field(
        default=None, description="URL for the app_migrate role; defaults to database_url"
    )
    database_pooler_mode: Literal["session", "transaction"] = "session"
    database_pool_size: int = 10
    statement_timeout_ms: int = 5000

    host_ihb: str = Field(description="Homeowner host, e.g. plan2build.in")
    host_pro: str = Field(description="Professional host, e.g. professionals.plan2build.in")
    host_ops: str = Field(description="Operations host, e.g. admin.plan2build.in")

    cookie_secure: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    sentry_dsn: SecretStr | None = None

    # Secrets (SECURITY section 9). Generate each with `python -c "import secrets;
    # print(secrets.token_urlsafe(32))"`; the encryption key is 32 random bytes, base64.
    otp_pepper: SecretStr = Field(description="Server pepper mixed into every OTP code hash")
    identifier_pepper: SecretStr = Field(
        description="HMAC key for contact and IP hashes in rate limits and security events"
    )
    encryption_key: SecretStr = Field(description="AES-256-GCM key, base64 of 32 bytes")

    # Outbound email (ADR-020). `smtp` is the development sink (Mailpit); `memory` is for tests.
    email_provider: Literal["resend", "smtp", "memory"] = "smtp"
    email_from: str = "Plan2Build <no-reply@plan2build.in>"
    resend_api_key: SecretStr | None = None
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    # Where operations notifications go (ruling 2.8). Unset: they are skipped and logged, never
    # sent to a guessed address. Set per environment once the operations mailbox exists.
    ops_notification_email: str | None = None
    # Open point F-09 (PRODUCT_FLOW_RECONCILIATION): whether a line's criteria headings show
    # before the package is active. A setting, not a rule; it starts hidden, as ruling 2.6.
    spec_criteria_before_package: bool = False

    # AI design concepts (Slice 3.1; F-08 first version). The provider is configuration and off
    # unless set: `demo` draws placeholders locally (never in production), `none` keeps generation
    # off until a provider is chosen (AQ-15). Quotas and limits are development defaults, not
    # commercial rules. Daily limits use a rolling 24 hours.
    ai_image_provider: Literal["demo", "none"] = "none"
    ai_free_generations_per_project: int = Field(default=3, ge=0)
    ai_max_projects_per_account_per_day: int = Field(default=3, ge=0)
    ai_max_generations_per_account_per_day: int = Field(default=10, ge=0)
    ai_provider_timeout_seconds: float = Field(default=90, gt=0)
    ai_provider_attempts: int = Field(default=2, ge=1, le=5)
    ai_image_width: int = Field(default=1024, ge=256, le=2048)
    ai_image_height: int = Field(default=768, ge=256, le=2048)

    # Billing (Slice 3.3; SLICE3_3_READINESS). `razorpay` is the only provider that takes money;
    # `fake` is the development and test gateway (local and test only); `none` keeps buying off.
    # Keys and secrets per environment (SECURITY section 9): only the key id reaches the browser.
    # Live Razorpay keys (`rzp_live_`) are accepted in production only.
    payment_provider: Literal["razorpay", "fake", "none"] = "none"
    payment_key_id: str | None = None
    payment_key_secret: SecretStr | None = None
    payment_webhook_secret: SecretStr | None = None
    razorpay_api_url: str = "https://api.razorpay.com/v1"
    payment_timeout_seconds: float = Field(default=15, gt=0)
    # An attempt with no outcome is checked against the provider after this many minutes and
    # expired when the provider has nothing for it (INTEGRATION_ARCHITECTURE 70).
    billing_attempt_check_minutes: int = Field(default=30, ge=1)
    # Open decision O-12: how long an unpaid order stays open. Unset: orders stay open until the
    # buyer cancels them.
    billing_unpaid_order_hours: int | None = Field(default=None, ge=1)
    # A TrueType font for invoice PDFs (Unicode names and addresses). Required in production.
    invoice_font_path: str | None = None

    # Connections (Slice 3.4): the professional's response window (N-07) and the open requests a
    # family may hold per project and category (N-05). Configuration, not code.
    connection_response_hours: int = Field(default=48, ge=1)
    connection_open_limit: int = Field(default=3, ge=1)
    # Slice 3.6 (QD-04, QD-05): at most this many contractors per RFQ, initialised to 3 for the
    # POC; an invitation not answered within this many hours expires.
    rfq_max_recipients: int = Field(default=3, ge=1)
    rfq_invitation_response_hours: int = Field(default=48, ge=1)
    rfq_quote_attachments_max: int = Field(default=5, ge=0)

    # Object storage, S3 API (ADR-006): Cloudflare R2 in staging and production, MinIO locally.
    # Browsers reach the public endpoint; the API and worker may use an internal one.
    storage_provider: Literal["s3", "memory"] = "s3"
    storage_endpoint_internal: str = "http://localhost:9000"
    storage_endpoint_public: str = "http://localhost:9000"
    storage_region: str = "auto"
    storage_access_key: SecretStr | None = None
    storage_secret_key: SecretStr | None = None
    storage_bucket_private: str = "p2b-local-private"

    # Malware scanning (INTEGRATION section 7): ClamAV over TCP. `accept_all` is for tests only.
    scanner_provider: Literal["clamav", "accept_all"] = "clamav"
    clamav_host: str = "localhost"
    clamav_port: int = 3310

    # Reverse geocoding for the locality (INTEGRATION section 5): Nominatim with a cache.
    geocoder_provider: Literal["nominatim", "none"] = "nominatim"
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "Plan2Build/0.1 (contact: tech@plan2build.in)"

    # Audiences where a verified, unknown contact may create an account (slice 1: homeowners).
    # Homeowners and professionals may register themselves (D-04); a professional registering
    # is never public until operations approve a category. Operations accounts never self-register.
    self_registration_audiences: frozenset[Audience] = frozenset({Audience.IHB, Audience.PRO})

    worker_queues: list[str] | None = None
    worker_concurrency: int = 8
    worker_heartbeat_path: str = "/tmp/p2b-worker-heartbeat"  # noqa: S108 (container-local file)

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if self.env == "production":
            if self.email_provider != "resend" or self.resend_api_key is None:
                raise ValueError("production sends email through Resend only")
            if not self.cookie_secure:
                raise ValueError("production cookies must be Secure")
            if self.storage_provider != "s3" or self.scanner_provider != "clamav":
                raise ValueError("production stores files in R2 and scans them with ClamAV")
            if self.ai_image_provider == "demo":
                raise ValueError("demo AI images never reach production homeowners")
            if self.payment_provider == "fake":
                raise ValueError("the fake payment gateway never takes production payments")
            if self.payment_provider == "razorpay" and not (self.payment_key_id or "").startswith(
                "rzp_live_"
            ):
                raise ValueError("production takes payments with live Razorpay keys only")
            if self.payment_provider != "none" and not self.invoice_font_path:
                raise ValueError("production invoices need P2B_INVOICE_FONT_PATH")
        elif (self.payment_key_id or "").startswith("rzp_live_"):
            raise ValueError("live Razorpay keys are for production only")
        if self.payment_provider == "fake" and self.env not in ("local", "test"):
            raise ValueError("the fake payment gateway runs locally and in tests only")
        if self.payment_provider != "none" and not (
            self.payment_key_id and self.payment_key_secret and self.payment_webhook_secret
        ):
            raise ValueError(
                "a payment provider needs P2B_PAYMENT_KEY_ID, _KEY_SECRET and _WEBHOOK_SECRET"
            )
        return self

    @property
    def docs_enabled(self) -> bool:
        return self.env == "local"

    @property
    def audience_by_host(self) -> dict[str, Audience]:
        return {
            self.host_ihb.lower(): Audience.IHB,
            self.host_pro.lower(): Audience.PRO,
            self.host_ops.lower(): Audience.OPS,
        }

    def host_for(self, audience: Audience) -> str:
        return {
            Audience.IHB: self.host_ihb,
            Audience.PRO: self.host_pro,
            Audience.OPS: self.host_ops,
        }[audience]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from the environment
