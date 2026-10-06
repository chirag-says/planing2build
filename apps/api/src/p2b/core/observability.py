"""Error reporting (ADR-017). Sentry only when a DSN is configured; personal data never sent."""

import sentry_sdk

from p2b.core.config import Settings


def init_sentry(settings: Settings) -> None:
    if settings.sentry_dsn is None:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.env,
        release=settings.release,
        send_default_pii=False,
        traces_sample_rate=0.1,
    )
