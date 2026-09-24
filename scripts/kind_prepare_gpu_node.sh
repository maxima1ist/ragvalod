#!/usr/bin/env bash
# Copy host NVIDIA userspace into a kind node (device plugin is not enough:
# kind's containerd has no NVIDIA Container Toolkit).
#
#   scripts/kind_create.sh k8s/kind-gpu.yaml
#   scripts/kind_prepare_gpu_node.sh ragvalod-smoke-control-plane
set -euo pipefail

NODE=${1:-ragvalod-smoke-control-plane}

if docker info >/dev/null 2>&1; then
  DOCKER=(docker)
else
  DOCKER=(sudo docker)
fi

if ! "${DOCKER[@]}" inspect "$NODE" >/dev/null 2>&1; then
  echo "kind node container not found: $NODE" >&2
  exit 1
fi

"${DOCKER[@]}" cp /usr/bin/nvidia-smi "$NODE:/usr/local/bin/nvidia-smi"

libdir=/usr/lib/x86_64-linux-gnu
for lib in libcuda.so.1 libnvidia-ml.so.1; do
  if [[ -e "$libdir/$lib" ]]; then
    "${DOCKER[@]}" cp "$libdir/$lib" "$NODE:$libdir/$lib"
    target=$(readlink -f "$libdir/$lib" || true)
    if [[ -n "$target" && "$target" != "$libdir/$lib" && -e "$target" ]]; then
      "${DOCKER[@]}" cp "$target" "$NODE:$target"
    fi
  fi
done

"${DOCKER[@]}" exec "$NODE" ldconfig
"${DOCKER[@]}" exec "$NODE" nvidia-smi -L

echo
echo "To reuse Compose HF weights, recreate kind with extraMount:"
if mp=$("${DOCKER[@]}" volume inspect ragvalod_hf_cache --format '{{.Mountpoint}}' 2>/dev/null); then
  echo "  hostPath: $mp"
  echo "  containerPath: /hf-cache"
else
  echo "  (volume ragvalod_hf_cache not found — run make up-local-llm first)"
fi
