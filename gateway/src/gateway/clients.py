"""Async gRPC clients for Ingestion and RAG Orchestrator."""

from __future__ import annotations

from typing import Any

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc

from ragvalod_proto import ingestion_pb2, ingestion_pb2_grpc, rag_pb2, rag_pb2_grpc


async def check_grpc_health(addr: str, *, timeout_s: float = 3.0) -> bool:
    try:
        async with grpc.aio.insecure_channel(addr) as channel:
            stub = health_pb2_grpc.HealthStub(channel)
            response = await stub.Check(
                health_pb2.HealthCheckRequest(service=""),
                timeout=timeout_s,
            )
            return response.status == health_pb2.HealthCheckResponse.SERVING
    except Exception:
        return False


class IngestionClient:
    def __init__(self, addr: str) -> None:
        self._addr = addr

    async def list_sources(self) -> list[dict[str, Any]]:
        async with grpc.aio.insecure_channel(self._addr) as channel:
            stub = ingestion_pb2_grpc.IngestionServiceStub(channel)
            response = await stub.ListSources(ingestion_pb2.ListSourcesRequest())
            return [
                {
                    "name": s.name,
                    "description": s.description,
                    "requires_credentials": s.requires_credentials,
                }
                for s in response.sources
            ]

    async def trigger_ingest(
        self,
        *,
        sources: list[dict[str, Any]],
        all_with_credentials: bool = False,
    ) -> str:
        specs = [
            ingestion_pb2.SourceSpec(
                name=s["name"],
                credentials=s.get("credentials") or {},
                options=s.get("options") or {},
            )
            for s in sources
        ]
        async with grpc.aio.insecure_channel(self._addr) as channel:
            stub = ingestion_pb2_grpc.IngestionServiceStub(channel)
            response = await stub.TriggerIngest(
                ingestion_pb2.TriggerIngestRequest(
                    sources=specs,
                    all_with_credentials=all_with_credentials,
                )
            )
            return response.job_id

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        async with grpc.aio.insecure_channel(self._addr) as channel:
            stub = ingestion_pb2_grpc.IngestionServiceStub(channel)
            response = await stub.GetJobStatus(ingestion_pb2.GetJobStatusRequest(job_id=job_id))
            return {
                "job_id": response.job_id,
                "state": _job_state_name(response.state),
                "message": response.message,
                "started_at": response.started_at,
                "finished_at": response.finished_at,
                "sources": [
                    {
                        "source_name": s.source_name,
                        "state": _source_state_name(s.state),
                        "message": s.message,
                        "documents_processed": s.documents_processed,
                        "chunks_written": s.chunks_written,
                        "error": s.error,
                    }
                    for s in response.sources
                ],
            }

    async def upsert_schedule(self, body: dict[str, Any]) -> str:
        specs = [
            ingestion_pb2.SourceSpec(
                name=s["name"],
                credentials=s.get("credentials") or {},
                options=s.get("options") or {},
            )
            for s in (body.get("sources") or [])
        ]
        async with grpc.aio.insecure_channel(self._addr) as channel:
            stub = ingestion_pb2_grpc.IngestionServiceStub(channel)
            response = await stub.UpsertSchedule(
                ingestion_pb2.UpsertScheduleRequest(
                    schedule_id=body.get("schedule_id") or "",
                    name=body["name"],
                    cron=body["cron"],
                    enabled=bool(body.get("enabled", True)),
                    sources=specs,
                    all_with_credentials=bool(body.get("all_with_credentials", False)),
                )
            )
            return response.schedule_id

    async def list_schedules(self) -> list[dict[str, Any]]:
        async with grpc.aio.insecure_channel(self._addr) as channel:
            stub = ingestion_pb2_grpc.IngestionServiceStub(channel)
            response = await stub.ListSchedules(ingestion_pb2.ListSchedulesRequest())
            return [
                {
                    "schedule_id": s.schedule_id,
                    "name": s.name,
                    "cron": s.cron,
                    "enabled": s.enabled,
                    "source_names": list(s.source_names),
                    "all_with_credentials": s.all_with_credentials,
                    "last_run_at": s.last_run_at,
                    "last_job_id": s.last_job_id,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                }
                for s in response.schedules
            ]

    async def delete_schedule(self, schedule_id: str) -> None:
        async with grpc.aio.insecure_channel(self._addr) as channel:
            stub = ingestion_pb2_grpc.IngestionServiceStub(channel)
            await stub.DeleteSchedule(ingestion_pb2.DeleteScheduleRequest(schedule_id=schedule_id))

    async def run_schedule(self, schedule_id: str) -> str:
        async with grpc.aio.insecure_channel(self._addr) as channel:
            stub = ingestion_pb2_grpc.IngestionServiceStub(channel)
            response = await stub.RunSchedule(
                ingestion_pb2.RunScheduleRequest(schedule_id=schedule_id)
            )
            return response.job_id


class RagClient:
    def __init__(self, addr: str) -> None:
        self._addr = addr

    async def get_data_status(self) -> dict[str, Any]:
        async with grpc.aio.insecure_channel(self._addr) as channel:
            stub = rag_pb2_grpc.RagServiceStub(channel)
            response = await stub.GetDataStatus(rag_pb2.GetDataStatusRequest())
            return {
                "data_initialized": response.data_initialized,
                "sources": [
                    {
                        "source_name": s.source_name,
                        "ingested_at": s.ingested_at,
                        "document_count": s.document_count,
                    }
                    for s in response.sources
                ],
            }

    async def generate_answer(
        self,
        *,
        query: str,
        top_k: int | None,
        rerank_top_n: int | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        retrieval = rag_pb2.RetrievalParams()
        if top_k is not None:
            retrieval.top_k = top_k
        if rerank_top_n is not None:
            retrieval.rerank_top_n = rerank_top_n
        generation = rag_pb2.GenerationParams()
        if temperature is not None:
            generation.temperature = temperature
        if max_tokens is not None:
            generation.max_tokens = max_tokens

        async with grpc.aio.insecure_channel(self._addr) as channel:
            stub = rag_pb2_grpc.RagServiceStub(channel)
            response = await stub.GenerateAnswer(
                rag_pb2.GenerateAnswerRequest(
                    query=query,
                    retrieval=retrieval,
                    generation=generation,
                )
            )
            return {
                "answer": response.answer,
                "used_chunks": [
                    {
                        "id": c.id,
                        "text": c.text,
                        "source": c.source,
                        "title": c.title,
                        "section_path": c.section_path,
                        "score": c.score,
                    }
                    for c in response.used_chunks
                ],
            }


def _job_state_name(state: int) -> str:
    return ingestion_pb2.JobState.Name(state).removeprefix("JOB_STATE_").lower()


def _source_state_name(state: int) -> str:
    return ingestion_pb2.SourceJobState.Name(state).removeprefix("SOURCE_JOB_STATE_").lower()
