"""Optional Langfuse tracing for RAG generate (no-op when keys unset)."""

from __future__ import annotations

import logging
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Protocol

logger = logging.getLogger("rag_orchestrator.tracing")


class SpanHandle(Protocol):
    def end(self, *, output: Any | None = None, metadata: dict[str, Any] | None = None) -> None: ...


class TraceHandle(Protocol):
    @property
    def id(self) -> str | None: ...

    def span(
        self,
        name: str,
        *,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SpanHandle: ...

    def generation(
        self,
        name: str,
        *,
        model: str | None = None,
        input: Any | None = None,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    def update(
        self,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...


class Tracer(Protocol):
    enabled: bool

    def start_trace(
        self,
        name: str,
        *,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AbstractContextManager[TraceHandle]: ...


@dataclass(slots=True)
class _NoOpSpan:
    def end(self, *, output: Any | None = None, metadata: dict[str, Any] | None = None) -> None:
        del output, metadata


@dataclass(slots=True)
class _NoOpTrace:
    @property
    def id(self) -> str | None:
        return None

    def span(
        self,
        name: str,
        *,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> _NoOpSpan:
        del name, input, metadata
        return _NoOpSpan()

    def generation(
        self,
        name: str,
        *,
        model: str | None = None,
        input: Any | None = None,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        del name, model, input, output, metadata

    def update(
        self,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        del output, metadata


@dataclass(slots=True)
class _NoOpTraceCtx:
    def __enter__(self) -> _NoOpTrace:
        return _NoOpTrace()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, exc, tb


@dataclass(slots=True)
class NoOpTracer:
    enabled: bool = False

    def start_trace(
        self,
        name: str,
        *,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> _NoOpTraceCtx:
        del name, input, metadata
        return _NoOpTraceCtx()


@dataclass(slots=True)
class _LangfuseSpan:
    _span: Any

    def end(self, *, output: Any | None = None, metadata: dict[str, Any] | None = None) -> None:
        kwargs: dict[str, Any] = {}
        if output is not None:
            kwargs["output"] = output
        if metadata is not None:
            kwargs["metadata"] = metadata
        self._span.end(**kwargs)


@dataclass(slots=True)
class _LangfuseTrace:
    _trace: Any

    @property
    def id(self) -> str | None:
        return getattr(self._trace, "id", None)

    def span(
        self,
        name: str,
        *,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> _LangfuseSpan:
        kwargs: dict[str, Any] = {"name": name}
        if input is not None:
            kwargs["input"] = input
        if metadata is not None:
            kwargs["metadata"] = metadata
        return _LangfuseSpan(self._trace.span(**kwargs))

    def generation(
        self,
        name: str,
        *,
        model: str | None = None,
        input: Any | None = None,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"name": name}
        if model is not None:
            kwargs["model"] = model
        if input is not None:
            kwargs["input"] = input
        if output is not None:
            kwargs["output"] = output
        if metadata is not None:
            kwargs["metadata"] = metadata
        gen = self._trace.generation(**kwargs)
        gen.end()

    def update(
        self,
        *,
        output: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {}
        if output is not None:
            kwargs["output"] = output
        if metadata is not None:
            kwargs["metadata"] = metadata
        if kwargs:
            self._trace.update(**kwargs)


@dataclass(slots=True)
class _LangfuseTraceCtx:
    _client: Any
    _name: str
    _input: Any | None
    _metadata: dict[str, Any] | None
    _trace: Any | None = field(default=None, init=False)

    def __enter__(self) -> _LangfuseTrace:
        kwargs: dict[str, Any] = {"name": self._name}
        if self._input is not None:
            kwargs["input"] = self._input
        if self._metadata is not None:
            kwargs["metadata"] = self._metadata
        self._trace = self._client.trace(**kwargs)
        return _LangfuseTrace(self._trace)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del tb
        if self._trace is not None and exc is not None:
            self._trace.update(
                metadata={"error": str(exc), "error_type": getattr(exc_type, "__name__", None)},
                level="ERROR",
            )
        try:
            self._client.flush()
        except Exception:  # noqa: BLE001 — never fail the request on telemetry flush
            logger.exception("langfuse flush failed")


@dataclass(slots=True)
class LangfuseTracer:
    _client: Any
    enabled: bool = True

    def start_trace(
        self,
        name: str,
        *,
        input: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> _LangfuseTraceCtx:
        return _LangfuseTraceCtx(self._client, name, input, metadata)


def build_tracer(
    *,
    host: str,
    public_key: str,
    secret_key: str,
) -> Tracer:
    """Return a live Langfuse tracer when keys are set; otherwise a no-op."""
    if not (public_key.strip() and secret_key.strip()):
        logger.info("langfuse tracing disabled (keys unset)")
        return NoOpTracer()

    try:
        from langfuse import Langfuse
    except ImportError:
        logger.warning("langfuse package missing; tracing disabled")
        return NoOpTracer()

    client = Langfuse(
        public_key=public_key.strip(),
        secret_key=secret_key.strip(),
        host=host.rstrip("/"),
    )
    logger.info("langfuse tracing enabled host=%s", host)
    return LangfuseTracer(client)


# Kept on the trace so the external judge can see a full ~512-token chunk.
TRACE_USED_CHUNK_TEXT_LIMIT = 4000


def chunk_payloads(chunks: list[Any], *, text_limit: int = 500) -> list[dict[str, Any]]:
    """Serialize retrieved chunks for Langfuse metadata (truncated text)."""
    rows: list[dict[str, Any]] = []
    for c in chunks:
        text = getattr(c, "text", "") or ""
        rows.append(
            {
                "id": getattr(c, "id", ""),
                "source": getattr(c, "source", ""),
                "title": getattr(c, "title", ""),
                "section_path": getattr(c, "section_path", ""),
                "score": getattr(c, "score", None),
                "text": text[:text_limit],
            }
        )
    return rows
