"""Ingestion Service gRPC health and stub tests."""

from __future__ import annotations

import grpc
import pytest
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from ingestion.config import Settings
from ingestion.jobs import JobManager
from ingestion.main import IngestionServicer
from ingestion.pipeline.embeddings import EmbeddingClient
from ingestion.qdrant_store import QdrantDocumentStore
from ingestion.sources.factory import SourceFactory
from ragvalod_proto import ingestion_pb2, ingestion_pb2_grpc


@pytest.fixture
async def ingestion_channel():
    settings = Settings()
    factory = SourceFactory(settings)
    embeddings = EmbeddingClient(
        base_url="http://127.0.0.1:9",
        api_key="test",
        model_alias="embedder-default",
        doc_prefix="passage: ",
        batch_size=8,
    )
    store = QdrantDocumentStore(
        host="127.0.0.1",
        http_port=9,
        grpc_port=9,
        collection="documents",
        embedding_model_name="intfloat/multilingual-e5-small",
        vector_size=384,
    )
    jobs = JobManager(settings, factory, embeddings, store)

    server = grpc.aio.server()
    ingestion_pb2_grpc.add_IngestionServiceServicer_to_server(
        IngestionServicer(factory, jobs),
        server,
    )
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
        await store.close()


@pytest.mark.asyncio
async def test_health_serving(ingestion_channel: grpc.aio.Channel) -> None:
    stub = health_pb2_grpc.HealthStub(ingestion_channel)
    response = await stub.Check(health_pb2.HealthCheckRequest(service=""))
    assert response.status == health_pb2.HealthCheckResponse.SERVING


@pytest.mark.asyncio
async def test_list_sources_includes_local_files(ingestion_channel: grpc.aio.Channel) -> None:
    stub = ingestion_pb2_grpc.IngestionServiceStub(ingestion_channel)
    response = await stub.ListSources(ingestion_pb2.ListSourcesRequest())
    names = {s.name for s in response.sources}
    assert "local_files" in names
