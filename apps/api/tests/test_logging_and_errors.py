"""Log allow-list (contract section 14) and the error envelope for validation failures
(API_ARCHITECTURE section 1)."""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, Field

from p2b.core.errors import NotFound, install_error_handlers
from p2b.core.logging import allow_list


def test_fields_outside_the_allow_list_never_reach_the_log() -> None:
    raw = {"event": "user.contacted", "user_id": "u-1", "email": "a@b.in", "otp_code": "1"}
    event = allow_list(None, "info", raw)
    assert event == {"event": "user.contacted", "user_id": "u-1", "dropped_fields": 2}


class Body(BaseModel):
    area_sqft: int = Field(ge=300, le=12000)


def _probe_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.post("/probe")
    async def probe(body: Body) -> dict[str, int]:
        return {"area": body.area_sqft}

    @app.get("/missing")
    async def missing() -> None:
        raise NotFound

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("database password is hunter2")

    return app


async def test_validation_errors_use_the_envelope_with_a_fields_map() -> None:
    async with AsyncClient(transport=ASGITransport(app=_probe_app()), base_url="http://t") as c:
        response = await c.post("/probe", json={"area_sqft": 50})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert list(error["details"]["fields"]) == ["area_sqft"]


async def test_typed_errors_and_unexpected_errors_never_leak_internals() -> None:
    transport = ASGITransport(app=_probe_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        missing = await c.get("/missing")
        boom = await c.get("/boom")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"
    assert boom.status_code == 500
    assert boom.json()["error"]["code"] == "INTERNAL"
    assert "hunter2" not in boom.text
