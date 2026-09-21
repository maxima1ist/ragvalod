#!/usr/bin/env python3
"""Break down RAG latency by phase (stage 11.1).

Measures embed → vector search → rerank → chat the same way the orchestrator
does (LiteLLM + Qdrant gRPC). Use after ingest with data_initialized=true.

  LITELLM_BASE_URL=http://localhost:4000 \\
  QDRANT_HOST=localhost \\
  uv run python scripts/profile_rag.py

  uv run python scripts/profile_rag.py --top-k-sweep 10,20,30,50 --skip-chat
  uv run python scripts/profile_rag.py --repeat-embed 3

LiteLLM in-memory cache makes repeated identical embed/chat calls much faster;
restart litellm or vary query text for cold timings.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rag_orchestrator" / "src"))

from rag_orchestrator.litellm_client import LiteLLMClient  # noqa: E402
from rag_orchestrator.prompt import render_messages  # noqa: E402
from rag_orchestrator.qdrant_reader import QdrantReader  # noqa: E402


@dataclass(slots=True)
class PhaseTimings:
    embed_s: float
    search_s: float
    rerank_s: float
    prompt_s: float
    chat_s: float
    candidate_count: int
    used_count: int

    @property
    def retrieval_s(self) -> float:
        return self.embed_s + self.search_s + self.rerank_s

    @property
    def total_s(self) -> float:
        return self.retrieval_s + self.prompt_s + self.chat_s


def _pct(part: float, whole: float) -> float:
    if whole <= 0:
        return 0.0
    return 100.0 * part / whole


def format_report(
    query: str,
    timings: PhaseTimings,
    *,
    top_k: int,
    rerank_top_n: int,
    embed_repeats: list[float] | None = None,
) -> str:
    lines = [
        f"query: {query[:120]!r}",
        f"top_k={top_k} rerank_top_n={rerank_top_n} "
        f"candidates={timings.candidate_count} used={timings.used_count}",
        "--- phase seconds (% of total) ---",
        f"  embed:   {timings.embed_s:7.3f}  ({_pct(timings.embed_s, timings.total_s):5.1f}%)",
        f"  search:  {timings.search_s:7.3f}  ({_pct(timings.search_s, timings.total_s):5.1f}%)",
        f"  rerank:  {timings.rerank_s:7.3f}  ({_pct(timings.rerank_s, timings.total_s):5.1f}%)",
        f"  prompt:  {timings.prompt_s:7.3f}  ({_pct(timings.prompt_s, timings.total_s):5.1f}%)",
        f"  chat:    {timings.chat_s:7.3f}  ({_pct(timings.chat_s, timings.total_s):5.1f}%)",
        f"  total:   {timings.total_s:7.3f}",
        f"  retrieval subtotal: {timings.retrieval_s:.3f}s",
    ]
    if embed_repeats:
        cold, *warm = embed_repeats
        if warm:
            lines.append(
                f"embed cache probe: cold={cold:.3f}s warm_mean={sum(warm) / len(warm):.3f}s "
                f"(n={len(embed_repeats)})"
            )
    return "\n".join(lines)


async def profile_once(
    *,
    llm: LiteLLMClient,
    store: QdrantReader,
    query: str,
    top_k: int,
    rerank_top_n: int,
    max_tokens: int,
    temperature: float,
    skip_chat: bool,
) -> PhaseTimings:
    t0 = time.perf_counter()
    vector = await llm.embed_query(query)
    embed_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    candidates = await store.search(vector, top_k=top_k)
    search_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    used = await llm.rerank(query, candidates, top_n=rerank_top_n)
    rerank_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    system_prompt, user_prompt = render_messages(query, used)
    prompt_s = time.perf_counter() - t0

    chat_s = 0.0
    if not skip_chat:
        t0 = time.perf_counter()
        await llm.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        chat_s = time.perf_counter() - t0

    return PhaseTimings(
        embed_s=embed_s,
        search_s=search_s,
        rerank_s=rerank_s,
        prompt_s=prompt_s,
        chat_s=chat_s,
        candidate_count=len(candidates),
        used_count=len(used),
    )


async def probe_embed_cache(llm: LiteLLMClient, query: str, repeats: int) -> list[float]:
    times: list[float] = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        await llm.embed_query(query)
        times.append(time.perf_counter() - t0)
    return times


def _build_clients() -> tuple[LiteLLMClient, QdrantReader]:
    litellm_base = os.environ.get("LITELLM_BASE_URL", "http://localhost:4000")
    api_key = os.environ.get("LITELLM_MASTER_KEY", "sk-ragvalod-local")
    qdrant_host = os.environ.get("QDRANT_HOST", os.environ.get("RAG_QDRANT_HOST", "localhost"))
    http_port = int(
        os.environ.get("QDRANT_HTTP_PORT", os.environ.get("RAG_QDRANT_HTTP_PORT", "6333"))
    )
    grpc_port = int(
        os.environ.get("QDRANT_GRPC_PORT", os.environ.get("RAG_QDRANT_GRPC_PORT", "6334"))
    )
    collection = os.environ.get("RAG_COLLECTION_NAME", "documents")
    embedding_model = os.environ.get("RAG_EMBEDDING_MODEL_ALIAS", "embedder-default")
    embedding_name = os.environ.get("RAG_EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-small")
    query_prefix = os.environ.get("RAG_EMBEDDING_QUERY_PREFIX", "query: ")
    reranker = os.environ.get("RAG_RERANKER_MODEL_ALIAS", "reranker-default")
    chat = os.environ.get("RAG_CHAT_MODEL_ALIAS", "chat-default")
    vector_size = int(os.environ.get("RAG_EMBEDDING_VECTOR_SIZE", "384"))

    llm = LiteLLMClient(
        base_url=litellm_base,
        api_key=api_key,
        embedding_model_alias=embedding_model,
        query_prefix=query_prefix,
        reranker_model_alias=reranker,
        chat_model_alias=chat,
    )
    store = QdrantReader(
        host=qdrant_host,
        http_port=http_port,
        grpc_port=grpc_port,
        collection=collection,
        embedding_model_name=embedding_name,
        vector_size=vector_size,
    )
    return llm, store


async def _async_main(args: argparse.Namespace) -> int:
    llm, store = _build_clients()

    if not await store.is_initialized():
        print("Qdrant collection not initialized — run ingest first.", file=sys.stderr)
        return 1

    embed_probe: list[float] | None = None
    if args.repeat_embed > 1:
        embed_probe = await probe_embed_cache(llm, args.query, args.repeat_embed)

    if args.top_k_sweep:
        print("=== top_k sweep (search + rerank only) ===")
        for top_k in args.top_k_sweep:
            t0 = time.perf_counter()
            vector = await llm.embed_query(args.query)
            embed_s = time.perf_counter() - t0
            t0 = time.perf_counter()
            candidates = await store.search(vector, top_k=top_k)
            search_s = time.perf_counter() - t0
            t0 = time.perf_counter()
            await llm.rerank(args.query, candidates, top_n=args.rerank_top_n)
            rerank_s = time.perf_counter() - t0
            print(
                f"top_k={top_k:3d}  embed={embed_s:.3f}s search={search_s:.3f}s "
                f"rerank={rerank_s:.3f}s (n={len(candidates)})"
            )
        print()

    timings = await profile_once(
        llm=llm,
        store=store,
        query=args.query,
        top_k=args.top_k,
        rerank_top_n=args.rerank_top_n,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        skip_chat=args.skip_chat,
    )
    print(
        format_report(
            args.query,
            timings,
            top_k=args.top_k,
            rerank_top_n=args.rerank_top_n,
            embed_repeats=embed_probe,
        )
    )
    return 0


def _parse_top_k_sweep(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile RAG pipeline phases.")
    parser.add_argument(
        "--query",
        default=os.environ.get(
            "PROFILE_RAG_QUERY",
            "What is the serial of Skrygalov-amber and who may move it?",
        ),
    )
    parser.add_argument("--top-k", type=int, default=int(os.environ.get("RAG_DEFAULT_TOP_K", "50")))
    parser.add_argument(
        "--rerank-top-n",
        type=int,
        default=int(os.environ.get("RAG_DEFAULT_RERANK_TOP_N", "5")),
    )
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--skip-chat", action="store_true", help="Skip vLLM/chat phase.")
    parser.add_argument(
        "--top-k-sweep",
        type=_parse_top_k_sweep,
        default=None,
        metavar="K1,K2,...",
        help="Run search+rerank at each top_k (shared embed).",
    )
    parser.add_argument(
        "--repeat-embed",
        type=int,
        default=1,
        help="Repeat embed with same query to observe LiteLLM cache.",
    )
    args = parser.parse_args()
    if args.top_k_sweep is None and os.environ.get("PROFILE_RAG_TOP_K_SWEEP"):
        args.top_k_sweep = _parse_top_k_sweep(os.environ["PROFILE_RAG_TOP_K_SWEEP"])

    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
