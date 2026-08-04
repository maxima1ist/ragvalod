"""Unit tests for rerank result mapping."""

import httpx
import pytest
import respx

from rag_orchestrator.litellm_client import LiteLLMClient
from rag_orchestrator.qdrant_reader import RetrievedChunk


@pytest.mark.asyncio
@respx.mock
async def test_rerank_reorders_by_index() -> None:
    client = LiteLLMClient(
        base_url="http://litellm.test",
        api_key="sk-test",
        embedding_model_alias="embedder-default",
        query_prefix="query: ",
        reranker_model_alias="reranker-default",
        chat_model_alias="chat-default",
    )
    chunks = [
        RetrievedChunk("a", "about bananas", "s", "t", "", 0.1),
        RetrievedChunk("b", "Paris is the capital", "s", "t", "", 0.2),
        RetrievedChunk("c", "vector db", "s", "t", "", 0.3),
    ]
    respx.post("http://litellm.test/rerank").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {"index": 1, "relevance_score": 0.99},
                    {"index": 2, "relevance_score": 0.4},
                ]
            },
        )
    )
    out = await client.rerank("capital of France?", chunks, top_n=2)
    assert [c.id for c in out] == ["b", "c"]
    assert out[0].score == pytest.approx(0.99)
