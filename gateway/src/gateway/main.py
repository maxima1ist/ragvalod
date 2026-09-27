"""API Gateway — REST entrypoint for ragvalod."""

from __future__ import annotations

import logging
import sys

import grpc
import httpx
import uvicorn
from fastapi import Depends, FastAPI, HTTPException

from gateway.auth import require_api_key
from gateway.clients import IngestionClient, RagClient, check_grpc_health
from gateway.config import Settings
from gateway.errors import http_exception_handler, raise_from_grpc
from gateway.langfuse_client import LangfuseStatsClient
from gateway.schemas import (
    GenerateRequest,
    GenerateResponse,
    IngestRequest,
    IngestResponse,
    RunScheduleResponse,
    ScheduleInfo,
    SourceInfo,
    UpsertScheduleRequest,
    UpsertScheduleResponse,
    UsedChunk,
)

settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("gateway")

app = FastAPI(title="ragvalod-gateway", version="0.1.0")
app.add_exception_handler(HTTPException, http_exception_handler)

ingestion = IngestionClient(settings.ingestion_grpc_addr)
rag = RagClient(settings.rag_grpc_addr)
langfuse_stats = LangfuseStatsClient(
    host=settings.langfuse_host,
    public_key=settings.langfuse_public_key,
    secret_key=settings.langfuse_secret_key,
)


@app.get("/health")
async def health() -> dict:
    """Aggregated readiness: sibling services + data markers from RAG."""
    ingestion_ok = await check_grpc_health(settings.ingestion_grpc_addr)
    rag_ok = await check_grpc_health(settings.rag_grpc_addr)
    litellm_ok = await _check_litellm(settings.litellm_base_url)

    data_initialized = False
    sources: list[dict] = []
    if rag_ok:
        try:
            status = await rag.get_data_status()
            data_initialized = bool(status["data_initialized"])
            sources = status["sources"]
        except Exception as exc:  # noqa: BLE001 — health must not fail hard
            logger.warning("GetDataStatus failed: %s", exc)
            rag_ok = False

    overall = "ok" if (ingestion_ok and rag_ok and litellm_ok) else "degraded"
    return {
        "status": overall,
        "service": "gateway",
        "data_initialized": data_initialized,
        "sources": sources,
        "dependencies": {
            "ingestion": "up" if ingestion_ok else "down",
            "rag_orchestrator": "up" if rag_ok else "down",
            "litellm": "up" if litellm_ok else "down",
        },
    }


@app.get("/sources", dependencies=[Depends(require_api_key)])
async def list_sources() -> dict[str, list[SourceInfo]]:
    try:
        rows = await ingestion.list_sources()
    except grpc.aio.AioRpcError as exc:
        raise_from_grpc(exc)
    return {"sources": [SourceInfo(**row) for row in rows]}


@app.post("/ingest", dependencies=[Depends(require_api_key)])
async def trigger_ingest(body: IngestRequest) -> IngestResponse:
    if not body.sources and not body.all_with_credentials:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_argument",
                "message": "sources or all_with_credentials required",
            },
        )
    try:
        job_id = await ingestion.trigger_ingest(
            sources=[s.model_dump() for s in body.sources],
            all_with_credentials=body.all_with_credentials,
        )
    except grpc.aio.AioRpcError as exc:
        raise_from_grpc(exc)
    return IngestResponse(job_id=job_id)


@app.get("/ingest/{job_id}", dependencies=[Depends(require_api_key)])
async def get_ingest_job(job_id: str) -> dict:
    try:
        return await ingestion.get_job_status(job_id)
    except grpc.aio.AioRpcError as exc:
        raise_from_grpc(exc)


@app.post("/schedules", dependencies=[Depends(require_api_key)])
async def upsert_schedule(body: UpsertScheduleRequest) -> UpsertScheduleResponse:
    if not body.sources and not body.all_with_credentials:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_argument",
                "message": "sources or all_with_credentials required",
            },
        )
    try:
        schedule_id = await ingestion.upsert_schedule(body.model_dump())
    except grpc.aio.AioRpcError as exc:
        raise_from_grpc(exc)
    return UpsertScheduleResponse(schedule_id=schedule_id)


@app.get("/schedules", dependencies=[Depends(require_api_key)])
async def list_schedules() -> dict[str, list[ScheduleInfo]]:
    try:
        rows = await ingestion.list_schedules()
    except grpc.aio.AioRpcError as exc:
        raise_from_grpc(exc)
    return {"schedules": [ScheduleInfo(**row) for row in rows]}


@app.delete("/documents", dependencies=[Depends(require_api_key)])
async def delete_document(source: str, doc_id: str = "") -> dict[str, str]:
    """Remove one stored document, or the whole source when doc_id is omitted."""
    try:
        await ingestion.delete_document(source, doc_id)
    except grpc.aio.AioRpcError as exc:
        raise_from_grpc(exc)
    body = {"status": "deleted", "source": source}
    if doc_id:
        body["doc_id"] = doc_id
    return body


@app.delete("/schedules/{schedule_id}", dependencies=[Depends(require_api_key)])
async def delete_schedule(schedule_id: str) -> dict[str, str]:
    try:
        await ingestion.delete_schedule(schedule_id)
    except grpc.aio.AioRpcError as exc:
        raise_from_grpc(exc)
    return {"status": "deleted", "schedule_id": schedule_id}


@app.post("/schedules/{schedule_id}/run", dependencies=[Depends(require_api_key)])
async def run_schedule(schedule_id: str) -> RunScheduleResponse:
    try:
        job_id = await ingestion.run_schedule(schedule_id)
    except grpc.aio.AioRpcError as exc:
        raise_from_grpc(exc)
    return RunScheduleResponse(job_id=job_id)


@app.post("/generate", dependencies=[Depends(require_api_key)])
async def generate(body: GenerateRequest) -> GenerateResponse:
    try:
        result = await rag.generate_answer(
            query=body.query,
            top_k=body.top_k,
            rerank_top_n=body.rerank_top_n,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
    except grpc.aio.AioRpcError as exc:
        raise_from_grpc(exc)
    return GenerateResponse(
        answer=result["answer"],
        used_chunks=[UsedChunk(**c) for c in result["used_chunks"]],
    )


@app.get("/stats", dependencies=[Depends(require_api_key)])
async def stats() -> dict:
    """Aggregated Langfuse trace/score stats (HTTP; Langfuse has no gRPC)."""
    return await langfuse_stats.fetch_stats()


async def _check_litellm(base_url: str) -> bool:
    url = f"{base_url.rstrip('/')}/health/liveliness"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url)
            return response.status_code < 500
    except Exception:
        return False


def main() -> None:
    logger.info("starting gateway on %s:%s", settings.host, settings.port)
    uvicorn.run(
        "gateway.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
