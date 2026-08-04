"""Ingestion Service gRPC health and stub tests."""

from __future__ import annotations

import grpc
import pytest
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from ragvalod_proto import ingestion_pb2, ingestion_pb2_grpc


@pytest.fixture
async def ingestion_channel():
    from ingestion.main import IngestionServicer

    server = grpc.aio.server()
    ingestion_pb2_grpc.add_IngestionServiceServicer_to_server(IngestionServicer(), server)
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
async def test_health_serving(ingestion_channel: grpc.aio.Channel) -> None:
    stub = health_pb2_grpc.HealthStub(ingestion_channel)
    response = await stub.Check(health_pb2.HealthCheckRequest(service=""))
    assert response.status == health_pb2.HealthCheckResponse.SERVING


@pytest.mark.asyncio
async def test_list_sources_empty(ingestion_channel: grpc.aio.Channel) -> None:
    stub = ingestion_pb2_grpc.IngestionServiceStub(ingestion_channel)
    response = await stub.ListSources(ingestion_pb2.ListSourcesRequest())
    assert list(response.sources) == []
