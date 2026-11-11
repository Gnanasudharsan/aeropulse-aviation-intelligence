"""FastAPI application factory."""

from __future__ import annotations

import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app import __version__
from app.api.v1 import airports, operations, system, weather
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.ratelimit import RateLimitMiddleware

log = get_logger("app.api")

_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    422: "validation_error",
    429: "rate_limited",
}


def _error(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "details": details}}, status_code=status
    )


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(s.log_level, json=s.app_env != "development")
    app = FastAPI(
        title="AeroPulse API",
        version=__version__,
        description=(
            "Real-time U.S. airport operations and weather intelligence built on FAA NAS Status "
            "and NOAA Aviation Weather Center data. All timestamps are UTC (ISO-8601). "
            "Reported FAA events, observed weather and derived indicators are kept distinct."
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(RateLimitMiddleware, limit_per_minute=s.rate_limit_per_minute)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_allow_origins,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
        max_age=600,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path != "/api/v1/health":
            log.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                ms=elapsed_ms,
                request_id=request_id,
            )
        return response

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "error")
        return _error(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
        return _error(422, "validation_error", "Request validation failed", details)

    @app.exception_handler(OperationalError)
    async def db_unavailable(_: Request, exc: OperationalError) -> JSONResponse:
        log.error(
            "database_unavailable",
            error=type(exc.orig).__name__ if exc.orig else "OperationalError",
        )
        return _error(503, "database_unavailable", "The database is temporarily unavailable")

    @app.exception_handler(SQLAlchemyError)
    async def db_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        log.error("database_error", error=type(exc).__name__)
        return _error(500, "internal_error", "An internal error occurred")

    for router in (system.router, airports.router, operations.router, weather.router):
        app.include_router(router, prefix="/api/v1")

    @app.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"name": "AeroPulse API", "docs": "/api/docs", "health": "/api/v1/health"}

    return app


app = create_app()
