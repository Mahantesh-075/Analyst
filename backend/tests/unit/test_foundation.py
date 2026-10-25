import pytest
from httpx import AsyncClient

from app.core.errors import AppException, ErrorCode
from app.main import app


@pytest.mark.asyncio
async def test_healthz(async_client: AsyncClient) -> None:
    res = await async_client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
    assert "X-Request-ID" in res.headers


@pytest.mark.asyncio
async def test_readyz(async_client: AsyncClient) -> None:
    res = await async_client.get("/readyz")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["database"] == "ok"
    assert data["redis"] == "ok"


@pytest.mark.asyncio
async def test_custom_request_id_propagated(async_client: AsyncClient) -> None:
    res = await async_client.get("/healthz", headers={"X-Request-ID": "test-req-123"})
    assert res.status_code == 200
    assert res.headers["X-Request-ID"] == "test-req-123"


@pytest.mark.asyncio
async def test_error_envelope_format(async_client: AsyncClient) -> None:
    # Temporarily register a test route that raises an AppException
    @app.get("/test-error-endpoint")
    async def error_endpoint() -> None:
        raise AppException(
            code=ErrorCode.DATASET_TOO_LARGE,
            message="Uploaded file exceeds limit of 200 MB",
            status_code=413,
            details={"max_mb": 200, "actual_mb": 250},
        )

    res = await async_client.get("/test-error-endpoint", headers={"X-Request-ID": "err-test-456"})
    assert res.status_code == 413
    data = res.json()
    assert "error" in data
    assert "request_id" in data
    assert data["request_id"] == "err-test-456"
    assert data["error"]["code"] == "DATASET_TOO_LARGE"
    assert data["error"]["message"] == "Uploaded file exceeds limit of 200 MB"
    assert data["error"]["details"] == {"max_mb": 200, "actual_mb": 250}
