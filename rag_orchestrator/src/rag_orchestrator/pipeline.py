"""RAG generate pipeline: embed → search → rerank → prompt → chat."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from rag_orchestrator.config import Settings
from rag_orchestrator.litellm_client import LiteLLMClient
from rag_orchestrator.prompt import render_messages
from rag_orchestrator.qdrant_reader import QdrantReader, RetrievedChunk
from rag_orchestrator.tracing import NoOpTracer, Tracer, chunk_payloads

logger = logging.getLogger("rag_orchestrator.pipeline")


@dataclass(slots=True)
class GenerateResult:
    answer: str
    used_chunks: list[RetrievedChunk]
    trace_id: str | None = None


class RagPipeline:
    def __init__(
        self,
        settings: Settings,
        store: QdrantReader,
        llm: LiteLLMClient,
        tracer: Tracer | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._llm = llm
        self._tracer: Tracer = tracer or NoOpTracer()

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

        with self._tracer.start_trace(
            "rag.generate",
            input={"query": query},
            metadata={"top_k": top_k, "rerank_top_n": rerank_top_n},
        ) as trace:
            embed_span = trace.span("embed_query", input={"query": query})
            query_vector = await self._llm.embed_query(query)
            embed_span.end(output={"dims": len(query_vector)})

            search_span = trace.span("vector_search", metadata={"top_k": top_k})
            candidates = await self._store.search(query_vector, top_k=top_k)
            search_span.end(
                output={"count": len(candidates)},
                metadata={"candidates": chunk_payloads(candidates, text_limit=200)},
            )
            logger.info("retrieved %s candidates", len(candidates))

            rerank_span = trace.span(
                "rerank",
                metadata={"rerank_top_n": rerank_top_n, "candidate_count": len(candidates)},
            )
            used = await self._llm.rerank(query, candidates, top_n=rerank_top_n)
            rerank_span.end(
                output={"count": len(used)},
                metadata={"used_chunks": chunk_payloads(used)},
            )
            logger.info("reranked to %s chunks", len(used))

            system_prompt, user_prompt = render_messages(query, used)
            prompt_span = trace.span(
                "prompt",
                metadata={
                    "system_chars": len(system_prompt),
                    "user_chars": len(user_prompt),
                },
            )
            # Persist full prompts for debug; truncate only in logs.
            prompt_span.end(
                output={
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                }
            )

            answer = await self._llm.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            trace.generation(
                "chat",
                model=self._settings.chat_model_alias,
                input={
                    "system": system_prompt,
                    "user": user_prompt,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
                output=answer,
            )
            logger.info("answer chars=%s preview=%r", len(answer), answer[:200])

            used_payload = chunk_payloads(used)
            trace.update(
                output={"answer": answer},
                metadata={
                    "used_chunks": used_payload,
                    "chunk_ids": [c["id"] for c in used_payload],
                    "sources": sorted({c["source"] for c in used_payload if c["source"]}),
                },
            )
            return GenerateResult(answer=answer, used_chunks=used, trace_id=trace.id)
