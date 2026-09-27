"""RAG Orchestrator gRPC health and data-status tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import grpc
import pytest
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from rag_orchestrator.main import RagServicer
from rag_orchestrator.pipeline import GenerateResult, RagPipeline
from rag_orchestrator.qdrant_reader import RetrievedChunk, SourceMarker
from ragvalod_proto import rag_pb2, rag_pb2_grpc


@pytest.fixture
async def rag_channel():
    store = AsyncMock()
    store.is_initialized = AsyncMock(return_value=False)
    store.list_source_markers = AsyncMock(return_value=[])
    pipeline = AsyncMock(spec=RagPipeline)

    server = grpc.aio.server()
    rag_pb2_grpc.add_RagServiceServicer_to_server(RagServicer(store, pipeline), server)
    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)

    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    try:
        yield channel, store, pipeline
    finally:
        await channel.close()
        await server.stop(grace=None)


@pytest.mark.asyncio
async def test_health_serving(rag_channel) -> None:
    channel, _, _ = rag_channel
    stub = health_pb2_grpc.HealthStub(channel)
    response = await stub.Check(health_pb2.HealthCheckRequest(service=""))
    assert response.status == health_pb2.HealthCheckResponse.SERVING


@pytest.mark.asyncio
async def test_get_data_status(rag_channel) -> None:
    channel, store, _ = rag_channel
    store.is_initialized.return_value = True
    store.list_source_markers.return_value = [
        SourceMarker(
            source_name="local_files", ingested_at="2026-08-04T00:00:00Z", document_count=2
        )
    ]
    stub = rag_pb2_grpc.RagServiceStub(channel)
    response = await stub.GetDataStatus(rag_pb2.GetDataStatusRequest())
    assert response.data_initialized is True
    assert response.sources[0].source_name == "local_files"


@pytest.mark.asyncio
async def test_generate_requires_initialized_data(rag_channel) -> None:
    channel, store, _ = rag_channel
    store.is_initialized.return_value = False
    stub = rag_pb2_grpc.RagServiceStub(channel)
    with pytest.raises(grpc.aio.AioRpcError) as exc:
        await stub.GenerateAnswer(rag_pb2.GenerateAnswerRequest(query="hi"))
    assert exc.value.code() == grpc.StatusCode.FAILED_PRECONDITION


@pytest.mark.asyncio
async def test_generate_answer_ok(rag_channel) -> None:
    channel, store, pipeline = rag_channel
    store.is_initialized.return_value = True
    pipeline.generate = AsyncMock(
        return_value=GenerateResult(
            answer="Paris",
            used_chunks=[RetrievedChunk("1", "Paris is capital", "local_files", "a.md", "", 0.9)],
        )
    )
    stub = rag_pb2_grpc.RagServiceStub(channel)
    response = await stub.GenerateAnswer(rag_pb2.GenerateAnswerRequest(query="capital?"))
    assert response.answer == "Paris"
    assert response.used_chunks[0].source == "local_files"
