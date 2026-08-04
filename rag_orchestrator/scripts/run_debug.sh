#!/usr/bin/env bash
# Debug-run RAG Orchestrator with Qdrant + LiteLLM + Infinity.
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

export RAG_GRPC_HOST="${RAG_GRPC_HOST:-0.0.0.0}"
export RAG_GRPC_PORT="${RAG_GRPC_PORT:-50052}"
export RAG_QDRANT_HOST="${RAG_QDRANT_HOST:-127.0.0.1}"
export RAG_QDRANT_HTTP_PORT="${RAG_QDRANT_HTTP_PORT:-6333}"
export RAG_QDRANT_GRPC_PORT="${RAG_QDRANT_GRPC_PORT:-6334}"
export RAG_LITELLM_BASE_URL="${RAG_LITELLM_BASE_URL:-http://127.0.0.1:4000}"

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  source .env
  set +a
fi
export RAG_LITELLM_API_KEY="${RAG_LITELLM_API_KEY:-${LITELLM_MASTER_KEY:-sk-ragvalod-local}}"

echo "RAG Orchestrator debug on :${RAG_GRPC_PORT}"
uv run --package ragvalod-rag-orchestrator ragvalod-rag-orchestrator
