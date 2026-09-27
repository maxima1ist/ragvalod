"""Structure-aware chunking pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass

from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter
from llama_index.core.schema import BaseNode, Document, TextNode

from ingestion.sources.base import SourceDocument


@dataclass(slots=True)
class Chunk:
    chunk_id_key: str
    text: str
    source: str
    title: str
    section_path: str
    chunk_index: int
    doc_id: str
    uri: str


def _section_path_from_node(node: BaseNode) -> str:
    meta = node.metadata or {}
    for key in ("header_path", "section_path"):
        if meta.get(key):
            return str(meta[key])
    parts: list[str] = []
    for level in range(1, 7):
        value = meta.get(f"Header_{level}") or meta.get(f"header_{level}")
        if value:
            parts.append(str(value))
    return " > ".join(parts)


def _contextualize(title: str, section_path: str, body: str) -> str:
    crumbs = [p for p in (title, section_path) if p]
    if not crumbs:
        return body
    return f"{' > '.join(crumbs)}\n\n{body}"


def _split_sentences(text: str) -> list[str]:
    """Lightweight sentence split — avoids NLTK punkt dependency in containers."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def _split_nodes(nodes: list[BaseNode], splitter: SentenceSplitter) -> list[BaseNode]:
    as_docs = [Document(text=n.get_content(), metadata=dict(n.metadata or {})) for n in nodes]
    return list(splitter.get_nodes_from_documents(as_docs))


def chunk_documents(
    documents: list[SourceDocument],
    *,
    chunk_size: int = 512,
    chunk_overlap: int = 100,
) -> list[Chunk]:
    """MarkdownNodeParser (when applicable) → SentenceSplitter → contextualize."""
    md_parser = MarkdownNodeParser()
    splitter = SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunking_tokenizer_fn=_split_sentences,
    )
    chunks: list[Chunk] = []

    for doc in documents:
        li_doc = Document(
            text=doc.text,
            doc_id=doc.doc_id,
            metadata={
                **doc.metadata,
                "title": doc.title,
                "source": doc.source,
                "uri": doc.uri,
            },
        )
        if doc.content_type == "markdown":
            nodes: list[BaseNode] = list(md_parser.get_nodes_from_documents([li_doc]))
        else:
            nodes = [TextNode(text=doc.text, metadata=dict(li_doc.metadata))]

        split_nodes = _split_nodes(nodes, splitter)
        for idx, node in enumerate(split_nodes):
            body = node.get_content().strip()
            if not body:
                continue
            section_path = _section_path_from_node(node)
            text = _contextualize(doc.title, section_path, body)
            chunks.append(
                Chunk(
                    chunk_id_key=f"{doc.source}:{doc.doc_id}:{idx}",
                    text=text,
                    source=doc.source,
                    title=doc.title,
                    section_path=section_path,
                    chunk_index=idx,
                    doc_id=doc.doc_id,
                    uri=doc.uri,
                )
            )
    return chunks
