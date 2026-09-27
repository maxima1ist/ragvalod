#!/usr/bin/env python3
"""Repeat the judge on a fixed interval.

Compose service ``judge`` (profile ``monitoring``) runs this loop, defaulting
to one pass per hour. Kubernetes uses a CronJob and calls ``judge_traces.py``
directly, so the schedule is not doubled.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable

from judge_traces import main


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def loop_argv() -> list[str]:
    limit = os.environ.get("JUDGE_LIMIT", "5").strip() or "5"
    argv = ["--limit", limit]
    if _flag("JUDGE_DRY_RUN"):
        argv.append("--dry-run")
    return argv


def interval_seconds() -> int:
    raw = os.environ.get("JUDGE_INTERVAL_SECONDS", "3600").strip() or "3600"
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"JUDGE_INTERVAL_SECONDS must be an integer, got {raw!r}") from exc
    if value < 1:
        raise SystemExit("JUDGE_INTERVAL_SECONDS must be >= 1")
    return value


def iteration_limit() -> int | None:
    raw = os.environ.get("JUDGE_ITERATIONS", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"JUDGE_ITERATIONS must be an integer, got {raw!r}") from exc
    if value < 1:
        raise SystemExit("JUDGE_ITERATIONS must be >= 1")
    return value


def run_loop(
    *,
    run_once: Callable[[list[str]], int] = main,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    interval = interval_seconds()
    iterations = iteration_limit()
    argv = loop_argv()
    completed = 0
    last = 0
    while iterations is None or completed < iterations:
        print(f"judge tick interval={interval}s argv={argv}", flush=True)
        started = clock()
        try:
            last = run_once(argv)
        except Exception as exc:  # noqa: BLE001 — keep the loop alive
            print(f"FAIL: {exc}", file=sys.stderr)
            last = 1
        completed += 1
        if iterations is not None and completed >= iterations:
            return last
        remaining = interval - (clock() - started)
        if remaining > 0:
            sleep(remaining)
    return last


def main_loop() -> int:
    try:
        return run_loop()
    except SystemExit as exc:
        if exc.code not in (None, 0):
            print(f"FAIL: {exc}", file=sys.stderr)
            return int(exc.code) if isinstance(exc.code, int) else 1
        raise


if __name__ == "__main__":
    raise SystemExit(main_loop())
