"""Delete one stored document from the docstore and Qdrant."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ingestion.config import Settings
from ingestion.jobs import JobManager
from ingestion.pipeline.doc_manager import DocumentManager, DocumentNotStoredError
from ingestion.sources.base import SourceDocument
from ingestion.sources.factory import SourceFactory


def _doc(doc_id: str) -> SourceDocument:
    return SourceDocument(
        doc_id=doc_id,
        text="body",
        source="notion",
        title=doc_id,
        uri=f"/{doc_id}",
        content_type="markdown",
    )


def _manager(tmp_path: Path, doc_manager: DocumentManager) -> tuple[JobManager, MagicMock]:
    store = MagicMock()
    store.delete_by_doc_ids = AsyncMock()
    store.delete_source = AsyncMock()
    jobs = JobManager(
        Settings(),
        SourceFactory(Settings()),
        MagicMock(),
        store,
        doc_manager=doc_manager,
    )
    return jobs, store


@pytest.mark.asyncio
async def test_delete_document_clears_qdrant_then_docstore(tmp_path: Path) -> None:
    doc_manager = DocumentManager(tmp_path)
    doc_manager.sync("notion", [_doc("page-a"), _doc("page-b")])
    jobs, store = _manager(tmp_path, doc_manager)

    await jobs.delete_document("notion", "page-a")

    store.delete_by_doc_ids.assert_awaited_once_with("notion", ["page-a"])
    store.delete_source.assert_not_awaited()
    assert doc_manager.contains("notion", "page-a") is False
    assert doc_manager.contains("notion", "page-b") is True


@pytest.mark.asyncio
async def test_delete_document_missing_does_not_touch_qdrant(tmp_path: Path) -> None:
    doc_manager = DocumentManager(tmp_path)
    doc_manager.sync("notion", [_doc("page-a")])
    jobs, store = _manager(tmp_path, doc_manager)

    with pytest.raises(DocumentNotStoredError):
        await jobs.delete_document("notion", "missing")

    store.delete_by_doc_ids.assert_not_awaited()
    store.delete_source.assert_not_awaited()
    assert doc_manager.contains("notion", "page-a") is True


@pytest.mark.asyncio
async def test_delete_document_unknown_source(tmp_path: Path) -> None:
    jobs, store = _manager(tmp_path, DocumentManager(tmp_path))
    with pytest.raises(KeyError):
        await jobs.delete_document("nope", "page-a")
    store.delete_by_doc_ids.assert_not_awaited()
    store.delete_source.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_source_clears_qdrant_and_docstore(tmp_path: Path) -> None:
    doc_manager = DocumentManager(tmp_path)
    doc_manager.sync("notion", [_doc("page-a"), _doc("page-b")])
    doc_manager.sync("local_files", [_doc("page-a")])
    jobs, store = _manager(tmp_path, doc_manager)

    await jobs.delete_document("notion", "")

    store.delete_source.assert_awaited_once_with("notion")
    store.delete_by_doc_ids.assert_not_awaited()
    assert doc_manager.stored_doc_ids("notion") == []
    assert doc_manager.contains("local_files", "page-a") is True


@pytest.mark.asyncio
async def test_delete_source_missing_does_not_touch_qdrant(tmp_path: Path) -> None:
    jobs, store = _manager(tmp_path, DocumentManager(tmp_path))
    with pytest.raises(DocumentNotStoredError):
        await jobs.delete_document("notion", "")
    store.delete_source.assert_not_awaited()
