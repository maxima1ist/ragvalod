# syntax=docker/dockerfile:1
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=120 \
    UV_HTTP_RETRIES=5 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY proto ./proto
COPY rag_orchestrator ./rag_orchestrator

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package ragvalod-rag-orchestrator \
    || (sleep 5 && uv sync --frozen --no-dev --package ragvalod-rag-orchestrator) \
    || (sleep 15 && uv sync --frozen --no-dev --package ragvalod-rag-orchestrator) \
    || (sleep 30 && uv sync --frozen --no-dev --package ragvalod-rag-orchestrator)

EXPOSE 50052
CMD ["ragvalod-rag-orchestrator"]
