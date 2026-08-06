"""APScheduler-backed periodic ingest runner."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ingestion.credentials_crypto import CredentialsCryptoError
from ingestion.schedule_store import ScheduleRecord, ScheduleStore

if TYPE_CHECKING:
    from ingestion.jobs import JobManager
    from ingestion.sources.factory import SourceFactory

logger = logging.getLogger("ingestion.scheduler")


class IngestScheduler:
    def __init__(
        self,
        store: ScheduleStore,
        factory: SourceFactory,
        jobs: JobManager,
    ) -> None:
        self._store = store
        self._factory = factory
        self._jobs = jobs
        self._scheduler = AsyncIOScheduler()

    async def start(self) -> None:
        self._reload_jobs()
        if not self._scheduler.running:
            self._scheduler.start()
        logger.info("ingest scheduler started (%s jobs)", len(self._scheduler.get_jobs()))

    async def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("ingest scheduler stopped")

    def reload(self) -> None:
        self._reload_jobs()

    async def run_now(self, schedule_id: str) -> str:
        record = self._store.get(schedule_id)
        if record is None:
            raise KeyError(f"unknown schedule_id={schedule_id}")
        return await self._trigger(record)

    def _reload_jobs(self) -> None:
        for job in list(self._scheduler.get_jobs()):
            job.remove()
        for record in self._store.list():
            if not record.enabled:
                continue
            self._scheduler.add_job(
                self._trigger,
                trigger=CronTrigger.from_crontab(record.cron),
                id=record.schedule_id,
                args=[record.schedule_id],
                replace_existing=True,
                coalesce=True,
                max_instances=1,
                misfire_grace_time=300,
            )
            logger.info(
                "scheduled ingest id=%s cron=%s name=%s",
                record.schedule_id,
                record.cron,
                record.name,
            )

    async def _trigger(self, schedule_or_id: ScheduleRecord | str) -> str:
        if isinstance(schedule_or_id, str):
            record = self._store.get(schedule_or_id)
            if record is None:
                logger.warning("schedule %s missing at trigger time", schedule_or_id)
                raise KeyError(f"unknown schedule_id={schedule_or_id}")
        else:
            record = schedule_or_id

        try:
            requested = self._store.decrypt_sources(record)
            work_items = self._factory.resolve_job_sources(
                requested,
                all_with_credentials=record.all_with_credentials,
            )
        except (CredentialsCryptoError, KeyError, ValueError) as exc:
            logger.exception("schedule %s failed to resolve sources: %s", record.schedule_id, exc)
            raise

        if not work_items:
            raise ValueError(f"schedule {record.schedule_id}: no sources selected")

        job_id = await self._jobs.start_job(work_items)
        self._store.mark_run(record.schedule_id, job_id)
        logger.info(
            "schedule %s triggered job_id=%s sources=%s",
            record.schedule_id,
            job_id,
            len(work_items),
        )
        return job_id
