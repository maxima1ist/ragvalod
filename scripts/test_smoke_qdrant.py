"""Integration test for Qdrant smoke (requires running Qdrant)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

ROOT = Path(__file__).resolve().parents[1]


def _qdrant_available() -> bool:
    host = os.environ.get("QDRANT_HOST", "localhost")
    http_port = int(os.environ.get("QDRANT_HTTP_PORT", "6333"))
    try:
        client = QdrantClient(
            host=host,
            port=http_port,
            prefer_grpc=False,
            timeout=2,
            check_compatibility=False,
        )
        client.get_collections()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _qdrant_available(), reason="Qdrant is not reachable on localhost:6333")
def test_smoke_qdrant_script() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "smoke_qdrant.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
