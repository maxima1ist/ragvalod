"""Unit tests for LiteLLM chat request shaping."""

from __future__ import annotations

import httpx
import pytest
import respx

from rag_orchestrator.litellm_client import LiteLLMClient


@respx.mock
@pytest.mark.asyncio
async def test_chat_folds_system_into_single_user_message() -> None:
    base = "http://litellm.test"
    route = respx.post(f"{base}/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )
    )
    llm = LiteLLMClient(
        base_url=base,
        api_key="sk-test",
        embedding_model_alias="embedder-default",
        query_prefix="query: ",
        reranker_model_alias="reranker-default",
        chat_model_alias="chat-default",
    )
    answer = await llm.chat(
        system_prompt="You are helpful.",
        user_prompt="Say hi",
        temperature=0.0,
        max_tokens=16,
    )
    assert answer == "ok"
    assert route.called
    payload = route.calls.last.request.content
    import json

    body = json.loads(payload)
    assert body["messages"] == [
        {"role": "user", "content": "You are helpful.\n\nSay hi"},
    ]
