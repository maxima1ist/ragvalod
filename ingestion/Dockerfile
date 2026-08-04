# syntax=docker/dockerfile:1
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY proto ./proto
COPY ingestion ./ingestion

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package ragvalod-ingestion

EXPOSE 50051
CMD ["ragvalod-ingestion"]
