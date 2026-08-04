#!/usr/bin/env bash
# Debug-run Ingestion Service. Minimal deps: optional Qdrant via compose.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:${PATH}"

export INGESTION_GRPC_HOST="${INGESTION_GRPC_HOST:-127.0.0.1}"
export INGESTION_GRPC_PORT="${INGESTION_GRPC_PORT:-50051}"
export INGESTION_QDRANT_HOST="${INGESTION_QDRANT_HOST:-127.0.0.1}"
export INGESTION_QDRANT_GRPC_PORT="${INGESTION_QDRANT_GRPC_PORT:-6334}"

if [[ "${WITH_DEPS:-0}" == "1" ]]; then
  docker compose up -d qdrant
fi

uv run --package ragvalod-ingestion ragvalod-ingestion
