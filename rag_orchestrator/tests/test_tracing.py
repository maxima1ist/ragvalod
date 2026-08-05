"""Unit tests for optional Langfuse tracing wrappers."""

from __future__ import annotations

from rag_orchestrator.tracing import NoOpTracer, build_tracer, chunk_payloads


def test_noop_tracer_context() -> None:
    tracer = NoOpTracer()
    assert tracer.enabled is False
    with tracer.start_trace("rag.generate", input={"query": "q"}) as trace:
        assert trace.id is None
        span = trace.span("embed")
        span.end(output={"ok": True})
        trace.generation("chat", model="chat-default", output="hi")
        trace.update(output={"answer": "hi"})


def test_build_tracer_disabled_without_keys() -> None:
    tracer = build_tracer(host="http://langfuse:3000", public_key="", secret_key="")
    assert tracer.enabled is False


def test_chunk_payloads_truncates() -> None:
    class C:
        id = "1"
        text = "x" * 1000
        source = "local_files"
        title = "t"
        section_path = ""
        score = 0.5

    rows = chunk_payloads([C()], text_limit=10)
    assert rows[0]["text"] == "x" * 10
    assert rows[0]["id"] == "1"
