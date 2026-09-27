#!/usr/bin/env bash
# Render kind config (absolute test_data path) and create the cluster.
#
#   scripts/kind_create.sh                  # k8s/kind-smoke.yaml
#   scripts/kind_create.sh k8s/kind-gpu.yaml
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if command -v kind >/dev/null 2>&1; then
  KIND_BIN="${KIND_BIN:-kind}"
elif [[ -x /tmp/kind ]]; then
  KIND_BIN="${KIND_BIN:-/tmp/kind}"
else
  echo "kind not found (install it or set KIND_BIN)" >&2
  exit 1
fi
NAME="${KIND_CLUSTER_NAME:-ragvalod-smoke}"
SRC="${1:-$ROOT/k8s/kind-smoke.yaml}"
RENDERED="$(mktemp --suffix=-kind.yaml)"
trap 'rm -f "$RENDERED"' EXIT

if docker info >/dev/null 2>&1; then
  DOCKER=(docker)
else
  DOCKER=(sudo docker)
fi

HF_CACHE="${RAGVALOD_HF_CACHE:-}"
if [[ -z "$HF_CACHE" ]]; then
  HF_CACHE="$("${DOCKER[@]}" volume inspect ragvalod_hf_cache --format '{{.Mountpoint}}' 2>/dev/null || true)"
fi
if [[ -z "$HF_CACHE" ]]; then
  HF_CACHE="/var/tmp/ragvalod-hf-cache"
  mkdir -p "$HF_CACHE"
fi

sed -e "s|__RAGVALOD_TEST_DATA__|$ROOT/test_data|g" \
    -e "s|__RAGVALOD_HF_CACHE__|$HF_CACHE|g" \
    "$SRC" >"$RENDERED"
"$KIND_BIN" create cluster --name "$NAME" --config "$RENDERED" --wait 5m
