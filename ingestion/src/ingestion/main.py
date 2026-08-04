"""Ingestion Service — gRPC skeleton with standard health checking."""

from __future__ import annotations

import asyncio
import logging
import sys

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from ingestion.config import Settings
from ragvalod_proto import ingestion_pb2, ingestion_pb2_grpc

settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("ingestion")


class IngestionServicer(ingestion_pb2_grpc.IngestionServiceServicer):
    """Stub implementations — real logic arrives in stage 4."""

    async def TriggerIngest(
        self,
        request: ingestion_pb2.TriggerIngestRequest,
        context: grpc.aio.ServicerContext,
    ) -> ingestion_pb2.TriggerIngestResponse:
        await context.abort(grpc.StatusCode.UNIMPLEMENTED, "TriggerIngest not implemented yet")

    async def GetJobStatus(
        self,
        request: ingestion_pb2.GetJobStatusRequest,
        context: grpc.aio.ServicerContext,
    ) -> ingestion_pb2.GetJobStatusResponse:
        await context.abort(grpc.StatusCode.UNIMPLEMENTED, "GetJobStatus not implemented yet")

    async def ListSources(
        self,
        request: ingestion_pb2.ListSourcesRequest,
        context: grpc.aio.ServicerContext,
    ) -> ingestion_pb2.ListSourcesResponse:
        return ingestion_pb2.ListSourcesResponse(sources=[])


async def serve() -> None:
    server = grpc.aio.server()
    ingestion_pb2_grpc.add_IngestionServiceServicer_to_server(IngestionServicer(), server)

    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    health_servicer.set(
        "ragvalod.ingestion.v1.IngestionService",
        health_pb2.HealthCheckResponse.SERVING,
    )

    listen_addr = f"{settings.grpc_host}:{settings.grpc_port}"
    server.add_insecure_port(listen_addr)
    logger.info("starting ingestion gRPC on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
