"""Smoke: Langfuse health + ingest a minimal trace via public API.

Requires compose profile `monitoring` and seeded API keys (see .env.example).
"""

from __future__ import annotations

import os
import sys
import time
import uuid

import httpx

HOST = os.environ.get("LANGFUSE_HOST", "http://localhost:3000").rstrip("/")
PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "pk-lf-ragvalod-local")
SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "sk-lf-ragvalod-local")


def main() -> int:
    auth = (PUBLIC_KEY, SECRET_KEY)
    with httpx.Client(timeout=30.0, auth=auth) as client:
        health = client.get(f"{HOST}/api/public/health")
        health.raise_for_status()
        print(f"health: {health.json()}")

        trace_id = str(uuid.uuid4())
        now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
        batch = {
            "batch": [
                {
                    "id": str(uuid.uuid4()),
                    "type": "trace-create",
                    "timestamp": now,
                    "body": {
                        "id": trace_id,
                        "name": "smoke.langfuse",
                        "input": {"query": "ping"},
                        "output": {"answer": "pong"},
                        "metadata": {"source": "smoke_langfuse"},
                    },
                }
            ]
        }
        ingest = client.post(f"{HOST}/api/public/ingestion", json=batch)
        ingest.raise_for_status()
        print(f"ingested trace_id={trace_id} status={ingest.status_code}")

        # Brief wait for async processing.
        time.sleep(1.5)
        traces = client.get(f"{HOST}/api/public/traces", params={"limit": 5})
        traces.raise_for_status()
        data = traces.json().get("data") or []
        ids = {t.get("id") for t in data}
        if trace_id not in ids:
            # Soft check: list may lag; health+ingest OK is enough for smoke.
            print(f"warn: trace not yet in list (got {len(data)} recent); ingest OK")
        else:
            print("trace visible in /api/public/traces")

    print("OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
