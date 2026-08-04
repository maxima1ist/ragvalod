"""RAG Orchestrator — gRPC skeleton with standard health checking."""

from __future__ import annotations

import asyncio
import logging
import sys

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from rag_orchestrator.config import Settings
from ragvalod_proto import rag_pb2, rag_pb2_grpc

settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("rag_orchestrator")


class RagServicer(rag_pb2_grpc.RagServiceServicer):
    """Stub implementations — real logic arrives in stage 5."""

    async def GenerateAnswer(
        self,
        request: rag_pb2.GenerateAnswerRequest,
        context: grpc.aio.ServicerContext,
    ) -> rag_pb2.GenerateAnswerResponse:
        await context.abort(grpc.StatusCode.UNIMPLEMENTED, "GenerateAnswer not implemented yet")

    async def GetDataStatus(
        self,
        request: rag_pb2.GetDataStatusRequest,
        context: grpc.aio.ServicerContext,
    ) -> rag_pb2.GetDataStatusResponse:
        return rag_pb2.GetDataStatusResponse(data_initialized=False, sources=[])


async def serve() -> None:
    server = grpc.aio.server()
    rag_pb2_grpc.add_RagServiceServicer_to_server(RagServicer(), server)

    health_servicer = health.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    health_servicer.set("", health_pb2.HealthCheckResponse.SERVING)
    health_servicer.set(
        "ragvalod.rag.v1.RagService",
        health_pb2.HealthCheckResponse.SERVING,
    )

    listen_addr = f"{settings.grpc_host}:{settings.grpc_port}"
    server.add_insecure_port(listen_addr)
    logger.info("starting rag_orchestrator gRPC on %s", listen_addr)
    await server.start()
    await server.wait_for_termination()


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
