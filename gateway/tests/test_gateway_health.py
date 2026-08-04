"""Gateway REST + auth + gRPC error mapping tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import grpc
import pytest
from fastapi.testclient import TestClient

from gateway.auth import override_api_key_for_tests
from gateway.main import app


@pytest.fixture
def client() -> TestClient:
    override_api_key_for_tests("test-key")
    return TestClient(app)


def test_health_public_no_key() -> None:
    with (
        patch("gateway.main.check_grpc_health", new=AsyncMock(return_value=True)),
        patch("gateway.main._check_litellm", new=AsyncMock(return_value=True)),
        patch(
            "gateway.main.rag.get_data_status",
            new=AsyncMock(return_value={"data_initialized": True, "sources": []}),
        ),
    ):
        response = TestClient(app).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["data_initialized"] is True


def test_generate_requires_api_key(client: TestClient) -> None:
    response = client.post("/generate", json={"query": "hi"})
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


def test_generate_ok(client: TestClient) -> None:
    with patch(
        "gateway.main.rag.generate_answer",
        new=AsyncMock(
            return_value={
                "answer": "Paris",
                "used_chunks": [
                    {
                        "id": "1",
                        "text": "Paris is capital",
                        "source": "local_files",
                        "title": "a.md",
                        "section_path": "",
                        "score": 0.9,
                    }
                ],
            }
        ),
    ):
        response = client.post(
            "/generate",
            headers={"X-API-Key": "test-key"},
            json={"query": "capital?"},
        )
    assert response.status_code == 200
    assert response.json()["answer"] == "Paris"


def test_generate_data_not_initialized_maps_to_409(client: TestClient) -> None:
    err = grpc.aio.AioRpcError(
        code=grpc.StatusCode.FAILED_PRECONDITION,
        initial_metadata=None,
        trailing_metadata=None,
        details="data_not_initialized: run ingest before generate",
        debug_error_string=None,
    )

    async def boom(**_kwargs):
        raise err

    with patch("gateway.main.rag.generate_answer", new=boom):
        response = client.post(
            "/generate",
            headers={"X-API-Key": "test-key"},
            json={"query": "anything"},
        )
    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "data_not_initialized"


def test_ingest_and_sources(client: TestClient) -> None:
    with (
        patch(
            "gateway.main.ingestion.list_sources",
            new=AsyncMock(
                return_value=[
                    {
                        "name": "local_files",
                        "description": "Local directory",
                        "requires_credentials": False,
                    }
                ]
            ),
        ),
        patch(
            "gateway.main.ingestion.trigger_ingest",
            new=AsyncMock(return_value="job-1"),
        ),
        patch(
            "gateway.main.ingestion.get_job_status",
            new=AsyncMock(
                return_value={
                    "job_id": "job-1",
                    "state": "succeeded",
                    "message": "ok",
                    "started_at": "",
                    "finished_at": "",
                    "sources": [],
                }
            ),
        ),
    ):
        sources = client.get("/sources", headers={"X-API-Key": "test-key"})
        assert sources.status_code == 200
        assert sources.json()["sources"][0]["name"] == "local_files"

        ingest = client.post(
            "/ingest",
            headers={"X-API-Key": "test-key"},
            json={"sources": [{"name": "local_files"}]},
        )
        assert ingest.status_code == 200
        assert ingest.json()["job_id"] == "job-1"

        status = client.get("/ingest/job-1", headers={"X-API-Key": "test-key"})
        assert status.status_code == 200
        assert status.json()["state"] == "succeeded"
