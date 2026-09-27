#!/usr/bin/env python3
"""Trigger a local_files ingest job against a running Ingestion gRPC server."""

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
    parser.add_argument("--path", default="", help="Override local_files path option")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()

    options = {}
    if args.path:
        options["path"] = args.path

    async with grpc.aio.insecure_channel(args.addr) as channel:
        stub = ingestion_pb2_grpc.IngestionServiceStub(channel)
        sources = await stub.ListSources(ingestion_pb2.ListSourcesRequest())
        print("sources:", [(s.name, s.requires_credentials) for s in sources.sources])

        response = await stub.TriggerIngest(
            ingestion_pb2.TriggerIngestRequest(
                sources=[
                    ingestion_pb2.SourceSpec(
                        name="local_files",
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
            source_rows = [
                (
                    s.source_name,
                    ingestion_pb2.SourceJobState.Name(s.state),
                    s.chunks_written,
                    s.error,
                )
                for s in status.sources
            ]
            print(f"state={state} message={status.message!r} sources={source_rows}")
            if status.state in (
                ingestion_pb2.JOB_STATE_SUCCEEDED,
                ingestion_pb2.JOB_STATE_FAILED,
                ingestion_pb2.JOB_STATE_PARTIAL,
            ):
                return 0 if status.state == ingestion_pb2.JOB_STATE_SUCCEEDED else 1
            await asyncio.sleep(1.0)
        print("timeout waiting for job", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
