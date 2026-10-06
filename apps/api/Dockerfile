# One image, two commands: API (uvicorn) and worker (python -m p2b.worker). ADR-002, ADR-005.
FROM python:3.12-slim-bookworm AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH=/app/.venv/bin:$PATH

COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv

# A Unicode font for invoice PDFs (names and addresses in any script).
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
ENV P2B_INVOICE_FONT_PATH=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src
RUN uv sync --frozen --no-dev \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin app

USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status != 200)"
CMD ["uvicorn", "p2b.asgi:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--no-access-log"]
