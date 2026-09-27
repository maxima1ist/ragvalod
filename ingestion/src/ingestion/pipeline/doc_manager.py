"""Document dedup/delete via LlamaIndex IngestionPipeline + per-source docstore."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llama_index.core.ingestion import DocstoreStrategy, IngestionPipeline
from llama_index.core.schema import BaseNode, Document
from llama_index.core.storage.docstore import SimpleDocumentStore
from llama_index.core.vector_stores.types import (
    BasePydanticVectorStore,
    VectorStoreQuery,
    VectorStoreQueryResult,
)
from pydantic import Field

from ingestion.sources.base import SourceDocument

logger = logging.getLogger("ingestion.doc_manager")


class DocumentNotStoredError(Exception):
    """The source docstore has no entry for this doc_id."""


class RecordingVectorStore(BasePydanticVectorStore):
    """Minimal vector store so UPSERTS_AND_DELETE is enabled; we sync deletes to Qdrant."""

    stores_text: bool = True
    is_embedding_query: bool = False
    deleted_ref_doc_ids: list[str] = Field(default_factory=list)

    @property
    def client(self) -> Any:
        return None

    def add(self, nodes: list[BaseNode], **kwargs: Any) -> list[str]:
        # Embeddings / Qdrant writes stay in JobManager (LiteLLM), not here.
        del kwargs
        return [n.node_id for n in nodes]

    def delete(self, ref_doc_id: str, **kwargs: Any) -> None:
        del kwargs
        self.deleted_ref_doc_ids.append(ref_doc_id)

    def query(self, query: VectorStoreQuery, **kwargs: Any) -> VectorStoreQueryResult:
        del query, kwargs
        return VectorStoreQueryResult(nodes=[], similarities=[], ids=[])


@dataclass(slots=True)
class DocSyncResult:
    """Outcome of one source sync against the persisted docstore."""

    to_process: list[SourceDocument] = field(default_factory=list)
    # doc_ids whose Qdrant points must be removed (changed and/or deleted from source).
    qdrant_doc_ids_to_delete: list[str] = field(default_factory=list)
    skipped_unchanged: int = 0
    deleted_count: int = 0


class DocumentManager:
    """Per-source SimpleDocumentStore + IngestionPipeline (UPSERTS_AND_DELETE)."""

    def __init__(self, root_dir: Path) -> None:
        self._root = root_dir

    def _path_for(self, source: str) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in source)
        return self._root / f"{safe}.json"

    def sync(self, source: str, documents: list[SourceDocument]) -> DocSyncResult:
        path = self._path_for(source)
        if path.exists():
            docstore = SimpleDocumentStore.from_persist_path(str(path))
        else:
            docstore = SimpleDocumentStore()

        by_id = {doc.doc_id: doc for doc in documents}
        if len(by_id) != len(documents):
            logger.warning(
                "source %s: duplicate doc_ids in fetch; last wins (%s → %s)",
                source,
                len(documents),
                len(by_id),
            )

        li_docs = [
            Document(
                text=doc.text,
                doc_id=doc.doc_id,
                metadata={
                    **doc.metadata,
                    "title": doc.title,
                    "source": doc.source,
                    "uri": doc.uri,
                    "content_type": doc.content_type,
                },
            )
            for doc in by_id.values()
        ]

        recorder = RecordingVectorStore()
        pipeline = IngestionPipeline(
            transformations=[],
            docstore=docstore,
            vector_store=recorder,
            docstore_strategy=DocstoreStrategy.UPSERTS_AND_DELETE,
        )
        nodes = list(pipeline.run(documents=li_docs, store_doc_text=True))
        docstore.persist(persist_path=str(path))

        process_ids = [n.ref_doc_id or n.node_id for n in nodes]
        to_process = [by_id[doc_id] for doc_id in process_ids if doc_id in by_id]
        deleted_ids = list(dict.fromkeys(recorder.deleted_ref_doc_ids))
        # Changed docs appear in both deleted (old vectors) and to_process.
        skipped = len(by_id) - len(to_process)
        removed_only = [d for d in deleted_ids if d not in {doc.doc_id for doc in to_process}]

        logger.info(
            "docstore sync source=%s fetched=%s process=%s skipped=%s qdrant_delete=%s removed=%s",
            source,
            len(by_id),
            len(to_process),
            skipped,
            len(deleted_ids),
            len(removed_only),
        )
        return DocSyncResult(
            to_process=to_process,
            qdrant_doc_ids_to_delete=deleted_ids,
            skipped_unchanged=skipped,
            deleted_count=len(removed_only),
        )

    def stored_doc_ids(self, source: str) -> list[str]:
        path = self._path_for(source)
        if not path.exists():
            return []
        docstore = SimpleDocumentStore.from_persist_path(str(path))
        return list(docstore.get_all_document_hashes())

    def delete_source(self, source: str) -> None:
        """Drop the source docstore. Raises if it has no stored documents."""
        if not self.stored_doc_ids(source):
            raise DocumentNotStoredError(f"source not stored: source={source}")
        self._path_for(source).unlink()
        logger.info("docstore deleted source=%s", source)

    def contains(self, source: str, doc_id: str) -> bool:
        path = self._path_for(source)
        if not path.exists():
            return False
        docstore = SimpleDocumentStore.from_persist_path(str(path))
        return bool(docstore.document_exists(doc_id))

    def delete(self, source: str, doc_id: str) -> None:
        """Drop one document from the source docstore. Raises if it is not stored."""
        path = self._path_for(source)
        if not path.exists():
            raise DocumentNotStoredError(f"document not stored: source={source} doc_id={doc_id}")
        docstore = SimpleDocumentStore.from_persist_path(str(path))
        if not docstore.document_exists(doc_id):
            raise DocumentNotStoredError(f"document not stored: source={source} doc_id={doc_id}")
        docstore.delete_document(doc_id)
        docstore.persist(persist_path=str(path))
        logger.info("docstore deleted source=%s doc_id=%s", source, doc_id)
