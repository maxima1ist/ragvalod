#!/usr/bin/env python3
"""Score recent rag.generate traces with an external LLM judge.

Reads traces from Langfuse, asks LiteLLM alias ``judge-default`` (OpenRouter,
not the chat model) for three scores, and writes them back via the scores API.
Does not run inside POST /generate.

Usage:
  make judge
  uv run python scripts/judge_traces.py --limit 5
  uv run python scripts/judge_traces.py --trace-id <id> --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

SCORE_NAMES = ("faithfulness", "answer_relevancy", "context_precision")
TRACE_NAME = "rag.generate"

SYSTEM_PROMPT = """You evaluate one retrieval-augmented answer.
Use only the question, the retrieved context, and the answer.
Do not use outside knowledge.

Return one JSON object and no other text. Keys:
- faithfulness: number from 0 to 1. Share of answer claims that the context supports.
  Use 1 when every claim is supported, or when the answer correctly says the context
  is insufficient. Use 0 when the answer contradicts the context or adds unsupported facts.
- answer_relevancy: number from 0 to 1. How directly the answer addresses the question.
- context_precision: number from 0 to 1. Share of context chunks that help answer
  the question.
- reasons: object with the same three keys and a short sentence each.

The question, context, and answer may be in any language.
Scores are fractions from 0 to 1, not percentages."""

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_START_RE = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_FENCE_END_RE = re.compile(r"\s*```\s*$")


@dataclass(frozen=True, slots=True)
class JudgeCase:
    trace_id: str
    query: str
    answer: str
    chunks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class JudgeScores:
    values: dict[str, float]
    reasons: dict[str, str]


@dataclass(frozen=True, slots=True)
class JudgeSettings:
    langfuse_host: str
    public_key: str
    secret_key: str
    litellm_base_url: str
    litellm_api_key: str
    model: str = "judge-default"
    fallback_model: str | None = "judge-fallback"
    limit: int = 5
    scan: int = 50
    trace_id: str | None = None
    dry_run: bool = False


@dataclass(slots=True)
class JudgeSummary:
    scored: int = 0
    skipped: int = 0
    failed: int = 0
    dry_run: int = 0
    errors: list[str] = field(default_factory=list)


def load_dotenv(path: Path) -> None:
    """Fill unset environment variables from a .env file. Never overrides."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def _keep_service_hosts() -> bool:
    return os.environ.get("JUDGE_KEEP_SERVICE_HOSTS", "").strip().lower() in {"1", "true", "yes"}


def host_side_url(url: str, *, service: str, port: int) -> str:
    """Rewrite a compose DNS hostname to localhost for this host-side script."""
    parsed = urlparse(url)
    if parsed.hostname == service:
        return f"http://localhost:{port}"
    return url.rstrip("/")


def resolve_service_url(url: str, *, service: str, port: int) -> str:
    """Keep compose/k8s DNS when JUDGE_KEEP_SERVICE_HOSTS=1; otherwise use localhost."""
    if _keep_service_hosts():
        return url.rstrip("/")
    return host_side_url(url, service=service, port=port)


def settings_from_env(argv: list[str] | None = None) -> JudgeSettings:
    parser = argparse.ArgumentParser(description="Score rag.generate traces with judge-default.")
    parser.add_argument("--limit", type=int, default=5, help="Max traces to score this run.")
    parser.add_argument("--scan", type=int, default=50, help="How many recent traces to inspect.")
    parser.add_argument("--trace-id", default=None, help="Score one trace and ignore --limit.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print cases without calling the judge.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("JUDGE_MODEL", "judge-default"),
        help="LiteLLM alias. Must not be chat-default.",
    )
    args = parser.parse_args(argv)
    if args.model == "chat-default":
        raise SystemExit("judge model must not be chat-default")
    if args.limit < 1 or args.scan < 1:
        raise SystemExit("--limit and --scan must be >= 1")

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "pk-lf-ragvalod-local").strip()
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "sk-lf-ragvalod-local").strip()
    litellm_key = os.environ.get("LITELLM_MASTER_KEY", "sk-ragvalod-local").strip()
    missing = [
        name
        for name, value in (
            ("LANGFUSE_PUBLIC_KEY", public_key),
            ("LANGFUSE_SECRET_KEY", secret_key),
            ("LITELLM_MASTER_KEY", litellm_key),
        )
        if not value
    ]
    if missing:
        raise SystemExit(f"missing env: {', '.join(missing)}")

    langfuse_host = resolve_service_url(
        os.environ.get("LANGFUSE_HOST", "http://localhost:3000"),
        service="langfuse",
        port=3000,
    )
    litellm_base = resolve_service_url(
        os.environ.get("LITELLM_BASE_URL", "http://localhost:4000"),
        service="litellm",
        port=4000,
    )
    return JudgeSettings(
        langfuse_host=langfuse_host,
        public_key=public_key,
        secret_key=secret_key,
        litellm_base_url=litellm_base,
        litellm_api_key=litellm_key,
        model=args.model,
        fallback_model=_fallback_model(),
        limit=args.limit,
        scan=max(args.scan, args.limit),
        trace_id=args.trace_id,
        dry_run=args.dry_run,
    )


def _fallback_model() -> str | None:
    raw = os.environ.get("JUDGE_FALLBACK_MODEL", "judge-fallback").strip()
    if not raw:
        return None
    if raw == "chat-default":
        raise SystemExit("judge fallback must not be chat-default")
    return raw


def model_chain(settings: JudgeSettings) -> list[str]:
    chain = [settings.model]
    fallback = settings.fallback_model
    if fallback and fallback not in chain:
        chain.append(fallback)
    return chain


def _text_field(payload: Any, key: str) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, str):
            return value.strip()
    return ""


def _chunk_texts(metadata: Any) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    raw = metadata.get("used_chunks") or []
    if not isinstance(raw, list):
        return []
    texts: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            texts.append(item.strip())
        elif isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
    return texts


def extract_case(trace: dict[str, Any]) -> JudgeCase | None:
    trace_id = trace.get("id")
    if not isinstance(trace_id, str) or not trace_id:
        return None
    query = _text_field(trace.get("input"), "query")
    answer = _text_field(trace.get("output"), "answer")
    if not query or not answer:
        return None
    return JudgeCase(
        trace_id=trace_id,
        query=query,
        answer=answer,
        chunks=tuple(_chunk_texts(trace.get("metadata"))),
    )


def build_user_prompt(case: JudgeCase) -> str:
    if case.chunks:
        context = "\n\n".join(
            f"[{index}] {text}" for index, text in enumerate(case.chunks, start=1)
        )
    else:
        context = "(empty)"
    return f"Question:\n{case.query}\n\nContext:\n{context}\n\nAnswer:\n{case.answer}"


def _json_object(text: str) -> dict[str, Any]:
    cleaned = _THINK_RE.sub("", text).strip()
    cleaned = _FENCE_START_RE.sub("", cleaned)
    cleaned = _FENCE_END_RE.sub("", cleaned).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("judge response is not JSON") from None
        data = json.loads(cleaned[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("judge response JSON is not an object")
    return data


def _as_float(value: Any, name: str) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{name} is not a number")
    if isinstance(value, str):
        value = value.strip()
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} is not a number") from exc


def parse_judge_response(content: str) -> JudgeScores:
    data = _json_object(content)
    nested = data.get("scores")
    source = data
    if not all(name in data for name in SCORE_NAMES) and isinstance(nested, dict):
        source = nested
    values = {name: _as_float(source.get(name), name) for name in SCORE_NAMES}
    percent = all(value > 1 for value in values.values()) and all(
        value <= 100 for value in values.values()
    )
    if percent:
        values = {name: value / 100 for name, value in values.items()}
    for name, value in values.items():
        if value < 0 or value > 1:
            raise ValueError(f"{name} out of range: {value}")
    reasons_raw = source.get("reasons")
    if not isinstance(reasons_raw, dict):
        reasons_raw = data.get("reasons") if isinstance(data.get("reasons"), dict) else {}
    reasons: dict[str, str] = {}
    for name in SCORE_NAMES:
        text = reasons_raw.get(name) if isinstance(reasons_raw, dict) else None
        if isinstance(text, str) and text.strip():
            reasons[name] = text.strip()[:500]
    return JudgeScores(values=values, reasons=reasons)


def message_text(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        joined = "".join(parts).strip()
        if joined:
            return joined
    for key in ("reasoning", "reasoning_content"):
        reasoning = message.get(key)
        if isinstance(reasoning, str) and reasoning.strip():
            return reasoning
    return ""


def score_id(trace_id: str, name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ragvalod/{trace_id}/{name}"))


def _raise_for_status(response: httpx.Response, what: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = response.text[:300].replace("\n", " ")
        raise RuntimeError(f"{what} failed: HTTP {response.status_code} {body}") from exc


def _existing_score_names(client: httpx.Client, host: str, trace_id: str) -> set[str]:
    response = client.get(
        f"{host}/api/public/scores",
        params={"traceId": trace_id, "limit": 100},
    )
    _raise_for_status(response, "list scores")
    names: set[str] = set()
    for row in response.json().get("data") or []:
        if not isinstance(row, dict):
            continue
        if row.get("traceId") != trace_id:
            continue
        name = row.get("name")
        if name in SCORE_NAMES:
            names.add(str(name))
    return names


def _list_traces(client: httpx.Client, settings: JudgeSettings) -> list[dict[str, Any]]:
    if settings.trace_id:
        response = client.get(f"{settings.langfuse_host}/api/public/traces/{settings.trace_id}")
        _raise_for_status(response, "get trace")
        body = response.json()
        trace = body.get("trace") if isinstance(body, dict) and "trace" in body else body
        if not isinstance(trace, dict):
            raise RuntimeError("get trace returned an unexpected body")
        return [trace]

    response = client.get(
        f"{settings.langfuse_host}/api/public/traces",
        params={"limit": settings.scan},
    )
    _raise_for_status(response, "list traces")
    rows = response.json().get("data") or []
    return [row for row in rows if isinstance(row, dict) and row.get("name") == TRACE_NAME]


_RETRY_STATUS = {429, 502, 503, 504}


def _call_judge(
    client: httpx.Client, settings: JudgeSettings, case: JudgeCase
) -> tuple[JudgeScores, str]:
    chain = model_chain(settings)
    payload_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(case)},
    ]
    last_error: Exception | None = None
    for index, model in enumerate(chain):
        response = client.post(
            f"{settings.litellm_base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.litellm_api_key}"},
            json={
                "model": model,
                "temperature": 0,
                "max_tokens": 512,
                "messages": payload_messages,
            },
        )
        has_next = index < len(chain) - 1
        if response.status_code in _RETRY_STATUS and has_next:
            print(
                f"retry {case.trace_id} {model} HTTP {response.status_code}",
                file=sys.stderr,
            )
            continue
        try:
            _raise_for_status(response, "judge chat")
            body = response.json()
            message = body["choices"][0]["message"]
            text = message_text(message)
            if not text:
                raise ValueError("empty judge response")
            served = body.get("model")
            if not isinstance(served, str) or not served.strip():
                served = model
            return parse_judge_response(text), served
        except (RuntimeError, ValueError, KeyError, IndexError) as exc:
            last_error = exc
            if has_next:
                print(f"retry {case.trace_id} {model}: {exc}", file=sys.stderr)
                continue
            raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("judge chat failed")


def _post_scores(
    client: httpx.Client,
    host: str,
    case: JudgeCase,
    scores: JudgeScores,
    existing: set[str],
    served_model: str,
) -> None:
    for name in SCORE_NAMES:
        if name in existing:
            continue
        reason = scores.reasons.get(name)
        comment = f"judge={served_model}"
        if reason:
            comment = f"{comment}; {reason}"
        response = client.post(
            f"{host}/api/public/scores",
            json={
                "id": score_id(case.trace_id, name),
                "traceId": case.trace_id,
                "name": name,
                "value": scores.values[name],
                "dataType": "NUMERIC",
                "comment": comment[:500],
            },
        )
        _raise_for_status(response, f"post score {name}")


def judge_pending(settings: JudgeSettings) -> JudgeSummary:
    summary = JudgeSummary()
    auth = (settings.public_key, settings.secret_key)
    with (
        httpx.Client(timeout=120.0, auth=auth) as langfuse,
        httpx.Client(timeout=120.0) as litellm,
    ):
        traces = _list_traces(langfuse, settings)
        attempted = 0
        for trace in traces:
            if settings.trace_id is None and attempted >= settings.limit:
                break
            case = extract_case(trace)
            if case is None:
                print(f"skip {trace.get('id')} missing query or answer")
                summary.skipped += 1
                continue
            existing = _existing_score_names(langfuse, settings.langfuse_host, case.trace_id)
            if existing >= set(SCORE_NAMES):
                print(f"skip {case.trace_id} already scored")
                summary.skipped += 1
                continue
            if settings.trace_id is None:
                attempted += 1
            if settings.dry_run:
                print(
                    f"dry-run {case.trace_id} chunks={len(case.chunks)} "
                    f"missing={','.join(name for name in SCORE_NAMES if name not in existing)}"
                )
                summary.dry_run += 1
                continue
            try:
                scores, served = _call_judge(litellm, settings, case)
                _post_scores(
                    langfuse,
                    settings.langfuse_host,
                    case,
                    scores,
                    existing,
                    served,
                )
            except (httpx.HTTPError, RuntimeError, ValueError, KeyError, IndexError) as exc:
                print(f"FAIL {case.trace_id}: {exc}", file=sys.stderr)
                summary.failed += 1
                summary.errors.append(f"{case.trace_id}: {exc}")
                continue
            rendered = " ".join(f"{name}={scores.values[name]:.2f}" for name in SCORE_NAMES)
            print(f"scored {case.trace_id} {rendered}")
            summary.scored += 1
    print(
        f"done scored={summary.scored} skipped={summary.skipped} "
        f"failed={summary.failed} dry_run={summary.dry_run}"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    try:
        settings = settings_from_env(argv)
    except SystemExit as exc:
        if exc.code not in (None, 0):
            print(f"FAIL: {exc}", file=sys.stderr)
            return int(exc.code) if isinstance(exc.code, int) else 1
        raise
    try:
        summary = judge_pending(settings)
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
