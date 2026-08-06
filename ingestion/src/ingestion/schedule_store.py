"""Persistent schedule store with Fernet-encrypted credentials."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apscheduler.triggers.cron import CronTrigger

from ingestion.credentials_crypto import CredentialsCrypto, CredentialsCryptoError

logger = logging.getLogger("ingestion.schedules")


@dataclass(slots=True)
class StoredSourceSpec:
    name: str
    credentials_encrypted: str = ""
    options: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ScheduleRecord:
    schedule_id: str
    name: str
    cron: str
    enabled: bool
    sources: list[StoredSourceSpec]
    all_with_credentials: bool = False
    created_at: str = ""
    updated_at: str = ""
    last_run_at: str = ""
    last_job_id: str = ""

    def source_names(self) -> list[str]:
        return [s.name for s in self.sources]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "name": self.name,
            "cron": self.cron,
            "enabled": self.enabled,
            "source_names": self.source_names(),
            "all_with_credentials": self.all_with_credentials,
            "last_run_at": self.last_run_at,
            "last_job_id": self.last_job_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def validate_cron(cron: str) -> None:
    expression = (cron or "").strip()
    if not expression:
        raise ValueError("cron expression is required")
    parts = expression.split()
    if len(parts) != 5:
        raise ValueError("cron must have 5 fields: minute hour day month day_of_week")
    try:
        CronTrigger.from_crontab(expression)
    except Exception as exc:  # noqa: BLE001 — surface as ValueError
        raise ValueError(f"invalid cron expression: {expression}") from exc


class ScheduleStore:
    def __init__(self, path: Path, crypto: CredentialsCrypto) -> None:
        self._path = path
        self._crypto = crypto
        self._lock = threading.RLock()
        self._schedules: dict[str, ScheduleRecord] = {}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def list(self) -> list[ScheduleRecord]:
        with self._lock:
            return sorted(self._schedules.values(), key=lambda s: s.created_at)

    def get(self, schedule_id: str) -> ScheduleRecord | None:
        with self._lock:
            return self._schedules.get(schedule_id)

    def upsert(
        self,
        *,
        schedule_id: str | None,
        name: str,
        cron: str,
        enabled: bool,
        sources: list[tuple[str, dict[str, str], dict[str, str]]],
        all_with_credentials: bool,
    ) -> ScheduleRecord:
        validate_cron(cron)
        if not name.strip():
            raise ValueError("schedule name is required")
        if not sources and not all_with_credentials:
            raise ValueError("sources or all_with_credentials required")

        needs_crypto = any(bool(creds) for _, creds, _ in sources)
        if needs_crypto and not self._crypto.enabled:
            raise CredentialsCryptoError(
                "cannot store schedule credentials without INGESTION_CREDENTIALS_ENCRYPTION_KEY"
            )

        now = datetime.now(UTC).isoformat()
        with self._lock:
            existing = self._schedules.get(schedule_id) if schedule_id else None
            if schedule_id and existing is None:
                raise KeyError(f"unknown schedule_id={schedule_id}")

            sid = schedule_id or str(uuid.uuid4())
            stored_sources = [
                StoredSourceSpec(
                    name=src_name,
                    credentials_encrypted=self._crypto.encrypt_mapping(creds),
                    options=dict(opts),
                )
                for src_name, creds, opts in sources
            ]
            record = ScheduleRecord(
                schedule_id=sid,
                name=name.strip(),
                cron=cron.strip(),
                enabled=enabled,
                sources=stored_sources,
                all_with_credentials=all_with_credentials,
                created_at=existing.created_at if existing else now,
                updated_at=now,
                last_run_at=existing.last_run_at if existing else "",
                last_job_id=existing.last_job_id if existing else "",
            )
            self._schedules[sid] = record
            self._persist()
            logger.info("schedule upserted id=%s name=%s cron=%s", sid, record.name, record.cron)
            return record

    def delete(self, schedule_id: str) -> None:
        with self._lock:
            if schedule_id not in self._schedules:
                raise KeyError(f"unknown schedule_id={schedule_id}")
            del self._schedules[schedule_id]
            self._persist()
            logger.info("schedule deleted id=%s", schedule_id)

    def mark_run(self, schedule_id: str, job_id: str) -> None:
        with self._lock:
            record = self._schedules.get(schedule_id)
            if record is None:
                return
            record.last_run_at = datetime.now(UTC).isoformat()
            record.last_job_id = job_id
            record.updated_at = record.last_run_at
            self._persist()

    def decrypt_sources(
        self, record: ScheduleRecord
    ) -> list[tuple[str, dict[str, str], dict[str, str]]]:
        return [
            (
                src.name,
                self._crypto.decrypt_mapping(src.credentials_encrypted),
                dict(src.options),
            )
            for src in record.sources
        ]

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("failed to load schedules from %s", self._path)
            return
        for item in raw.get("schedules") or []:
            try:
                record = ScheduleRecord(
                    schedule_id=str(item["schedule_id"]),
                    name=str(item.get("name") or ""),
                    cron=str(item.get("cron") or ""),
                    enabled=bool(item.get("enabled", True)),
                    sources=[
                        StoredSourceSpec(
                            name=str(s.get("name") or ""),
                            credentials_encrypted=str(s.get("credentials_encrypted") or ""),
                            options={str(k): str(v) for k, v in (s.get("options") or {}).items()},
                        )
                        for s in (item.get("sources") or [])
                    ],
                    all_with_credentials=bool(item.get("all_with_credentials", False)),
                    created_at=str(item.get("created_at") or ""),
                    updated_at=str(item.get("updated_at") or ""),
                    last_run_at=str(item.get("last_run_at") or ""),
                    last_job_id=str(item.get("last_job_id") or ""),
                )
            except (KeyError, TypeError, ValueError):
                logger.exception("skipping corrupt schedule entry: %s", item)
                continue
            self._schedules[record.schedule_id] = record
        logger.info("loaded %s schedules from %s", len(self._schedules), self._path)

    def _persist(self) -> None:
        payload = {
            "schedules": [
                {
                    "schedule_id": s.schedule_id,
                    "name": s.name,
                    "cron": s.cron,
                    "enabled": s.enabled,
                    "all_with_credentials": s.all_with_credentials,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                    "last_run_at": s.last_run_at,
                    "last_job_id": s.last_job_id,
                    "sources": [
                        {
                            "name": src.name,
                            "credentials_encrypted": src.credentials_encrypted,
                            "options": src.options,
                        }
                        for src in s.sources
                    ],
                }
                for s in self._schedules.values()
            ]
        }
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self._path)
