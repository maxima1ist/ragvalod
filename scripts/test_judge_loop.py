"""Unit tests for the hourly judge loop."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from judge_loop import interval_seconds, loop_argv, run_loop  # noqa: E402


def test_loop_argv_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_LIMIT", "2")
    monkeypatch.setenv("JUDGE_DRY_RUN", "1")
    assert loop_argv() == ["--limit", "2", "--dry-run"]


def test_interval_rejects_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_INTERVAL_SECONDS", "0")
    with pytest.raises(SystemExit, match=">="):
        interval_seconds()


def test_run_loop_stops_after_iterations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_INTERVAL_SECONDS", "3600")
    monkeypatch.setenv("JUDGE_ITERATIONS", "2")
    monkeypatch.delenv("JUDGE_DRY_RUN", raising=False)
    calls: list[list[str]] = []
    slept: list[float] = []
    clock = {"now": 0.0}

    def run_once(argv: list[str]) -> int:
        calls.append(argv)
        clock["now"] += 5
        return 0

    def sleep(seconds: float) -> None:
        slept.append(seconds)
        clock["now"] += seconds

    code = run_loop(run_once=run_once, sleep=sleep, clock=lambda: clock["now"])

    assert code == 0
    assert calls == [["--limit", "5"], ["--limit", "5"]]
    assert slept == [3595.0]


def test_run_loop_continues_after_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_INTERVAL_SECONDS", "10")
    monkeypatch.setenv("JUDGE_ITERATIONS", "2")
    calls = {"n": 0}

    def run_once(_argv: list[str]) -> int:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("langfuse down")
        return 0

    code = run_loop(run_once=run_once, sleep=lambda _seconds: None, clock=lambda: 0.0)

    assert code == 0
    assert calls["n"] == 2
