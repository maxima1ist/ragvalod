#!/usr/bin/env bash
# Debug-run Gateway alone (no compose dependencies required for the skeleton).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:${PATH}"

export GATEWAY_HOST="${GATEWAY_HOST:-127.0.0.1}"
export GATEWAY_PORT="${GATEWAY_PORT:-8000}"
export GATEWAY_INGESTION_GRPC_ADDR="${GATEWAY_INGESTION_GRPC_ADDR:-127.0.0.1:50051}"
export GATEWAY_RAG_GRPC_ADDR="${GATEWAY_RAG_GRPC_ADDR:-127.0.0.1:50052}"

uv run --package ragvalod-gateway ragvalod-gateway
