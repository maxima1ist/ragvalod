#!/usr/bin/env python3
"""Trigger a Notion ingest job (token from env / CLI, not persisted)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time

import grpc

from ragvalod_proto import ingestion_pb2, ingestion_pb2_grpc


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--addr",
        default=os.environ.get("INGESTION_GRPC_ADDR", "127.0.0.1:50051"),
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("NOTION_ACCESS_KEY")
        or os.environ.get("NOTION_INTEGRATION_TOKEN")
        or "",
    )
    parser.add_argument("--page-ids", default="", help="Comma-separated Notion page IDs")
    parser.add_argument("--query", default="", help="Search query when page-ids omitted")
    parser.add_argument("--max-pages", default="3")
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()

    if not args.token:
        print("missing Notion token (--token or NOTION_ACCESS_KEY)", file=sys.stderr)
        return 1

    options: dict[str, str] = {"max_pages": args.max_pages}
    if args.page_ids:
        options["page_ids"] = args.page_ids
    if args.query:
        options["query"] = args.query

    async with grpc.aio.insecure_channel(args.addr) as channel:
        stub = ingestion_pb2_grpc.IngestionServiceStub(channel)
        response = await stub.TriggerIngest(
            ingestion_pb2.TriggerIngestRequest(
                sources=[
                    ingestion_pb2.SourceSpec(
                        name="notion",
                        credentials={"integration_token": args.token},
                        options=options,
                    )
                ]
            )
        )
        job_id = response.job_id
        print("job_id:", job_id)
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            status = await stub.GetJobStatus(ingestion_pb2.GetJobStatusRequest(job_id=job_id))
            state = ingestion_pb2.JobState.Name(status.state)
            print(
                f"state={state} message={status.message!r} sources=",
                [
                    (
                        s.source_name,
                        ingestion_pb2.SourceJobState.Name(s.state),
                        s.documents_processed,
                        s.chunks_written,
                        s.error,
                    )
                    for s in status.sources
                ],
            )
            if status.state in (
                ingestion_pb2.JOB_STATE_SUCCEEDED,
                ingestion_pb2.JOB_STATE_FAILED,
                ingestion_pb2.JOB_STATE_PARTIAL,
            ):
                return 0 if status.state == ingestion_pb2.JOB_STATE_SUCCEEDED else 1
            await asyncio.sleep(2.0)
        print("timeout", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
