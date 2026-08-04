"""Embeddings via LiteLLM OpenAI-compatible API."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("ingestion.embeddings")


class EmbeddingClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model_alias: str,
        doc_prefix: str,
        batch_size: int,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model_alias = model_alias
        self._doc_prefix = doc_prefix
        self._batch_size = batch_size

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        async with httpx.AsyncClient(timeout=120.0) as client:
            for start in range(0, len(texts), self._batch_size):
                batch = texts[start : start + self._batch_size]
                prefixed = [f"{self._doc_prefix}{t}" if self._doc_prefix else t for t in batch]
                logger.info(
                    "embedding batch %s-%s via %s",
                    start,
                    start + len(batch) - 1,
                    self._model_alias,
                )
                response = await client.post(
                    f"{self._base_url}/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self._model_alias, "input": prefixed},
                )
                response.raise_for_status()
                data = response.json()["data"]
                data_sorted = sorted(data, key=lambda item: item["index"])
                vectors.extend(item["embedding"] for item in data_sorted)
        return vectors
