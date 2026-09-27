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


def test_schedules_crud(client: TestClient) -> None:
    with (
        patch(
            "gateway.main.ingestion.upsert_schedule",
            new=AsyncMock(return_value="sched-1"),
        ),
        patch(
            "gateway.main.ingestion.list_schedules",
            new=AsyncMock(
                return_value=[
                    {
                        "schedule_id": "sched-1",
                        "name": "local-daily",
                        "cron": "0 3 * * *",
                        "enabled": True,
                        "source_names": ["local_files"],
                        "all_with_credentials": False,
                        "last_run_at": "",
                        "last_job_id": "",
                        "created_at": "t0",
                        "updated_at": "t0",
                    }
                ]
            ),
        ),
        patch("gateway.main.ingestion.delete_schedule", new=AsyncMock()),
        patch(
            "gateway.main.ingestion.run_schedule",
            new=AsyncMock(return_value="job-99"),
        ),
    ):
        created = client.post(
            "/schedules",
            headers={"X-API-Key": "test-key"},
            json={
                "name": "local-daily",
                "cron": "0 3 * * *",
                "sources": [{"name": "local_files"}],
            },
        )
        assert created.status_code == 200
        assert created.json()["schedule_id"] == "sched-1"

        listed = client.get("/schedules", headers={"X-API-Key": "test-key"})
        assert listed.status_code == 200
        assert listed.json()["schedules"][0]["name"] == "local-daily"

        run = client.post("/schedules/sched-1/run", headers={"X-API-Key": "test-key"})
        assert run.status_code == 200
        assert run.json()["job_id"] == "job-99"

        deleted = client.delete("/schedules/sched-1", headers={"X-API-Key": "test-key"})
        assert deleted.status_code == 200
        assert deleted.json()["status"] == "deleted"


def test_delete_document_requires_api_key(client: TestClient) -> None:
    response = client.delete("/documents", params={"source": "notion", "doc_id": "page-1"})
    assert response.status_code == 401


def test_delete_document_ok(client: TestClient) -> None:
    with patch("gateway.main.ingestion.delete_document", new=AsyncMock()) as delete:
        response = client.delete(
            "/documents",
            headers={"X-API-Key": "test-key"},
            params={"source": "notion", "doc_id": "page-1"},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "source": "notion", "doc_id": "page-1"}
    delete.assert_awaited_once_with("notion", "page-1")


def test_delete_source_ok(client: TestClient) -> None:
    with patch("gateway.main.ingestion.delete_document", new=AsyncMock()) as delete:
        response = client.delete(
            "/documents",
            headers={"X-API-Key": "test-key"},
            params={"source": "notion"},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "deleted", "source": "notion"}
    delete.assert_awaited_once_with("notion", "")


def test_delete_document_not_stored(client: TestClient) -> None:
    error = grpc.aio.AioRpcError(
        code=grpc.StatusCode.NOT_FOUND,
        initial_metadata=None,
        trailing_metadata=None,
        details="document not stored: source=notion doc_id=missing",
        debug_error_string=None,
    )
    with patch("gateway.main.ingestion.delete_document", new=AsyncMock(side_effect=error)):
        response = client.delete(
            "/documents",
            headers={"X-API-Key": "test-key"},
            params={"source": "notion", "doc_id": "missing"},
        )
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"
