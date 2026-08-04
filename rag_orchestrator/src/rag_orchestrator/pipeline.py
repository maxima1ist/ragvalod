"""RAG generate pipeline: embed → search → rerank → prompt → chat."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from rag_orchestrator.config import Settings
from rag_orchestrator.litellm_client import LiteLLMClient
from rag_orchestrator.prompt import render_messages
from rag_orchestrator.qdrant_reader import QdrantReader, RetrievedChunk

logger = logging.getLogger("rag_orchestrator.pipeline")


@dataclass(slots=True)
class GenerateResult:
    answer: str
    used_chunks: list[RetrievedChunk]


class RagPipeline:
    def __init__(
        self,
        settings: Settings,
        store: QdrantReader,
        llm: LiteLLMClient,
    ) -> None:
        self._settings = settings
        self._store = store
        self._llm = llm

    async def generate(
        self,
        *,
        query: str,
        top_k: int | None,
        rerank_top_n: int | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> GenerateResult:
        top_k = top_k or self._settings.default_top_k
        rerank_top_n = rerank_top_n or self._settings.default_rerank_top_n
        temperature = self._settings.default_temperature if temperature is None else temperature
        max_tokens = max_tokens or self._settings.default_max_tokens

        logger.info(
            "generate query=%r top_k=%s rerank_top_n=%s",
            query[:200],
            top_k,
            rerank_top_n,
        )

        query_vector = await self._llm.embed_query(query)
        candidates = await self._store.search(query_vector, top_k=top_k)
        logger.info("retrieved %s candidates", len(candidates))

        used = await self._llm.rerank(query, candidates, top_n=rerank_top_n)
        logger.info("reranked to %s chunks", len(used))

        system_prompt, user_prompt = render_messages(query, used)
        answer = await self._llm.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        logger.info("answer chars=%s preview=%r", len(answer), answer[:200])
        return GenerateResult(answer=answer, used_chunks=used)
