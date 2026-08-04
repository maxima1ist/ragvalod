#!/usr/bin/env bash
# Debug-run Gateway against local compose stack (ingestion/rag/litellm).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:${PATH}"

if docker info >/dev/null 2>&1; then
  DOCKER=(docker)
else
  DOCKER=(sudo docker)
fi

"${DOCKER[@]}" compose up -d qdrant infinity litellm ingestion rag_orchestrator

export GATEWAY_HOST="${GATEWAY_HOST:-0.0.0.0}"
export GATEWAY_PORT="${GATEWAY_PORT:-8000}"
export GATEWAY_INGESTION_GRPC_ADDR="${GATEWAY_INGESTION_GRPC_ADDR:-127.0.0.1:50051}"
export GATEWAY_RAG_GRPC_ADDR="${GATEWAY_RAG_GRPC_ADDR:-127.0.0.1:50052}"
export GATEWAY_LITELLM_BASE_URL="${GATEWAY_LITELLM_BASE_URL:-http://127.0.0.1:4000}"

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a
fi

echo "Gateway debug on :${GATEWAY_PORT}"
uv run --package ragvalod-gateway ragvalod-gateway
