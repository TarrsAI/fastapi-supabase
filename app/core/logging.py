"""structlog setup + per-request middleware that tags every log line
with a short request_id.

Any `get_logger().info(...)` inside a route handler automatically picks
up the request_id from contextvars — handlers don't need to thread it
through. START / END / SLOW / ERROR lines are emitted by the middleware.
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response

_REQUEST_ID: ContextVar[str | None] = ContextVar("_REQUEST_ID", default=None)


def _add_request_id(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    rid = _REQUEST_ID.get()
    if rid:
        event_dict.setdefault("request_id", rid)
    return event_dict


def configure_logging() -> None:
    """Idempotent — safe to call from `main.py` at import time."""
    level = os.environ.get("LOG_LEVEL", "info").upper()
    logging.basicConfig(format="%(message)s", level=level)

    is_dev = os.environ.get("NODE_ENV", "development") != "production"

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        _add_request_id,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if is_dev:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level) if isinstance(level, str) else level,
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "app") -> Any:
    """Return a bound structlog logger. Use anywhere — request_id is
    auto-attached via contextvars when set by the middleware."""
    return structlog.get_logger(name)


SLOW_MS = 1500


def install(app: FastAPI) -> None:
    """Register the request-id + access-log middleware.

    NOTE: starlette runs middlewares in REVERSE order of registration
    for the request, so this should be added LAST in `main.py` (after
    CORS) — that way the request_id is already set before any other
    middleware logs anything.
    """

    @app.middleware("http")
    async def access_log_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:8]
        token = _REQUEST_ID.set(rid)
        log = get_logger().bind(method=request.method, path=request.url.path)
        start = time.perf_counter()
        log.info("request.start")
        try:
            response = await call_next(request)
            dur_ms = int((time.perf_counter() - start) * 1000)
            response.headers["x-request-id"] = rid
            ctx = {"status": response.status_code, "dur_ms": dur_ms}
            if response.status_code >= 500:
                log.error("request.end", **ctx)
            elif dur_ms >= SLOW_MS:
                log.warning("request.slow", **ctx)
            else:
                log.info("request.end", **ctx)
            return response
        finally:
            _REQUEST_ID.reset(token)
