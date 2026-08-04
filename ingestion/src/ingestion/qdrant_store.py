"""Qdrant persistence: collection, chunk upsert, manifest and readiness markers."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as rest_models

from ingestion.pipeline.chunking import Chunk

logger = logging.getLogger("ingestion.qdrant")

_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # URL namespace
MANIFEST_KEY = "__manifest__"
INIT_MARKER_KEY = "__init_marker__"


def deterministic_id(key: str) -> str:
    return str(uuid.uuid5(_NS, key))


class QdrantDocumentStore:
    def __init__(
        self,
        *,
        host: str,
        http_port: int,
        grpc_port: int,
        collection: str,
        embedding_model_name: str,
        vector_size: int,
    ) -> None:
        self._client = AsyncQdrantClient(
            host=host,
            port=http_port,
            grpc_port=grpc_port,
            prefer_grpc=True,
            check_compatibility=False,
        )
        self._collection = collection
        self._embedding_model_name = embedding_model_name
        self._vector_size = vector_size

    async def close(self) -> None:
        await self._client.close()

    async def ensure_collection(self) -> None:
        exists = await self._client.collection_exists(self._collection)
        if not exists:
            logger.info(
                "creating collection %s dim=%s model=%s",
                self._collection,
                self._vector_size,
                self._embedding_model_name,
            )
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=rest_models.VectorParams(
                    size=self._vector_size,
                    distance=rest_models.Distance.COSINE,
                ),
            )
            await self._upsert_service_point(
                MANIFEST_KEY,
                {
                    "kind": "manifest",
                    "embedding_model": self._embedding_model_name,
                    "vector_size": self._vector_size,
                },
            )
            return

        manifest = await self._get_payload(MANIFEST_KEY)
        if not manifest:
            raise RuntimeError(
                f"collection '{self._collection}' exists but has no embedding manifest; "
                "refusing to write"
            )
        stored_model = manifest.get("embedding_model")
        if stored_model != self._embedding_model_name:
            raise RuntimeError(
                f"embedding model mismatch for collection '{self._collection}': "
                f"stored={stored_model!r} config={self._embedding_model_name!r}"
            )
        stored_dim = int(manifest.get("vector_size") or 0)
        if stored_dim and stored_dim != self._vector_size:
            raise RuntimeError(
                f"vector size mismatch for collection '{self._collection}': "
                f"stored={stored_dim} config={self._vector_size}"
            )

    async def upsert_chunks(self, chunks: list[Chunk], vectors: list[list[float]]) -> int:
        if len(chunks) != len(vectors):
            raise ValueError("chunks/vectors length mismatch")
        if not chunks:
            return 0
        points = [
            rest_models.PointStruct(
                id=deterministic_id(chunk.chunk_id_key),
                vector=vector,
                payload={
                    "kind": "chunk",
                    "text": chunk.text,
                    "source": chunk.source,
                    "title": chunk.title,
                    "section_path": chunk.section_path,
                    "chunk_index": chunk.chunk_index,
                    "doc_id": chunk.doc_id,
                    "uri": chunk.uri,
                },
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        await self._client.upsert(collection_name=self._collection, points=points)
        return len(points)

    async def write_source_marker(self, source: str, document_count: int) -> None:
        await self._upsert_service_point(
            f"__source_marker__:{source}",
            {
                "kind": "source_marker",
                "source_name": source,
                "ingested_at": datetime.now(UTC).isoformat(),
                "document_count": document_count,
            },
        )

    async def is_initialized(self) -> bool:
        payload = await self._get_payload(INIT_MARKER_KEY)
        return bool(payload and payload.get("kind") == "init_marker")

    async def write_init_marker_once(self) -> bool:
        """Write-once initialization marker. Returns True if written now."""
        if await self.is_initialized():
            return False
        await self._upsert_service_point(
            INIT_MARKER_KEY,
            {
                "kind": "init_marker",
                "initialized_at": datetime.now(UTC).isoformat(),
            },
        )
        return True

    async def _upsert_service_point(self, key: str, payload: dict[str, Any]) -> None:
        zero = [0.0] * self._vector_size
        await self._client.upsert(
            collection_name=self._collection,
            points=[
                rest_models.PointStruct(
                    id=deterministic_id(key),
                    vector=zero,
                    payload=payload,
                )
            ],
        )

    async def _get_payload(self, key: str) -> dict[str, Any] | None:
        point_id = deterministic_id(key)
        points = await self._client.retrieve(
            collection_name=self._collection,
            ids=[point_id],
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            return None
        payload = points[0].payload or {}
        return dict(payload)
