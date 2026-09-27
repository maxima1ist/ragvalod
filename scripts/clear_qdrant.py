#!/usr/bin/env python3
"""Delete the ragvalod documents collection from a running Qdrant.

Usage (Qdrant on localhost:6333, e.g. after `make up`):
  uv run python scripts/clear_qdrant.py

After clearing, restart rag_orchestrator so it drops the in-memory
data_initialized cache:
  docker compose restart rag_orchestrator
"""

from __future__ import annotations

import logging
import os

from qdrant_client import QdrantClient

logger = logging.getLogger("clear_qdrant")

COLLECTION = os.environ.get("QDRANT_COLLECTION", "documents")
HOST = os.environ.get("QDRANT_HOST", "localhost")
HTTP_PORT = int(os.environ.get("QDRANT_HTTP_PORT", "6333"))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    client = QdrantClient(host=HOST, port=HTTP_PORT, prefer_grpc=False, timeout=10.0)
    if not client.collection_exists(COLLECTION):
        logger.info("collection %s does not exist — nothing to delete", COLLECTION)
        return 0
    logger.info("deleting collection %s", COLLECTION)
    client.delete_collection(COLLECTION)
    logger.info(
        "done. Restart rag_orchestrator to clear data_initialized cache: "
        "docker compose restart rag_orchestrator"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
