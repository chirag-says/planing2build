"""Structured JSON logging with a field allow-list (OBSERVABILITY section 1; contract section 14).

Only allow-listed keys leave the process. Anything else is dropped and counted, so a developer who
logs `email=...` or `body=...` by mistake leaks nothing; the `dropped_fields` key shows that it
happened.
"""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        # structlog and envelope
        "event", "level", "timestamp", "logger", "exception", "service", "env", "release",
        # request
        "request_id", "method", "route", "path", "status", "duration_ms", "audience",
        # actor (ids only, never contact values)
        "user_id", "session_id",
        # outcomes
        "error_code", "error_class", "reason",
        # events and jobs
        "event_type", "aggregate_type", "aggregate_id", "outbox_id", "handler",
        "job", "job_id", "queue", "attempt", "count", "processed", "failed",
    }
)  # fmt: skip


def allow_list(
    _logger: Any, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    dropped = sorted(key for key in event_dict if key not in ALLOWED_FIELDS)
    for key in dropped:
        del event_dict[key]
    if dropped:
        event_dict["dropped_fields"] = len(dropped)
    return event_dict


def configure_logging(*, level: str, service: str, env: str, release: str) -> None:
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.format_exc_info,
    ]
    structlog.configure(
        processors=[
            *shared,
            allow_list,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(service=service, env=env, release=release)

    # Libraries that log through the standard library (uvicorn, sqlalchemy, procrastinate)
    # go through the same allow-list and renderer.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                allow_list,
                structlog.processors.JSONRenderer(),
            ],
        )
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
