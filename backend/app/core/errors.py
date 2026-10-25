from enum import StrEnum
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ErrorCode(StrEnum):
    AUTH_INVALID = "AUTH_INVALID"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    UNAUTHORIZED = "AUTH_INVALID"
    RATE_LIMITED = "RATE_LIMITED"
    FILE_TYPE_REJECTED = "FILE_TYPE_REJECTED"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"
    DATASET_TOO_LARGE = "DATASET_TOO_LARGE"
    PARSE_FAILED = "PARSE_FAILED"
    PROPOSAL_INVALID_PARAMS = "PROPOSAL_INVALID_PARAMS"
    APPLY_FAILED = "APPLY_FAILED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    LLM_BUDGET_EXCEEDED = "LLM_BUDGET_EXCEEDED"
    SPEC_INVALID = "SPEC_INVALID"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
    request_id: str


class AppException(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            details=exc.details,
        ),
        request_id=request_id,
    )
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())
