"""In-memory ingest job model and runner."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from ingestion.config import Settings
from ingestion.pipeline.chunking import chunk_documents
from ingestion.pipeline.embeddings import EmbeddingClient
from ingestion.qdrant_store import QdrantDocumentStore
from ingestion.sources.base import DataSource
from ingestion.sources.factory import SourceFactory

logger = logging.getLogger("ingestion.jobs")


class JobState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class SourceJobState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class SourceJobStatus:
    source_name: str
    state: SourceJobState = SourceJobState.PENDING
    message: str = ""
    documents_processed: int = 0
    chunks_written: int = 0
    error: str = ""


@dataclass
class JobRecord:
    job_id: str
    state: JobState = JobState.PENDING
    message: str = ""
    sources: list[SourceJobStatus] = field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobManager:
    def __init__(
        self,
        settings: Settings,
        factory: SourceFactory,
        embeddings: EmbeddingClient,
        store: QdrantDocumentStore,
    ) -> None:
        self._settings = settings
        self._factory = factory
        self._embeddings = embeddings
        self._store = store
        self._jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    async def start_job(
        self,
        work_items: list[tuple[DataSource, dict[str, str], dict[str, str]]],
    ) -> str:
        job_id = str(uuid.uuid4())
        record = JobRecord(
            job_id=job_id,
            state=JobState.PENDING,
            sources=[SourceJobStatus(source_name=adapter.name) for adapter, _, _ in work_items],
        )
        async with self._lock:
            self._jobs[job_id] = record
        asyncio.create_task(self._run_job(job_id, work_items), name=f"ingest-{job_id}")
        return job_id

    async def _run_job(
        self,
        job_id: str,
        work_items: list[tuple[DataSource, dict[str, str], dict[str, str]]],
    ) -> None:
        record = self._jobs[job_id]
        record.state = JobState.RUNNING
        record.started_at = datetime.now(UTC)
        logger.info("job %s started with %s sources", job_id, len(work_items))

        try:
            await self._store.ensure_collection()
        except Exception as exc:
            record.state = JobState.FAILED
            record.message = f"failed to prepare Qdrant collection: {exc}"
            record.finished_at = datetime.now(UTC)
            for status in record.sources:
                status.state = SourceJobState.FAILED
                status.error = str(exc)
            logger.exception("job %s collection prepare failed", job_id)
            return

        successes = 0
        failures = 0
        for index, (adapter, credentials, options) in enumerate(work_items):
            status = record.sources[index]
            status.state = SourceJobState.RUNNING
            try:
                docs = await adapter.fetch(credentials, options)
                chunks = chunk_documents(
                    docs,
                    chunk_size=self._settings.chunk_size,
                    chunk_overlap=self._settings.chunk_overlap,
                )
                vectors = await self._embeddings.embed_texts([c.text for c in chunks])
                written = await self._store.upsert_chunks(chunks, vectors)
                await self._store.write_source_marker(adapter.name, document_count=len(docs))
                status.state = SourceJobState.SUCCEEDED
                status.documents_processed = len(docs)
                status.chunks_written = written
                status.message = "ok"
                successes += 1
                logger.info(
                    "job %s source %s ok docs=%s chunks=%s",
                    job_id,
                    adapter.name,
                    len(docs),
                    written,
                )
            except Exception as exc:
                failures += 1
                status.state = SourceJobState.FAILED
                status.error = str(exc)
                status.message = "failed"
                logger.exception("job %s source %s failed", job_id, adapter.name)
            finally:
                # Drop credentials reference ASAP after source finishes.
                credentials.clear()

        if successes and not failures:
            record.state = JobState.SUCCEEDED
            record.message = "all sources succeeded"
            try:
                wrote = await self._store.write_init_marker_once()
                if wrote:
                    logger.info("job %s wrote initialization marker", job_id)
            except Exception:
                logger.exception("job %s failed to write init marker", job_id)
                record.state = JobState.PARTIAL
                record.message = "sources ok but init marker write failed"
        elif successes and failures:
            record.state = JobState.PARTIAL
            record.message = "some sources failed"
        else:
            record.state = JobState.FAILED
            record.message = "all sources failed"

        record.finished_at = datetime.now(UTC)
        logger.info("job %s finished state=%s", job_id, record.state.value)
