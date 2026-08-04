#!/usr/bin/env bash
# Debug-run RAG Orchestrator. Minimal deps: optional Qdrant via compose.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:${PATH}"

export RAG_GRPC_HOST="${RAG_GRPC_HOST:-127.0.0.1}"
export RAG_GRPC_PORT="${RAG_GRPC_PORT:-50052}"
export RAG_QDRANT_HOST="${RAG_QDRANT_HOST:-127.0.0.1}"
export RAG_QDRANT_GRPC_PORT="${RAG_QDRANT_GRPC_PORT:-6334}"

if [[ "${WITH_DEPS:-0}" == "1" ]]; then
  docker compose up -d qdrant
fi

uv run --package ragvalod-rag-orchestrator ragvalod-rag-orchestrator
