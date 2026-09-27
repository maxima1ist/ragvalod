#!/usr/bin/env bash
# Debug-run Ingestion with minimal deps: Qdrant + LiteLLM + Infinity.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:${PATH}"

if docker info >/dev/null 2>&1; then
  DOCKER=(docker)
else
  DOCKER=(sudo docker)
fi

"${DOCKER[@]}" compose up -d qdrant infinity litellm

export INGESTION_GRPC_HOST="${INGESTION_GRPC_HOST:-0.0.0.0}"
export INGESTION_GRPC_PORT="${INGESTION_GRPC_PORT:-50051}"
export INGESTION_QDRANT_HOST="${INGESTION_QDRANT_HOST:-127.0.0.1}"
export INGESTION_QDRANT_HTTP_PORT="${INGESTION_QDRANT_HTTP_PORT:-6333}"
export INGESTION_QDRANT_GRPC_PORT="${INGESTION_QDRANT_GRPC_PORT:-6334}"
export INGESTION_LITELLM_BASE_URL="${INGESTION_LITELLM_BASE_URL:-http://127.0.0.1:4000}"
export INGESTION_LOCAL_FILES_DIR="${INGESTION_LOCAL_FILES_DIR:-$ROOT/data}"

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a
fi
export INGESTION_LITELLM_API_KEY="${INGESTION_LITELLM_API_KEY:-${LITELLM_MASTER_KEY:-sk-ragvalod-local}}"

echo "Ingestion debug on :${INGESTION_GRPC_PORT} (local_files=${INGESTION_LOCAL_FILES_DIR})"
uv run --package ragvalod-ingestion ragvalod-ingestion
