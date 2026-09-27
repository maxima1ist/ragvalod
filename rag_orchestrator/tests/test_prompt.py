"""Unit tests for prompt rendering."""

from rag_orchestrator.prompt import render_messages
from rag_orchestrator.qdrant_reader import RetrievedChunk


def test_render_messages_includes_context_and_question() -> None:
    chunks = [
        RetrievedChunk(
            id="1",
            text="Paris is the capital of France.",
            source="local_files",
            title="geo.md",
            section_path="Europe",
            score=0.9,
        )
    ]
    system_prompt, user_prompt = render_messages("What is the capital of France?", chunks)
    assert "[1]" in system_prompt
    assert "Paris is the capital of France." in system_prompt
    assert "local_files" in system_prompt
    assert "What is the capital of France?" in user_prompt
