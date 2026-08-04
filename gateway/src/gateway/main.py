"""API Gateway — FastAPI skeleton (REST routes filled in stage 6)."""

from __future__ import annotations

import logging
import sys

import uvicorn
from fastapi import FastAPI

from gateway.config import Settings

settings = Settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("gateway")

app = FastAPI(title="ragvalod-gateway", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe for compose healthcheck. Aggregated status comes in stage 6."""
    return {"status": "ok", "service": "gateway"}


def main() -> None:
    logger.info("starting gateway on %s:%s", settings.host, settings.port)
    uvicorn.run(
        "gateway.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
