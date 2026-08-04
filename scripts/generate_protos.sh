#!/usr/bin/env bash
# Generate Python gRPC stubs from proto/ into proto/ragvalod_proto/.
# Do not edit generated files by hand.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:${PATH}"

OUT_DIR="${ROOT}/proto/ragvalod_proto"
mkdir -p "${OUT_DIR}"

uv run python -m grpc_tools.protoc \
  -I "${ROOT}/proto" \
  --python_out="${OUT_DIR}" \
  --grpc_python_out="${OUT_DIR}" \
  --pyi_out="${OUT_DIR}" \
  "${ROOT}/proto/ingestion.proto" \
  "${ROOT}/proto/rag.proto"

uv run python - <<'PY'
from pathlib import Path

out = Path("proto/ragvalod_proto")
for path in out.glob("*_pb2_grpc.py"):
    text = path.read_text()
    lines = []
    for line in text.splitlines(keepends=True):
        if line.startswith("import ") and "_pb2 as " in line and "grpc" not in line:
            mod = line.split()[1]
            rest = line[len(f"import {mod}") :]
            line = f"from . import {mod}{rest}"
        lines.append(line)
    path.write_text("".join(lines))

(out / "__init__.py").write_text(
    '"""Generated gRPC stubs. Regenerate via scripts/generate_protos.sh — do not edit."""\n'
    "from . import ingestion_pb2, ingestion_pb2_grpc, rag_pb2, rag_pb2_grpc\n\n"
    '__all__ = ["ingestion_pb2", "ingestion_pb2_grpc", "rag_pb2", "rag_pb2_grpc"]\n'
)
print(f"Generated stubs in {out.resolve()}")
PY

echo "OK: gRPC stubs generated"
