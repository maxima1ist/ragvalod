"""Map gRPC errors to HTTP responses."""

from __future__ import annotations

from typing import NoReturn

import grpc
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


def raise_from_grpc(exc: grpc.aio.AioRpcError) -> NoReturn:
    code = exc.code()
    details = exc.details() or ""
    if code == grpc.StatusCode.FAILED_PRECONDITION and "data_not_initialized" in details:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "data_not_initialized",
                "message": "данные не инициализированы, запустите ингест",
                "details": details,
            },
        )
    if code == grpc.StatusCode.INVALID_ARGUMENT:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_argument", "message": details},
        )
    if code == grpc.StatusCode.NOT_FOUND:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": details},
        )
    if code == grpc.StatusCode.UNAVAILABLE:
        raise HTTPException(
            status_code=503,
            detail={"error": "unavailable", "message": details},
        )
    raise HTTPException(
        status_code=502,
        detail={"error": "upstream_grpc_error", "message": f"{code.name}: {details}"},
    )


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Preserve dict details as JSON body (FastAPI default stringifies them)."""
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "http_error", "message": str(exc.detail)},
    )
