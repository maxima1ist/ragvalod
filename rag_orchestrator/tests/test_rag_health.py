"""RAG Orchestrator gRPC health and stub tests."""

from __future__ import annotations

import grpc
import pytest
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from ragvalod_proto import rag_pb2, rag_pb2_grpc


@pytest.fixture
async def rag_channel():
    from rag_orchestrator.main import RagServicer

    server = grpc.aio.server()
    rag_pb2_grpc.add_RagServiceServicer_to_server(RagServicer(), server)
    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)

    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    channel = grpc.aio.insecure_channel(f"127.0.0.1:{port}")
    try:
        yield channel
    finally:
        await channel.close()
        await server.stop(grace=None)


@pytest.mark.asyncio
async def test_health_serving(rag_channel: grpc.aio.Channel) -> None:
    stub = health_pb2_grpc.HealthStub(rag_channel)
    response = await stub.Check(health_pb2.HealthCheckRequest(service=""))
    assert response.status == health_pb2.HealthCheckResponse.SERVING


@pytest.mark.asyncio
async def test_get_data_status_uninitialized(rag_channel: grpc.aio.Channel) -> None:
    stub = rag_pb2_grpc.RagServiceStub(rag_channel)
    response = await stub.GetDataStatus(rag_pb2.GetDataStatusRequest())
    assert response.data_initialized is False
    assert list(response.sources) == []
