"""Structured HTTP errors + global handlers that shape every failure
into the response envelope.

`HTTPError(expected=True)` flags errors thrown for a known upstream
state (Supabase down, RLS denial we couldn't pre-empt, project paused).
The exception handler will:
  - log them at WARNING, not ERROR (no stack spam)
  - forward the message to the client even on 5xx (raw 500s stay
    opaque to avoid leaking PG / SQL / network details)

Same semantics as express-supabase's `httpErr({expected})` — keep the
two stacks aligned so the AI scaffolding new endpoints sees one
shape across languages.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.core.response import Envelope


class HTTPError(Exception):
    """Service-layer-throwable error. Routers should NOT catch this —
    let it propagate to the global handler so the response envelope is
    shaped consistently.

    Args:
        message: User-facing message. Safe to echo to the client EVEN
            on 5xx if `expected=True`; raw 500s have their message
            replaced with "Internal error" before reaching the client.
        status_code: HTTP status. 4xx are always client-safe; 5xx are
            opaque unless `expected=True`.
        code: Optional structured code (e.g. "ERR_AUTH_EXPIRED") for the
            frontend to switch on without parsing the message.
        expected: Known upstream / downstream state — flips logging from
            ERROR to WARNING and lets the message through on 5xx.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        *,
        code: str | None = None,
        expected: bool = False,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.expected = expected


def _safe_to_forward(status: int, expected: bool) -> bool:
    return status < 500 or expected


async def _http_error_handler(request: Request, exc: HTTPError) -> JSONResponse:
    log = get_logger().bind(
        method=request.method,
        path=request.url.path,
        status=exc.status_code,
        code=exc.code,
    )
    if exc.status_code < 500:
        log.debug("client_error", message=exc.message)
    elif exc.expected:
        log.warning("upstream_unavailable", message=exc.message)
    else:
        log.error("application_error", message=exc.message, exc_info=exc)

    safe = _safe_to_forward(exc.status_code, exc.expected)
    return JSONResponse(
        status_code=exc.status_code,
        content=Envelope[Any](
            success=False,
            message=exc.message if safe else "Internal error",
            data=None,
            code=exc.code if safe else None,
        ).model_dump(exclude_none=False),
    )


async def _starlette_http_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """FastAPI / Starlette raise HTTPException directly (auth deps, 404s
    from route mismatch, etc.). Shape those into the envelope too so the
    client sees one response format from every endpoint."""
    get_logger().bind(
        method=request.method,
        path=request.url.path,
        status=exc.status_code,
    ).debug("client_error", message=str(exc.detail))

    safe = _safe_to_forward(exc.status_code, expected=False)
    return JSONResponse(
        status_code=exc.status_code,
        content=Envelope[Any](
            success=False,
            message=str(exc.detail) if safe else "Internal error",
            data=None,
        ).model_dump(exclude_none=False),
    )


async def _validation_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    get_logger().bind(
        method=request.method,
        path=request.url.path,
    ).debug("validation_error", errors=exc.errors())
    return JSONResponse(
        status_code=422,
        content=Envelope[Any](
            success=False,
            message="Validation failed",
            data={"errors": exc.errors()},
            code="ERR_VALIDATION",
        ).model_dump(exclude_none=False),
    )


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for anything the service / router didn't wrap in
    HTTPError. Log loudly (this is a bug), respond opaquely."""
    get_logger().bind(
        method=request.method,
        path=request.url.path,
    ).error("unhandled_exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=Envelope[Any](
            success=False,
            message="Internal error",
            data=None,
        ).model_dump(exclude_none=False),
    )


def install(app: FastAPI) -> None:
    """Wire all exception handlers in one call from `main.py`."""
    app.add_exception_handler(HTTPError, _http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _starlette_http_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_handler)
