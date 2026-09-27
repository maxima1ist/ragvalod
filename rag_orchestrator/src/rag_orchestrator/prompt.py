"""Jinja2 prompt rendering for RAG generation."""

from __future__ import annotations

from jinja2 import BaseLoader, Environment

from rag_orchestrator.qdrant_reader import RetrievedChunk

_TEMPLATE = (
    "You are ragvalod, a personal RAG assistant. "
    "Answer using only the provided context chunks.\n"
    "If the context is insufficient, say you do not know. "
    "Be concise and cite sources by number like [1].\n"
    "\n"
    "{% for chunk in chunks -%}\n"
    "[{{ chunk.index }}] source={{ chunk.source }} title={{ chunk.title }}"
    "{% if chunk.section_path %} section={{ chunk.section_path }}{% endif %}\n"
    "{{ chunk.text }}\n"
    "\n"
    "{% endfor %}\n"
    "---USER---\n"
    "Question: {{ query }}\n"
)

_ENV = Environment(loader=BaseLoader(), trim_blocks=True, lstrip_blocks=True)


def render_messages(query: str, chunks: list[RetrievedChunk]) -> tuple[str, str]:
    """Return (system_prompt, user_prompt)."""
    template = _ENV.from_string(_TEMPLATE)
    rendered = template.render(
        query=query,
        chunks=[
            {
                "index": i + 1,
                "text": c.text,
                "source": c.source,
                "title": c.title,
                "section_path": c.section_path,
                "score": c.score,
            }
            for i, c in enumerate(chunks)
        ],
    )
    if "\n---USER---\n" not in rendered:
        raise RuntimeError("rag template must contain ---USER--- separator")
    system_prompt, user_prompt = rendered.split("\n---USER---\n", 1)
    return system_prompt.strip(), user_prompt.strip()
