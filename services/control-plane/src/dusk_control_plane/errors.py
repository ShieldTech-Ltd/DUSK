"""Safe, standardized API error handling."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from dusk_control_plane.models import ErrorDetail, ErrorEnvelope
from dusk_control_plane.request_context import get_request_id

logger = logging.getLogger(__name__)


def error_response(*, status_code: int, code: str, message: str, retryable: bool) -> JSONResponse:
    """Build a response containing no exception or dependency detail."""
    request_id = get_request_id()
    body = ErrorEnvelope(
        error=ErrorDetail(
            code=code,
            message=message,
            request_id=request_id,
            retryable=retryable,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={
            "X-Request-ID": request_id,
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def install_error_handlers(app: FastAPI) -> None:
    """Install handlers with stable public codes and sanitized messages."""

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return error_response(
            status_code=422,
            code="REQUEST_VALIDATION_FAILED",
            message="Request validation failed",
            retryable=False,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return error_response(
                status_code=404,
                code="NOT_FOUND",
                message="Resource not found",
                retryable=False,
            )
        if exc.status_code == 405:
            return error_response(
                status_code=405,
                code="METHOD_NOT_ALLOWED",
                message="Method not allowed",
                retryable=False,
            )
        return error_response(
            status_code=exc.status_code,
            code="HTTP_ERROR",
            message="Request could not be completed",
            retryable=exc.status_code >= 500,
        )

    @app.exception_handler(Exception)
    async def unhandled_error(_request: Request, _exc: Exception) -> JSONResponse:
        logger.error("unhandled control-plane request failure request_id=%s", get_request_id())
        return error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="Internal service error",
            retryable=True,
        )
