#!/usr/bin/env bash
# Bring up the full base stack (Qdrant + service skeletons).
# LiteLLM / Infinity: docker compose --profile models up -d  (stage 3)
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

"${DOCKER[@]}" compose up -d --build "$@"
"${DOCKER[@]}" compose ps
