"""Integration-style pipeline test with mocked LiteLLM HTTP."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from rag_orchestrator.config import Settings
from rag_orchestrator.litellm_client import LiteLLMClient
from rag_orchestrator.pipeline import RagPipeline
from rag_orchestrator.qdrant_reader import RetrievedChunk


@respx.mock
@pytest.mark.asyncio
async def test_pipeline_full_cycle_http_mock() -> None:
    base = "http://litellm.test"
    respx.post(f"{base}/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}]},
        )
    )
    respx.post(f"{base}/rerank").mock(
        return_value=httpx.Response(
            200,
            json={"results": [{"index": 1, "relevance_score": 0.95}]},
        )
    )
    respx.post(f"{base}/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Answer from mock"}}]},
        )
    )

    store = AsyncMock()
    store.search = AsyncMock(
        return_value=[
            RetrievedChunk("a", "first", "local_files", "a.md", "", 0.5),
            RetrievedChunk("b", "second", "local_files", "b.md", "", 0.4),
        ]
    )
    llm = LiteLLMClient(
        base_url=base,
        api_key="sk-test",
        embedding_model_alias="embedder-default",
        query_prefix="query: ",
        reranker_model_alias="reranker-default",
        chat_model_alias="chat-default",
    )
    pipeline = RagPipeline(Settings(), store, llm)
    result = await pipeline.generate(
        query="what?",
        top_k=10,
        rerank_top_n=1,
        temperature=0.1,
        max_tokens=64,
    )
    assert result.answer == "Answer from mock"
    assert len(result.used_chunks) == 1
    assert result.used_chunks[0].id == "b"
    assert result.used_chunks[0].score == pytest.approx(0.95)
    store.search.assert_awaited_once()
