"""Notion adapter — Markdown-aware wrapper over llama-index NotionPageReader."""

from __future__ import annotations

import asyncio
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any

from llama_index.readers.notion import NotionPageReader

from ingestion.sources.base import DataSource, ProgressCallback, SourceDocument

logger = logging.getLogger("ingestion.sources.notion")
_DEFAULT_CONCURRENCY = 3
_MAX_CONCURRENCY = 8

_PAGE_URL = "https://api.notion.com/v1/pages/{page_id}"
_SEARCH_URL = "https://api.notion.com/v1/search"
_HEADING_PREFIX = {
    "heading_1": "# ",
    "heading_2": "## ",
    "heading_3": "### ",
}
_SKIP_CHILD_OBJECTS = frozenset({"child_page", "child_database"})
_TOKEN_KEYS = (
    "integration_token",
    "token",
    "notion_token",
    "access_key",
    "NOTION_ACCESS_KEY",
)


def _plain_rich_text(rich_text: list[dict[str, Any]] | None) -> str:
    parts: list[str] = []
    for item in rich_text or []:
        if "plain_text" in item:
            parts.append(str(item["plain_text"]))
        elif "text" in item and isinstance(item["text"], dict):
            parts.append(str(item["text"].get("content") or ""))
    return "".join(parts)


def _extract_token(credentials: dict[str, str]) -> str:
    for key in _TOKEN_KEYS:
        value = (credentials.get(key) or "").strip()
        if value:
            return value
    return ""


def _parse_id_list(raw: str) -> list[str]:
    if not raw.strip():
        return []
    parts = re.split(r"[\s,;]+", raw.strip())
    return [p for p in parts if p]


def _parse_concurrency(raw: str) -> int:
    if not raw.strip():
        return _DEFAULT_CONCURRENCY
    value = int(raw.strip())
    if value < 1:
        raise ValueError("max_concurrency must be >= 1")
    return min(value, _MAX_CONCURRENCY)


def _page_title_from_properties(properties: dict[str, Any]) -> str:
    for value in properties.values():
        if not isinstance(value, dict):
            continue
        if value.get("type") == "title":
            title = _plain_rich_text(value.get("title"))
            if title:
                return title
    return ""


class MarkdownNotionPageReader(NotionPageReader):
    """NotionPageReader that emits Markdown headings and does not flatten child pages."""

    def _read_block(self, block_id: str, num_tabs: int = 0) -> str:
        result_lines: list[str] = []
        start_cursor: str | None = None

        while True:
            block_url = f"https://api.notion.com/v1/blocks/{block_id}/children"
            if start_cursor:
                block_url = f"{block_url}?start_cursor={start_cursor}"
            res = self._request_with_retry("GET", block_url, headers=self.headers, json=None)
            data = res.json()
            indent = "\t" * num_tabs

            for result in data.get("results") or []:
                result_type = str(result.get("type") or "")
                result_obj = result.get(result_type) or {}
                has_children = bool(result.get("has_children"))
                line = self._format_block(result_type, result_obj, indent)
                if line is not None:
                    result_lines.append(line)

                # Do not flatten child pages/DBs into the parent document — they are
                # ingested as separate SourceDocuments when discovered via search.
                if has_children and result_type not in _SKIP_CHILD_OBJECTS:
                    child_text = self._read_block(str(result["id"]), num_tabs=num_tabs + 1)
                    if child_text.strip():
                        result_lines.append(child_text)

            if not data.get("has_more") or not data.get("next_cursor"):
                break
            start_cursor = str(data["next_cursor"])

        return "\n".join(result_lines)

    def _format_block(
        self, result_type: str, result_obj: dict[str, Any], indent: str
    ) -> str | None:
        if result_type in _HEADING_PREFIX:
            text = _plain_rich_text(result_obj.get("rich_text"))
            return f"{indent}{_HEADING_PREFIX[result_type]}{text}".rstrip()
        if result_type == "child_page":
            title = str(result_obj.get("title") or "Untitled")
            return f"{indent}[child page: {title}]"
        if result_type == "child_database":
            title = str(result_obj.get("title") or "Untitled")
            return f"{indent}[child database: {title}]"
        if result_type == "bulleted_list_item":
            text = _plain_rich_text(result_obj.get("rich_text"))
            return f"{indent}- {text}".rstrip()
        if result_type == "numbered_list_item":
            text = _plain_rich_text(result_obj.get("rich_text"))
            return f"{indent}1. {text}".rstrip()
        if result_type == "to_do":
            text = _plain_rich_text(result_obj.get("rich_text"))
            mark = "x" if result_obj.get("checked") else " "
            return f"{indent}- [{mark}] {text}".rstrip()
        if result_type == "quote":
            text = _plain_rich_text(result_obj.get("rich_text"))
            return f"{indent}> {text}".rstrip()
        if result_type == "code":
            text = _plain_rich_text(result_obj.get("rich_text"))
            lang = str(result_obj.get("language") or "")
            return f"{indent}```{lang}\n{text}\n{indent}```"
        if result_type == "divider":
            return f"{indent}---"
        if "rich_text" in result_obj:
            text = _plain_rich_text(result_obj.get("rich_text"))
            return f"{indent}{text}".rstrip() if text else None
        return None

    def get_page_meta(self, page_id: str) -> tuple[str, str, datetime | None]:
        res = self._request_with_retry(
            "GET",
            _PAGE_URL.format(page_id=page_id),
            headers=self.headers,
            json=None,
        )
        data = res.json()
        title = _page_title_from_properties(data.get("properties") or {}) or page_id
        url = str(data.get("url") or "")
        modified = None
        raw = data.get("last_edited_time")
        if raw:
            try:
                modified = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                modified = None
        return title, url, modified

    def search_pages(
        self,
        *,
        query: str = "",
        max_pages: int | None = None,
    ) -> list[dict[str, str]]:
        """Return [{id, title, url}, ...] for pages visible to the integration."""
        pages: list[dict[str, str]] = []
        start_cursor: str | None = None
        while True:
            body: dict[str, Any] = {
                "filter": {"property": "object", "value": "page"},
                "page_size": 100,
            }
            if query:
                body["query"] = query
            if start_cursor:
                body["start_cursor"] = start_cursor
            res = self._request_with_retry("POST", _SEARCH_URL, headers=self.headers, json=body)
            data = res.json()
            for result in data.get("results") or []:
                if result.get("object") != "page":
                    continue
                page_id = str(result.get("id"))
                title = _page_title_from_properties(result.get("properties") or {}) or page_id
                pages.append(
                    {
                        "id": page_id,
                        "title": title,
                        "url": str(result.get("url") or ""),
                    }
                )
                if max_pages is not None and len(pages) >= max_pages:
                    return pages
            if not data.get("has_more"):
                break
            start_cursor = data.get("next_cursor")
            if not start_cursor:
                break
        return pages


class NotionDataSource(DataSource):
    name = "notion"
    description = "Read Notion pages/databases via integration token (Markdown-aware)"
    requires_credentials = True

    async def fetch(
        self,
        credentials: dict[str, str],
        options: dict[str, str],
        *,
        progress: ProgressCallback | None = None,
    ) -> list[SourceDocument]:
        token = _extract_token(credentials)
        if not token:
            raise ValueError(
                "notion requires credentials.integration_token "
                "(aliases: token, notion_token, access_key)"
            )
        return await asyncio.to_thread(self._fetch_sync, token, options, progress)

    def _fetch_sync(
        self,
        token: str,
        options: dict[str, str],
        progress: ProgressCallback | None,
    ) -> list[SourceDocument]:
        reader = MarkdownNotionPageReader(integration_token=token)
        page_ids = _parse_id_list(options.get("page_ids") or options.get("page_id") or "")
        database_ids = _parse_id_list(
            options.get("database_ids") or options.get("database_id") or ""
        )
        query = (options.get("query") or options.get("search") or "").strip()
        max_raw = (options.get("max_pages") or "").strip().lower()
        # Default discovery cap=10. Explicit page_ids are not capped unless max_pages set.
        # max_pages=all|0 → no cap when discovering.
        if max_raw in {"all", "0"}:
            max_pages: int | None = None
        elif max_raw == "":
            max_pages = 10
        else:
            max_pages = max(1, int(max_raw))

        page_meta: dict[str, dict[str, str]] = {}
        if database_ids:
            for database_id in database_ids:
                page_ids.extend(reader.query_database(database_id))

        if not page_ids:
            discovered = reader.search_pages(query=query, max_pages=max_pages)
            page_ids = [p["id"] for p in discovered]
            page_meta = {p["id"]: p for p in discovered}
            logger.info(
                "notion discovered %s pages query=%r max_pages=%s",
                len(page_ids),
                query,
                max_pages,
            )
        else:
            seen: set[str] = set()
            unique: list[str] = []
            for page_id in page_ids:
                if page_id not in seen:
                    seen.add(page_id)
                    unique.append(page_id)
            page_ids = unique
            if max_raw not in {"", "all", "0"} and max_pages is not None:
                page_ids = page_ids[:max_pages]

        if not page_ids:
            raise ValueError("notion: no pages to ingest (check Connections / page_ids)")

        concurrency = _parse_concurrency(options.get("max_concurrency") or "")
        total = len(page_ids)
        logger.info(
            "notion fetching %s pages with max_concurrency=%s",
            total,
            concurrency,
        )

        def load_one(page_id: str) -> SourceDocument:
            text = reader.read_page(page_id)
            cached = page_meta.get(page_id)
            if cached:
                title = cached.get("title") or page_id
                url = cached.get("url") or ""
                modified = None
            else:
                title, url, modified = reader.get_page_meta(page_id)
            return SourceDocument(
                doc_id=page_id,
                text=text or title,
                source=self.name,
                title=title,
                uri=url,
                modified_at=modified or datetime.now(UTC),
                content_type="markdown",
                metadata={"page_id": page_id, "url": url},
            )

        documents_by_id: dict[str, SourceDocument] = {}
        done = 0
        progress_lock = threading.Lock()

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(load_one, page_id): page_id for page_id in page_ids}
            for future in as_completed(futures):
                page_id = futures[future]
                try:
                    document = future.result()
                except Exception:
                    logger.exception("notion fetch failed page_id=%s", page_id)
                    raise
                documents_by_id[document.doc_id] = document
                with progress_lock:
                    done += 1
                    logger.info(
                        "notion fetch %s/%s title=%r chars=%s",
                        done,
                        total,
                        document.title,
                        len(document.text or ""),
                    )
                    if progress is not None:
                        progress(done, total, document.title)

        documents = [documents_by_id[page_id] for page_id in page_ids]
        logger.info("notion loaded %s pages", len(documents))
        return documents
