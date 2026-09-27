#!/usr/bin/env python3
"""Load / latency probe for local chat via Gateway.

Measures sequential and parallel POST /generate latency and rough tok/s
from max_tokens (upper bound; actual completion may be shorter).

Note: LiteLLM in-memory cache can make repeated identical queries look
instant — restart the litellm container or vary the query text.

  GATEWAY_API_KEY=… uv run python scripts/bench_local_llm.py
  uv run python scripts/bench_local_llm.py --parallel 4 --requests 8
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx


def one_generate(
    client: httpx.Client,
    headers: dict[str, str],
    query: str,
    max_tokens: int,
) -> tuple[float, int, int]:
    """Return (elapsed_sec, status_code, completion_chars)."""
    t0 = time.perf_counter()
    resp = client.post(
        "/generate",
        headers=headers,
        json={
            "query": query,
            "top_k": 10,
            "rerank_top_n": 3,
            "max_tokens": max_tokens,
            "temperature": 0.1,
        },
    )
    elapsed = time.perf_counter() - t0
    chars = 0
    if resp.status_code == 200:
        chars = len(resp.json().get("answer") or "")
    return elapsed, resp.status_code, chars


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base", default=os.environ.get("GATEWAY_BASE_URL", "http://127.0.0.1:8000")
    )
    parser.add_argument("--api-key", default=os.environ.get("GATEWAY_API_KEY", "change-me"))
    parser.add_argument(
        "--query",
        default="What is the serial of Skrygalov-amber and who may move it?",
    )
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--requests", type=int, default=4, help="total generate calls")
    parser.add_argument("--parallel", type=int, default=1, help="concurrent workers")
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args()

    headers = {"X-API-Key": args.api_key}
    # RAG + local LLM can be slow on cold start.
    timeout = httpx.Timeout(600.0, connect=30.0)

    with httpx.Client(base_url=args.base, timeout=timeout) as client:
        health = client.get("/health")
        health.raise_for_status()
        body = health.json()
        print("health:", body)
        if not body.get("data_initialized"):
            print("data_initialized=false — run ingest first", file=sys.stderr)
            return 1

        for i in range(args.warmup):
            elapsed, status, chars = one_generate(client, headers, args.query, args.max_tokens)
            print(f"warmup[{i}]: {elapsed:.2f}s status={status} chars={chars}")
            if status != 200:
                print("warmup failed", file=sys.stderr)
                return 1

        latencies: list[float] = []
        failures = 0

        def job(_: int) -> tuple[float, int, int]:
            return one_generate(client, headers, args.query, args.max_tokens)

        t_batch = time.perf_counter()
        with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
            futures = [pool.submit(job, i) for i in range(args.requests)]
            for fut in as_completed(futures):
                elapsed, status, chars = fut.result()
                latencies.append(elapsed)
                if status != 200:
                    failures += 1
                approx_tps = (args.max_tokens / elapsed) if elapsed > 0 else 0.0
                print(
                    f"req: {elapsed:.2f}s status={status} chars={chars} "
                    f"approx_max_tok/s={approx_tps:.1f}"
                )
        batch_elapsed = time.perf_counter() - t_batch

    if not latencies:
        return 1

    print("---")
    print(f"parallel={args.parallel} requests={args.requests} failures={failures}")
    print(
        f"latency_s: min={min(latencies):.2f} "
        f"p50={statistics.median(latencies):.2f} "
        f"mean={statistics.mean(latencies):.2f} "
        f"max={max(latencies):.2f}"
    )
    print(f"batch_wall_s={batch_elapsed:.2f}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
