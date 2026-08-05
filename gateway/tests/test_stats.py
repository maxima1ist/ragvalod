"""Gateway /stats endpoint tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from gateway.auth import override_api_key_for_tests
from gateway.main import app


def test_stats_requires_api_key() -> None:
    override_api_key_for_tests("test-key")
    response = TestClient(app).get("/stats")
    assert response.status_code == 401


def test_stats_disabled_when_unconfigured() -> None:
    override_api_key_for_tests("test-key")
    with patch(
        "gateway.main.langfuse_stats.fetch_stats",
        new=AsyncMock(
            return_value={
                "enabled": False,
                "message": "Langfuse not configured (set LANGFUSE_PUBLIC_KEY/SECRET_KEY)",
            }
        ),
    ):
        response = TestClient(app).get("/stats", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_stats_ok() -> None:
    override_api_key_for_tests("test-key")
    with patch(
        "gateway.main.langfuse_stats.fetch_stats",
        new=AsyncMock(
            return_value={
                "enabled": True,
                "reachable": True,
                "host": "http://langfuse:3000",
                "traces": {"returned": 1, "total_items": 1, "recent": []},
                "scores": {"returned": 0, "by_name": {}},
            }
        ),
    ):
        response = TestClient(app).get("/stats", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["reachable"] is True
