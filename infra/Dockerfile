FROM python:3.12.13-slim-bookworm

ARG APS_RUNTIME_VERSION=0.1.0
ARG APS_APPLICATION_VERSION=0.0.0
ARG APS_SCHEMA_VERSION=2.10.0
ARG APS_CODE_COMMIT=uncommitted

LABEL org.opencontainers.image.title="PlantNexus APS Runtime" \
    org.opencontainers.image.version="${APS_RUNTIME_VERSION}" \
    org.opencontainers.image.revision="${APS_CODE_COMMIT}" \
    io.plantnexus.aps.application.version="${APS_APPLICATION_VERSION}" \
    io.plantnexus.aps.schema.version="${APS_SCHEMA_VERSION}" \
    io.plantnexus.aps.release.input="P8-09-derived-not-production-digest-pinned"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1

RUN python -m pip install --no-cache-dir uv==0.11.32

WORKDIR /workspace

COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
COPY alembic.ini ./alembic.ini
COPY schemas ./schemas
COPY infra/release ./infra/release

RUN uv sync --locked --no-dev --no-editable \
    && useradd --create-home --uid 10001 plantnexus

ENV PATH="/workspace/.venv/bin:${PATH}"

USER plantnexus

CMD ["uvicorn", "app.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
