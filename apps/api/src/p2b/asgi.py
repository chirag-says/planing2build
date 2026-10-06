"""ASGI entry point: `uvicorn p2b.asgi:app`."""

from p2b.main import create_app

app = create_app()
