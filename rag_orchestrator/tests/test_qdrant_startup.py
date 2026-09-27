"""Startup retry when Qdrant is not yet reachable."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from rag_orchestrator.qdrant_reader import QdrantReader


def _reader() -> QdrantReader:
    store = QdrantReader.__new__(QdrantReader)
    store._client = MagicMock()
    store._collection = "docs"
    store._embedding_model_name = "intfloat/multilingual-e5-small"
    store._vector_size = 384
    store._initialized_cached = None
    return store


@pytest.mark.asyncio
async def test_wait_for_qdrant_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _reader()
    calls = {"n": 0}

    async def _validate() -> None:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("UNAVAILABLE :6334")

    store.validate_manifest_at_startup = _validate  # type: ignore[method-assign]
    slept: list[float] = []

    async def _sleep(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr("rag_orchestrator.qdrant_reader.asyncio.sleep", _sleep)
    await store.wait_for_qdrant_at_startup(attempts=5, delay_seconds=0.01)
    assert calls["n"] == 3
    assert slept == [0.01, 0.01]


@pytest.mark.asyncio
async def test_wait_for_qdrant_does_not_retry_model_mismatch() -> None:
    store = _reader()
    store.validate_manifest_at_startup = AsyncMock(  # type: ignore[method-assign]
        side_effect=RuntimeError("embedding model mismatch")
    )
    with pytest.raises(RuntimeError, match="embedding model mismatch"):
        await store.wait_for_qdrant_at_startup(attempts=5, delay_seconds=0.01)
    store.validate_manifest_at_startup.assert_awaited_once()
