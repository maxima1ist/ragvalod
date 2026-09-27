"""Unit tests for structure-aware chunking."""

from ingestion.pipeline.chunking import chunk_documents
from ingestion.sources.base import SourceDocument


def test_markdown_chunking_keeps_section_context() -> None:
    docs = [
        SourceDocument(
            doc_id="/tmp/welcome.md",
            text="# Title\n\nIntro paragraph.\n\n## Section\n\nDetails about retrieval.\n",
            source="local_files",
            title="welcome.md",
            uri="/tmp/welcome.md",
            content_type="markdown",
        )
    ]
    chunks = chunk_documents(docs, chunk_size=512, chunk_overlap=50)
    assert chunks
    assert any("welcome.md" in c.text for c in chunks)
    assert all(c.source == "local_files" for c in chunks)


def test_plain_text_chunking() -> None:
    docs = [
        SourceDocument(
            doc_id="/tmp/notes.txt",
            text="Rogvolod was a prince of Polotsk. " * 40,
            source="local_files",
            title="notes.txt",
            content_type="text",
        )
    ]
    chunks = chunk_documents(docs, chunk_size=64, chunk_overlap=10)
    assert len(chunks) >= 2
    assert chunks[0].chunk_index == 0
