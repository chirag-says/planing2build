"""Job queue on PostgreSQL (Procrastinate; ADR-009; EVENT_AND_BACKGROUND_JOB_ARCHITECTURE 3).

Modules declare tasks on their own `procrastinate.Blueprint` in `jobs.py`; the composition root
(`p2b.worker`) adds them to the app. Request handlers never defer jobs: the relay's event handlers
do, so a job exists only if the business change committed.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from procrastinate import App, Blueprint, PsycopgConnector

from p2b.core.config import Settings
from p2b.core.db import Database
from p2b.core.images import ImageProvider
from p2b.core.messaging import MessageProvider
from p2b.core.payments import PaymentGateway
from p2b.core.scanning import Scanner
from p2b.core.storage import Storage

# Named queues with their purpose; concurrency per queue is set by how workers are started.
QUEUES: tuple[str, ...] = ("priority", "notify", "render", "files", "ai", "engine", "maintenance")


def libpq_url(settings: Settings) -> str:
    """Procrastinate uses psycopg; strip the SQLAlchemy driver suffix from the URL."""
    return str(settings.database_url).replace("postgresql+asyncpg://", "postgresql://", 1)


def build_job_app(settings: Settings, blueprints: Iterable[tuple[str, Blueprint]] = ()) -> App:
    app = App(connector=PsycopgConnector(conninfo=libpq_url(settings)))
    for namespace, blueprint in blueprints:
        app.add_tasks_from(blueprint, namespace=namespace)
    return app


@dataclass(frozen=True)
class JobResources:
    """What jobs need from the process, handed to them through Procrastinate's additional
    context (key `resources`) by the composition root, so jobs hold no globals."""

    database: Database
    settings: Settings
    message_provider: MessageProvider
    storage: Storage
    scanner: Scanner
    image_provider: ImageProvider
    payment_gateway: PaymentGateway


RESOURCES_KEY = "resources"
