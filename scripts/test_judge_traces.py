"""Unit tests for the external Langfuse judge (no live OpenRouter or Langfuse)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
import pytest
import respx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from judge_traces import (  # noqa: E402
    SCORE_NAMES,
    JudgeSettings,
    extract_case,
    host_side_url,
    judge_pending,
    load_dotenv,
    parse_judge_response,
    settings_from_env,
)


def _settings(**overrides: object) -> JudgeSettings:
    base = dict(
        langfuse_host="http://langfuse.test",
        public_key="pk",
        secret_key="sk",
        litellm_base_url="http://litellm.test",
        litellm_api_key="sk-test",
        model="judge-default",
        limit=5,
        scan=20,
    )
    base.update(overrides)
    return JudgeSettings(**base)  # type: ignore[arg-type]


def test_parse_judge_response_fenced_json() -> None:
    raw = """```json
{"faithfulness": 0.5, "answer_relevancy": "1", "context_precision": 0,
 "reasons": {"faithfulness": "half"}}
```"""
    scores = parse_judge_response(raw)
    assert scores.values == {
        "faithfulness": 0.5,
        "answer_relevancy": 1.0,
        "context_precision": 0.0,
    }
    assert scores.reasons["faithfulness"] == "half"


def test_parse_judge_response_strips_think_and_scales_percent() -> None:
    raw = (
        '<think>{"faithfulness": 1}</think>\n'
        '{"scores": {"faithfulness": 80, "answer_relevancy": 50, "context_precision": 100}}'
    )
    scores = parse_judge_response(raw)
    assert scores.values["faithfulness"] == pytest.approx(0.8)
    assert scores.values["context_precision"] == pytest.approx(1.0)


def test_parse_judge_response_rejects_out_of_range() -> None:
    raw = json.dumps({"faithfulness": 1.2, "answer_relevancy": 0.2, "context_precision": 0.2})
    with pytest.raises(ValueError, match="out of range"):
        parse_judge_response(raw)


def test_extract_case_reads_trace_fields() -> None:
    case = extract_case(
        {
            "id": "t1",
            "input": {"query": "Где?"},
            "output": {"answer": "Там."},
            "metadata": {"used_chunks": [{"text": "контекст"}, "  ", {"text": ""}]},
        }
    )
    assert case is not None
    assert case.query == "Где?"
    assert case.chunks == ("контекст",)


def test_extract_case_skips_incomplete_trace() -> None:
    assert extract_case({"id": "t1", "input": {"query": "q"}, "output": {}}) is None


def test_settings_keep_service_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JUDGE_KEEP_SERVICE_HOSTS", "1")
    monkeypatch.setenv("LANGFUSE_HOST", "http://langfuse:3000")
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm:4000")
    settings = settings_from_env([])
    assert settings.langfuse_host == "http://langfuse:3000"
    assert settings.litellm_base_url == "http://litellm:4000"


def test_host_side_url_rewrites_compose_dns() -> None:
    assert host_side_url("http://langfuse:3000", service="langfuse", port=3000) == (
        "http://localhost:3000"
    )
    assert host_side_url("http://localhost:4000", service="litellm", port=4000) == (
        "http://localhost:4000"
    )


def test_load_dotenv_does_not_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LITELLM_MASTER_KEY", "from-env")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text(
        'LITELLM_MASTER_KEY=from-file\nLANGFUSE_PUBLIC_KEY="pk-file"\n',
        encoding="utf-8",
    )
    load_dotenv(path)
    assert os.environ["LITELLM_MASTER_KEY"] == "from-env"
    assert os.environ["LANGFUSE_PUBLIC_KEY"] == "pk-file"


def test_settings_reject_chat_model() -> None:
    with pytest.raises(SystemExit, match="chat-default"):
        settings_from_env(["--model", "chat-default"])


def test_judge_alias_is_not_the_chat_model() -> None:
    for relative in (
        "configs/litellm.yaml",
        "configs/litellm.redis.yaml",
        "k8s/base/configs/litellm.yaml",
        "k8s/overlays/ha/configs/litellm.redis.yaml",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "model_name: judge-default" in text
        assert "model_name: judge-fallback" in text
        assert "openrouter/qwen/qwen3.8-27b:free" in text
        assert "openrouter/nvidia/nemotron-3-super-120b-a12b:free" in text
        assert "model_name: chat-default" in text
        chat_block, judge_block = text.split("model_name: judge-default", 1)
        assert "hosted_vllm/Qwen/Qwen2.5-7B-Instruct-AWQ" in chat_block
        judge_only = judge_block.split("model_name:", 1)[0]
        assert "hosted_vllm/Qwen/Qwen2.5-7B-Instruct-AWQ" not in judge_only


@respx.mock
def test_judge_posts_only_missing_scores() -> None:
    host = "http://langfuse.test"
    llm = "http://litellm.test"
    respx.get(f"{host}/api/public/traces").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "new",
                        "name": "rag.generate",
                        "input": {"query": "Где столица?"},
                        "output": {"answer": "Париж."},
                        "metadata": {"used_chunks": [{"text": "Париж — столица Франции."}]},
                    },
                    {
                        "id": "partial",
                        "name": "rag.generate",
                        "input": {"query": "q"},
                        "output": {"answer": "a"},
                        "metadata": {"used_chunks": [{"text": "ctx"}]},
                    },
                    {
                        "id": "done",
                        "name": "rag.generate",
                        "input": {"query": "q2"},
                        "output": {"answer": "a2"},
                        "metadata": {"used_chunks": [{"text": "ctx2"}]},
                    },
                    {
                        "id": "smoke",
                        "name": "smoke.langfuse",
                        "input": {"query": "ping"},
                        "output": {"answer": "pong"},
                    },
                ]
            },
        )
    )

    def scores(request: httpx.Request) -> httpx.Response:
        trace_id = request.url.params.get("traceId")
        if trace_id == "done":
            data = [{"traceId": "done", "name": name, "value": 1} for name in SCORE_NAMES]
        elif trace_id == "partial":
            data = [{"traceId": "partial", "name": "faithfulness", "value": 0.4}]
        else:
            data = []
        return httpx.Response(200, json={"data": data})

    respx.get(f"{host}/api/public/scores").mock(side_effect=scores)
    chat = respx.post(f"{llm}/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "faithfulness": 1,
                                    "answer_relevancy": 0.5,
                                    "context_precision": 0.25,
                                    "reasons": {"faithfulness": "supported"},
                                }
                            )
                        }
                    }
                ]
            },
        )
    )
    posted = respx.post(f"{host}/api/public/scores").mock(
        return_value=httpx.Response(200, json={"id": "s"})
    )

    summary = judge_pending(_settings())

    assert summary.scored == 2
    assert summary.skipped == 1
    assert summary.failed == 0
    assert chat.call_count == 2
    first_body = json.loads(chat.calls[0].request.content)
    assert first_body["model"] == "judge-default"
    assert first_body["messages"][0]["role"] == "system"
    assert "Где столица?" in first_body["messages"][1]["content"]
    assert chat.calls[0].request.headers["authorization"] == "Bearer sk-test"
    posted_bodies = [json.loads(call.request.content) for call in posted.calls]
    names_by_trace: dict[str, set[str]] = {}
    for body in posted_bodies:
        names_by_trace.setdefault(body["traceId"], set()).add(body["name"])
        assert body["dataType"] == "NUMERIC"
        assert body["value"] in {1, 0.5, 0.25}
    assert names_by_trace["new"] == set(SCORE_NAMES)
    assert names_by_trace["partial"] == {"answer_relevancy", "context_precision"}
    assert "done" not in names_by_trace


@respx.mock
def test_judge_uses_fallback_after_rate_limit() -> None:
    host = "http://langfuse.test"
    llm = "http://litellm.test"
    respx.get(f"{host}/api/public/traces").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "new",
                        "name": "rag.generate",
                        "input": {"query": "q"},
                        "output": {"answer": "a"},
                        "metadata": {"used_chunks": [{"text": "ctx"}]},
                    }
                ]
            },
        )
    )
    respx.get(f"{host}/api/public/scores").mock(return_value=httpx.Response(200, json={"data": []}))

    def chat(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if body["model"] == "judge-default":
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        return httpx.Response(
            200,
            json={
                "model": "nvidia/nemotron-3-super-120b-a12b:free",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "faithfulness": 0.2,
                                    "answer_relevancy": 0.3,
                                    "context_precision": 0.4,
                                }
                            )
                        }
                    }
                ],
            },
        )

    respx.post(f"{llm}/v1/chat/completions").mock(side_effect=chat)
    posted = respx.post(f"{host}/api/public/scores").mock(
        return_value=httpx.Response(200, json={"id": "s"})
    )

    summary = judge_pending(_settings())

    assert summary.scored == 1
    assert summary.failed == 0
    bodies = [json.loads(call.request.content) for call in posted.calls]
    assert {body["name"] for body in bodies} == set(SCORE_NAMES)
    assert bodies[0]["comment"].startswith("judge=nvidia/nemotron-3-super-120b-a12b:free")


@respx.mock
def test_dry_run_does_not_call_the_model() -> None:
    host = "http://langfuse.test"
    respx.get(f"{host}/api/public/traces/t1").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "t1",
                "name": "rag.generate",
                "input": {"query": "q"},
                "output": {"answer": "a"},
                "metadata": {"used_chunks": []},
            },
        )
    )
    respx.get(f"{host}/api/public/scores").mock(return_value=httpx.Response(200, json={"data": []}))
    chat = respx.post("http://litellm.test/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={})
    )

    summary = judge_pending(_settings(trace_id="t1", dry_run=True))

    assert summary.dry_run == 1
    assert summary.scored == 0
    assert chat.call_count == 0
