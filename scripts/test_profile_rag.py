"""Unit tests for RAG profile report formatting."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from profile_rag import PhaseTimings, _pct, format_report  # noqa: E402


def test_pct_zero_total() -> None:
    assert _pct(1.0, 0.0) == 0.0


def test_format_report_includes_phases() -> None:
    timings = PhaseTimings(
        embed_s=0.05,
        search_s=0.02,
        rerank_s=0.8,
        prompt_s=0.001,
        chat_s=8.0,
        candidate_count=30,
        used_count=5,
    )
    text = format_report("hello?", timings, top_k=30, rerank_top_n=5)
    assert "embed:" in text
    assert "chat:" in text
    assert "total:" in text
    assert "candidates=30" in text
    assert timings.total_s == 8.871


def test_format_report_embed_cache_probe() -> None:
    timings = PhaseTimings(
        embed_s=0.1,
        search_s=0.01,
        rerank_s=0.2,
        prompt_s=0.0,
        chat_s=0.0,
        candidate_count=10,
        used_count=3,
    )
    text = format_report(
        "q",
        timings,
        top_k=10,
        rerank_top_n=3,
        embed_repeats=[0.15, 0.002, 0.001],
    )
    assert "embed cache probe" in text
