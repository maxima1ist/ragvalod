"""Integration test for LiteLLM smoke (requires running LiteLLM + Infinity)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _litellm_available() -> bool:
    base = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/")
    key = os.environ.get("LITELLM_MASTER_KEY", "sk-ragvalod-local")
    try:
        response = httpx.get(
            f"{base}/health/liveliness",
            headers={"Authorization": f"Bearer {key}"},
            timeout=2.0,
        )
        return response.status_code < 500
    except Exception:
        return False


@pytest.mark.skipif(not _litellm_available(), reason="LiteLLM is not reachable on localhost:4000")
def test_smoke_litellm_script() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "smoke_litellm.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ},
    )
    assert result.returncode == 0, result.stdout + result.stderr
