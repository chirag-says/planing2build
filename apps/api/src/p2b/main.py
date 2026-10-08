"""Composition root for the HTTP API: wires settings, logging, database, middleware and routers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI

from p2b.assurance.ops_router import router as assurance_ops_router
from p2b.assurance.router import router as assurance_router
from p2b.audit.interface import record_security_event
from p2b.billing.ops_router import router as billing_ops_router
from p2b.billing.router import dev_router as billing_dev_router
from p2b.billing.router import router as billing_router
from p2b.buildplan.ops_router import router as buildplan_ops_router
from p2b.buildplan.router import router as buildplan_router
from p2b.catalog.router import router as catalog_router
from p2b.construction.ops_router import router as construction_ops_router
from p2b.construction.router import router as construction_router
from p2b.core import health
from p2b.core.config import Settings, get_settings
from p2b.core.db import Database
from p2b.core.errors import ERROR_RESPONSES, install_error_handlers
from p2b.core.http import EdgeMiddleware
from p2b.core.logging import configure_logging
from p2b.core.observability import init_sentry
from p2b.core.vocabulary import Audience, SecuritySeverity
from p2b.designs.router import router as designs_router
from p2b.documents.router import router as documents_router
from p2b.engagements.ops_router import router as engagements_ops_router
from p2b.engagements.router import router as engagements_router
from p2b.houseplans.ops_router import router as houseplans_ops_router
from p2b.houseplans.router import router as houseplans_router
from p2b.identity.router import router as identity_router
from p2b.integrations.ai_images import build_image_provider
from p2b.integrations.ai_text import build_text_provider
from p2b.integrations.nominatim import build_geocoder
from p2b.integrations.razorpay import build_payment_gateway
from p2b.integrations.storage import build_storage
from p2b.money.router import router as money_router
from p2b.operations.professionals_router import router as professional_review_router
from p2b.operations.router import router as operations_router
from p2b.professionals.router import router as professionals_router
from p2b.projects.router import router as projects_router
from p2b.records.ops_router import router as records_ops_router
from p2b.records.router import router as records_router
from p2b.rfq.ops_router import router as rfq_ops_router
from p2b.rfq.router import router as rfq_router

API_VERSION = "v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(
        level=settings.log_level, service=settings.service_name, env=settings.env,
        release=settings.release,
    )  # fmt: skip
    init_sentry(settings)
    database = Database(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await database.dispose()

    app = FastAPI(
        title="Plan2Build API",
        version=API_VERSION,
        openapi_url=f"/api/{API_VERSION}/openapi.json" if settings.docs_enabled else None,
        docs_url=f"/api/{API_VERSION}/docs" if settings.docs_enabled else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.migration_head = health.expected_migration_head()
    app.state.storage = build_storage(settings)
    app.state.image_provider = build_image_provider(settings)
    app.state.text_provider = build_text_provider(settings)
    app.state.geocoder = build_geocoder(settings)
    app.state.payment_gateway = build_payment_gateway(settings, database)

    install_error_handlers(app)

    async def on_security_event(
        kind: str, audience: Audience | None, details: dict[str, Any]
    ) -> None:
        await record_security_event(
            database, kind=kind, severity=SecuritySeverity.WARNING, audience=audience,
            details=details,
        )  # fmt: skip

    app.add_middleware(EdgeMiddleware, settings=settings, on_security_event=on_security_event)

    app.include_router(health.router)
    api = APIRouter(prefix=f"/api/{API_VERSION}", responses=ERROR_RESPONSES)
    api.include_router(identity_router)
    api.include_router(catalog_router)
    api.include_router(projects_router)
    api.include_router(documents_router)
    api.include_router(designs_router)
    api.include_router(houseplans_router)
    api.include_router(houseplans_ops_router)
    api.include_router(professionals_router)
    api.include_router(professional_review_router)
    api.include_router(operations_router)
    api.include_router(billing_router)
    api.include_router(billing_ops_router)
    api.include_router(engagements_router)
    api.include_router(engagements_ops_router)
    api.include_router(buildplan_router)
    api.include_router(buildplan_ops_router)
    api.include_router(rfq_router)
    api.include_router(rfq_ops_router)
    api.include_router(construction_router)
    api.include_router(construction_ops_router)
    api.include_router(money_router)
    api.include_router(assurance_router)
    api.include_router(assurance_ops_router)
    api.include_router(records_router)
    api.include_router(records_ops_router)
    if settings.payment_provider == "fake":  # local development and tests only (Settings)
        api.include_router(billing_dev_router)
    app.include_router(api)
    return app
