#!/usr/bin/env bash
# Tear down the compose stack (keeps volumes by default).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if docker info >/dev/null 2>&1; then
  DOCKER=(docker)
else
  DOCKER=(sudo docker)
fi

"${DOCKER[@]}" compose --profile models --profile local-llm --profile monitoring down "$@"
