#!/usr/bin/env python3
"""Smoke-test Qdrant over gRPC: create collection, upsert, search.

Usage (Qdrant must be reachable, e.g. via `docker compose up -d qdrant`):
  uv run python scripts/smoke_qdrant.py
"""

from __future__ import annotations

import logging
import os
import sys
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as rest_models

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("smoke_qdrant")

COLLECTION = "ragvalod_smoke"
VECTOR_SIZE = 8


def main() -> int:
    host = os.environ.get("QDRANT_HOST", "localhost")
    grpc_port = int(os.environ.get("QDRANT_GRPC_PORT", "6334"))
    http_port = int(os.environ.get("QDRANT_HTTP_PORT", "6333"))

    logger.info(
        "connecting to Qdrant %s http=%s grpc=%s (prefer_grpc=True)",
        host,
        http_port,
        grpc_port,
    )
    client = QdrantClient(
        host=host,
        port=http_port,
        grpc_port=grpc_port,
        prefer_grpc=True,
        check_compatibility=False,
    )

    if client.collection_exists(COLLECTION):
        logger.info("deleting existing collection %s", COLLECTION)
        client.delete_collection(COLLECTION)

    logger.info("creating collection %s (dim=%s)", COLLECTION, VECTOR_SIZE)
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=rest_models.VectorParams(
            size=VECTOR_SIZE,
            distance=rest_models.Distance.COSINE,
        ),
    )

    point_id = str(uuid.uuid4())
    vector = [float(i) / VECTOR_SIZE for i in range(VECTOR_SIZE)]
    payload = {"text": "ragvalod smoke point", "source": "smoke"}

    logger.info("upserting point %s", point_id)
    client.upsert(
        collection_name=COLLECTION,
        points=[
            rest_models.PointStruct(id=point_id, vector=vector, payload=payload),
        ],
    )

    logger.info("searching nearest neighbors")
    hits = client.query_points(
        collection_name=COLLECTION,
        query=vector,
        limit=1,
    ).points
    if not hits:
        logger.error("search returned no hits")
        return 1

    hit = hits[0]
    logger.info("hit id=%s score=%s payload=%s", hit.id, hit.score, hit.payload)
    if hit.payload != payload:
        logger.error("payload mismatch: got %s expected %s", hit.payload, payload)
        return 1

    logger.info("cleaning up collection %s", COLLECTION)
    client.delete_collection(COLLECTION)
    logger.info("smoke_qdrant OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
