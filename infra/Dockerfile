FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1

RUN python -m pip install --no-cache-dir uv==0.11.32

WORKDIR /workspace

COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend

RUN uv sync --locked --no-dev --no-editable \
    && useradd --create-home --uid 10001 plantnexus

ENV PATH="/workspace/.venv/bin:${PATH}"

USER plantnexus

CMD ["uvicorn", "app.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
