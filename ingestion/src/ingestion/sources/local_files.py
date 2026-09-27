"""Local files adapter — SimpleDirectoryReader wrapper."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from llama_index.core import SimpleDirectoryReader

from ingestion.sources.base import DataSource, ProgressCallback, SourceDocument

logger = logging.getLogger("ingestion.sources.local_files")

_MARKDOWN_SUFFIXES = {".md", ".markdown"}
_SUPPORTED = {".txt", ".md", ".markdown", ".pdf", ".docx"}


class LocalFilesDataSource(DataSource):
    name = "local_files"
    description = "Read .txt/.md/.pdf/.docx from a mounted local directory"
    requires_credentials = False

    def __init__(self, default_dir: str) -> None:
        self._default_dir = default_dir

    async def fetch(
        self,
        credentials: dict[str, str],
        options: dict[str, str],
        *,
        progress: ProgressCallback | None = None,
    ) -> list[SourceDocument]:
        del credentials  # unused — adapter needs no secrets
        root = options.get("path") or options.get("dir") or self._default_dir
        if not os.path.exists(root):
            raise FileNotFoundError(f"local_files path does not exist: {root}")
        if not os.path.isdir(root):
            raise NotADirectoryError(f"local_files path is not a directory: {root}")

        logger.info("reading local files from %s", root)
        reader = SimpleDirectoryReader(
            input_dir=root,
            recursive=True,
            required_exts=sorted(_SUPPORTED),
            filename_as_id=True,
        )
        # SimpleDirectoryReader is sync/blocking; fine for first-pass ingest jobs.
        documents = reader.load_data()
        result: list[SourceDocument] = []
        total = len(documents)
        for index, doc in enumerate(documents, start=1):
            file_path = str(doc.metadata.get("file_path") or doc.doc_id or "")
            suffix = Path(file_path).suffix.lower()
            content_type = "markdown" if suffix in _MARKDOWN_SUFFIXES else "text"
            title = Path(file_path).name if file_path else (doc.doc_id or "untitled")
            modified = None
            if "last_modified_date" in doc.metadata:
                try:
                    modified = datetime.fromisoformat(str(doc.metadata["last_modified_date"]))
                except ValueError:
                    modified = None
            result.append(
                SourceDocument(
                    doc_id=file_path or str(doc.doc_id),
                    text=doc.get_content(),
                    source=self.name,
                    title=title,
                    uri=file_path,
                    modified_at=modified or datetime.now(UTC),
                    content_type=content_type,
                    metadata=dict(doc.metadata),
                )
            )
            if progress is not None:
                progress(index, total, title)
        logger.info("loaded %s documents from %s", len(result), root)
        return result
