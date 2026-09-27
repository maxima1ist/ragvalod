#!/usr/bin/env python3
"""Call GenerateAnswer / GetDataStatus on a running RAG Orchestrator."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import grpc

from ragvalod_proto import rag_pb2, rag_pb2_grpc


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--addr",
        default=os.environ.get("RAG_GRPC_ADDR", "127.0.0.1:50052"),
    )
    parser.add_argument("--query", default="What is ragvalod named after?")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--rerank-top-n", type=int, default=3)
    args = parser.parse_args()

    async with grpc.aio.insecure_channel(args.addr) as channel:
        stub = rag_pb2_grpc.RagServiceStub(channel)
        status = await stub.GetDataStatus(rag_pb2.GetDataStatusRequest())
        print(
            "data_initialized=",
            status.data_initialized,
            "sources=",
            [(s.source_name, s.document_count, s.ingested_at) for s in status.sources],
        )
        try:
            response = await stub.GenerateAnswer(
                rag_pb2.GenerateAnswerRequest(
                    query=args.query,
                    retrieval=rag_pb2.RetrievalParams(
                        top_k=args.top_k,
                        rerank_top_n=args.rerank_top_n,
                    ),
                    generation=rag_pb2.GenerationParams(temperature=0.2, max_tokens=256),
                )
            )
        except grpc.aio.AioRpcError as exc:
            print(f"RPC error: {exc.code().name} {exc.details()}", file=sys.stderr)
            return 1
        print("answer:", response.answer)
        print("used_chunks:")
        for chunk in response.used_chunks:
            print(f"  - [{chunk.score:.3f}] {chunk.source}/{chunk.title}: {chunk.text[:120]}")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
