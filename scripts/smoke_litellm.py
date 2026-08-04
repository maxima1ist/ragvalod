#!/usr/bin/env python3
"""Smoke-test LiteLLM Proxy: chat, batch embeddings, rerank.

Requires LiteLLM (+ Infinity for embed/rerank) running, e.g.:
  docker compose up -d litellm infinity

Usage:
  uv run python scripts/smoke_litellm.py
"""

from __future__ import annotations

import logging
import os
import sys

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("smoke_litellm")


def _base_url() -> str:
    return os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").rstrip("/")


def _headers() -> dict[str, str]:
    key = os.environ.get("LITELLM_MASTER_KEY", "sk-ragvalod-local")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def check_chat(client: httpx.Client) -> None:
    logger.info("POST /v1/chat/completions (chat-default)")
    response = client.post(
        f"{_base_url()}/v1/chat/completions",
        headers=_headers(),
        json={
            "model": "chat-default",
            "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
            "max_tokens": 32,
            "temperature": 0,
        },
        timeout=120.0,
    )
    response.raise_for_status()
    body = response.json()
    content = body["choices"][0]["message"].get("content") or ""
    logger.info("chat response: %s", content[:200] if content else "<empty>")
    if not content.strip():
        raise RuntimeError("empty chat completion content")


def check_embeddings(client: httpx.Client) -> None:
    texts = [
        "passage: The capital of France is Paris.",
        "passage: Qdrant stores vector embeddings.",
        "passage: Ragvalod is a personal RAG chatbot.",
    ]
    logger.info("POST /v1/embeddings batch size=%s (embedder-default)", len(texts))
    response = client.post(
        f"{_base_url()}/v1/embeddings",
        headers=_headers(),
        json={"model": "embedder-default", "input": texts},
        timeout=120.0,
    )
    response.raise_for_status()
    data = response.json()["data"]
    if len(data) != len(texts):
        raise RuntimeError(f"expected {len(texts)} embeddings, got {len(data)}")
    dim = len(data[0]["embedding"])
    logger.info("embeddings ok: count=%s dim=%s", len(data), dim)
    if dim < 8:
        raise RuntimeError(f"embedding dim too small: {dim}")


def check_rerank(client: httpx.Client) -> None:
    documents = [
        "Paris is the capital of France.",
        "Vector databases store embeddings.",
        "Bananas are yellow fruit.",
    ]
    logger.info("POST /rerank (reranker-default)")
    response = client.post(
        f"{_base_url()}/rerank",
        headers=_headers(),
        json={
            "model": "reranker-default",
            "query": "What is the capital of France?",
            "documents": documents,
            "top_n": 2,
        },
        timeout=120.0,
    )
    response.raise_for_status()
    body = response.json()
    results = body.get("results") or body.get("data") or []
    if not results:
        raise RuntimeError(f"empty rerank results: {body}")
    logger.info("rerank top result: %s", results[0])


def main() -> int:
    logger.info("LiteLLM base URL: %s", _base_url())
    with httpx.Client() as client:
        check_chat(client)
        check_embeddings(client)
        check_rerank(client)
    logger.info("smoke_litellm OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logger.exception("smoke_litellm FAILED")
        raise SystemExit(1) from None
