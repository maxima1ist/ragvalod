"""Google Drive adapter — thin wrapper over llama-index GoogleDriveReader."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from llama_index.readers.google import GoogleDriveReader

from ingestion.sources.base import DataSource, ProgressCallback, SourceDocument

logger = logging.getLogger("ingestion.sources.google_drive")

_MARKDOWN_SUFFIXES = {".md", ".markdown"}
_SERVICE_ACCOUNT_KEYS = (
    "service_account_key",
    "service_account_json",
    "google_service_account_key",
)
_AUTHORIZED_USER_KEYS = (
    "authorized_user_info",
    "authorized_user_json",
    "oauth_token",
)
_SERVICE_ACCOUNT_PATH_KEYS = (
    "service_account_key_path",
    "credentials_path",
)


def _parse_id_list(raw: str) -> list[str]:
    if not raw.strip():
        return []
    parts = re.split(r"[\s,;]+", raw.strip())
    return [p for p in parts if p]


def _parse_json_object(raw: str, *, field: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"google_drive credentials.{field} must be valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"google_drive credentials.{field} must be a JSON object")
    return value


def _first_nonempty(mapping: dict[str, str], keys: tuple[str, ...]) -> tuple[str, str]:
    for key in keys:
        value = (mapping.get(key) or "").strip()
        if value:
            return key, value
    return "", ""


def _build_reader(credentials: dict[str, str]) -> GoogleDriveReader:
    key_name, service_raw = _first_nonempty(credentials, _SERVICE_ACCOUNT_KEYS)
    if service_raw:
        return GoogleDriveReader(
            service_account_key=_parse_json_object(service_raw, field=key_name),
            is_cloud=True,
        )

    user_name, user_raw = _first_nonempty(credentials, _AUTHORIZED_USER_KEYS)
    if user_raw:
        return GoogleDriveReader(
            authorized_user_info=_parse_json_object(user_raw, field=user_name),
            is_cloud=True,
        )

    path_name, path_raw = _first_nonempty(credentials, _SERVICE_ACCOUNT_PATH_KEYS)
    if path_raw:
        path = Path(path_raw)
        if not path.is_file():
            raise FileNotFoundError(
                f"google_drive credentials.{path_name} does not exist: {path_raw}"
            )
        return GoogleDriveReader(
            service_account_key=_parse_json_object(
                path.read_text(encoding="utf-8"),
                field=path_name,
            ),
            is_cloud=True,
        )

    raise ValueError(
        "google_drive requires credentials.service_account_key (JSON), "
        "authorized_user_info (JSON), or service_account_key_path"
    )


def _content_type_for(name: str) -> str:
    return "markdown" if Path(name).suffix.lower() in _MARKDOWN_SUFFIXES else "text"


def _doc_title(meta: dict[str, Any], fallback: str) -> str:
    for key in ("file_name", "name", "title"):
        value = meta.get(key)
        if value:
            return str(value)
    return fallback


def _doc_uri(meta: dict[str, Any], file_id: str) -> str:
    for key in ("url", "webViewLink", "uri"):
        value = meta.get(key)
        if value:
            return str(value)
    return f"https://drive.google.com/file/d/{file_id}/view" if file_id else ""


def _modified_at(meta: dict[str, Any]) -> datetime | None:
    for key in ("modifiedTime", "modified_at", "last_modified_date"):
        raw = meta.get(key)
        if not raw:
            continue
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            continue
    return None


class GoogleDriveDataSource(DataSource):
    name = "google_drive"
    description = (
        "Read Google Drive files/folders via service account or OAuth token "
        "(llama-index GoogleDriveReader)"
    )
    requires_credentials = True

    async def fetch(
        self,
        credentials: dict[str, str],
        options: dict[str, str],
        *,
        progress: ProgressCallback | None = None,
    ) -> list[SourceDocument]:
        return await asyncio.to_thread(self._fetch_sync, credentials, options, progress)

    def _fetch_sync(
        self,
        credentials: dict[str, str],
        options: dict[str, str],
        progress: ProgressCallback | None,
    ) -> list[SourceDocument]:
        reader = _build_reader(credentials)
        folder_id = (options.get("folder_id") or options.get("folder") or "").strip()
        file_ids = _parse_id_list(options.get("file_ids") or options.get("file_id") or "")
        query = (
            options.get("query_string") or options.get("query") or options.get("search") or ""
        ).strip()
        drive_id = (options.get("drive_id") or "").strip() or None

        if not folder_id and not file_ids:
            raise ValueError(
                "google_drive requires options.folder_id or options.file_ids "
                "(share the folder/files with the service account email)"
            )

        logger.info(
            "google_drive loading folder_id=%r file_ids=%s query=%r drive_id=%r",
            folder_id or None,
            len(file_ids),
            query or None,
            drive_id,
        )
        documents = reader.load_data(
            folder_id=folder_id or None,
            file_ids=file_ids or None,
            query_string=query or None,
            drive_id=drive_id,
        )
        if not documents:
            raise ValueError(
                "google_drive: no documents loaded (check sharing / folder_id / file_ids)"
            )

        result: list[SourceDocument] = []
        total = len(documents)
        for index, doc in enumerate(documents, start=1):
            meta = dict(doc.metadata or {})
            file_id = str(meta.get("file_id") or meta.get("id") or doc.doc_id or f"doc-{index}")
            title = _doc_title(meta, file_id)
            uri = _doc_uri(meta, file_id)
            result.append(
                SourceDocument(
                    doc_id=file_id,
                    text=doc.get_content() or title,
                    source=self.name,
                    title=title,
                    uri=uri,
                    modified_at=_modified_at(meta) or datetime.now(UTC),
                    content_type=_content_type_for(title),
                    metadata=meta,
                )
            )
            if progress is not None:
                progress(index, total, title)

        logger.info("google_drive loaded %s documents", len(result))
        return result
