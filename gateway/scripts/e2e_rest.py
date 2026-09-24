#!/usr/bin/env python3
"""Live REST smoke against a running Gateway (stage 6.4)."""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base", default=os.environ.get("GATEWAY_BASE_URL", "http://127.0.0.1:8000")
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GATEWAY_API_KEY", "change-me"),
    )
    parser.add_argument(
        "--query",
        default="What is Markus Vileika's badge code, and which drawer may only he open?",
    )
    parser.add_argument(
        "--local-files-path",
        default=os.environ.get("E2E_LOCAL_FILES_PATH", "/test_data"),
        help="Container path for local_files ingest (smoke corpus default: /test_data)",
    )
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument(
        "--skip-generate",
        action="store_true",
        help="Stop after ingest (kind local overlay has no vLLM)",
    )
    args = parser.parse_args()

    headers = {"X-API-Key": args.api_key}
    with httpx.Client(base_url=args.base, timeout=120.0) as client:
        health = client.get("/health")
        health.raise_for_status()
        print("health:", health.json())

        sources = client.get("/sources", headers=headers)
        sources.raise_for_status()
        print("sources:", sources.json())

        if not args.skip_ingest:
            ingest = client.post(
                "/ingest",
                headers=headers,
                json={
                    "sources": [
                        {
                            "name": "local_files",
                            "options": {"path": args.local_files_path},
                        }
                    ]
                },
            )
            ingest.raise_for_status()
            job_id = ingest.json()["job_id"]
            print("job_id:", job_id)
            for _ in range(120):
                status = client.get(f"/ingest/{job_id}", headers=headers)
                status.raise_for_status()
                body = status.json()
                print("ingest:", body["state"], body.get("message"))
                if body["state"] in {"succeeded", "failed", "partial"}:
                    if body["state"] != "succeeded":
                        return 1
                    break
                time.sleep(1)
            else:
                print("ingest timeout", file=sys.stderr)
                return 1

        if args.skip_generate:
            return 0

        gen = client.post(
            "/generate",
            headers=headers,
            json={"query": args.query, "top_k": 10, "rerank_top_n": 3, "max_tokens": 256},
        )
        print("generate query:", args.query)
        print("generate status:", gen.status_code)
        print("generate body:", gen.text)
        if gen.status_code != 200:
            return 1
        answer = gen.json()["answer"]
        if "RGV-SMOKE-7F3A9C21" not in answer and "C-17" not in answer:
            print("WARN: expected smoke fact missing from answer", file=sys.stderr)
            return 2
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
