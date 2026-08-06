"""Unit tests for document dedup / delete sync (stage 10.3)."""

from __future__ import annotations

from pathlib import Path

from ingestion.pipeline.doc_manager import DocumentManager
from ingestion.sources.base import SourceDocument


def _doc(doc_id: str, text: str) -> SourceDocument:
    return SourceDocument(
        doc_id=doc_id,
        text=text,
        source="local_files",
        title=doc_id,
        uri=f"/{doc_id}",
        content_type="text",
    )


def test_first_sync_processes_all(tmp_path: Path) -> None:
    mgr = DocumentManager(tmp_path)
    result = mgr.sync("local_files", [_doc("a", "one"), _doc("b", "two")])
    assert {d.doc_id for d in result.to_process} == {"a", "b"}
    assert result.qdrant_doc_ids_to_delete == []
    assert result.skipped_unchanged == 0


def test_unchanged_docs_are_skipped(tmp_path: Path) -> None:
    mgr = DocumentManager(tmp_path)
    docs = [_doc("a", "one"), _doc("b", "two")]
    mgr.sync("local_files", docs)
    again = mgr.sync("local_files", docs)
    assert again.to_process == []
    assert again.skipped_unchanged == 2
    assert again.qdrant_doc_ids_to_delete == []


def test_changed_doc_reprocessed_and_marked_for_qdrant_delete(tmp_path: Path) -> None:
    mgr = DocumentManager(tmp_path)
    mgr.sync("local_files", [_doc("a", "one"), _doc("b", "two")])
    result = mgr.sync("local_files", [_doc("a", "one changed"), _doc("b", "two")])
    assert [d.doc_id for d in result.to_process] == ["a"]
    assert "a" in result.qdrant_doc_ids_to_delete
    assert result.skipped_unchanged == 1


def test_removed_doc_deleted(tmp_path: Path) -> None:
    mgr = DocumentManager(tmp_path)
    mgr.sync("local_files", [_doc("a", "one"), _doc("b", "two")])
    result = mgr.sync("local_files", [_doc("a", "one")])
    assert result.to_process == []
    assert result.qdrant_doc_ids_to_delete == ["b"]
    assert result.deleted_count == 1
    assert result.skipped_unchanged == 1


def test_sources_have_isolated_docstores(tmp_path: Path) -> None:
    mgr = DocumentManager(tmp_path)
    mgr.sync("local_files", [_doc("a", "one")])
    mgr.sync("notion", [_doc("a", "notion page")])
    # Re-sync local_files alone must not delete notion's "a".
    local_again = mgr.sync("local_files", [_doc("a", "one")])
    assert local_again.to_process == []
    notion_again = mgr.sync("notion", [_doc("a", "notion page")])
    assert notion_again.to_process == []
    assert (tmp_path / "local_files.json").exists()
    assert (tmp_path / "notion.json").exists()
