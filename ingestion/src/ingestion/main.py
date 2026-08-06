"""Ingestion Service — gRPC API with async ingest jobs and schedules."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc

from ingestion.config import Settings
from ingestion.credentials_crypto import CredentialsCrypto, CredentialsCryptoError
from ingestion.jobs import JobManager, JobState, SourceJobState
from ingestion.pipeline.embeddings import EmbeddingClient
from ingestion.qdrant_store import QdrantDocumentStore
from ingestion.schedule_store import ScheduleStore
from ingestion.scheduler import IngestScheduler
from ingestion.sources.factory import SourceFactory
from ragvalod_proto import ingestion_pb2, ingestion_pb2_grpc

settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("ingestion")

_JOB_STATE_PROTO = {
    JobState.PENDING: ingestion_pb2.JOB_STATE_PENDING,
    JobState.RUNNING: ingestion_pb2.JOB_STATE_RUNNING,
    JobState.SUCCEEDED: ingestion_pb2.JOB_STATE_SUCCEEDED,
    JobState.FAILED: ingestion_pb2.JOB_STATE_FAILED,
    JobState.PARTIAL: ingestion_pb2.JOB_STATE_PARTIAL,
}

_SOURCE_STATE_PROTO = {
    SourceJobState.PENDING: ingestion_pb2.SOURCE_JOB_STATE_PENDING,
    SourceJobState.RUNNING: ingestion_pb2.SOURCE_JOB_STATE_RUNNING,
    SourceJobState.SUCCEEDED: ingestion_pb2.SOURCE_JOB_STATE_SUCCEEDED,
    SourceJobState.FAILED: ingestion_pb2.SOURCE_JOB_STATE_FAILED,
    SourceJobState.SKIPPED: ingestion_pb2.SOURCE_JOB_STATE_SKIPPED,
}


class IngestionServicer(ingestion_pb2_grpc.IngestionServiceServicer):
    def __init__(
        self,
        factory: SourceFactory,
        jobs: JobManager,
        schedules: ScheduleStore,
        scheduler: IngestScheduler,
    ) -> None:
        self._factory = factory
        self._jobs = jobs
        self._schedules = schedules
        self._scheduler = scheduler

    async def TriggerIngest(
        self,
        request: ingestion_pb2.TriggerIngestRequest,
        context: grpc.aio.ServicerContext,
    ) -> ingestion_pb2.TriggerIngestResponse:
        requested = [
            (spec.name, dict(spec.credentials), dict(spec.options)) for spec in request.sources
        ]
        try:
            work_items = self._factory.resolve_job_sources(
                requested,
                all_with_credentials=request.all_with_credentials,
            )
        except (KeyError, ValueError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        if not work_items:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "no sources selected for ingest",
            )

        job_id = await self._jobs.start_job(work_items)
        logger.info("TriggerIngest accepted job_id=%s sources=%s", job_id, len(work_items))
        return ingestion_pb2.TriggerIngestResponse(job_id=job_id)

    async def GetJobStatus(
        self,
        request: ingestion_pb2.GetJobStatusRequest,
        context: grpc.aio.ServicerContext,
    ) -> ingestion_pb2.GetJobStatusResponse:
        record = self._jobs.get(request.job_id)
        if record is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"unknown job_id={request.job_id}")

        return ingestion_pb2.GetJobStatusResponse(
            job_id=record.job_id,
            state=_JOB_STATE_PROTO[record.state],
            message=record.message,
            sources=[
                ingestion_pb2.SourceJobStatus(
                    source_name=s.source_name,
                    state=_SOURCE_STATE_PROTO[s.state],
                    message=s.message,
                    documents_processed=s.documents_processed,
                    chunks_written=s.chunks_written,
                    error=s.error,
                )
                for s in record.sources
            ],
            started_at=record.started_at.isoformat() if record.started_at else "",
            finished_at=record.finished_at.isoformat() if record.finished_at else "",
        )

    async def ListSources(
        self,
        request: ingestion_pb2.ListSourcesRequest,
        context: grpc.aio.ServicerContext,
    ) -> ingestion_pb2.ListSourcesResponse:
        del request, context
        return ingestion_pb2.ListSourcesResponse(
            sources=[
                ingestion_pb2.SourceInfo(
                    name=info.name,
                    description=info.description,
                    requires_credentials=info.requires_credentials,
                )
                for info in self._factory.list_sources()
            ]
        )

    async def UpsertSchedule(
        self,
        request: ingestion_pb2.UpsertScheduleRequest,
        context: grpc.aio.ServicerContext,
    ) -> ingestion_pb2.UpsertScheduleResponse:
        sources = [
            (spec.name, dict(spec.credentials), dict(spec.options)) for spec in request.sources
        ]
        try:
            record = self._schedules.upsert(
                schedule_id=request.schedule_id or None,
                name=request.name,
                cron=request.cron,
                enabled=request.enabled,
                sources=sources,
                all_with_credentials=request.all_with_credentials,
            )
        except KeyError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        except (CredentialsCryptoError, ValueError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))

        self._scheduler.reload()
        return ingestion_pb2.UpsertScheduleResponse(schedule_id=record.schedule_id)

    async def ListSchedules(
        self,
        request: ingestion_pb2.ListSchedulesRequest,
        context: grpc.aio.ServicerContext,
    ) -> ingestion_pb2.ListSchedulesResponse:
        del request, context
        return ingestion_pb2.ListSchedulesResponse(
            schedules=[
                ingestion_pb2.ScheduleInfo(
                    schedule_id=s.schedule_id,
                    name=s.name,
                    cron=s.cron,
                    enabled=s.enabled,
                    source_names=s.source_names(),
                    all_with_credentials=s.all_with_credentials,
                    last_run_at=s.last_run_at,
                    last_job_id=s.last_job_id,
                    created_at=s.created_at,
                    updated_at=s.updated_at,
                )
                for s in self._schedules.list()
            ]
        )

    async def DeleteSchedule(
        self,
        request: ingestion_pb2.DeleteScheduleRequest,
        context: grpc.aio.ServicerContext,
    ) -> ingestion_pb2.DeleteScheduleResponse:
        try:
            self._schedules.delete(request.schedule_id)
        except KeyError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        self._scheduler.reload()
        return ingestion_pb2.DeleteScheduleResponse()

    async def RunSchedule(
        self,
        request: ingestion_pb2.RunScheduleRequest,
        context: grpc.aio.ServicerContext,
    ) -> ingestion_pb2.RunScheduleResponse:
        try:
            job_id = await self._scheduler.run_now(request.schedule_id)
        except KeyError as exc:
            await context.abort(grpc.StatusCode.NOT_FOUND, str(exc))
        except (CredentialsCryptoError, ValueError) as exc:
            await context.abort(grpc.StatusCode.FAILED_PRECONDITION, str(exc))
        return ingestion_pb2.RunScheduleResponse(job_id=job_id)


async def serve() -> None:
    factory = SourceFactory(settings)
    embeddings = EmbeddingClient(
        base_url=settings.litellm_base_url,
        api_key=settings.litellm_api_key,
        model_alias=settings.embedding_model_alias,
        doc_prefix=settings.embedding_doc_prefix,
        batch_size=settings.embedding_batch_size,
    )
    store = QdrantDocumentStore(
        host=settings.qdrant_host,
        http_port=settings.qdrant_http_port,
        grpc_port=settings.qdrant_grpc_port,
        collection=settings.collection_name,
        embedding_model_name=settings.embedding_model_name,
        vector_size=settings.embedding_vector_size,
    )
    jobs = JobManager(settings, factory, embeddings, store)
    crypto = CredentialsCrypto(settings.credentials_encryption_key)
    data_dir = Path(settings.data_dir)
    schedules = ScheduleStore(data_dir / "schedules.json", crypto)
    scheduler = IngestScheduler(schedules, factory, jobs)
    servicer = IngestionServicer(factory, jobs, schedules, scheduler)

    server = grpc.aio.server()
    ingestion_pb2_grpc.add_IngestionServiceServicer_to_server(servicer, server)

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
    await scheduler.start()
    await server.start()
    try:
        await server.wait_for_termination()
    finally:
        await scheduler.shutdown()
        await store.close()


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
