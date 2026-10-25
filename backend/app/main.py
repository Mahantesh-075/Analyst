from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import (
    AppException,
    ErrorCode,
    ErrorDetail,
    ErrorEnvelope,
    app_exception_handler,
)
from app.core.logging import RequestIDMiddleware, setup_logging
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging(settings.ENV)
    logger = structlog.get_logger("lifespan")
    logger.info("application_starting", env=settings.ENV)
    yield
    logger.info("application_shutdown")


app = FastAPI(
    title="Analyst API",
    version="0.1.0",
    docs_url="/api/docs" if settings.ENV != "prod" else None,
    redoc_url=None,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID correlation
app.add_middleware(RequestIDMiddleware)

# Routes
app.include_router(api_v1_router)


# Exception Handlers
app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    errors = exc.errors()
    message = "Request validation failed"
    if errors:
        first_err = errors[0]
        loc_parts = [str(x) for x in first_err.get("loc", []) if x != "body"]
        detail_msg = first_err.get("msg", "")
        if loc_parts and detail_msg:
            field_name = loc_parts[-1].replace("_", " ").capitalize()
            message = f"{field_name}: {detail_msg}"
        elif detail_msg:
            message = detail_msg

    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code=ErrorCode.VALIDATION_FAILED,
            message=message,
            details={"errors": errors},
        ),
        request_id=request_id,
    )
    return JSONResponse(status_code=422, content=envelope.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger = structlog.get_logger("api.unhandled")
    logger.error("unhandled_exception", error=str(exc), exc_info=True)
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected internal error occurred",
            details={},
        ),
        request_id=request_id,
    )
    return JSONResponse(status_code=500, content=envelope.model_dump())


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["health"])
async def readyz() -> JSONResponse:
    checks: dict[str, str] = {
        "status": "ready",
        "database": "ok",
        "redis": "ok",
    }
    healthy = True

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        healthy = False

    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.close()
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"
        healthy = False

    status_code = 200 if healthy else 503
    checks["status"] = "ready" if healthy else "not_ready"
    return JSONResponse(status_code=status_code, content=checks)
