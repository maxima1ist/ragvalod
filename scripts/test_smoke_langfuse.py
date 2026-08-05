"""Unit-ish tests for smoke_langfuse helpers (no live Langfuse required)."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def test_smoke_langfuse_module_loads() -> None:
    path = Path(__file__).with_name("smoke_langfuse.py")
    spec = importlib.util.spec_from_file_location("smoke_langfuse", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert callable(mod.main)
