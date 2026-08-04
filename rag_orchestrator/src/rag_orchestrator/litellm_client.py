"""LiteLLM OpenAI-compatible client: embeddings, rerank, chat."""

from __future__ import annotations

import httpx

from rag_orchestrator.qdrant_reader import RetrievedChunk


class LiteLLMClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        embedding_model_alias: str,
        query_prefix: str,
        reranker_model_alias: str,
        chat_model_alias: str,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._embedding_model_alias = embedding_model_alias
        self._query_prefix = query_prefix
        self._reranker_model_alias = reranker_model_alias
        self._chat_model_alias = chat_model_alias

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def embed_query(self, query: str) -> list[float]:
        text = f"{self._query_prefix}{query}" if self._query_prefix else query
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/v1/embeddings",
                headers=self._headers(),
                json={"model": self._embedding_model_alias, "input": [text]},
            )
            response.raise_for_status()
            data = response.json()["data"]
            return list(data[0]["embedding"])

    async def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int,
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []
        documents = [c.text for c in chunks]
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/rerank",
                headers=self._headers(),
                json={
                    "model": self._reranker_model_alias,
                    "query": query,
                    "documents": documents,
                    "top_n": top_n,
                },
            )
            response.raise_for_status()
            body = response.json()
            results = body.get("results") or body.get("data") or []

        reranked: list[RetrievedChunk] = []
        for item in results[:top_n]:
            index = int(item["index"])
            score = float(item.get("relevance_score") or item.get("score") or 0.0)
            base = chunks[index]
            reranked.append(
                RetrievedChunk(
                    id=base.id,
                    text=base.text,
                    source=base.source,
                    title=base.title,
                    section_path=base.section_path,
                    score=score,
                )
            )
        return reranked

    async def chat(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/v1/chat/completions",
                headers=self._headers(),
                json={
                    "model": self._chat_model_alias,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            return str(response.json()["choices"][0]["message"]["content"])
