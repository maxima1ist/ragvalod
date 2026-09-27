"""Langfuse HTTP client for Gateway aggregated stats."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("gateway.langfuse")


class LangfuseStatsClient:
    def __init__(self, *, host: str, public_key: str, secret_key: str) -> None:
        self._host = host.rstrip("/")
        self._public_key = public_key.strip()
        self._secret_key = secret_key.strip()

    @property
    def enabled(self) -> bool:
        return bool(self._host and self._public_key and self._secret_key)

    async def fetch_stats(self, *, recent_limit: int = 10) -> dict[str, Any]:
        if not self.enabled:
            return {
                "enabled": False,
                "message": "Langfuse not configured (set LANGFUSE_PUBLIC_KEY/SECRET_KEY)",
            }

        auth = (self._public_key, self._secret_key)
        try:
            async with httpx.AsyncClient(timeout=10.0, auth=auth) as client:
                health = await client.get(f"{self._host}/api/public/health")
                health_ok = health.status_code < 500

                traces_resp = await client.get(
                    f"{self._host}/api/public/traces",
                    params={"limit": recent_limit},
                )
                traces_resp.raise_for_status()
                traces_body = traces_resp.json()

                scores_resp = await client.get(
                    f"{self._host}/api/public/scores",
                    params={"limit": 100},
                )
                scores_resp.raise_for_status()
                scores_body = scores_resp.json()
        except Exception as exc:  # noqa: BLE001 — surface as degraded stats
            logger.warning("langfuse stats fetch failed: %s", exc)
            return {
                "enabled": True,
                "reachable": False,
                "host": self._host,
                "error": str(exc),
            }

        traces = traces_body.get("data") or []
        meta = traces_body.get("meta") or {}
        scores = scores_body.get("data") or []

        by_name: dict[str, dict[str, float | int]] = {}
        for score in scores:
            name = score.get("name") or "unknown"
            value = score.get("value")
            if value is None:
                continue
            try:
                num = float(value)
            except (TypeError, ValueError):
                continue
            bucket = by_name.setdefault(name, {"count": 0, "sum": 0.0, "avg": 0.0})
            bucket["count"] = int(bucket["count"]) + 1
            bucket["sum"] = float(bucket["sum"]) + num
            bucket["avg"] = float(bucket["sum"]) / int(bucket["count"])

        recent = [
            {
                "id": t.get("id"),
                "name": t.get("name"),
                "timestamp": t.get("timestamp"),
                "input": t.get("input"),
                "output": t.get("output"),
            }
            for t in traces
        ]

        return {
            "enabled": True,
            "reachable": health_ok,
            "host": self._host,
            "traces": {
                "returned": len(traces),
                "total_items": meta.get("totalItems"),
                "recent": recent,
            },
            "scores": {
                "returned": len(scores),
                "by_name": by_name,
            },
        }
