"""API-key authentication for Gateway (header X-API-Key)."""

from __future__ import annotations

from fastapi import Header, HTTPException

from gateway.config import Settings

_settings = Settings()


async def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    """Reject when GATEWAY_API_KEY is set and request does not present it.

    Accepts either X-API-Key or Authorization: Bearer <key>.
    /health stays public (not decorated).
    """
    expected = (_settings.api_key or "").strip()
    if not expected:
        return

    presented = (x_api_key or "").strip()
    if not presented and authorization:
        auth = authorization.strip()
        if auth.lower().startswith("bearer "):
            presented = auth[7:].strip()

    if presented != expected:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "missing or invalid API key"},
        )


def override_api_key_for_tests(api_key: str) -> None:
    """Test helper to mutate the module-level settings without reload."""
    _settings.api_key = api_key
