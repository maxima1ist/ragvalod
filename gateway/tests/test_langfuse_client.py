"""Tests for LangfuseStatsClient HTTP aggregation."""

from __future__ import annotations

import httpx
import pytest
import respx

from gateway.langfuse_client import LangfuseStatsClient


@pytest.mark.asyncio
async def test_stats_disabled_without_keys() -> None:
    client = LangfuseStatsClient(host="http://langfuse:3000", public_key="", secret_key="")
    body = await client.fetch_stats()
    assert body["enabled"] is False


@respx.mock
@pytest.mark.asyncio
async def test_stats_aggregates_scores() -> None:
    host = "http://langfuse.test"
    respx.get(f"{host}/api/public/health").mock(
        return_value=httpx.Response(200, json={"status": "ok"})
    )
    respx.get(f"{host}/api/public/traces").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "t1",
                        "name": "rag.generate",
                        "timestamp": "2026-08-05T00:00:00.000Z",
                        "input": {"query": "q"},
                        "output": {"answer": "a"},
                    }
                ],
                "meta": {"totalItems": 1},
            },
        )
    )
    respx.get(f"{host}/api/public/scores").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {"name": "faithfulness", "value": 0.8},
                    {"name": "faithfulness", "value": 1.0},
                    {"name": "answer_relevancy", "value": 0.5},
                ]
            },
        )
    )

    client = LangfuseStatsClient(host=host, public_key="pk", secret_key="sk")
    body = await client.fetch_stats()
    assert body["enabled"] is True
    assert body["reachable"] is True
    assert body["traces"]["total_items"] == 1
    assert body["scores"]["by_name"]["faithfulness"]["count"] == 2
    assert body["scores"]["by_name"]["faithfulness"]["avg"] == pytest.approx(0.9)
