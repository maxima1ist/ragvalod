"""Qdrant read path for RAG: readiness markers, manifest check, vector search."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as rest_models

logger = logging.getLogger("rag_orchestrator.qdrant")

_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
MANIFEST_KEY = "__manifest__"
INIT_MARKER_KEY = "__init_marker__"


def deterministic_id(key: str) -> str:
    return str(uuid.uuid5(_NS, key))


@dataclass(slots=True)
class RetrievedChunk:
    id: str
    text: str
    source: str
    title: str
    section_path: str
    score: float


@dataclass(slots=True)
class SourceMarker:
    source_name: str
    ingested_at: str
    document_count: int


class QdrantReader:
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
        self._initialized_cached: bool | None = None

    async def close(self) -> None:
        await self._client.close()

    async def validate_manifest_at_startup(self) -> None:
        """Fail hard on model mismatch; tolerate missing collection (cold start)."""
        exists = await self._client.collection_exists(self._collection)
        if not exists:
            logger.warning(
                "collection %s missing — waiting for ingest before GenerateAnswer",
                self._collection,
            )
            return
        manifest = await self._get_payload(MANIFEST_KEY)
        if not manifest:
            logger.warning("collection %s has no manifest yet", self._collection)
            return
        stored = manifest.get("embedding_model")
        if stored != self._embedding_model_name:
            raise RuntimeError(
                f"embedding model mismatch: qdrant={stored!r} config={self._embedding_model_name!r}"
            )
        stored_dim = int(manifest.get("vector_size") or 0)
        if stored_dim and stored_dim != self._vector_size:
            raise RuntimeError(
                f"vector size mismatch: qdrant={stored_dim} config={self._vector_size}"
            )
        logger.info(
            "manifest ok model=%s dim=%s",
            self._embedding_model_name,
            self._vector_size,
        )

    async def is_initialized(self) -> bool:
        if self._initialized_cached is True:
            return True
        payload = await self._get_payload(INIT_MARKER_KEY)
        ready = bool(payload and payload.get("kind") == "init_marker")
        if ready:
            self._initialized_cached = True
        return ready

    async def list_source_markers(self) -> list[SourceMarker]:
        exists = await self._client.collection_exists(self._collection)
        if not exists:
            return []
        points, _ = await self._client.scroll(
            collection_name=self._collection,
            scroll_filter=rest_models.Filter(
                must=[
                    rest_models.FieldCondition(
                        key="kind",
                        match=rest_models.MatchValue(value="source_marker"),
                    )
                ]
            ),
            limit=100,
            with_payload=True,
            with_vectors=False,
        )
        markers: list[SourceMarker] = []
        for point in points:
            payload = point.payload or {}
            markers.append(
                SourceMarker(
                    source_name=str(payload.get("source_name") or ""),
                    ingested_at=str(payload.get("ingested_at") or ""),
                    document_count=int(payload.get("document_count") or 0),
                )
            )
        return markers

    async def search(self, vector: list[float], top_k: int) -> list[RetrievedChunk]:
        response = await self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=top_k,
            query_filter=rest_models.Filter(
                must=[
                    rest_models.FieldCondition(
                        key="kind",
                        match=rest_models.MatchValue(value="chunk"),
                    )
                ]
            ),
            with_payload=True,
        )
        results: list[RetrievedChunk] = []
        for hit in response.points:
            payload = hit.payload or {}
            results.append(
                RetrievedChunk(
                    id=str(hit.id),
                    text=str(payload.get("text") or ""),
                    source=str(payload.get("source") or ""),
                    title=str(payload.get("title") or ""),
                    section_path=str(payload.get("section_path") or ""),
                    score=float(hit.score or 0.0),
                )
            )
        return results

    async def _get_payload(self, key: str) -> dict[str, Any] | None:
        exists = await self._client.collection_exists(self._collection)
        if not exists:
            return None
        points = await self._client.retrieve(
            collection_name=self._collection,
            ids=[deterministic_id(key)],
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            return None
        return dict(points[0].payload or {})
