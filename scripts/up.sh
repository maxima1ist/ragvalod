#!/usr/bin/env bash
# Bring up the full base stack (Qdrant + services + LiteLLM + Infinity).
# Optional: docker compose --profile local-llm up -d
# Optional: docker compose --profile monitoring up -d
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

if docker info >/dev/null 2>&1; then
  DOCKER=(docker)
else
  DOCKER=(sudo docker)
fi

# Profiles must precede the subcommand: compose --profile X up …
"${DOCKER[@]}" compose "$@" up -d --build
"${DOCKER[@]}" compose "$@" ps
