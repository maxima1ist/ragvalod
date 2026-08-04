"""RAG Orchestrator — gRPC service for retrieval-augmented generation."""

from __future__ import annotations

import asyncio
import logging
import sys

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from rag_orchestrator.config import Settings
from rag_orchestrator.litellm_client import LiteLLMClient
from rag_orchestrator.pipeline import RagPipeline
from rag_orchestrator.qdrant_reader import QdrantReader
from ragvalod_proto import rag_pb2, rag_pb2_grpc

settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("rag_orchestrator")


class RagServicer(rag_pb2_grpc.RagServiceServicer):
    def __init__(self, store: QdrantReader, pipeline: RagPipeline) -> None:
        self._store = store
        self._pipeline = pipeline

    async def GenerateAnswer(
        self,
        request: rag_pb2.GenerateAnswerRequest,
        context: grpc.aio.ServicerContext,
    ) -> rag_pb2.GenerateAnswerResponse:
        query = (request.query or "").strip()
        if not query:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "query must be non-empty")

        if not await self._store.is_initialized():
            await context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                "data_not_initialized: run ingest before generate",
            )

        retrieval = request.retrieval
        generation = request.generation
        result = await self._pipeline.generate(
            query=query,
            top_k=retrieval.top_k if retrieval and retrieval.top_k else None,
            rerank_top_n=retrieval.rerank_top_n if retrieval and retrieval.rerank_top_n else None,
            temperature=generation.temperature if generation and generation.temperature else None,
            max_tokens=generation.max_tokens if generation and generation.max_tokens else None,
        )
        return rag_pb2.GenerateAnswerResponse(
            answer=result.answer,
            used_chunks=[
                rag_pb2.UsedChunk(
                    id=c.id,
                    text=c.text,
                    source=c.source,
                    title=c.title,
                    section_path=c.section_path,
                    score=c.score,
                )
                for c in result.used_chunks
            ],
        )

    async def GetDataStatus(
        self,
        request: rag_pb2.GetDataStatusRequest,
        context: grpc.aio.ServicerContext,
    ) -> rag_pb2.GetDataStatusResponse:
        del request, context
        initialized = await self._store.is_initialized()
        markers = await self._store.list_source_markers()
        return rag_pb2.GetDataStatusResponse(
            data_initialized=initialized,
            sources=[
                rag_pb2.SourceMarker(
                    source_name=m.source_name,
                    ingested_at=m.ingested_at,
                    document_count=m.document_count,
                )
                for m in markers
            ],
        )


async def serve() -> None:
    store = QdrantReader(
        host=settings.qdrant_host,
        http_port=settings.qdrant_http_port,
        grpc_port=settings.qdrant_grpc_port,
        collection=settings.collection_name,
        embedding_model_name=settings.embedding_model_name,
        vector_size=settings.embedding_vector_size,
    )
    await store.validate_manifest_at_startup()

    llm = LiteLLMClient(
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
        embedding_model_alias=settings.embedding_model_alias,
        query_prefix=settings.embedding_query_prefix,
        reranker_model_alias=settings.reranker_model_alias,
        chat_model_alias=settings.chat_model_alias,
    )
    pipeline = RagPipeline(settings, store, llm)
    servicer = RagServicer(store, pipeline)

    server = grpc.aio.server()
    rag_pb2_grpc.add_RagServiceServicer_to_server(servicer, server)

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
    try:
        await server.wait_for_termination()
    finally:
        await store.close()


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
